"""Database adapters for legacy compatibility."""

from .user_stats_adapter import (
    UserStatsAdapter,
    create_user_stats_adapter,
    initialize_adapter,
    get_user_stats,
    create_user_stats,
    get_or_create_user_stats,
    update_quiz_completion,
    get_leaderboard,
    get_user_rank,
    update_level,
    reset_streak
)

__all__ = [
    'UserStatsAdapter',
    'create_user_stats_adapter',
    'initialize_adapter',
    'get_user_stats',
    'create_user_stats',
    'get_or_create_user_stats',
    'update_quiz_completion',
    'get_leaderboard',
    'get_user_rank',
    'update_level',
    'reset_streak',
]