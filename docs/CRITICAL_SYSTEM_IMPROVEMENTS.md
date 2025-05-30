# Critical System Improvements

This document outlines essential technical improvements needed to enhance the Quiz Bot's reliability, performance, and scalability. These changes address core infrastructure issues and should be prioritized for implementation.

## 🔑 Session Management Fixes

### Current Issues

The most critical issues in the current session management system are:

1. Session tracking uses only channel_id as the key, causing conflicts across guilds
2. Memory leaks from abandoned sessions not being properly cleaned up
3. No session recovery mechanism after bot restarts or disconnects
4. Race conditions in multi-user quiz scenarios

### Implementation Guide

#### 1. Composite Key Session Tracking

Update the `GroupQuizManager` session storage to use (guild_id, channel_id) tuple as keys:

```python
class GroupQuizManager:
    def __init__(self):
        # Change from channel_id -> session to (guild_id, channel_id) -> session
        self.active_sessions: Dict[Tuple[int, int], GroupQuizSession] = {}
    
    def create_session(self, guild_id: int, channel_id: int, host_id: int, **kwargs) -> GroupQuizSession:
        """Create a new quiz session using composite key."""
        session = GroupQuizSession(
            guild_id=guild_id,
            channel_id=channel_id,
            host_id=host_id,
            **kwargs
        )
        
        # Use tuple of (guild_id, channel_id) as the key
        self.active_sessions[(guild_id, channel_id)] = session
        return session
    
    def get_session(self, guild_id: int, channel_id: int) -> Optional[GroupQuizSession]:
        """Get a session using composite key."""
        return self.active_sessions.get((guild_id, channel_id))
    
    def end_session(self, guild_id: int, channel_id: int) -> bool:
        """End and remove a session using composite key."""
        if (guild_id, channel_id) in self.active_sessions:
            # Clean up any resources
            session = self.active_sessions[(guild_id, channel_id)]
            session.is_active = False
            session.is_finished = True
            
            # Remove from active sessions
            del self.active_sessions[(guild_id, channel_id)]
            return True
        return False
```

#### 2. Session Cleanup for Abandoned Quizzes

Implement robust cleanup of inactive sessions:

```python
@tasks.loop(minutes=5)
async def cleanup_inactive_sessions(self):
    """Clean up inactive group quiz sessions."""
    now = datetime.now()
    keys_to_remove = []
    
    for (guild_id, channel_id), session in self.active_sessions.items():
        try:
            # Check if session is inactive (no activity for 30 minutes)
            if session.start_time and (now - session.start_time > timedelta(minutes=30)):
                if not session.is_finished:
                    # Get channel if possible
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.send("⏰ Trivia session expired due to inactivity.")
                    
                    # Mark for removal
                    keys_to_remove.append((guild_id, channel_id))
                    logger.info(f"Marking inactive session for cleanup: guild_id={guild_id}, channel_id={channel_id}")
            
            # Also clean up finished sessions that weren't removed
            elif session.is_finished:
                keys_to_remove.append((guild_id, channel_id))
                logger.info(f"Marking finished session for cleanup: guild_id={guild_id}, channel_id={channel_id}")
                
        except Exception as e:
            logger.error(f"Error checking session status: {e}", exc_info=True)
            # If we can't properly check, it's safer to remove the session
            keys_to_remove.append((guild_id, channel_id))
    
    # Remove all marked sessions in a separate loop to avoid dict mutation issues
    for key in keys_to_remove:
        try:
            del self.active_sessions[key]
            logger.info(f"Removed inactive session: guild_id={key[0]}, channel_id={key[1]}")
        except KeyError:
            pass  # Already removed
        except Exception as e:
            logger.error(f"Error removing session: {e}", exc_info=True)
```

#### 3. Session State Persistence

Implement session state persistence for recovery:

