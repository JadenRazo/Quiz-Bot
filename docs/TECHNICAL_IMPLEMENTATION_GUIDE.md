# 🔧 Technical Implementation Guide

This guide provides detailed technical specifications for implementing the critical enhancements outlined in the Enhancement Roadmap.

## 1. Multi-Guild Support Implementation

### 1.1 Database Schema Updates

```sql
-- Add guild context to all relevant tables
ALTER TABLE user_quiz_sessions 
ADD COLUMN guild_id BIGINT;

-- Create guild-specific tables
CREATE TABLE guild_quiz_templates (
    guild_id BIGINT NOT NULL,
    template_id SERIAL,
    name VARCHAR(100),
    settings JSONB,
    PRIMARY KEY (guild_id, template_id)
);

-- Add composite indexes for performance
CREATE INDEX idx_quiz_sessions_guild_user 
ON user_quiz_sessions(guild_id, user_id);
```

### 1.2 Session Manager Refactor

```python
# services/group_quiz.py
class GroupQuizManager:
    def __init__(self, bot=None):
        # Use composite key for proper guild separation
        self.active_sessions: Dict[Tuple[int, int], GroupQuizSession] = {}
        
    def create_session(self, guild_id: int, channel_id: int, **kwargs):
        key = (guild_id, channel_id)
        session = GroupQuizSession(guild_id=guild_id, channel_id=channel_id, **kwargs)
        self.active_sessions[key] = session
        return session
```

### 1.3 Context Propagation

```python
# Ensure guild context in all operations
class QuizCog(BaseCog):
    @commands.hybrid_command()
    async def start(self, ctx: commands.Context, topic: str):
        # Always include guild_id
        session = await self.quiz_manager.create_session(
            guild_id=ctx.guild.id,
            channel_id=ctx.channel.id,
            user_id=ctx.author.id,
            topic=topic
        )
```

## 2. Rich Media Support

### 2.1 Database Schema for Media

```sql
-- Media storage table
CREATE TABLE quiz_media (
    media_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id INTEGER,
    media_type VARCHAR(20) NOT NULL, -- image, audio, video, code
    media_url TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Update questions table
ALTER TABLE quiz_questions 
ADD COLUMN media_id UUID REFERENCES quiz_media(media_id);
```

### 2.2 Media Handler Service

```python
# services/media_handler.py
class MediaHandler:
    SUPPORTED_TYPES = ['image', 'audio', 'video', 'code']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    async def process_media(self, file: discord.File, media_type: str) -> str:
        """Process and store media file, return URL"""
        if media_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported media type: {media_type}")
            
        # Validate file size
        if file.size > self.MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file.size} bytes")
            
        # Upload to CDN/S3
        url = await self._upload_to_storage(file)
        
        # Store metadata in database
        media_id = await self._store_media_metadata(url, media_type)
        
        return media_id
```

### 2.3 Rich Embed Creation

```python
# utils/embeds.py
def create_question_embed(question: Question, media: Optional[Media] = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"Question {question.number}",
        description=question.text,
        color=discord.Color.blue()
    )
    
    if media:
        if media.type == 'image':
            embed.set_image(url=media.url)
        elif media.type == 'code':
            # Use code block formatting
            embed.add_field(
                name="Code",
                value=f"```{media.metadata.get('language', 'python')}\n{media.content}\n```",
                inline=False
            )
    
    return embed
```

## 3. Adaptive Learning System

### 3.1 Performance Tracking Schema

