"""Cog loader utility to handle dynamic cog loading with proper naming."""

import asyncio
import logging
from typing import Dict, List, Optional, Type
from discord.ext import commands

logger = logging.getLogger("bot.cog_loader")


class CogLoader:
    """Handles loading and managing cogs with proper naming and context."""
    
    # Map of file names to expected cog class names
    COG_NAME_MAP = {
        "admin": "AdminCog",
        "help": "HelpCog",
        "quiz": "QuizCog",
        "group_quiz": "GroupQuizCog",
        "faq": "FAQCog",
        "onboarding": "OnboardingCog",
        "stats": "StatsCog",
        "preferences": "PreferencesCog",
        "custom_quiz": "CustomQuizCog",
        "version": "VersionCog"
    }
    
    @classmethod
    def get_cog_class_name(cls, filename: str) -> str:
        """
        Get the expected cog class name from filename.
        
        Args:
            filename: The cog file name (without .py)
            
        Returns:
            str: The expected cog class name
        """
        return cls.COG_NAME_MAP.get(filename, f"{filename.title()}Cog")
    
    @classmethod
    def find_cog_instance(cls, bot: commands.Bot, filename: str) -> Optional[commands.Cog]:
        """
        Find a loaded cog instance by filename.
        
        Args:
            bot: The bot instance
            filename: The cog file name (without .py)
            
        Returns:
            Optional[commands.Cog]: The cog instance if found
        """
        # First try the direct name from the map
        expected_name = cls.get_cog_class_name(filename)
        cog = bot.get_cog(expected_name)
        
        if cog:
            return cog
        
        # Try the filename directly
        cog = bot.get_cog(filename.title())
        if cog:
            return cog
        
        # Try to find by checking all loaded cogs
        for name, cog_instance in bot.cogs.items():
            # Check if the cog's module matches what we're looking for
            if hasattr(cog_instance, "__module__"):
                module_name = cog_instance.__module__
                if f"cogs.{filename}" in module_name:
                    return cog_instance
        
        return None
    
    # Removed conflict detection code as we're using hybrid commands
    
    @classmethod
    async def load_cog_with_context(
        cls,
        bot: commands.Bot,
        module_name: str,
        context: Optional[object] = None
    ) -> bool:
        """
        Load a cog and set its context if available.
        
        Args:
            bot: The bot instance
            module_name: The full module name (e.g., "cogs.admin")
            context: The bot context to set
            
        Returns:
            bool: True if successfully loaded
        """
        try:
            # Load the extension
            await bot.load_extension(module_name)
            
            # Extract filename from module name
            filename = module_name.split('.')[-1]
            
            # Find the cog instance
            cog_instance = cls.find_cog_instance(bot, filename)
            
            if cog_instance and context and hasattr(cog_instance, "set_context"):
                # Set the context if the cog supports it
                set_context_method = getattr(cog_instance, "set_context")
                if asyncio.iscoroutinefunction(set_context_method):
                    await set_context_method(context)
                else:
                    set_context_method(context)
                
                logger.info(f"Successfully set context for {module_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load cog {module_name}: {e}", exc_info=True)
            return False
    
    @classmethod
    def get_all_cogs_to_load(cls) -> List[str]:
        """
        Get list of all cogs that should be loaded.
        
        Returns:
            List[str]: List of cog module names
        """
        return [f"cogs.{name}" for name in cls.COG_NAME_MAP.keys()]