```python
class GroupQuizManager:
    # Add methods for state persistence
    
    async def save_session_states(self):
        """Save active session states to database for recovery."""
        if not hasattr(self, 'db_service') or not self.db_service:
            logger.warning("Cannot save session states: database service unavailable")
            return False
            
        try:
            saved_count = 0
            for (guild_id, channel_id), session in self.active_sessions.items():
                # Only save active, non-finished sessions
                if session.is_active and not session.is_finished:
                    # Convert session to serializable state
                    session_state = {
                        'guild_id': guild_id,
                        'channel_id': channel_id,
                        'host_id': session.host_id,
                        'topic': session.topic,
                        'current_question_idx': session.current_question_idx,
                        'participants': session.participants,
                        'start_time': session.start_time.isoformat(),
                        'is_private': session.is_private,
                        'single_answer_mode': session.single_answer_mode,
                        'timeout': session.timeout,
                        # Don't store questions - will regenerate if needed
                    }
                    
                    # Save to database
                    await self.db_service.save_session_state(
                        session_id=f"{guild_id}_{channel_id}",
                        session_type="group_quiz",
                        session_data=session_state,
                        expiry=datetime.now() + timedelta(hours=1)  # Auto-expire after 1 hour
                    )
                    saved_count += 1
                    
            logger.info(f"Saved {saved_count} session states")
            return True
        except Exception as e:
            logger.error(f"Error saving session states: {e}", exc_info=True)
            return False
    
    async def load_session_states(self):
        """Load saved session states from database on restart."""
        if not hasattr(self, 'db_service') or not self.db_service:
            logger.warning("Cannot load session states: database service unavailable")
            return False
            
        try:
            # Get all saved session states
            saved_states = await self.db_service.get_session_states(
                session_type="group_quiz",
                not_expired_only=True
            )
            
            restored_count = 0
            for state_data in saved_states:
                try:
                    session_id = state_data['session_id']
                    session_data = state_data['session_data']
                    
                    # Parse guild_id and channel_id from session_id
                    guild_id, channel_id = map(int, session_id.split('_'))
                    
                    # Create a placeholder session with minimal data
                    placeholder_session = GroupQuizSession(
                        guild_id=guild_id,
                        channel_id=channel_id,
                        host_id=session_data['host_id'],
                        topic=session_data['topic'],
                        questions=[],  # Empty list - will need recovery
                        timeout=session_data.get('timeout', 30),
                        is_private=session_data.get('is_private', False),
                        single_answer_mode=session_data.get('single_answer_mode', False)
                    )
                    
                    # Mark as needing recovery
                    placeholder_session.needs_recovery = True
                    placeholder_session.participants = session_data.get('participants', {})
                    
                    # Store in active sessions
                    self.active_sessions[(guild_id, channel_id)] = placeholder_session
                    restored_count += 1
                    
                except Exception as inner_e:
                    logger.error(f"Error restoring session {state_data.get('session_id', 'unknown')}: {inner_e}")
                    continue
                    
            logger.info(f"Restored {restored_count} session states")
            return True
        except Exception as e:
            logger.error(f"Error loading session states: {e}", exc_info=True)
            return False
```

#### 4. Session Recovery Mechanism

Add methods to handle session recovery after bot restart:

```python
async def recover_session(self, ctx, session):
    """Attempt to recover a quiz session after bot restart."""
    if not session.needs_recovery:
        return False
        
    try:
        # Create recovery embed
        embed = create_embed(
            title="Quiz Session Recovery",
            description=(
                f"A previous quiz on **{session.topic}** was interrupted.\n"
                f"Would you like to continue where you left off or start a new quiz?"
            ),
            color=Color.gold()
        )
        
        # Create recovery options view
        view = discord.ui.View(timeout=60)
        
        continue_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Continue Quiz",
            custom_id="recover_continue"
        )
        
        new_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Start New Quiz",
            custom_id="recover_new"
        )
        
        cancel_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Cancel",
            custom_id="recover_cancel"
        )
        
        async def continue_callback(interaction):
            await interaction.response.defer()
            # Generate new questions if needed
            if not session.questions:
                session.questions = await self.quiz_generator.generate_quiz(
                    topic=session.topic,
                    difficulty=session.difficulty,
                    question_count=5  # Default if unknown
                )
            
            # Restore session state
            session.needs_recovery = False
            session.is_active = True
            session.start_time = datetime.now()
            
            # Continue from current question
            await self._ask_next_trivia_question(ctx, session)
            
        async def new_callback(interaction):
            await interaction.response.defer()
            # End the recovered session
            self.end_session(session.guild_id, session.channel_id)
            # Prompt to start a new quiz
            await ctx.send("The previous quiz has been cancelled. Use `/trivia start` to begin a new quiz.")
            
        async def cancel_callback(interaction):
            await interaction.response.defer()
            # Just end the recovered session without starting a new one
            self.end_session(session.guild_id, session.channel_id)
            await ctx.send("Quiz recovery cancelled.")
        
        continue_button.callback = continue_callback
        new_button.callback = new_callback
        cancel_button.callback = cancel_callback
        
        view.add_item(continue_button)
        view.add_item(new_button)
        view.add_item(cancel_button)
        
        await ctx.send(embed=embed, view=view)
        return True
        
    except Exception as e:
        logger.error(f"Error during session recovery: {e}")
        return False
```