```sql
-- User performance by topic
CREATE TABLE user_topic_performance (
    user_id BIGINT,
    guild_id BIGINT,
    topic VARCHAR(100),
    difficulty_level INTEGER,
    success_rate FLOAT,
    total_attempts INTEGER,
    last_attempt TIMESTAMP,
    PRIMARY KEY (user_id, guild_id, topic)
);

-- Learning recommendations
CREATE TABLE learning_recommendations (
    user_id BIGINT,
    guild_id BIGINT,
    topic VARCHAR(100),
    recommended_difficulty INTEGER,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3.2 Adaptive Algorithm

```python
# services/adaptive_learning.py
class AdaptiveLearningEngine:
    def calculate_next_difficulty(self, user_id: int, topic: str, guild_id: int) -> int:
        """Calculate appropriate difficulty based on performance"""
        performance = await self.get_user_performance(user_id, topic, guild_id)
        
        if performance.success_rate > 0.8:
            return min(performance.current_difficulty + 1, 5)
        elif performance.success_rate < 0.5:
            return max(performance.current_difficulty - 1, 1)
        else:
            return performance.current_difficulty
    
    async def generate_learning_path(self, user_id: int, guild_id: int) -> List[Topic]:
        """Generate personalized learning path"""
        weak_topics = await self.identify_weak_areas(user_id, guild_id)
        strong_topics = await self.identify_strengths(user_id, guild_id)
        
        # Balance weak areas with confidence boosters
        path = []
        for i in range(10):
            if i % 3 == 0 and strong_topics:
                path.append(random.choice(strong_topics))
            elif weak_topics:
                path.append(weak_topics.pop(0))
                
        return path
```

## 4. Gamification System

### 4.1 Experience System

```python
# services/experience_system.py
class ExperienceSystem:
    XP_PER_CORRECT = 10
    XP_PER_STREAK = 5
    XP_PER_PERFECT_QUIZ = 50
    
    async def award_xp(self, user_id: int, guild_id: int, 
                       action: str, metadata: dict) -> int:
        """Award XP for various actions"""
        xp_earned = 0
        
        if action == 'correct_answer':
            xp_earned = self.XP_PER_CORRECT
            if metadata.get('streak', 0) > 3:
                xp_earned += self.XP_PER_STREAK
                
        elif action == 'quiz_complete':
            if metadata.get('perfect', False):
                xp_earned = self.XP_PER_PERFECT_QUIZ
                
        # Apply multipliers
        xp_earned = int(xp_earned * metadata.get('multiplier', 1.0))
        
        # Update database
        await self.db.update_user_xp(user_id, guild_id, xp_earned)
        
        # Check for level up
        await self.check_level_up(user_id, guild_id)
        
        return xp_earned
```

### 4.2 Achievement System

```python
# services/achievements.py
class AchievementManager:
    achievements = {
        'first_quiz': {
            'name': 'Quiz Beginner',
            'description': 'Complete your first quiz',
            'icon': '🎯',
            'xp': 50
        },
        'perfect_streak_5': {
            'name': 'Perfectionist',
            'description': 'Get 5 perfect quizzes in a row',
            'icon': '⭐',
            'xp': 200
        },
        'topic_master': {
            'name': 'Subject Expert',
            'description': 'Master a topic with 90% accuracy',
            'icon': '🏆',
            'xp': 500
        }
    }
    
    async def check_achievements(self, user_id: int, guild_id: int, 
                                context: dict) -> List[Achievement]:
        """Check if user earned any achievements"""
        earned = []
        
        user_stats = await self.get_user_stats(user_id, guild_id)
        
        # Check each achievement condition
        if user_stats.quizzes_completed == 1:
            earned.append(self.achievements['first_quiz'])
            
        if user_stats.perfect_streak >= 5:
            earned.append(self.achievements['perfect_streak_5'])
            
        # Award achievements
        for achievement in earned:
            await self.award_achievement(user_id, guild_id, achievement)
            
        return earned
```

## 5. Competition System

### 5.1 Tournament Framework

```python
# services/tournament_manager.py
class TournamentManager:
    def __init__(self, db_service):
        self.db = db_service
        self.active_tournaments = {}
        
    async def create_tournament(self, guild_id: int, name: str, 
                                settings: dict) -> Tournament:
        """Create a new tournament"""
        tournament = Tournament(
            guild_id=guild_id,
            name=name,
            topic=settings.get('topic'),
            duration=settings.get('duration', 7),  # days
            max_participants=settings.get('max_participants', 100),
            entry_fee=settings.get('entry_fee', 0),
            prizes=settings.get('prizes', [])
        )
        
        # Save to database
        tournament_id = await self.db.create_tournament(tournament)
        tournament.id = tournament_id
        
        # Cache active tournament
        self.active_tournaments[guild_id] = tournament
        
        return tournament
    
    async def join_tournament(self, user_id: int, tournament_id: int) -> bool:
        """Join a tournament"""
        tournament = await self.get_tournament(tournament_id)
        
        if tournament.is_full():
            return False
            
        if tournament.has_entry_fee():
            if not await self.deduct_entry_fee(user_id, tournament.entry_fee):
                return False
                
        await self.db.add_tournament_participant(tournament_id, user_id)
        return True
