"""
Utility functions and helpers for the educational quiz bot.

This module provides various utility functions and classes used throughout the bot,
including UI components, error handling, feature flags, and other helpers.
"""

from utils.ui import (
    # Helper functions
    create_embed,
    create_progress_bar,
    get_color_for_difficulty,
    get_emoji_for_category,
    format_duration,
    get_medal,
    format_leaderboard_entry,
    
    # Constants
    MEDALS,
    PROGRESS_BAR_CHARS,
    DIFFICULTY_COLORS,
    CATEGORY_EMOJIS,
    REACTION_EMOJIS
)

# Make context available
from utils.context import BotContext

# Make error handling available
from utils.errors import (
    BotError, 
    ErrorSeverity,
    ConfigurationError,
    DatabaseError,
    APIError,
    QuizGenerationError,
    UserInputError,
    log_exception,
    handle_command_error,
    safe_execute
)

# Make decorators available
from utils.decorators import (
    cache_result,
    time_execution,
    retry
)

# Make feature flags available
from utils.feature_flags import (
    FeatureFlag,
    feature_manager
)

# Import content size limiting utilities
from utils.content import (
    truncate_content,
    truncate_dict_content,
    normalize_quiz_content,
    CONTENT_SIZE_LIMITS
)

__all__ = [
    # Classes
    'BotContext',
    'BotError',
    'ErrorSeverity',
    'ConfigurationError',
    'DatabaseError',
    'APIError',
    'QuizGenerationError',
    'UserInputError',
    'FeatureFlag',
    
    # Functions
    'create_embed',
    'create_progress_bar',
    'get_color_for_difficulty',
    'get_emoji_for_category',
    'format_duration',
    'get_medal',
    'format_leaderboard_entry',
    'log_exception',
    'handle_command_error',
    'safe_execute',
    'cache_result',
    'time_execution',
    'retry',
    'truncate_content',
    'truncate_dict_content',
    'normalize_quiz_content',
    
    # Instances
    'feature_manager',
    
    # Constants
    'MEDALS',
    'PROGRESS_BAR_CHARS',
    'DIFFICULTY_COLORS',
    'CATEGORY_EMOJIS',
    'REACTION_EMOJIS',
    'CONTENT_SIZE_LIMITS'
] 