## 🛠️ Error Handling Improvements

### Current Issues

The existing error handling system has these weaknesses:

1. Error messages are often too technical for end users
2. Background tasks lack proper error boundaries
3. Error context isn't properly captured for debugging
4. Errors in one component can cascade to others

### Implementation Guide

#### 1. User-Friendly Error Messages

Create a centralized error message system:

```python
# utils/messages.py

ERROR_MESSAGES = {
    # Database errors
    "db_connection": "I couldn't connect to the database. Please try again in a few moments.",
    "db_query": "There was a problem retrieving your data. Please try again.",
    
    # Quiz generation errors
    "generation_failed": "I couldn't generate questions about '{topic}'. Try a different topic or try again later.",
    "invalid_topic": "That topic seems a bit too complex. Try something more specific.",
    "provider_unavailable": "The AI service is currently unavailable. Please try again later or use a different provider.",
    
    # Session errors
    "session_exists": "There's already an active quiz in this channel. Use `/trivia stop` to end it first.",
    "session_not_found": "There's no active quiz in this channel. Use `/trivia start` to begin one.",
    "session_expired": "The quiz session has expired due to inactivity.",
    
    # Permission errors
    "not_quiz_host": "Only the quiz host or a moderator can perform this action.",
    "missing_permissions": "I need more permissions to do that. Please ask a server admin to check my role permissions.",
    
    # Input validation
    "invalid_count": "The question count must be between 1 and 20.",
    "invalid_timeout": "The timeout must be between 5 and 120 seconds.",
    "invalid_difficulty": "Please choose a valid difficulty: easy, medium, or hard.",
    
    # Fallback
    "generic_error": "Something went wrong. Please try again later."
}

def create_error_embed(title="Error", error_key="generic_error", **format_args):
    """Create a user-friendly error embed."""
    # Get the error message, format with any provided arguments
    message = ERROR_MESSAGES.get(error_key, ERROR_MESSAGES["generic_error"])
    message = message.format(**format_args)
    
    embed = discord.Embed(
        title=f"❌ {title}",
        description=message,
        color=discord.Color.red()
    )
    
    # Add help text for common errors
    if error_key == "session_exists":
        embed.add_field(
            name="What to do",
            value="Run `/trivia stop` to end the current quiz, or wait for it to finish.",
            inline=False
        )
    elif error_key == "generation_failed":
        embed.add_field(
            name="Suggestions",
            value="Try a more common topic, or be more specific about what you want to learn.",
            inline=False
        )
    elif error_key == "provider_unavailable":
        embed.add_field(
            name="Available providers",
            value="Try specifying a different provider: `/trivia start topic:History provider:openai`",
            inline=False
        )
    
    return embed
```

#### 2. Error Boundaries for Background Tasks

Implement proper error boundaries:

