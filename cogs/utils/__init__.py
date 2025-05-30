"""
Utilities for cogs.

This module provides common functionality for all cogs including:
- Permission checks
- Embed creation
- Input validation
- Common decorators
- Legacy utility functions (for backward compatibility)
"""

# Import from new utility modules
from .permissions import (
    is_bot_admin,
    has_server_permission,
    has_role,
    check_admin_permissions,
    check_manage_permissions,
    check_bot_permissions,
    PermissionChecks
)

from .embeds import (
    create_base_embed,
    create_error_embed,
    create_success_embed,
    create_quiz_embed,
    create_leaderboard_embed,
    create_stats_embed,
    add_fields_to_embed,
    COLORS
)

from .validation import (
    validate_quiz_count,
    validate_topic,
    validate_difficulty,
    validate_provider,
    validate_username,
    validate_quiz_parameters,
    validate_answer,
    validate_timeframe,
    validate_category,
    MIN_QUIZ_QUESTIONS,
    MAX_QUIZ_QUESTIONS,
    VALID_DIFFICULTIES,
    VALID_PROVIDERS
)

from .decorators import (
    require_context,
    in_guild_only,
    cooldown_with_bypass,
    admin_only,
    typing_indicator,
    handle_errors,
    ensure_database,
    feature_required,
    owner_only
)

# Legacy imports for backward compatibility
from typing import Optional, Union, List
import discord
from discord.ext import commands


def check_permissions(
    ctx: commands.Context,
    required_permissions: List[str],
    check_guild: bool = True
) -> bool:
    """
    Check if a user has required permissions.
    
    Args:
        ctx: The command context
        required_permissions: List of permission names required
        check_guild: Whether to check for guild context
        
    Returns:
        bool: True if user has permissions
    """
    if check_guild and not ctx.guild:
        return False
    
    # Bot owners always have permission
    if ctx.bot.is_owner(ctx.author):
        return True
    
    # Check each required permission
    for permission in required_permissions:
        if not getattr(ctx.author.guild_permissions, permission, False):
            return False
    
    return True


async def safe_send(
    destination: Union[discord.TextChannel, discord.User, commands.Context],
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    **kwargs
) -> Optional[discord.Message]:
    """
    Safely send a message to a destination.
    
    Args:
        destination: Where to send the message
        content: Text content to send
        embed: Embed to send
        **kwargs: Additional arguments for send()
        
    Returns:
        Optional[discord.Message]: The sent message, or None if failed
    """
    try:
        if isinstance(destination, commands.Context):
            async with destination.typing():
                return await destination.send(content=content, embed=embed, **kwargs)
        else:
            # For non-Context destinations, check if they support typing
            if hasattr(destination, 'typing'):
                async with destination.typing():
                    return await destination.send(content=content, embed=embed, **kwargs)
            else:
                return await destination.send(content=content, embed=embed, **kwargs)
    except discord.Forbidden:
        # Try to send a simpler message if possible
        if isinstance(destination, commands.Context):
            try:
                async with destination.author.typing():
                    return await destination.author.send(
                        "I don't have permission to send messages in that channel."
                    )
            except:
                pass
    except Exception:
        pass
    
    return None


def format_duration(seconds: int) -> str:
    """
    Format seconds into a human-readable duration.
    
    Args:
        seconds: Number of seconds
        
    Returns:
        str: Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def truncate_string(text: str, max_length: int = 1024, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        text: The text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        str: Truncated string
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


class CogMixin:
    """Mixin class providing common functionality for cogs."""
    
    async def send_error(
        self,
        ctx: commands.Context,
        error_message: str,
        ephemeral: bool = False
    ) -> Optional[discord.Message]:
        """
        Send an error message with consistent formatting.
        
        Args:
            ctx: Command context
            error_message: The error message to send
            ephemeral: Whether to send as ephemeral (slash commands only)
            
        Returns:
            Optional[discord.Message]: The sent message
        """
        embed = discord.Embed(
            title="❌ Error",
            description=error_message,
            color=discord.Color.red()
        )
        
        kwargs = {"embed": embed}
        if ephemeral and hasattr(ctx, "interaction"):
            kwargs["ephemeral"] = True
        
        return await safe_send(ctx, **kwargs)
    
    async def send_success(
        self,
        ctx: commands.Context,
        success_message: str,
        ephemeral: bool = False
    ) -> Optional[discord.Message]:
        """
        Send a success message with consistent formatting.
        
        Args:
            ctx: Command context
            success_message: The success message to send
            ephemeral: Whether to send as ephemeral (slash commands only)
            
        Returns:
            Optional[discord.Message]: The sent message
        """
        embed = discord.Embed(
            title="✅ Success",
            description=success_message,
            color=discord.Color.green()
        )
        
        kwargs = {"embed": embed}
        if ephemeral and hasattr(ctx, "interaction"):
            kwargs["ephemeral"] = True
        
        return await safe_send(ctx, **kwargs)


# List all exported items
__all__ = [
    # New permissions utilities
    'is_bot_admin',
    'has_server_permission',
    'has_role',
    'check_admin_permissions',
    'check_manage_permissions',
    'check_bot_permissions',
    'PermissionChecks',
    
    # New embed utilities
    'create_base_embed',
    'create_error_embed',
    'create_success_embed',
    'create_quiz_embed',
    'create_leaderboard_embed',
    'create_stats_embed',
    'add_fields_to_embed',
    'COLORS',
    
    # New validation utilities
    'validate_quiz_count',
    'validate_topic',
    'validate_difficulty',
    'validate_provider',
    'validate_username',
    'validate_quiz_parameters',
    'validate_answer',
    'validate_timeframe',
    'validate_category',
    'MIN_QUIZ_QUESTIONS',
    'MAX_QUIZ_QUESTIONS',
    'VALID_DIFFICULTIES',
    'VALID_PROVIDERS',
    
    # New decorators
    'require_context',
    'in_guild_only',
    'cooldown_with_bypass',
    'admin_only',
    'typing_indicator',
    'handle_errors',
    'ensure_database',
    'feature_required',
    'owner_only',
    
    # Legacy utilities
    'check_permissions',
    'safe_send',
    'format_duration',
    'truncate_string',
    'CogMixin'
]