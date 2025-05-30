"""Base cog class that all other cogs should inherit from."""

import logging
from typing import Optional
from discord.ext import commands
from utils.context import BotContext


class BaseCog(commands.Cog):
    """
    Base cog class that provides common functionality for all cogs.
    
    This class implements:
    - Standardized initialization
    - Context management
    - Logging setup
    - Common error handling
    """
    
    def __init__(self, bot: commands.Bot, name: str = None):
        """
        Initialize the base cog.
        
        Args:
            bot: The Discord bot instance
            name: Optional name for the cog (defaults to class name)
        """
        self.bot = bot
        self.context: Optional[BotContext] = None
        self.config = None
        self.db_service = None
        self.message_router = None
        self.cog_name = name or self.__class__.__name__
        
        # Set up logging for this cog
        self.logger = logging.getLogger(f"bot.{self.cog_name.lower()}")
        self.logger.info(f"{self.cog_name} initialized")
    
    def set_context(self, context: BotContext) -> None:
        """
        Set the bot context and extract commonly used services.
        
        Args:
            context: The bot context containing shared resources
        """
        self.context = context
        self.config = context.config
        self.db_service = context.db_service
        self.message_router = context.message_router
        self.logger.info(f"Context set for {self.cog_name}")
    
    async def cog_load(self) -> None:
        """Called when the cog is loaded. Override for custom behavior."""
        self.logger.debug(f"{self.cog_name} loaded")
    
    async def cog_unload(self) -> None:
        """Called when the cog is unloaded. Override for cleanup."""
        self.logger.debug(f"{self.cog_name} unloaded")
    
    async def cog_check(self, ctx: commands.Context) -> bool:
        """
        Global check for all commands in this cog.
        Override to add custom checks.
        
        Args:
            ctx: The command context
            
        Returns:
            bool: True if the command can run, False otherwise
        """
        return True
    
    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """
        Error handler for commands in this cog.
        Override to customize error handling.
        
        Args:
            ctx: The command context
            error: The exception that was raised
        """
        self.logger.error(f"Error in {ctx.command}: {error}", exc_info=True)
        
        # Let it propagate to the bot's error handler
        # unless you want to handle it specifically here
        ctx.error_handled = False
    
    def is_feature_enabled(self, feature: str, guild_id: Optional[int] = None) -> bool:
        """
        Convenience method to check if a feature is enabled.
        
        Args:
            feature: The feature flag to check
            guild_id: Optional guild ID for guild-specific overrides
            
        Returns:
            bool: True if feature is enabled
        """
        if self.context:
            return self.context.is_feature_enabled(feature, guild_id)
        return False
    
    @property
    def feature_manager(self):
        """Quick access to the feature manager."""
        return self.context.feature_manager if self.context else None


async def setup_with_context(bot: commands.Bot, context: BotContext, cog_class: type[BaseCog]) -> BaseCog:
    """
    Standard setup function for cogs using the context.
    
    Args:
        bot: The Discord bot instance
        context: The bot context
        cog_class: The cog class to instantiate
        
    Returns:
        The initialized cog instance
    """
    cog = cog_class(bot)
    cog.set_context(context)
    await bot.add_cog(cog)
    return cog