```python
def safe_task(name=None):
    """Decorator to create a safe background task with error boundaries."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            task_name = name or func.__name__
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                logger.debug(f"Task {task_name} was cancelled")
                raise  # Re-raise cancellation
            except Exception as e:
                logger.error(f"Error in background task {task_name}: {e}", exc_info=True)
                # Don't propagate exceptions from background tasks
        return wrapper
    return decorator

# Usage in task loops
@tasks.loop(minutes=5)
@safe_task(name="cleanup_sessions")
async def cleanup_inactive_sessions(self):
    # Implementation...
```

#### 3. Contextual Error Logging

Enhance error logging with better context:

```python
class ContextualLogger:
    """Logger that maintains context between log messages."""
    
    def __init__(self, logger_name, default_context=None):
        self.logger = logging.getLogger(logger_name)
        self.context = default_context or {}
    
    def with_context(self, **kwargs):
        """Create a new logger with additional context."""
        new_logger = ContextualLogger(self.logger.name)
        new_logger.context = {**self.context, **kwargs}
        return new_logger
    
    def _format_context(self):
        """Format the context for logging."""
        if not self.context:
            return ""
            
        context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
        return f"[{context_str}]"
    
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(f"{self._format_context()} {msg}", *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self.logger.info(f"{self._format_context()} {msg}", *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(f"{self._format_context()} {msg}", *args, **kwargs)
    
    def error(self, msg, *args, exc_info=False, **kwargs):
        self.logger.error(f"{self._format_context()} {msg}", *args, exc_info=exc_info, **kwargs)
    
    def critical(self, msg, *args, exc_info=True, **kwargs):
        self.logger.critical(f"{self._format_context()} {msg}", *args, exc_info=exc_info, **kwargs)

# Usage in a cog
def __init__(self, bot):
    self.bot = bot
    self.logger = ContextualLogger("bot.quiz", {"cog": "QuizCog"})
    
async def quiz_start(self, ctx, topic, **kwargs):
    # Add context for this command execution
    cmd_logger = self.logger.with_context(
        user_id=ctx.author.id,
        guild_id=ctx.guild.id if ctx.guild else None,
        channel_id=ctx.channel.id,
        command="quiz_start"
    )
    
    try:
        # Command implementation
        pass
    except Exception as e:
        cmd_logger.error(f"Error executing quiz_start: {e}", exc_info=True)
        # User-friendly error handling
```

#### 4. Error Recovery Strategies

Implement graceful error recovery:

```python
class RobustConnection:
    """A database connection wrapper with automatic retry and fallback."""
    
    def __init__(self, db_service, logger=None):
        self.db = db_service
        self.logger = logger or logging.getLogger("bot.database")
        self.fallback_cache = {}
        self.retries = 3
        self.retry_delay = 1.0  # seconds
    
    async def execute(self, operation_name, func, *args, use_cache=False, **kwargs):
        """Execute a database operation with retry logic."""
        last_error = None
        
        for attempt in range(self.retries):
            try:
                result = await func(*args, **kwargs)
                
                # If successful and caching enabled, update cache
                if use_cache:
                    cache_key = self._get_cache_key(operation_name, args, kwargs)
                    self.fallback_cache[cache_key] = {
                        'data': result,
                        'timestamp': time.time()
                    }
                
                return result
            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Database operation {operation_name} failed (attempt {attempt+1}/{self.retries}): {e}"
                )
                
                # Wait before retry (exponential backoff)
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        # All retries failed
        self.logger.error(f"All retries failed for {operation_name}: {last_error}")
        
        # Use cached data if available and requested
        if use_cache:
            cache_key = self._get_cache_key(operation_name, args, kwargs)
            cached_data = self.fallback_cache.get(cache_key)
            
            if cached_data:
                cache_age = time.time() - cached_data['timestamp']
                self.logger.info(
                    f"Using cached data for {operation_name} ({cache_age:.1f}s old)"
                )
                return cached_data['data']
        
        # Re-raise the last error if no fallback available
        raise last_error
    
    def _get_cache_key(self, operation_name, args, kwargs):
        """Generate a cache key from operation and arguments."""
        # Simple cache key generation - can be improved
        args_str = str(args) + str(sorted(kwargs.items()))
        return f"{operation_name}:{hash(args_str)}"

# Usage example
async def get_user_stats(self, user_id):
    try:
        # Use robust connection wrapper
        return await self.db_conn.execute(
            'get_user_stats',
            self.db_service.get_user_stats,
            user_id,
            use_cache=True  # Allow using cached data on failure
        )
    except Exception as e:
        self.logger.error(f"Failed to get user stats: {e}")
        # Return empty stats as fallback
        return {
            'quizzes_taken': 0,
            'correct_answers': 0,
            'wrong_answers': 0,
            'total_score': 0,
            'average_score': 0,
            '_is_fallback': True
        }
```

