"""Common decorators for cog commands."""

import asyncio
import functools
import logging
from typing import Callable, Optional, Any
from discord.ext import commands

logger = logging.getLogger("bot.cogs.utils.decorators")


def require_context(func: Callable) -> Callable:
    """
    Decorator to ensure the cog has context set before command execution.
    
    Args:
        func: The command function to wrap
        
    Returns:
        Callable: The wrapped function
    """
    @functools.wraps(func)
    async def wrapper(self, ctx: commands.Context, *args, **kwargs):
        if not hasattr(self, 'context') or self.context is None:
            async with ctx.typing():
                await ctx.send("Bot is not properly initialized. Please try again later.")
            logger.error(f"Context not set for {self.__class__.__name__}")
            return
        return await func(self, ctx, *args, **kwargs)
    return wrapper


def in_guild_only(func: Callable) -> Callable:
    """
    Decorator to ensure command is only used in guilds.
    
    Args:
        func: The command function to wrap
        
    Returns:
        Callable: The wrapped function
    """
    @functools.wraps(func)
    async def wrapper(self, ctx: commands.Context, *args, **kwargs):
        if not ctx.guild:
            async with ctx.typing():
                await ctx.send("This command can only be used in a server.")
            return
        return await func(self, ctx, *args, **kwargs)
    return wrapper


def cooldown_with_bypass(
    rate: int = 1,
    per: float = 60.0,
    bypass_roles: Optional[list] = None
) -> Callable:
    """
    Decorator to add cooldown with role bypass.
    
    Args:
        rate: Number of times the command can be used
        per: Cooldown period in seconds
        bypass_roles: List of role names that bypass the cooldown
        
    Returns:
        Callable: The decorator function
    """
    def decorator(func: Callable) -> Callable:
        # First apply the standard cooldown
        func = commands.cooldown(rate, per, commands.BucketType.user)(func)
        
        @functools.wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            # Check if user has bypass role
            if bypass_roles and ctx.guild and ctx.author:
                user_roles = [role.name.lower() for role in ctx.author.roles]
                for bypass_role in bypass_roles:
                    if bypass_role.lower() in user_roles:
                        # Reset cooldown for this user
                        ctx.command.reset_cooldown(ctx)
                        break
            
            try:
                return await func(self, ctx, *args, **kwargs)
            except commands.CommandOnCooldown as e:
                async with ctx.typing():
                    await ctx.send(f"This command is on cooldown. Please try again in {e.retry_after:.0f} seconds.")
                raise
        
        return wrapper
    return decorator


def admin_only(admin_users: Optional[list] = None, admin_roles: Optional[list] = None) -> Callable:
    """
    Decorator to restrict command to admins only.
    
    Args:
        admin_users: List of admin user IDs
        admin_roles: List of admin role names
        
    Returns:
        Callable: The decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            # Check if user is in admin users list
            if admin_users and ctx.author.id in admin_users:
                return await func(self, ctx, *args, **kwargs)
            
            # Check if user has admin role
            if admin_roles and ctx.guild:
                user_roles = [role.name.lower() for role in ctx.author.roles]
                for admin_role in admin_roles:
                    if admin_role.lower() in user_roles:
                        return await func(self, ctx, *args, **kwargs)
            
            # Check if user is guild owner
            if ctx.guild and ctx.author.id == ctx.guild.owner_id:
                return await func(self, ctx, *args, **kwargs)
            
            # Check if user has administrator permission
            if ctx.guild and ctx.author.guild_permissions.administrator:
                return await func(self, ctx, *args, **kwargs)
            
            async with ctx.typing():
                await ctx.send("You don't have permission to use this command.")
            return
        
        return wrapper
    return decorator


def typing_indicator(func: Callable) -> Callable:
    """
    Decorator to show typing indicator during command execution.
    
    Args:
        func: The command function to wrap
        
    Returns:
        Callable: The wrapped function
    """
    @functools.wraps(func)
    async def wrapper(self, ctx: commands.Context, *args, **kwargs):
        async with ctx.typing():
            return await func(self, ctx, *args, **kwargs)
    return wrapper


def handle_errors(
    send_error_message: bool = True,
    log_errors: bool = True,
    error_message: str = "An error occurred while processing your command."
) -> Callable:
    """
    Decorator to handle command errors.
    
    Args:
        send_error_message: Whether to send error message to user
        log_errors: Whether to log errors
        error_message: Custom error message
        
    Returns:
        Callable: The decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            try:
                return await func(self, ctx, *args, **kwargs)
            except commands.CommandError:
                # Let command errors propagate
                raise
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                
                if send_error_message:
                    async with ctx.typing():
                        await ctx.send(error_message)
                
                # Don't re-raise to prevent bot from showing default error
                return None
        
        return wrapper
    return decorator


def ensure_database(func: Callable) -> Callable:
    """
    Decorator to ensure database is available for the command.
    
    Args:
        func: The command function to wrap
        
    Returns:
        Callable: The wrapped function
    """
    @functools.wraps(func)
    async def wrapper(self, ctx: commands.Context, *args, **kwargs):
        if not hasattr(self, 'db_service') or self.db_service is None:
            async with ctx.typing():
                await ctx.send("Database functionality is not available at the moment.")
            logger.error(f"Database service not available for {self.__class__.__name__}")
            return
        return await func(self, ctx, *args, **kwargs)
    return wrapper


def feature_required(feature_flag: str) -> Callable:
    """
    Decorator to ensure a feature is enabled before running command.
    
    Args:
        feature_flag: The feature flag to check
        
    Returns:
        Callable: The decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            if not self.is_feature_enabled(feature_flag, ctx.guild.id if ctx.guild else None):
                async with ctx.typing():
                    await ctx.send("This feature is not currently enabled.")
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator


def owner_only(func: Callable) -> Callable:
    """
    Decorator to restrict command to bot owner only.
    
    Args:
        func: The command function to wrap
        
    Returns:
        Callable: The wrapped function
    """
    @functools.wraps(func)
    async def wrapper(self, ctx: commands.Context, *args, **kwargs):
        # Get owner ID from config
        owner_id = None
        if hasattr(self, 'config') and self.config:
            owner_id = getattr(self.config, 'owner_id', None)
        
        if not owner_id:
            async with ctx.typing():
                await ctx.send("Owner ID is not configured.")
            logger.error("Owner ID not configured in bot settings")
            return
        
        if ctx.author.id != owner_id:
            async with ctx.typing():
                await ctx.send("This command can only be used by the bot owner.")
            return
        
        return await func(self, ctx, *args, **kwargs)
    return wrapper