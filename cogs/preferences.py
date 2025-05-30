"""User preference management commands."""

import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Optional, Any, Literal, ClassVar
import logging
import datetime

from cogs.base_cog import BaseCog
from cogs.utils.embeds import create_base_embed, create_success_embed, create_error_embed
from cogs.utils.decorators import require_context
from cogs.utils.validation import validate_integer_range


class PreferencesCog(BaseCog):
    """User preference management commands."""
    
    # Class constants
    THEMES: ClassVar[List[str]] = ["default", "dark", "light", "colorful", "minimal"]
    
    def __init__(self, bot: commands.Bot):
        """Initialize the preferences cog."""
        super().__init__(bot, name="Preferences")
    
    def _create_preferences_embed(self, user: discord.Member, preferences: Dict[str, Any]) -> discord.Embed:
        """Create an embed showing user preferences."""
        embed = create_base_embed(
            title=f"⚙️ Preferences for {user.display_name}",
            description="Your personal quiz and bot preferences.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Quiz Preferences
        quiz_prefs = [
            f"**Difficulty:** {preferences.get('difficulty', 'medium').capitalize()}",
            f"**Question Count:** {preferences.get('question_count', 5)}",
            f"**Question Type:** {preferences.get('question_type', 'multiple_choice').replace('_', ' ').capitalize()}"
        ]
        
        embed.add_field(
            name="🎮 Quiz Preferences",
            value="\n".join(quiz_prefs),
            inline=True
        )
        
        # UI Preferences
        ui_prefs = [
            f"**Theme:** {preferences.get('theme', 'default').capitalize()}",
        ]
        
        embed.add_field(
            name="🎨 UI Preferences",
            value="\n".join(ui_prefs),
            inline=True
        )
        
        embed.add_field(
            name="ℹ️ About Preferences",
            value=(
                "Your preferences are applied automatically when you start a quiz.\n"
                "Use `/preferences set` to change your preferences."
            ),
            inline=False
        )
        
        return embed
    
    @commands.hybrid_group(name="preferences", description="Manage your personal quiz preferences.")
    @require_context
    async def preferences_group(self, ctx: commands.Context):
        """Commands for managing personal preferences."""
        if ctx.invoked_subcommand is None:
            # Show current preferences
            try:
                # Get user's preferences
                preferences = await self.db_service.get_user_preferences(ctx.author.id)
                
                # Create and send preferences embed
                embed = self._create_preferences_embed(ctx.author, preferences)
                async with ctx.typing():
                    await ctx.send(embed=embed)
                
            except Exception as e:
                self.logger.error(f"Error fetching preferences for {ctx.author.id}: {e}")
                error_embed = create_error_embed(
                    description="Error fetching your preferences. Please try again later."
                )
                async with ctx.typing():
                    await ctx.send(embed=error_embed, ephemeral=True)
    
    @preferences_group.command(name="set", description="Set your quiz preferences.")
    @app_commands.describe(
        difficulty="Your preferred difficulty level",
        question_count="Preferred number of questions per quiz",
        question_type="Preferred question type",
        theme="UI theme preference"
    )
    @require_context
    async def set_preferences(self, ctx: commands.Context,
                            difficulty: Optional[Literal["easy", "medium", "hard"]] = None,
                            question_count: Optional[int] = None,
                            question_type: Optional[Literal["multiple_choice", "true_false", "short_answer"]] = None,
                            theme: Optional[Literal["default", "dark", "light", "colorful", "minimal"]] = None):
        """Set your personal quiz preferences."""
        try:
            # Validate question count
            if question_count is not None:
                validation_error = validate_integer_range(question_count, min_value=1, max_value=50, 
                                                         field_name="Question count")
                if validation_error:
                    error_embed = create_error_embed(description=validation_error)
                    async with ctx.typing():
                        await ctx.send(embed=error_embed, ephemeral=True)
                    return
            
            # Save preferences to database
            success = await self.db_service.set_user_preferences(
                user_id=ctx.author.id,
                difficulty=difficulty,
                question_count=question_count,
                question_type=question_type,
                theme=theme
            )
            
            if success:
                # Get updated preferences
                preferences = await self.db_service.get_user_preferences(ctx.author.id)
                
                # Create confirmation embed
                embed = create_success_embed(
                    title="✅ Preferences Updated",
                    description="Your preferences have been successfully updated!"
                )
                preferences_embed = self._create_preferences_embed(ctx.author, preferences)
                async with ctx.typing():
                    await ctx.send(embeds=[embed, preferences_embed])
            else:
                error_embed = create_error_embed(
                    description="Failed to update preferences. Please try again later."
                )
                async with ctx.typing():
                    await ctx.send(embed=error_embed, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error setting preferences for {ctx.author.id}: {e}")
            error_embed = create_error_embed(
                description="Error updating your preferences. Please try again later."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed, ephemeral=True)
    
    @preferences_group.command(name="reset", description="Reset your preferences to default values.")
    @require_context
    async def reset_preferences(self, ctx: commands.Context):
        """Reset your preferences to default values."""
        try:
            # Set default preferences
            success = await self.db_service.set_user_preferences(
                user_id=ctx.author.id,
                difficulty="medium",
                question_count=5,
                question_type="multiple_choice",
                theme="default"
            )
            
            if success:
                # Get updated preferences
                preferences = await self.db_service.get_user_preferences(ctx.author.id)
                
                # Create confirmation embed
                embed = create_success_embed(
                    title="✅ Preferences Reset",
                    description="Your preferences have been reset to default values!"
                )
                preferences_embed = self._create_preferences_embed(ctx.author, preferences)
                async with ctx.typing():
                    await ctx.send(embeds=[embed, preferences_embed])
            else:
                error_embed = create_error_embed(
                    description="Failed to reset preferences. Please try again later."
                )
                async with ctx.typing():
                    await ctx.send(embed=error_embed, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error resetting preferences for {ctx.author.id}: {e}")
            error_embed = create_error_embed(
                description="Error resetting your preferences. Please try again later."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed, ephemeral=True)
    
    @set_preferences.autocomplete("theme")
    async def theme_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Provide autocomplete for theme options."""
        return [
            app_commands.Choice(name=theme.capitalize(), value=theme)
            for theme in self.THEMES
            if current.lower() in theme.lower()
        ]


async def setup(bot: commands.Bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(PreferencesCog(bot))


async def setup_with_context(bot: commands.Bot, context: Any) -> commands.Cog:
    """Setup function that uses the context pattern."""
    cog = PreferencesCog(bot)
    cog.set_context(context)
    await bot.add_cog(cog)
    return cog