## 📊 Database Optimizations

### Current Issues

The database layer has these performance concerns:

1. Inefficient queries for leaderboards and statistics
2. Lack of proper indexing on frequently queried columns
3. Connection pool exhaustion during peak usage
4. Transaction handling issues in multi-step operations

### Implementation Guide

#### 1. Query Optimization for Leaderboards

Optimize leaderboard queries:

```python
async def get_guild_leaderboard(self, guild_id, category=None, timeframe=None, limit=10):
    """Get optimized guild leaderboard with filtering options."""
    try:
        # Base query with proper indexing considerations
        query = """
            SELECT 
                uqs.user_id,
                u.username,
                COUNT(DISTINCT uqs.quiz_id) AS quizzes_taken,
                SUM(uqs.correct_answers) AS total_correct,
                SUM(uqs.wrong_answers) AS total_wrong,
                SUM(uqs.points) AS total_points,
                MAX(uqs.created_at) AS last_quiz_date
            FROM user_quiz_sessions uqs
            JOIN users u ON uqs.user_id = u.user_id
            WHERE uqs.guild_id = $1
        """
        params = [guild_id]
        param_count = 1
        
        # Add category filter if specified
        if category and category != "all":
            param_count += 1
            query += f" AND uqs.category = ${param_count}"
            params.append(category)
        
        # Add timeframe filter if specified
        if timeframe:
            param_count += 1
            if timeframe == "daily":
                query += f" AND uqs.created_at > NOW() - INTERVAL '1 day'"
            elif timeframe == "weekly":
                query += f" AND uqs.created_at > NOW() - INTERVAL '7 days'"
            elif timeframe == "monthly":
                query += f" AND uqs.created_at > NOW() - INTERVAL '30 days'"
        
        # Group by and order
        query += """
            GROUP BY uqs.user_id, u.username
            ORDER BY total_points DESC
            LIMIT ${}
        """.format(param_count + 1)
        params.append(limit)
        
        # Execute with connection from pool
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            # Transform results
            return [
                {
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "quizzes_taken": row["quizzes_taken"],
                    "total_correct": row["total_correct"],
                    "total_wrong": row["total_wrong"],
                    "total_points": row["total_points"],
                    "accuracy": round(row["total_correct"] / (row["total_correct"] + row["total_wrong"]) * 100, 1) if row["total_correct"] + row["total_wrong"] > 0 else 0,
                    "last_quiz_date": row["last_quiz_date"]
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Error fetching guild leaderboard: {e}")
        return []
```

#### 2. Implement Proper Database Indexing

Add indexes to improve query performance:

```sql
-- Add this to a migration script

-- Index for user_id lookups across the system
CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);

-- Composite index for guild leaderboards (most common filters)
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_guild_user ON user_quiz_sessions(guild_id, user_id);

-- Index for timeframe filtering
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_created_at ON user_quiz_sessions(created_at);

-- Category filtering index
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_category ON user_quiz_sessions(category);

-- Composite index for user stats by guild
CREATE INDEX IF NOT EXISTS idx_quiz_stats_user_guild ON user_quiz_sessions(user_id, guild_id);

-- Improve query performance for topic-based lookups
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_topic ON user_quiz_sessions(topic);
```

#### 3. Implement Smart Connection Pooling

Improve connection pool management:

