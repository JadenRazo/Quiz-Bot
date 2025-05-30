"""User-friendly error messages and helpful suggestions."""

import discord
from typing import Optional, Dict, Any

# Error message constants
ERROR_MESSAGES = {
    "quiz_not_found": "❌ Quiz session not found. Try starting a new quiz with `/trivia start`",
    "already_active": "❌ There's already an active trivia quiz in this channel. Please wait for it to finish or use `/trivia stop` to end it.",
    "no_permission": "❌ You don't have permission to use this command. Only the quiz host or a moderator can do this.",
    "generation_failed": "❌ Failed to generate quiz questions. Please try again with a different topic or provider.",
    "database_error": "❌ A database error occurred. Your progress has been saved locally. Please try again later.",
    "timeout_error": "❌ The request timed out. Please try again with fewer questions or a simpler topic.",
    "invalid_input": "❌ Invalid input. Please check your command and try again.",
    "service_unavailable": "❌ The quiz service is temporarily unavailable. Please try again in a few moments.",
    "rate_limited": "❌ You're using commands too quickly. Please wait a moment before trying again.",
    "not_in_quiz": "❌ You're not participating in a quiz. Join one with `/trivia start`",
}

# Success message templates
SUCCESS_MESSAGES = {
    "quiz_started": "🎮 Trivia game started! Get ready for {count} questions about **{topic}**!",
    "quiz_ended": "🏁 Trivia game ended! Thanks for playing!",
    "correct_answer": "✅ Correct! You earned **{points}** points!",
    "wrong_answer": "❌ Sorry, that's incorrect. The answer was **{answer}**",
    "level_up": "🎊 **LEVEL UP!** You're now Level {level}! 🎉",
    "achievement_unlocked": "🏆 **Achievement Unlocked:** {achievement_name}",
    "streak_bonus": "🔥 **{streak} Answer Streak!** Bonus XP: +{bonus}",
}

# Help suggestions for common issues
HELP_SUGGESTIONS = {
    "no_questions": "Try a broader topic or different difficulty level.",
    "connection_error": "Check your internet connection and try again.",
    "permission_denied": "Ask a server administrator to grant you the necessary permissions.",
    "invalid_topic": "Try using a more general topic like 'Science', 'History', or 'Sports'.",
}

def format_error_message(error_key: str, **kwargs) -> str:
    """Format an error message with optional parameters."""
    message = ERROR_MESSAGES.get(error_key, "❌ An unexpected error occurred.")
    
    # Add suggestions if available
    suggestion = HELP_SUGGESTIONS.get(error_key)
    if suggestion:
        message += f"\n💡 **Tip:** {suggestion}"
    
    return message.format(**kwargs)

def format_success_message(success_key: str, **kwargs) -> str:
    """Format a success message with parameters."""
    message = SUCCESS_MESSAGES.get(success_key, "✅ Success!")
    return message.format(**kwargs)

def create_error_embed(
    title: str = "Error",
    description: str = None,
    error_key: str = None,
    **kwargs
) -> discord.Embed:
    """Create a formatted error embed."""
    embed = discord.Embed(
        title=f"❌ {title}",
        color=discord.Color.red()
    )
    
    if error_key:
        description = format_error_message(error_key, **kwargs)
    
    if description:
        embed.description = description
    
    return embed

def create_success_embed(
    title: str = "Success",
    description: str = None,
    success_key: str = None,
    **kwargs
) -> discord.Embed:
    """Create a formatted success embed."""
    embed = discord.Embed(
        title=f"✅ {title}",
        color=discord.Color.green()
    )
    
    if success_key:
        description = format_success_message(success_key, **kwargs)
    
    if description:
        embed.description = description
    
    return embed