import os
import logging
import json
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

import asyncpg
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from utils.errors import DatabaseError, log_exception, safe_execute
from services.database_extensions.user_stats import UserStatsService

logger = logging.getLogger("bot.database")

# Define ConfigError class
class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass

class DatabaseService(UserStatsService):
    """Service for managing user data and quiz statistics using PostgreSQL with asyncpg.
    
    Implements connection pooling (5-20 connections), retry logic with tenacity,
    and multi-guild data isolation via composite keys (user_id, guild_id).
    """
    
    def __init__(self, config=None):
        """
        Initialize the database service with PostgreSQL connection.
        
        Args:
            config: Database configuration object with connection details
        
        Raises:
            DatabaseError: If database connection or initialization fails
        """
        try:
            # Load config if not provided
            if config is None:
                from config import load_config
                config = load_config().database
                
            if config is None:
                raise ConfigError("Database configuration is missing")
                
            # Store the configuration
            self.config = config
            
            # Initialize connection pool (will be created in async initialize)
            self._connection_pool = None
            
            # Cache for column names
            self._table_columns = {}
            
            # Connection pool monitoring
            self._pool_stats = {
                'connections_created': 0,
                'connections_closed': 0,
                'queries_executed': 0,
                'errors': 0
            }
            
            # Log successful initialization
            logger.info(f"PostgreSQL database service initialized (asyncpg) on {self.config.host}:{self.config.port}/{self.config.database}")
        except Exception as e:
            logger.critical(f"Failed to initialize PostgreSQL database", exc_info=True)
            # Set the pool to None to indicate initialization failure
            self._connection_pool = None
            # Re-raise certain errors for immediate handling
            if isinstance(e, ConfigError) or isinstance(e, ImportError):
                raise
    
    async def initialize(self):
        """
        Asynchronously initialize the database service.
        This is called during bot startup.
        
        Raises:
            DatabaseError: If database initialization fails
        """
        if self._connection_pool:
            logger.debug("Database already initialized, skipping initialization")
            return
            
        try:
            # Connect to PostgreSQL database
            await self._create_connection_pool()
            await self._initialize_tables()
            await self._initialize_extensions()
            self.initialized = True
            logger.info(f"PostgreSQL database service initialized successfully on {self.config.host}:{self.config.port}/{self.config.database}")
        except Exception as e:
            error_msg = f"Failed to initialize PostgreSQL database"
            logger.critical(error_msg, exc_info=True)
            raise DatabaseError(
                message=error_msg,
                original_exception=e,
                details={"host": self.config.host, "database": self.config.database}
            )
    
    async def _create_connection_pool(self):
        """
        Create a PostgreSQL connection pool using asyncpg.
            
        Raises:
            DatabaseError: If connection pool creation fails
        """
        try:
            # Check for missing configuration
            if not hasattr(self, 'config') or self.config is None:
                raise ConfigError("Database configuration is missing")
                
            # Validate required config fields
            if not all([
                hasattr(self.config, 'host') and self.config.host,
                hasattr(self.config, 'port') and self.config.port,
                hasattr(self.config, 'database') and self.config.database,
                hasattr(self.config, 'user') and self.config.user
            ]):
                raise ConfigError("Database configuration is incomplete. Required fields: host, port, database, user.")
            
            # Build connection parameters
            dsn = f"postgresql://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
            
            # Add SSL if enabled
            ssl_mode = 'require' if self.config.use_ssl else 'prefer'
            
            # Create connection pool with improved settings
            self._connection_pool = await asyncpg.create_pool(
                dsn,
                min_size=self.config.min_connections if hasattr(self.config, 'min_connections') else 5,
                max_size=self.config.max_connections if hasattr(self.config, 'max_connections') else 20,
                command_timeout=30,  # 30 second timeout for commands
                max_inactive_connection_lifetime=300,  # 5 minutes
                ssl=ssl_mode,
                server_settings={
                    'application_name': 'quiz_bot',
                    'jit': 'off',  # Disable JIT for more predictable performance
                    'tcp_keepalives_idle': '600',      # 10 minutes
                    'tcp_keepalives_interval': '30',   # 30 seconds  
                    'tcp_keepalives_count': '3',       # 3 probes
                    'statement_timeout': '30000'       # 30 second statement timeout
                },
                init=self._init_connection
            )
            
            # Test connection
            async with self._connection_pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            
            logger.debug(f"Created PostgreSQL connection pool with {self.config.min_connections if hasattr(self.config, 'min_connections') else 5}-{self.config.max_connections if hasattr(self.config, 'max_connections') else 20} connections")
            # asyncpg pools don't have _size attribute, use _minsize and _maxsize instead
            pool_size = getattr(self._connection_pool, '_minsize', 5)
            self._pool_stats['connections_created'] = pool_size
        except asyncpg.PostgresError as e:
            error_msg = f"PostgreSQL connection error: Could not connect to database server"
            logger.error(error_msg, exc_info=True)
            raise DatabaseError(
                message=error_msg,
                original_exception=e,
                details={
                    "host": self.config.host,
                    "port": self.config.port,
                    "database": self.config.database,
                    "error": str(e)
                }
            )
        except Exception as e:
            error_msg = f"PostgreSQL connection pool error"
            logger.error(error_msg, exc_info=True)
            raise DatabaseError(
                message=error_msg,
                original_exception=e,
                details={
                    "host": self.config.host,
                    "port": self.config.port,
                    "database": self.config.database
                }
            )
    
    async def _init_connection(self, conn):
        """Initialize each connection in the pool."""
        # Set up any connection-specific settings here
        await conn.execute("SET TIME ZONE 'UTC'")
        # Prepare commonly used statements for better performance
        await self._prepare_statements(conn)
    
    async def _prepare_statements(self, conn):
        """Prepare commonly used SQL statements for better performance."""
        # Prepare common queries
        await conn.prepare("SELECT * FROM users WHERE user_id = $1")
        await conn.prepare("SELECT COUNT(*) FROM users WHERE user_id = $1")
        # Add more prepared statements as needed
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool with monitoring and timeout.
        
        Usage:
            async with self.acquire() as conn:
                result = await conn.fetch(query, params)
        """
        conn = None
        try:
            # Add timeout for connection acquisition to prevent hanging
            conn = await asyncio.wait_for(
                self._connection_pool.acquire(), 
                timeout=10.0  # 10 second timeout
            )
            yield conn
        except asyncio.TimeoutError:
            self._pool_stats['errors'] += 1
            logger.error("Database connection acquisition timed out after 10 seconds")
            raise DatabaseError("Database connection timeout")
        except Exception as e:
            self._pool_stats['errors'] += 1
            raise
        finally:
            if conn:
                try:
                    await self._connection_pool.release(conn)
                    self._pool_stats['queries_executed'] += 1
                except Exception as release_error:
                    logger.error(f"Error releasing connection: {release_error}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), 
           retry=retry_if_exception_type(asyncpg.PostgresConnectionError),
           reraise=True)
    async def _execute_query(self, query, params=None, fetch=True, fetch_one=False):
        """
        Execute a SQL query and optionally fetch results.
        
        Args:
            query: SQL query to execute
            params: Query parameters (asyncpg uses $1, $2, etc.)
            fetch: Whether to fetch results
            fetch_one: Whether to fetch one result or all
            
        Returns:
            Query results if fetch is True, otherwise None
        """
        # Convert psycopg2 style (%s) to asyncpg style ($1, $2, etc.) if needed
        if params and '%s' in query:
            query = self._convert_query_params(query, params)
        
        async with self.acquire() as conn:
            try:
                if fetch:
                    if fetch_one:
                        result = await conn.fetchrow(query, *params if params else [])
                        # Convert Record to dict for compatibility
                        return dict(result) if result else None
                    else:
                        results = await conn.fetch(query, *params if params else [])
                        # Convert Records to dicts for compatibility
                        return [dict(row) for row in results]
                else:
                    await conn.execute(query, *params if params else [])
                    return None
            except Exception as e:
                logger.error(f"Query execution error: {e}, query: {query[:100]}...")
                raise
    
    async def _execute_many(self, query, params_list):
        """
        Execute a SQL query with multiple parameter sets.
        
        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
            
        Returns:
            Number of rows affected
        """
        if not params_list:
            return 0
            
        # Convert psycopg2 style to asyncpg style if needed
        if '%s' in query:
            query = self._convert_query_params(query, params_list[0])
        
        async with self.acquire() as conn:
            try:
                # Use executemany for batch operations
                await conn.executemany(query, params_list)
                # asyncpg doesn't return rowcount directly, so we estimate
                return len(params_list)
            except Exception as e:
                logger.error(f"Batch query execution error: {e}")
                raise
    
    def _convert_query_params(self, query, params):
        """Convert psycopg2 style %s placeholders to asyncpg style $1, $2, etc."""
        # Count the number of %s placeholders
        count = query.count('%s')
        # Replace each %s with $1, $2, etc.
        for i in range(count):
            query = query.replace('%s', f'${i+1}', 1)
        return query
    
    async def _initialize_tables(self):
        """
        Initialize database tables if they don't exist.
        
        Raises:
            DatabaseError: If table creation fails
        """
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT NOT NULL,
            quizzes_taken INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            wrong_answers INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            last_active TIMESTAMP WITH TIME ZONE
        );
        """
        
        create_quizzes_table = """
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id SERIAL PRIMARY KEY,
            host_id BIGINT NOT NULL,
            topic TEXT NOT NULL,
            category TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            question_count INTEGER NOT NULL,
            template TEXT NOT NULL,
            provider TEXT NOT NULL,
            is_private BOOLEAN DEFAULT FALSE,
            is_group BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (host_id) REFERENCES users (user_id)
        );
        """
        
        create_saved_configs_table = """
        CREATE TABLE IF NOT EXISTS saved_configs (
            config_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            topic TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            difficulty TEXT DEFAULT 'medium',
            question_count INTEGER DEFAULT 5,
            template TEXT DEFAULT 'standard',
            provider TEXT DEFAULT 'openai',
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        """
        
        create_achievements_table = """
        CREATE TABLE IF NOT EXISTS achievements (
            achievement_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            earned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        """
        
        # Create the cache table for optimizing common queries
        create_cache_table = """
        CREATE TABLE IF NOT EXISTS query_cache (
            cache_key TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            expires_at BIGINT NOT NULL
        );
        """
        
        # Create detailed stats tracking table for extended functionality
        create_quiz_sessions_table = """
        CREATE TABLE IF NOT EXISTS user_quiz_sessions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            quiz_id VARCHAR(100) NOT NULL,
            topic VARCHAR(255) NOT NULL,
            correct_answers INTEGER DEFAULT 0,
            wrong_answers INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            difficulty VARCHAR(50) DEFAULT 'medium',
            category VARCHAR(100) DEFAULT 'general',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Create guild members table for server-specific tracking
        create_guild_members_table = """
        CREATE TABLE IF NOT EXISTS guild_members (
            user_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, guild_id)
        );
        """

        # Create table for guild onboarding logs
        create_guild_onboarding_log_table = """
        CREATE TABLE IF NOT EXISTS guild_onboarding_log (
            guild_id BIGINT PRIMARY KEY,
            channel_id BIGINT NOT NULL,
            onboarded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # --- Add Indexes --- 
        create_indexes = """
        -- Indexes for users table
        CREATE INDEX IF NOT EXISTS idx_users_points ON users (points DESC);
        CREATE INDEX IF NOT EXISTS idx_users_last_active ON users (last_active DESC NULLS LAST);

        -- Indexes for user_quiz_sessions table (crucial for stats performance)
        CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_user_id ON user_quiz_sessions (user_id);
        CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_topic ON user_quiz_sessions (topic);
        CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_category ON user_quiz_sessions (category);
        CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_difficulty ON user_quiz_sessions (difficulty);
        CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_created_at ON user_quiz_sessions (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_user_topic ON user_quiz_sessions (user_id, topic);
        CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_user_category ON user_quiz_sessions (user_id, category);
        CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_user_difficulty ON user_quiz_sessions (user_id, difficulty);
        
        -- Indexes for quizzes table
        CREATE INDEX IF NOT EXISTS idx_quizzes_host_id ON quizzes (host_id);
        CREATE INDEX IF NOT EXISTS idx_quizzes_timestamp ON quizzes (timestamp DESC);

        -- Indexes for achievements table
        CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON achievements (user_id);
        CREATE INDEX IF NOT EXISTS idx_achievements_user_name ON achievements (user_id, name);

        -- Indexes for saved_configs table
        CREATE INDEX IF NOT EXISTS idx_saved_configs_user_id ON saved_configs (user_id);

        -- Indexes for guild_members table
        CREATE INDEX IF NOT EXISTS idx_guild_members_guild_id ON guild_members (guild_id);

        -- Index for guild_onboarding_log table
        CREATE INDEX IF NOT EXISTS idx_guild_onboarding_log_onboarded_at ON guild_onboarding_log (onboarded_at DESC);
        """
        
        try:
            async with self.acquire() as conn:
                await conn.execute(create_users_table)
                await conn.execute(create_quizzes_table)
                await conn.execute(create_saved_configs_table)
                await conn.execute(create_achievements_table)
                await conn.execute(create_cache_table)
                await conn.execute(create_quiz_sessions_table)
                await conn.execute(create_guild_members_table)
                await conn.execute(create_guild_onboarding_log_table)
                
                # Execute index creation statements
                await conn.execute(create_indexes)
                
            logger.debug("Database tables and indexes initialized successfully")
        except Exception as e:
            error_msg = "Failed to initialize database tables"
            logger.error(error_msg, exc_info=True)
            raise DatabaseError(
                message=error_msg,
                original_exception=e
            )
    
    async def get_basic_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get basic user statistics from the users table.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Dictionary of basic user statistics
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            query = "SELECT * FROM users WHERE user_id = $1"
            result = await self._execute_query(query, (user_id,), fetch_one=True)
            
            if result:
                return result
            else:
                # Return default stats if user doesn't exist
                return {
                    "user_id": user_id,
                    "username": "Unknown",
                    "quizzes_taken": 0,
                    "correct_answers": 0,
                    "wrong_answers": 0,
                    "points": 0,
                    "level": 1,
                    "last_active": None
                }
        except Exception as e:
            logger.error(f"Failed to get user stats for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "username": "Unknown",
                "quizzes_taken": 0,
                "correct_answers": 0,
                "wrong_answers": 0,
                "points": 0,
                "level": 1,
                "last_active": None
            }
    
    async def update_user_stats(self, user_id: int, username: str, correct: int = 0, wrong: int = 0, points: int = 0) -> bool:
        """
        Update user statistics.
        
        Args:
            user_id: Discord user ID
            username: User's display name
            correct: Number of correct answers to add
            wrong: Number of wrong answers to add
            points: Number of points to add
            
        Returns:
            True if the user leveled up, False otherwise
            
        Raises:
            DatabaseError: If update fails
        """
        try:
            # First check if user exists
            query = "SELECT * FROM users WHERE user_id = $1"
            user = await self._execute_query(query, (user_id,), fetch_one=True)
            
            # If the user exists and current username is UnknownUser, but we have a better name now, update it
            if user and user.get('username') in ['Unknown', 'UnknownUser'] and username not in ['Unknown', 'UnknownUser']:
                logger.info(f"Updating unknown username to {username} for user ID {user_id}")
            
            # Get appropriate column names
            timestamp_col = await self._get_timestamp_column("users")
            
            async with self.acquire() as conn:
                if user:
                    # Dynamically check if points and level columns exist
                    columns = await self._get_column_names("users")
                    has_points = "points" in columns
                    has_level = "level" in columns
                    
                    # Adjust the update query based on available columns
                    if has_points and has_level:
                        update_query = f"""
                        UPDATE users
                        SET correct_answers = correct_answers + $1,
                            wrong_answers = wrong_answers + $2,
                            points = points + $3,
                            {timestamp_col} = CURRENT_TIMESTAMP
                        WHERE user_id = $4
                        RETURNING points, level
                        """
                        updated_stats = await conn.fetchrow(update_query, correct, wrong, points, user_id)
                        new_points = updated_stats['points']
                        current_level = updated_stats['level']
                        
                        # Check if user should level up (1 level for every 100 points)
                        new_level = new_points // 100 + 1
                        
                        if new_level > current_level:
                            level_query = "UPDATE users SET level = $1 WHERE user_id = $2"
                            await conn.execute(level_query, new_level, user_id)
                            logger.info(f"User {user_id} ({username}) leveled up to level {new_level}")
                            return True
                    else:
                        # Simpler update for tables without points/level
                        update_fields = []
                        params = []
                        param_count = 1
                        
                        if "correct_answers" in columns:
                            update_fields.append(f"correct_answers = correct_answers + ${param_count}")
                            params.append(correct)
                            param_count += 1
                            
                        if "wrong_answers" in columns:
                            update_fields.append(f"wrong_answers = wrong_answers + ${param_count}") 
                            params.append(wrong)
                            param_count += 1
                            
                        if has_points:
                            update_fields.append(f"points = points + ${param_count}")
                            params.append(points)
                            param_count += 1
                            
                        update_fields.append(f"{timestamp_col} = CURRENT_TIMESTAMP")
                        
                        update_query = f"""
                        UPDATE users
                        SET {", ".join(update_fields)}
                        WHERE user_id = ${param_count}
                        """
                        params.append(user_id)
                        await conn.execute(update_query, *params)
                else:
                    # Create new user
                    # Dynamically build the query based on available columns
                    columns = await self._get_column_names("users")
                    
                    # Base fields that should always be present
                    field_names = ["user_id", "username"]
                    field_values = [user_id, username]
                    placeholders = ["$1", "$2"]
                    
                    # Add optional fields if they exist
                    param_count = 3
                    if "correct_answers" in columns:
                        field_names.append("correct_answers")
                        field_values.append(correct)
                        placeholders.append(f"${param_count}")
                        param_count += 1
                        
                    if "wrong_answers" in columns:
                        field_names.append("wrong_answers")
                        field_values.append(wrong)
                        placeholders.append(f"${param_count}")
                        param_count += 1
                        
                    if "points" in columns:
                        field_names.append("points")
                        field_values.append(points)
                        placeholders.append(f"${param_count}")
                        param_count += 1
                        
                    # Add timestamp column
                    field_names.append(timestamp_col)
                    placeholders.append("CURRENT_TIMESTAMP")
                    
                    insert_query = f"""
                    INSERT INTO users ({", ".join(field_names)})
                    VALUES ({", ".join(placeholders)})
                    """
                    
                    await conn.execute(insert_query, *field_values)
                
                return False
        except Exception as e:
            logger.error(f"Failed to update user stats for user {user_id}: {e}")
            return False
    
    async def increment_quizzes_taken(self, user_id: int, username: str) -> None:
        """
        Increment the number of quizzes taken by a user.
        
        Args:
            user_id: Discord user ID
            username: User's display name
            
        Raises:
            DatabaseError: If update fails
        """
        try:
            # Get appropriate timestamp column
            timestamp_col = await self._get_timestamp_column("users")
            columns = await self._get_column_names("users")

            if "quizzes_taken" in columns:
                query = f"""
                INSERT INTO users (user_id, username, quizzes_taken, {timestamp_col})
                VALUES ($1, $2, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    quizzes_taken = users.quizzes_taken + 1,
                    username = EXCLUDED.username,
                    {timestamp_col} = CURRENT_TIMESTAMP
                """
                params = (user_id, username)
            else:
                # quizzes_taken column doesn't exist, just ensure user exists and update timestamp/username
                query = f"""
                INSERT INTO users (user_id, username, {timestamp_col})
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    {timestamp_col} = CURRENT_TIMESTAMP
                """
                params = (user_id, username)
            
            await self._execute_query(query, params, fetch=False)
            logger.debug(f"User {user_id} ({username}) activity recorded. quizzes_taken handled based on column presence.")
        except Exception as e:
            logger.error(f"Failed to increment quizzes taken for user {user_id}: {e}")
    
    async def save_quiz_config(self, user_id: int, name: str, **config) -> int:
        """
        Save a quiz configuration for later use.
        
        Args:
            user_id: Discord user ID
            name: Name for the saved configuration
            **config: Configuration parameters
            
        Returns:
            ID of the saved configuration
            
        Raises:
            DatabaseError: If save fails
        """
        try:
            # Ensure user exists first
            user_query = """
            INSERT INTO users (user_id, username, last_active)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO NOTHING
            """
            await self._execute_query(user_query, (user_id, "Unknown"), fetch=False)
            
            # Now insert the config
            insert_query = """
            INSERT INTO saved_configs (user_id, name, topic, category, difficulty, question_count, template, provider)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING config_id
            """
            
            result = await self._execute_query(
                insert_query,
                (
                    user_id,
                    name,
                    config.get("topic", ""),
                    config.get("category", "general"),
                    config.get("difficulty", "medium"),
                    config.get("question_count", 5),
                    config.get("template", "standard"),
                    config.get("provider", "openai")
                ),
                fetch_one=True
            )
            
            logger.info(f"Saved quiz config '{name}' for user {user_id}")
            return result["config_id"]
        except Exception as e:
            logger.error(f"Failed to save quiz config for user {user_id}: {e}")
            return -1
    
    async def get_saved_configs(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get saved quiz configurations for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            List of saved configurations
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            query = "SELECT * FROM saved_configs WHERE user_id = $1 ORDER BY name ASC"
            results = await self._execute_query(query, (user_id,))
            return results
        except Exception as e:
            logger.error(f"Failed to get saved configs for user {user_id}: {e}")
            return []
        
    async def record_quiz(self, host_id: int, topic: str, category: str, difficulty: str, 
                   question_count: int, template: str, provider: str, 
                   is_private: bool = False, is_group: bool = False, 
                   guild_id: Optional[int] = None) -> int:
        """
        Record a completed quiz.
        
        Args:
            host_id: Discord user ID of the quiz host
            topic: Quiz topic
            category: Quiz category
            difficulty: Quiz difficulty
            question_count: Number of questions
            template: Quiz template used
            provider: LLM provider used
            is_private: Whether it was a private quiz
            is_group: Whether it was a group quiz
            guild_id: Optional guild ID for guild-specific tracking
            
        Returns:
            ID of the recorded quiz
            
        Raises:
            DatabaseError: If recording fails
        """
        try:
            # Get appropriate timestamp column
            timestamp_col = await self._get_timestamp_column("users")
            
            # Ensure user exists first
            user_query = f"""
            INSERT INTO users (user_id, username, {timestamp_col})
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO NOTHING
            """
            await self._execute_query(user_query, (host_id, "Unknown"), fetch=False)
            
            # Now insert the quiz record
            insert_query = """
            INSERT INTO quizzes (
                host_id, guild_id, topic, category, difficulty, question_count, 
                template, provider, is_private, is_group, timestamp
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP)
            RETURNING quiz_id
            """
            
            result = await self._execute_query(
                insert_query,
                (
                    host_id,
                    guild_id,
                    topic,
                    category,
                    difficulty,
                    question_count,
                    template,
                    provider,
                    is_private,
                    is_group
                ),
                fetch_one=True
            )
            
            logger.info(f"Recorded quiz: {topic} by host {host_id}")
            return result["quiz_id"]
        except Exception as e:
            logger.error(f"Failed to record quiz by host {host_id}: {e}")
            return -1
    
    async def add_achievement(self, user_id: int, name: str, description: str, icon: str) -> int:
        """
        Add an achievement for a user.
        
        Args:
            user_id: Discord user ID
            name: Achievement name
            description: Achievement description
            icon: Emoji or icon for the achievement
            
        Returns:
            ID of the added achievement
            
        Raises:
            DatabaseError: If adding the achievement fails
        """
        try:
            # Check if the user already has this achievement
            query = "SELECT * FROM achievements WHERE user_id = $1 AND name = $2"
            existing = await self._execute_query(query, (user_id, name), fetch_one=True)
            
            if existing:
                # User already has this achievement
                logger.debug(f"User {user_id} already has achievement {name}")
                return -1
            
            # Ensure user exists first
            user_query = """
            INSERT INTO users (user_id, username, last_active)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO NOTHING
            """
            await self._execute_query(user_query, (user_id, "Unknown"), fetch=False)
            
            # Now insert the achievement
            insert_query = """
            INSERT INTO achievements (user_id, name, description, icon, earned_at)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            RETURNING achievement_id
            """
            
            result = await self._execute_query(
                insert_query, 
                (user_id, name, description, icon),
                fetch_one=True
            )
            
            logger.info(f"Added achievement {name} for user {user_id}")
            return result["achievement_id"]
        except Exception as e:
            logger.error(f"Failed to add achievement {name} for user {user_id}: {e}")
            return -1
    
    async def get_achievements(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get achievements for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            List of achievements
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            query = "SELECT * FROM achievements WHERE user_id = $1 ORDER BY earned_at DESC"
            results = await self._execute_query(query, (user_id,))
            return results
        except Exception as e:
            logger.error(f"Failed to get achievements for user {user_id}: {e}")
            return []
    
    # get_leaderboard method removed - using enhanced version from UserStatsService
    # The enhanced method supports guild_id, category, timeframe, and limit parameters
    
    # get_guild_leaderboard method removed - using enhanced get_leaderboard from UserStatsService
    # Call get_leaderboard(guild_id=guild_id, limit=limit) instead
    
    async def add_guild_member(self, guild_id: int, user_id: int) -> bool:
        """
        Add a guild member to the guild_members table.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            query = """
            INSERT INTO guild_members (guild_id, user_id, joined_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (guild_id, user_id) DO NOTHING
            """
            
            await self._execute_query(query, (guild_id, user_id), fetch=False)
            logger.debug(f"Added user {user_id} to guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add guild member {user_id} to guild {guild_id}: {e}")
            return False
    
    async def cache_query_result(self, key: str, data: str, expires_in_seconds: int = 300) -> bool:
        """
        Cache a query result.
        
        Args:
            key: Cache key
            data: Serialized data to cache
            expires_in_seconds: Seconds until the cache expires
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            expires_at = int(time.time()) + expires_in_seconds
            
            query = """
            INSERT INTO query_cache (cache_key, data, expires_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (cache_key) 
            DO UPDATE SET 
                data = EXCLUDED.data,
                expires_at = EXCLUDED.expires_at
            """
            
            await self._execute_query(query, (key, data, expires_at), fetch=False)
            
            logger.debug(f"Cached query result for key {key}, expires in {expires_in_seconds}s")
            return True
        except Exception as e:
            logger.error(f"Failed to cache query result for key {key}: {e}")
            return False
    
    async def get_cached_query_result(self, key: str) -> Optional[str]:
        """
        Get a cached query result.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data if found and not expired, None otherwise
        """
        try:
            current_time = int(time.time())
            
            query = """
            SELECT data FROM query_cache 
            WHERE cache_key = $1 AND expires_at > $2
            """
            
            result = await self._execute_query(query, (key, current_time), fetch_one=True)
            
            if result:
                logger.debug(f"Cache hit for key {key}")
                return result["data"]
            
            logger.debug(f"Cache miss for key {key}")
            return None
        except Exception as e:
            logger.error(f"Failed to get cached query result for key {key}: {e}")
            return None
    
    async def clear_expired_cache(self) -> int:
        """
        Clear expired cache entries.
        
        Returns:
            Number of entries cleared
        """
        try:
            current_time = int(time.time())
            
            query = "DELETE FROM query_cache WHERE expires_at <= $1"
            
            async with self.acquire() as conn:
                result = await conn.execute(query, current_time)
                # Extract row count from result string
                count = int(result.split()[-1]) if result and 'DELETE' in result else 0
            
            if count > 0:
                logger.info(f"Cleared {count} expired cache entries")
            
            return count
        except Exception as e:
            logger.error(f"Failed to clear expired cache entries: {e}")
            return 0
    
    async def close(self):
        """Close the connection pool when shutting down."""
        if self._connection_pool:
            try:
                await self._connection_pool.close()
                logger.info("Closed all PostgreSQL database connections")
                self.initialized = False
            except Exception as e:
                logger.error(f"Error closing database connections: {e}")
                # Don't re-raise as this is typically called during shutdown

    async def get_connection(self):
        """
        Get a database connection for asynchronous operations.
        
        Returns:
            Database connection (asyncpg connection object)
        """
        try:
            # Acquire a connection from the pool
            conn = await self._connection_pool.acquire()
            return conn
        except Exception as e:
            logger.error(f"Error getting async connection: {e}")
            raise
    
    async def release_connection(self, conn):
        """
        Release a connection back to the pool.
        
        Args:
            conn: The connection to release
        """
        try:
            # Return the connection to the pool
            await self._connection_pool.release(conn)
        except Exception as e:
            logger.error(f"Error releasing connection: {e}")

    async def _initialize_extensions(self):
        """Initialize database extensions and associated services."""
        try:
            # Initialize UserStatsService - the parent class
            UserStatsService.__init__(self, self)
            
            logger.debug("Database extensions initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database extensions: {e}")
            raise

    async def _get_column_names(self, table_name):
        """Get the actual column names for a table to handle schema differences."""
        # Check cache first - this data is static for the application lifetime
        if table_name in self._table_columns:
            return self._table_columns[table_name]
            
        try:
            # Query the database for column names only once per table
            query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = $1
            ORDER BY ordinal_position
            """
            columns = await self._execute_query(query, (table_name,))
            
            # Extract column names from result
            column_names = [col['column_name'] for col in columns] if columns else []
            
            # Cache the result permanently (schema doesn't change during runtime)
            self._table_columns[table_name] = column_names
            logger.debug(f"Cached columns for {table_name} table: {column_names}")
            
            return column_names
        except Exception as e:
            logger.error(f"Error getting column names for {table_name}: {e}")
            # Cache empty result to avoid repeated failed queries
            self._table_columns[table_name] = []
            return []
            
    async def _get_timestamp_column(self, table_name="users"):
        """Get the appropriate timestamp column name (last_seen or last_active)."""
        columns = await self._get_column_names(table_name)
        
        if "last_active" in columns:
            return "last_active"
        elif "last_seen" in columns:
            return "last_seen"
        else:
            # Default fallback
            logger.warning(f"No timestamp column found in {table_name}, using 'last_seen' as default")
            return "last_seen"

    # Add this to ensure the UserStatsService is initialized with the proper timestamp column
    def get_user_stats_service(self):
        """Get the UserStatsService instance, initializing it if needed."""
        if not hasattr(self, 'user_stats'):
            from .database_extensions.user_stats import UserStatsService
            self.user_stats = UserStatsService(self)
            
        # Ensure the user_stats service is aware of the correct timestamp column
        if hasattr(self, '_table_columns') and 'users' in self._table_columns:
            # Note: This is now async, but we'll handle it differently
            pass
                
        return self.user_stats

    async def record_user_quiz_session(self, user_id, username, quiz_id, topic, 
                                      correct, wrong, points, difficulty, category, guild_id=None, skipped=0):
        """Record a quiz session using the UserStatsService."""
        try:
            # Make sure the user_stats service is available
            user_stats = self.get_user_stats_service()
            
            # Call the user_stats method directly
            return await user_stats.record_user_quiz_session(
                user_id=user_id,
                username=username,
                quiz_id=quiz_id,
                topic=topic,
                correct=correct,
                wrong=wrong,
                points=points,
                difficulty=difficulty,
                category=category,
                guild_id=guild_id,
                skipped=skipped
            )
        except Exception as e:
            logger.error(f"Error in record_user_quiz_session: {e}", exc_info=True)
            return False

    async def get_user_quiz_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get user quiz history using the UserStatsService."""
        try:
            # Make sure the user_stats service is available
            user_stats = self.get_user_stats_service()
            
            # Call the user_stats method directly
            return await user_stats.get_user_quiz_history(user_id, limit)
        except Exception as e:
            logger.error(f"Error in get_user_quiz_history: {e}", exc_info=True)
            return []

    # --- Batch Operations --- 
    
    async def batch_update_user_stats(self, user_updates: List[Dict[str, Any]]) -> bool:
        """
        Update stats for multiple users in a single batch.

        Args:
            user_updates: A list of dictionaries, each containing:
                          'user_id', 'username', 'correct', 'wrong', 'points'

        Returns:
            True if the batch operation was submitted successfully (errors handled internally),
            False otherwise.
        """
        if not user_updates:
            return True # Nothing to do
            
        try:
            async with self.acquire() as conn:
                async with conn.transaction():
                    # Step 1: Ensure all users exist, create if not (or update username/timestamp)
                    timestamp_col = await self._get_timestamp_column("users")
                    
                    # Prepare data for batch insert
                    user_data = [(u['user_id'], u['username']) for u in user_updates]
                    
                    # Use COPY for efficient bulk insert/update
                    await conn.execute(f"""
                        CREATE TEMP TABLE temp_users (user_id BIGINT, username TEXT) ON COMMIT DROP
                    """)
                    
                    await conn.copy_records_to_table(
                        'temp_users',
                        records=user_data
                    )
                    
                    await conn.execute(f"""
                        INSERT INTO users (user_id, username, {timestamp_col})
                        SELECT user_id, username, CURRENT_TIMESTAMP FROM temp_users
                        ON CONFLICT (user_id) DO UPDATE SET
                            username = EXCLUDED.username,
                            {timestamp_col} = CURRENT_TIMESTAMP
                    """)
                    
                    logger.debug(f"Ensured existence/updated basic info for {len(user_updates)} users in batch.")

                    # Step 2: Update stats (correct, wrong, points)
                    columns = await self._get_column_names("users")
                    
                    # Create a temporary table for updates
                    await conn.execute("""
                        CREATE TEMP TABLE temp_user_stats_update (
                            user_id BIGINT PRIMARY KEY,
                            add_correct INTEGER,
                            add_wrong INTEGER,
                            add_points INTEGER
                        ) ON COMMIT DROP
                    """)
                    
                    # Insert data into the temporary table
                    update_data = [
                        (u['user_id'], u['correct'], u['wrong'], u['points'])
                        for u in user_updates
                    ]
                    
                    await conn.copy_records_to_table(
                        'temp_user_stats_update',
                        records=update_data
                    )
                    
                    # Perform the update using the temporary table
                    update_parts = []
                    if "correct_answers" in columns:
                        update_parts.append("correct_answers = users.correct_answers + t.add_correct")
                    if "wrong_answers" in columns:
                        update_parts.append("wrong_answers = users.wrong_answers + t.add_wrong")
                    if "points" in columns:
                        update_parts.append("points = users.points + t.add_points")
                    
                    if update_parts: # Only update if relevant columns exist
                        update_query = f"""
                        UPDATE users
                        SET {', '.join(update_parts)}
                        FROM temp_user_stats_update t
                        WHERE users.user_id = t.user_id
                        """
                        await conn.execute(update_query)
                        logger.debug(f"Batch updated stats (correct/wrong/points) for users.")
                    else:
                        logger.warning("Skipping batch stats update as relevant columns (correct_answers, wrong_answers, points) are missing in 'users' table.")

            return True
        except Exception as e:
            logger.error(f"Failed to batch update user stats for {len(user_updates)} users: {e}")
            return False
            
    async def batch_increment_quizzes_taken(self, user_updates: List[Dict[str, Any]]) -> bool:
        """
        Increment quizzes_taken for multiple users in a single batch.

        Args:
            user_updates: A list of dictionaries, each needing at least 'user_id' and 'username'.

        Returns:
            True if the batch operation was submitted successfully (errors handled internally),
            False otherwise.
        """
        if not user_updates:
            return True
            
        try:
            async with self.acquire() as conn:
                # Use transaction to ensure temp table exists for the duration
                async with conn.transaction():
                    timestamp_col = await self._get_timestamp_column("users")
                    columns = await self._get_column_names("users")
                    
                    if "quizzes_taken" in columns:
                        # Prepare data for batch upsert
                        user_data = [(u['user_id'], u['username']) for u in user_updates]
                        
                        # Use temporary table for efficient batch operation
                        await conn.execute("""
                            CREATE TEMP TABLE temp_quiz_users (user_id BIGINT, username TEXT) ON COMMIT DROP
                        """)
                        
                        await conn.copy_records_to_table(
                            'temp_quiz_users',
                            records=user_data
                        )
                        
                        await conn.execute(f"""
                            INSERT INTO users (user_id, username, quizzes_taken, {timestamp_col})
                            SELECT user_id, username, 1, CURRENT_TIMESTAMP FROM temp_quiz_users
                            ON CONFLICT (user_id) DO UPDATE SET 
                                quizzes_taken = users.quizzes_taken + 1,
                                username = EXCLUDED.username,
                                {timestamp_col} = CURRENT_TIMESTAMP
                        """)
                        
                        logger.debug(f"Batch incremented quizzes_taken for {len(user_updates)} users (or inserted).")
                    else:
                        # quizzes_taken column doesn't exist, just ensure user exists and update timestamp/username
                        user_data = [(u['user_id'], u['username']) for u in user_updates]
                        
                        await conn.execute("""
                            CREATE TEMP TABLE temp_quiz_users (user_id BIGINT, username TEXT) ON COMMIT DROP
                        """)
                        
                        await conn.copy_records_to_table(
                            'temp_quiz_users',
                            records=user_data
                        )
                        
                        await conn.execute(f"""
                            INSERT INTO users (user_id, username, {timestamp_col})
                            SELECT user_id, username, CURRENT_TIMESTAMP FROM temp_quiz_users
                            ON CONFLICT (user_id) DO UPDATE SET
                                username = EXCLUDED.username,
                                {timestamp_col} = CURRENT_TIMESTAMP
                        """)
                        
                        logger.warning(f"'quizzes_taken' column missing. Batch recorded activity for {len(user_updates)} users.")
            
            return True
        except Exception as e:
            logger.error(f"Failed to batch increment quizzes_taken for {len(user_updates)} users: {e}")
            return False

    # --- End Batch Operations ---

    async def record_onboarding(self, guild_id: int, channel_id: int) -> None:
        """
        Record when the bot is added to a new guild or update existing record.

        Args:
            guild_id: The ID of the guild the bot was added to.
            channel_id: The ID of the channel where the welcome message was sent.
        """
        try:
            query = """
            INSERT INTO guild_onboarding_log (guild_id, channel_id, onboarded_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (guild_id) DO UPDATE SET
                channel_id = EXCLUDED.channel_id,
                onboarded_at = CURRENT_TIMESTAMP
            """
            await self._execute_query(query, (guild_id, channel_id), fetch=False)
            logger.info(f"Recorded or updated onboarding for guild {guild_id} in channel {channel_id}")
        except Exception as e:
            logger.error(f"Failed to record onboarding for guild {guild_id}: {e}")

    @property
    def pool(self):
        """Access to the connection pool for external services."""
        return self._connection_pool
    
    # --- Connection Pool Monitoring ---
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics for monitoring."""
        if not self._connection_pool:
            return {}
            
        stats = {
            'pool_size': getattr(self._connection_pool, '_size', getattr(self._connection_pool, '_minsize', 0)),
            'pool_free': getattr(self._connection_pool, '_queue', {}).qsize() if hasattr(getattr(self._connection_pool, '_queue', {}), 'qsize') else 0,
            'pool_maxsize': getattr(self._connection_pool, '_maxsize', 0),
            'pool_minsize': getattr(self._connection_pool, '_minsize', 0),
            'queries_executed': self._pool_stats['queries_executed'],
            'errors': self._pool_stats['errors'],
            'connections_created': self._pool_stats['connections_created'],
            'connections_closed': self._pool_stats['connections_closed']
        }
        
        return stats
    
    async def reset_pool_stats(self):
        """Reset connection pool statistics."""
        self._pool_stats = {
            'connections_created': 0,
            'connections_closed': 0,
            'queries_executed': 0,
            'errors': 0
        }

    # Note: All database operations are async. Use await when calling these methods.

# Initialize a global placeholder that will be populated by the context
db_service = None