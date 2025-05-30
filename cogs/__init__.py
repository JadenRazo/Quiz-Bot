"""Cogs module for the Educational Discord Bot."""

from .base_cog import BaseCog, setup_with_context

# Define available cogs - don't import them directly to avoid circular imports
__all__ = [
    "base_cog",
    "admin", 
    "help", 
    "quiz",
    "group_quiz", 
    "faq", 
    "onboarding", 
    "stats", 
    "preferences", 
    "custom_quiz",
    "models",
    "utils"
]