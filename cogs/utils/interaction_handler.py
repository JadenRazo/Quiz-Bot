"""Enhanced interaction error handling utilities for discord.py 2.5.2."""

import discord
from discord import app_commands
from typing import Optional, Union, Callable, TypeVar, Any
import asyncio
import logging
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger("bot.interaction_handler")

T = TypeVar('T')


class InteractionHandler:
    """Provides robust error handling and recovery for Discord interactions."""
    
    @staticmethod
    async def safe_response(
        interaction: discord.Interaction,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        view: Optional[discord.ui.View] = None,
        ephemeral: bool = False,
        thinking: bool = False
    ) -> Optional[discord.Message]:
        """
        Safely respond to an interaction with automatic error recovery.
        
        Args:
            interaction: The Discord interaction to respond to
            content: Text content for the response
            embed: Embed to include in the response
            view: View with UI components
            ephemeral: Whether the response should be ephemeral
            thinking: Whether to defer with a thinking state
            
        Returns:
            The message that was sent, or None if all attempts failed
        """
        try:
            # If not responded yet, send initial response
            if not interaction.response.is_done():
                if thinking:
                    await interaction.response.defer(ephemeral=ephemeral, thinking=True)
                else:
                    await interaction.response.send_message(
                        content=content,
                        embed=embed,
                        view=view,
                        ephemeral=ephemeral
                    )
                # For deferred responses, we need to use followup
                if thinking:
                    return await interaction.followup.send(
                        content=content,
                        embed=embed,
                        view=view
                    )
                else:
                    # Get the original response for non-deferred messages
                    return await interaction.original_response()
                    
            # If already responded, use followup
            else:
                return await interaction.followup.send(
                    content=content,
                    embed=embed,
                    view=view,
                    ephemeral=ephemeral
                )
                
        except discord.errors.InteractionResponded:
            # Interaction already responded to, try editing original
            try:
                return await interaction.edit_original_response(
                    content=content,
                    embed=embed,
                    view=view
                )
            except discord.errors.HTTPException:
                # If edit fails, try followup
                try:
                    return await interaction.followup.send(
                        content=content,
                        embed=embed,
                        view=view,
                        ephemeral=ephemeral
                    )
                except Exception as e:
                    logger.error(f"All response attempts failed: {e}")
                    return None
                    
        except discord.errors.NotFound:
            # Interaction token expired, try to send to channel directly
            if interaction.channel:
                try:
                    async with interaction.channel.typing():
                        return await interaction.channel.send(
                            content=content,
                            embed=embed,
                            view=view
                        )
                except Exception as e:
                    logger.error(f"Failed to send to channel after token expiry: {e}")
                    return None
                    
        except Exception as e:
            logger.error(f"Unexpected error in safe_response: {e}")
            # Last resort: try to send to channel
            if interaction.channel:
                try:
                    error_embed = discord.Embed(
                        title="⚠️ Interaction Error",
                        description="An error occurred while processing this interaction.",
                        color=discord.Color.yellow(),
                        timestamp=datetime.utcnow()
                    )
                    async with interaction.channel.typing():
                        return await interaction.channel.send(embed=error_embed)
                except:
                    return None
                    
    @staticmethod
    async def safe_defer(
        interaction: discord.Interaction,
        ephemeral: bool = False,
        thinking: bool = True
    ) -> bool:
        """
        Safely defer an interaction with error handling.
        
        Args:
            interaction: The interaction to defer
            ephemeral: Whether the eventual response should be ephemeral
            thinking: Whether to show thinking state
            
        Returns:
            True if defer was successful, False otherwise
        """
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=ephemeral, thinking=thinking)
                return True
            return True  # Already deferred/responded
        except discord.errors.InteractionResponded:
            return True  # Already responded
        except Exception as e:
            logger.error(f"Failed to defer interaction: {e}")
            return False
            
    @staticmethod
    async def safe_edit(
        interaction: discord.Interaction,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        view: Optional[discord.ui.View] = None
    ) -> bool:
        """
        Safely edit an interaction response.
        
        Returns:
            True if edit was successful, False otherwise
        """
        try:
            await interaction.edit_original_response(
                content=content,
                embed=embed,
                view=view
            )
            return True
        except discord.errors.NotFound:
            # Token expired, try sending new message
            if interaction.channel:
                try:
                    async with interaction.channel.typing():
                        await interaction.channel.send(
                            content=content,
                            embed=embed,
                            view=view
                        )
                    return True
                except:
                    return False
        except Exception as e:
            logger.error(f"Failed to edit interaction: {e}")
            return False


