# Multi-Guild Implementation Guide

This document outlines the necessary changes to make the quiz bot work seamlessly across multiple Discord guilds.

## Overview

The bot needs to properly segregate data and settings by guild to ensure that:
- Each guild can have its own configuration
- User statistics are tracked both globally and per-guild
- Quiz sessions don't interfere across guilds
- Administrators can customize their guild's experience

## Critical Changes Required

### 1. Group Quiz Manager (`services/group_quiz.py`)

**Current Issue**: Sessions are tracked by channel_id only, which can collide across guilds.

**Solution**: Use composite keys (guild_id, channel_id) for session tracking.

```python
# Replace this:
self.active_sessions: Dict[int, GroupQuizSession] = {}  # channel_id -> session

# With this:
self.active_sessions: Dict[Tuple[int, int], GroupQuizSession] = {}  # (guild_id, channel_id) -> session

# Update all methods to include guild_id:
def create_session(self, guild_id: int, channel_id: int, ...):
    session = GroupQuizSession(guild_id=guild_id, channel_id=channel_id, ...)
    self.active_sessions[(guild_id, channel_id)] = session
    return session

def get_session(self, guild_id: int, channel_id: int):
    return self.active_sessions.get((guild_id, channel_id))
```

### 2. Database Schema Updates

Add the following SQL migrations:

```sql
-- Add guild_id to user_quiz_sessions
ALTER TABLE user_quiz_sessions 
ADD COLUMN IF NOT EXISTS guild_id BIGINT;

-- Enhance guild_settings
ALTER TABLE guild_settings
ADD COLUMN IF NOT EXISTS quiz_channel_id BIGINT,
ADD COLUMN IF NOT EXISTS trivia_channel_id BIGINT,
ADD COLUMN IF NOT EXISTS admin_role_id BIGINT,
ADD COLUMN IF NOT EXISTS default_quiz_difficulty VARCHAR(20) DEFAULT 'medium',
ADD COLUMN IF NOT EXISTS default_question_count INTEGER DEFAULT 5;

-- Create guild-specific user preferences
CREATE TABLE IF NOT EXISTS guild_user_preferences (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    preferences JSONB,
    PRIMARY KEY (guild_id, user_id)
);

-- Create guild leaderboards
CREATE TABLE IF NOT EXISTS guild_leaderboards (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    total_points INTEGER NOT NULL DEFAULT 0,
    total_quizzes INTEGER NOT NULL DEFAULT 0,
    total_correct INTEGER NOT NULL DEFAULT 0,
    total_wrong INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
```

### 3. Group Quiz Cog (`cogs/group_quiz.py`)

Update all session operations to include guild_id:

```python
# In trivia_start command:
active_session = self.group_quiz_manager.get_session(ctx.guild.id, ctx.channel.id)

# Create session with guild context:
session = self.group_quiz_manager.create_session(
    guild_id=ctx.guild.id,
    channel_id=ctx.channel.id,
    # ... other params
)

# In trivia_stop command:
active_session = self.group_quiz_manager.get_session(ctx.guild.id, ctx.channel.id)

# End session with guild context:
self.group_quiz_manager.end_session(ctx.guild.id, ctx.channel.id)
```

### 4. Database Operations

Update all database operations to include guild context where appropriate:

```python
# When recording quiz results:
await record_batch_quiz_results(
    db_service=self.db_service,
    quiz_id=db_quiz_id,
    topic=session.topic,
    results=batch_results_data,
    guild_id=ctx.guild.id  # Add this
)

# When updating leaderboards:
await update_guild_user_stats(
    db_service=self.db_service,
    guild_id=session.guild_id,
    user_id=user_id,
    points=points,
    correct=correct,
    wrong=wrong
)
```

### 5. New Guild Configuration Commands

Add a new cog for guild-specific settings (`cogs/guild_preferences.py`):

```python
@commands.hybrid_group(name="guild", description="Guild-specific settings")
@commands.has_permissions(manage_guild=True)
async def guild_group(self, ctx):
    pass

@guild_group.command(name="set_quiz_channel")
async def set_quiz_channel(self, ctx, channel: discord.TextChannel):
    """Set the default quiz channel for this guild."""
    await self.db_service.set_guild_setting(
        guild_id=ctx.guild.id,
        setting_key="quiz_channel_id",
        setting_value=channel.id
    )

@guild_group.command(name="set_admin_role")
async def set_admin_role(self, ctx, role: discord.Role):
    """Set the admin role for quiz management."""
    await self.db_service.set_guild_setting(
        guild_id=ctx.guild.id,
        setting_key="admin_role_id",
        setting_value=role.id
    )
```

### 6. Stats Commands

Update stats commands to support guild vs global views:

```python
@commands.hybrid_command(name="stats")
async def stats(self, ctx, user: Optional[discord.Member] = None, 
                scope: Literal["server", "global"] = "server"):
    """View stats with guild context."""
    guild_id = ctx.guild.id if scope == "server" else None
    stats_data = await get_user_stats(
        self.db_service, 
        user_id,
        guild_id=guild_id
    )
```

### 7. Preferences System

Enhance preferences to support guild-specific overrides:

```python
async def get_effective_preferences(self, guild_id: int, user_id: int):
    """Get user preferences with guild overrides."""
    # Get global preferences
    global_prefs = await self.db_service.get_user_preferences(user_id)
    
    # Get guild-specific preferences
    guild_prefs = await self.db_service.get_guild_user_preferences(guild_id, user_id)
    
    # Merge with guild overrides taking precedence
    return {**global_prefs, **guild_prefs}
```

## Implementation Order

1. **Database Schema Updates** - Run the SQL migrations first
2. **GroupQuizManager Updates** - Update to use composite keys
3. **Database Operations** - Add guild context to all operations
4. **Group Quiz Cog** - Update to pass guild_id
5. **Guild Preferences Cog** - Add new guild configuration commands
6. **Stats Updates** - Add guild-specific views
7. **Preferences System** - Add guild override support

## Testing Checklist

- [ ] Trivia games run independently in different guilds
- [ ] Guild admins can set custom channels for quizzes
- [ ] User stats show correctly per guild
- [ ] Leaderboards are guild-specific
- [ ] Preferences can be overridden per guild
- [ ] Quiz sessions don't interfere across guilds
- [ ] Guild settings persist across bot restarts

## Configuration Examples

### Setting Up a New Guild

```bash
# Set quiz channel
/guild set_quiz_channel #quiz-channel

# Set trivia channel
/guild set_trivia_channel #trivia-games

# Set admin role
/guild set_admin_role @QuizMasters

# Enable/disable features
/guild enable_feature leaderboard
/guild disable_feature auto_quiz

# View settings
/guild settings
```

### User Experience

```bash
# View guild-specific stats
/stats scope:server

# View global stats
/stats scope:global

# Guild-specific leaderboard
/leaderboard

# Guild-specific preferences
/preferences quiz_channel #my-quiz-channel
```

## Migration Notes

For existing deployments:

1. Run SQL migrations during maintenance window
2. Update bot code to new version
3. Test in a staging guild first
4. Deploy to production
5. Monitor for any issues with existing data

The bot will automatically handle missing guild data with sensible defaults until administrators configure their preferences.