```python
class DatabaseConnectionManager:
    """Manages PostgreSQL connection pools with smart scaling."""
    
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger or logging.getLogger("bot.database")
        self.pool = None
        self.min_size = config.get("min_pool_size", 5)
        self.max_size = config.get("max_pool_size", 20)
        self.current_size = self.min_size
        self.last_resize_time = 0
        self.resize_cooldown = 60  # seconds
        self.connection_timeout = 10  # seconds
        
    async def initialize(self):
        """Initialize the connection pool."""
        try:
            # Create the initial pool with min_size
            self.pool = await asyncpg.create_pool(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"],
                min_size=self.min_size,
                max_size=self.current_size,
                command_timeout=self.connection_timeout
            )
            
            self.logger.info(f"Database pool initialized with {self.current_size} connections")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize database pool: {e}")
            return False
    
    async def get_connection(self):
        """Get a connection from the pool, with dynamic scaling if needed."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
            
        try:
            # Try to get a connection with timeout
            return await asyncio.wait_for(
                self.pool.acquire(), 
                timeout=self.connection_timeout
            )
        except asyncio.TimeoutError:
            # Pool exhaustion detected, try to scale up if possible
            await self._try_scale_up()
            
            # Retry with longer timeout
            return await asyncio.wait_for(
                self.pool.acquire(),
                timeout=self.connection_timeout * 2
            )
    
    async def release_connection(self, connection):
        """Release a connection back to the pool."""
        if self.pool:
            await self.pool.release(connection)
    
    async def _try_scale_up(self):
        """Try to increase pool size if needed and possible."""
        now = time.time()
        
        # Check if we can resize (cooldown + not at max)
        if (now - self.last_resize_time >= self.resize_cooldown and 
                self.current_size < self.max_size):
            
            # Calculate new size (25% increase, min +1)
            new_size = min(
                self.max_size,
                max(self.current_size + 1, int(self.current_size * 1.25))
            )
            
            if new_size > self.current_size:
                self.logger.warning(
                    f"Connection pool exhaustion detected. Scaling from {self.current_size} to {new_size}"
                )
                
                # Create a new pool with increased capacity
                old_pool = self.pool
                try:
                    self.pool = await asyncpg.create_pool(
                        host=self.config["host"],
                        port=self.config["port"],
                        user=self.config["user"],
                        password=self.config["password"],
                        database=self.config["database"],
                        min_size=self.min_size,
                        max_size=new_size,
                        command_timeout=self.connection_timeout
                    )
                    
                    self.current_size = new_size
                    self.last_resize_time = now
                    
                    # Close the old pool gracefully
                    asyncio.create_task(self._close_old_pool(old_pool))
                    return True
                except Exception as e:
                    self.logger.error(f"Failed to resize connection pool: {e}")
                    # Keep the old pool if resize failed
                    self.pool = old_pool
                    return False
        return False
    
    async def _close_old_pool(self, old_pool):
        """Close the old pool gracefully after a delay."""
        # Wait for existing operations to complete
        await asyncio.sleep(30)
        await old_pool.close()
        self.logger.info("Old connection pool closed successfully")
    
    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.logger.info("Database connection pool closed")
```

#### 4. Implement Proper Transaction Handling

Add robust transaction handling for multi-step operations:

```python
async def execute_transaction(self, operations):
    """Execute multiple operations in a single transaction."""
    connection = None
    transaction = None
    
    try:
        # Get connection from pool
        connection = await self.get_connection()
        
        # Start transaction
        transaction = connection.transaction()
        await transaction.start()
        
        results = []
        for operation in operations:
            func_name = operation["function"]
            args = operation.get("args", [])
            kwargs = operation.get("kwargs", {})
            
            # Get the function by name
            if not hasattr(self, func_name):
                raise ValueError(f"Unknown database function: {func_name}")
            
            func = getattr(self, func_name)
            
            # Execute function with transaction connection
            kwargs["connection"] = connection
            result = await func(*args, **kwargs)
            results.append(result)
        
        # Commit transaction
        await transaction.commit()
        return results
    
    except Exception as e:
        # Rollback transaction on error
        self.logger.error(f"Transaction failed: {e}")
        if transaction:
            try:
                await transaction.rollback()
            except Exception as rollback_error:
                self.logger.error(f"Rollback failed: {rollback_error}")
        raise
    
    finally:
        # Release connection back to pool
        if connection:
            await self.release_connection(connection)
```

