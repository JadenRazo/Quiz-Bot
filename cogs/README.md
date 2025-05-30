# Cogs Directory Structure

This directory contains all Discord command modules (cogs) for the Educational Quiz Bot. The cogs follow a clean OOP structure with shared utilities and data models.

## Directory Organization

```
cogs/
├── base_cog.py          # Base class for all cogs
├── models/              # Data models and entities
│   ├── __init__.py
│   └── quiz_models.py   # Quiz-related models
├── utils/               # Cog-specific utilities
│   ├── __init__.py
│   ├── permissions.py   # Permission checking utilities
│   ├── embeds.py        # Embed creation utilities
│   ├── validation.py    # Input validation utilities
│   └── decorators.py    # Common command decorators
└── [individual cogs]    # Specific functionality cogs
```

## Cog Structure

All cogs follow this pattern:

```python
from cogs.base_cog import BaseCog

class MyCog(BaseCog, name="MyCog"):
    def __init__(self, bot):
        super().__init__(bot, "MyCog")
        # Initialize cog-specific attributes
    
    def set_context(self, context):
        """Set bot context and extract configuration."""
        super().set_context(context)
        # Extract cog-specific configuration
    
    async def cog_load(self):
        """Called when cog is loaded."""
        await super().cog_load()
        # Perform cog-specific initialization
    
    # Define commands...
```

## Available Cogs

- **quiz.py** - Core quiz functionality
- **group_quiz.py** - Group quiz/trivia features
- **admin.py** - Administrative commands
- **help.py** - Help command system
- **faq.py** - FAQ management
- **onboarding.py** - Server onboarding
- **stats.py** - User statistics
- **preferences.py** - User preferences
- **custom_quiz.py** - Custom quiz creation

## Utilities

### Permission Utilities (`utils/permissions.py`)
- `check_admin_permissions()` - Check if user is admin
- `check_manage_permissions()` - Check management perms
- `check_bot_permissions()` - Check bot permissions
- `PermissionChecks` - Predefined permission decorators

### Embed Utilities (`utils/embeds.py`)
- `create_base_embed()` - Create standard embeds
- `create_error_embed()` - Error message embeds
- `create_success_embed()` - Success message embeds
- `create_quiz_embed()` - Quiz-specific embeds
- `create_leaderboard_embed()` - Leaderboard embeds
- `create_stats_embed()` - Statistics embeds

### Validation Utilities (`utils/validation.py`)
- `validate_quiz_parameters()` - Validate quiz inputs
- `validate_topic()` - Check topic validity
- `validate_difficulty()` - Validate difficulty levels
- `validate_provider()` - Check LLM provider
- `validate_username()` - Validate usernames

### Decorators (`utils/decorators.py`)
- `@require_context` - Ensure context is set
- `@in_guild_only` - Guild-only commands
- `@cooldown_with_bypass` - Cooldowns with role bypass
- `@admin_only` - Admin-only commands
- `@typing_indicator` - Show typing status
- `@handle_errors` - Error handling
- `@ensure_database` - Require database access
- `@feature_required` - Feature flag checks

## Data Models

### Quiz Models (`models/quiz_models.py`)
- `QuizState` - Enum for quiz states
- `QuizParticipant` - Participant data class
- `ActiveQuiz` - Active quiz session class

## Adding a New Cog

1. Create new file inheriting from `BaseCog`
2. Implement required methods:
   - `__init__()` - Initialize the cog
   - `set_context()` - Set bot context
   - `cog_load()` - Optional loading logic
3. Define commands using `@commands.command()` or `@app_commands.command()`
4. Add setup functions:
   ```python
   async def setup(bot):
       cog = MyCog(bot)
       await bot.add_cog(cog)
       return cog
   
   async def setup_with_context(bot, context):
       from cogs.base_cog import setup_with_context as base_setup
       return await base_setup(bot, context, MyCog)
   ```
5. Add to `main.py` cog list and `cog_loader.py` mapping

## Best Practices

1. Always inherit from `BaseCog`
2. Use utilities from `cogs/utils/` for common operations
3. Extract data models to `cogs/models/`
4. Use decorators for permission checks and error handling
5. Maintain consistent error messages and embed formatting
6. Log important operations using the cog's logger
7. Handle async operations properly
8. Validate user input before processing