```

### 5.2 Leaderboard System

```python
# services/leaderboard_manager.py
class LeaderboardManager:
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self, cache_service, db_service):
        self.cache = cache_service
        self.db = db_service
        
    async def get_guild_leaderboard(self, guild_id: int, 
                                    timeframe: str = 'all') -> List[LeaderboardEntry]:
        """Get guild leaderboard with caching"""
        cache_key = f"leaderboard:{guild_id}:{timeframe}"
        
        # Check cache first
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
            
        # Query database
        entries = await self.db.get_leaderboard(
            guild_id=guild_id,
            timeframe=timeframe,
            limit=100
        )
        
        # Cache results
        await self.cache.set(cache_key, entries, self.CACHE_TTL)
        
        return entries
```

## 6. Performance Optimizations

### 6.1 Database Connection Pooling

```python
# services/database.py
class DatabaseService:
    def __init__(self, config):
        self.pool = None
        self.config = config
        
    async def initialize(self):
        """Initialize connection pool"""
        self.pool = await asyncpg.create_pool(
            self.config.database_url,
            min_size=10,
            max_size=20,
            max_inactive_connection_lifetime=300,
            command_timeout=60
        )
    
    async def get_connection(self):
        """Get a connection from the pool"""
        async with self.pool.acquire() as connection:
            yield connection
```

### 6.2 Caching Layer

```python
# services/cache_service.py
import redis.asyncio as redis

class CacheService:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
        
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache with TTL"""
        await self.redis.setex(
            key, 
            ttl, 
            json.dumps(value, default=str)
        )
        
    async def invalidate(self, pattern: str):
        """Invalidate cache keys matching pattern"""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```

## 7. Error Recovery System

### 7.1 Graceful Error Handling

```python
# utils/errors.py
class QuizBotError(Exception):
    """Base exception for quiz bot"""
    pass

class SessionError(QuizBotError):
    """Session-related errors"""
    pass

class QuizNotFoundError(QuizBotError):
    """Quiz not found error"""
    pass

# Decorator for error handling
def handle_errors(error_message: str = "An error occurred"):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except QuizBotError as e:
                # Log the error
                logger.error(f"QuizBot error in {func.__name__}: {e}")
                
                # Send user-friendly message
                ctx = args[1]  # Assuming ctx is second argument
                await ctx.send(f"❌ {error_message}: {str(e)}")
                
            except Exception as e:
                # Log unexpected errors
                logger.exception(f"Unexpected error in {func.__name__}")
                
                # Send generic error message
                ctx = args[1]
                await ctx.send(f"❌ {error_message}. Please try again later.")
                
        return wrapper
    return decorator
```

### 7.2 Session Recovery

```python
# services/session_recovery.py
class SessionRecoveryService:
    def __init__(self, db_service, cache_service):
        self.db = db_service
        self.cache = cache_service
        
    async def save_session_state(self, session: QuizSession):
        """Save session state for recovery"""
        state = {
            'guild_id': session.guild_id,
            'channel_id': session.channel_id,
            'user_id': session.user_id,
            'current_question': session.current_question,
            'answers': session.answers,
            'start_time': session.start_time.isoformat(),
            'topic': session.topic
        }
        
        # Save to cache for quick recovery
        cache_key = f"session:{session.guild_id}:{session.channel_id}"
        await self.cache.set(cache_key, state, ttl=3600)
        
        # Also save to database for persistence
        await self.db.save_session_state(session.id, state)
        
    async def recover_session(self, guild_id: int, channel_id: int) -> Optional[QuizSession]:
        """Attempt to recover a session"""
        # Try cache first
        cache_key = f"session:{guild_id}:{channel_id}"
        state = await self.cache.get(cache_key)
        
        if not state:
            # Try database
            state = await self.db.get_session_state(guild_id, channel_id)
            
        if state:
            # Reconstruct session
            session = QuizSession.from_state(state)
            return session
            
        return None
```

This technical implementation guide provides the detailed specifications needed to implement the critical enhancements. Each section includes database schemas, code examples, and architectural decisions to ensure a robust implementation.