## 🔄 Concurrency Management

### Current Issues

The concurrency model has these weaknesses:

1. Potential race conditions in session state updates
2. Lack of proper synchronization in multi-user quizzes
3. Resource contention during peak load
4. Inefficient background task scheduling

### Implementation Guide

#### 1. Implement State Locks for Shared Resources

Add locking for concurrent access to shared state:

```python
class SynchronizedSessionManager:
    """Session manager with proper synchronization for concurrent access."""
    
    def __init__(self):
        self.active_sessions = {}
        self.session_locks = {}  # Locks for each session
        self.manager_lock = asyncio.Lock()  # Lock for session dictionary operations
    
    async def create_session(self, guild_id, channel_id, **kwargs):
        """Create a new session with proper locking."""
        session_key = (guild_id, channel_id)
        
        async with self.manager_lock:
            # Check if session already exists
            if session_key in self.active_sessions:
                return self.active_sessions[session_key]
            
            # Create a new session
            session = GroupQuizSession(guild_id, channel_id, **kwargs)
            self.active_sessions[session_key] = session
            
            # Create a lock for this session
            self.session_locks[session_key] = asyncio.Lock()
            
            return session
    
    async def get_session(self, guild_id, channel_id):
        """Get a session by key."""
        session_key = (guild_id, channel_id)
        
        async with self.manager_lock:
            return self.active_sessions.get(session_key)
    
    async def update_session(self, guild_id, channel_id, update_func):
        """Update a session with proper locking."""
        session_key = (guild_id, channel_id)
        
        # Get session lock (or None if session doesn't exist)
        session_lock = None
        async with self.manager_lock:
            if session_key not in self.active_sessions:
                return None
            session_lock = self.session_locks[session_key]
        
        if not session_lock:
            return None
        
        # Acquire session-specific lock and update
        async with session_lock:
            session = self.active_sessions.get(session_key)
            if not session:
                return None
                
            # Execute the update function
            result = await update_func(session)
            return result
    
    async def end_session(self, guild_id, channel_id):
        """End and remove a session with proper locking."""
        session_key = (guild_id, channel_id)
        
        async with self.manager_lock:
            if session_key not in self.active_sessions:
                return False
                
            # Get the session and mark as finished
            session = self.active_sessions[session_key]
            session.is_active = False
            session.is_finished = True
            
            # Remove from active sessions and locks
            del self.active_sessions[session_key]
            if session_key in self.session_locks:
                del self.session_locks[session_key]
                
            return True
```

#### 2. Implement Throttling for Resource-Intensive Operations

Add rate limiting to prevent overload:

```python
class RateLimiter:
    """Rate limiter for resource-intensive operations."""
    
    def __init__(self, rate=1, per=1.0, burst=1):
        self.rate = rate  # tokens per second
        self.per = per    # time period in seconds
        self.burst = burst  # maximum burst size
        self.tokens = burst
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self, tokens=1):
        """Acquire tokens from the rate limiter, waiting if necessary."""
        async with self.lock:
            await self._refill()
            
            if tokens > self.burst:
                raise ValueError(f"Requested tokens ({tokens}) exceeds maximum burst size ({self.burst})")
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0  # No wait needed
            
            # Calculate wait time
            missing_tokens = tokens - self.tokens
            wait_time = missing_tokens * self.per / self.rate
            
            # Return the wait time - caller must decide whether to wait or fail
            return wait_time
    
    async def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Calculate new tokens to add
        new_tokens = elapsed * self.rate / self.per
        if new_tokens > 0:
            self.tokens = min(self.burst, self.tokens + new_tokens)
            self.last_refill = now

# Usage with operations
class LLMService:
    def __init__(self):
        # Rate limiter for each provider
        self.rate_limiters = {
            "openai": RateLimiter(rate=20, per=60, burst=5),     # 20 requests per minute
            "anthropic": RateLimiter(rate=10, per=60, burst=3),  # 10 requests per minute
            "google": RateLimiter(rate=30, per=60, burst=5)      # 30 requests per minute
        }
        
    async def generate(self, prompt, provider="openai"):
        # Get appropriate rate limiter
        limiter = self.rate_limiters.get(provider, self.rate_limiters["openai"])
        
        # Try to acquire tokens
        wait_time = await limiter.acquire()
        
        if wait_time > 0:
            # Either wait or fail based on threshold
            if wait_time > 5.0:  # More than 5 seconds wait
                raise RateLimitExceeded(f"Rate limit exceeded for {provider}. Try again in {wait_time:.1f}s")
            else:
                # Wait for a reasonable time
                await asyncio.sleep(wait_time)
        
        # Now make the actual API call
        return await self._make_api_call(prompt, provider)
```