def interaction_error_handler(
    error_message: str = "An error occurred while processing your request.",
    log_errors: bool = True,
    ephemeral_errors: bool = True
):
    """
    Decorator for handling interaction errors gracefully.
    
    Args:
        error_message: Default error message to show users
        log_errors: Whether to log errors
        ephemeral_errors: Whether error messages should be ephemeral
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            try:
                return await func(self, interaction, *args, **kwargs)
            except app_commands.CommandOnCooldown as e:
                cooldown_embed = discord.Embed(
                    title="⏱️ Command on Cooldown",
                    description=f"Please wait {e.retry_after:.1f} seconds before using this command again.",
                    color=discord.Color.orange()
                )
                await InteractionHandler.safe_response(
                    interaction, 
                    embed=cooldown_embed, 
                    ephemeral=True
                )
            except app_commands.CheckFailure as e:
                permission_embed = discord.Embed(
                    title="🚫 Permission Denied",
                    description="You don't have permission to use this command.",
                    color=discord.Color.red()
                )
                await InteractionHandler.safe_response(
                    interaction, 
                    embed=permission_embed, 
                    ephemeral=True
                )
            except discord.errors.Forbidden:
                forbidden_embed = discord.Embed(
                    title="❌ Missing Permissions",
                    description="I don't have the required permissions to perform this action.",
                    color=discord.Color.red()
                )
                await InteractionHandler.safe_response(
                    interaction, 
                    embed=forbidden_embed, 
                    ephemeral=True
                )
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                    
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=error_message,
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                error_embed.set_footer(text="If this persists, please contact support.")
                
                await InteractionHandler.safe_response(
                    interaction,
                    embed=error_embed,
                    ephemeral=ephemeral_errors
                )
        return wrapper
    return decorator


class InteractionContext:
    """
    Context manager for handling long-running interactions with automatic defer.
    
    Usage:
        async with InteractionContext(interaction) as ctx:
            # Long operation here
            await ctx.send(content="Done!", embed=result_embed)
    """
    
    def __init__(
        self,
        interaction: discord.Interaction,
        thinking: bool = True,
        ephemeral: bool = False,
        defer_after: float = 2.0
    ):
        self.interaction = interaction
        self.thinking = thinking
        self.ephemeral = ephemeral
        self.defer_after = defer_after
        self._defer_task: Optional[asyncio.Task] = None
        self._deferred = False
        
    async def __aenter__(self):
        # Start defer timer
        self._defer_task = asyncio.create_task(self._auto_defer())
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cancel defer task if still running
        if self._defer_task and not self._defer_task.done():
            self._defer_task.cancel()
            
    async def _auto_defer(self):
        """Automatically defer if operation takes too long."""
        try:
            await asyncio.sleep(self.defer_after)
            if not self.interaction.response.is_done():
                await self.interaction.response.defer(
                    ephemeral=self.ephemeral,
                    thinking=self.thinking
                )
                self._deferred = True
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in auto-defer: {e}")
            
    async def send(self, **kwargs) -> Optional[discord.Message]:
        """Send a response using the appropriate method."""
        # Cancel defer task
        if self._defer_task and not self._defer_task.done():
            self._defer_task.cancel()
            
        # Use appropriate send method
        if self._deferred or self.interaction.response.is_done():
            return await self.interaction.followup.send(**kwargs)
        else:
            await self.interaction.response.send_message(**kwargs)
            return await self.interaction.original_response()


def with_interaction_context(thinking: bool = True, ephemeral: bool = False):
    """
    Decorator that provides InteractionContext to the decorated function.
    
    Usage:
        @with_interaction_context(thinking=True)
        async def my_command(self, interaction: discord.Interaction, ctx: InteractionContext):
            # Long operation
            await ctx.send(content="Done!")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            async with InteractionContext(interaction, thinking=thinking, ephemeral=ephemeral) as ctx:
                return await func(self, interaction, *args, ctx=ctx, **kwargs)
        return wrapper
    return decorator