#### 3. Implement Resource Pools for Limited Resources

Create resource pools for expensive resources:

```python
class ResourcePool:
    """Generic resource pool for managing limited resources."""
    
    def __init__(self, create_resource_func, max_size=10, timeout=10.0):
        self.create_resource = create_resource_func
        self.max_size = max_size
        self.timeout = timeout
        self.available = asyncio.Queue()
        self.in_use = set()
        self.size = 0
        self.lock = asyncio.Lock()
    
    async def get(self):
        """Get a resource from the pool."""
        # Try to get an available resource first
        try:
            resource = self.available.get_nowait()
            self.in_use.add(resource)
            return resource
        except asyncio.QueueEmpty:
            pass
        
        # If no resources available, try to create a new one if pool not at max
        async with self.lock:
            if self.size < self.max_size:
                try:
                    resource = await self.create_resource()
                    self.size += 1
                    self.in_use.add(resource)
                    return resource
                except Exception as e:
                    logger.error(f"Failed to create resource: {e}")
                    raise
        
        # If at max size, wait for a resource to become available
        try:
            resource = await asyncio.wait_for(self.available.get(), timeout=self.timeout)
            self.in_use.add(resource)
            return resource
        except asyncio.TimeoutError:
            raise TimeoutError("Timed out waiting for available resource")
    
    async def release(self, resource):
        """Release a resource back to the pool."""
        if resource in self.in_use:
            self.in_use.remove(resource)
            await self.available.put(resource)
    
    async def close(self):
        """Close all resources in the pool."""
        # Close available resources
        while not self.available.empty():
            resource = await self.available.get()
            await self._close_resource(resource)
        
        # Close in-use resources
        for resource in list(self.in_use):
            await self._close_resource(resource)
            self.in_use.remove(resource)
        
        self.size = 0
    
    async def _close_resource(self, resource):
        """Close a specific resource."""
        try:
            if hasattr(resource, 'close'):
                if asyncio.iscoroutinefunction(resource.close):
                    await resource.close()
                else:
                    resource.close()
            elif hasattr(resource, '__aclose__'):
                await resource.__aclose__()
        except Exception as e:
            logger.error(f"Error closing resource: {e}")
```

## 📝 Implementation Checklist

Here's a prioritized checklist for implementing these critical improvements:

### Week 1: Session Management Fixes

- [ ] Update group quiz manager to use (guild_id, channel_id) composite keys
- [ ] Implement session cleanup for abandoned quizzes
- [ ] Add session state persistence for recovery
- [ ] Implement basic error handling improvements

### Week 2: Error Handling and Database Optimization

- [ ] Create centralized error message system
- [ ] Implement contextual logging
- [ ] Add error boundaries for background tasks
- [ ] Optimize critical database queries
- [ ] Add proper indexing to database tables

### Week 3: Concurrency and Performance

- [ ] Implement state locks for shared resources
- [ ] Add rate limiting for resource-intensive operations
- [ ] Create smart connection pool management
- [ ] Implement proper transaction handling for multi-step operations
- [ ] Add resource pools for limited resources

### Week 4: Testing and Refinement

- [ ] Conduct load testing for all improvements
- [ ] Refine error messages based on common error patterns
- [ ] Optimize database queries further based on performance metrics
- [ ] Add automated monitoring and alerting
- [ ] Document and finalize all system improvements