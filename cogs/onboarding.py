"""Handles server onboarding and welcome messages."""

import discord
from discord.ext import commands
from typing import List, Dict, Optional, Any, ClassVar
import logging
import datetime

from cogs.base_cog import BaseCog
from cogs.utils.embeds import create_base_embed, create_success_embed, create_error_embed
from cogs.utils.decorators import require_context
from cogs.utils.permissions import check_admin_permissions


class WelcomeView(discord.ui.View):
    """View for the welcome message with quick access buttons."""
    
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)  # Persistent buttons
        self.bot = bot
    
    @discord.ui.button(label="Start a Quiz", style=discord.ButtonStyle.primary, custom_id="welcome:quiz")
    async def start_quiz(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Quick access to starting a quiz."""
        async with interaction.channel.typing():
            await interaction.response.send_message(
                "To start a quiz, use the `/quiz start` command. "
                "You'll need to specify a topic and optionally set the difficulty and question count.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Setup Guide", style=discord.ButtonStyle.secondary, custom_id="welcome:guide")
    async def setup_guide(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Show setup guide for server admins."""
        async with interaction.channel.typing():
            await interaction.response.send_message(
                "**Setup Guide for Administrators**\n\n"
                "1. Make sure the bot has the required permissions\n"
                "2. Use `/admin setup` to configure server-specific settings\n"
                "3. Use `/admin permissions` to set up role permissions\n\n"
                "For more detailed instructions, check out our documentation.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Command List", style=discord.ButtonStyle.secondary, custom_id="welcome:commands")
    async def command_list(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Show the list of available commands."""
        async with interaction.channel.typing():
            await interaction.response.send_message(
                "Use `/help` to see the full list of commands. "
                "Here are some of the most commonly used ones:\n\n"
                "• `/quiz start` - Start a new quiz\n"
                "• `/trivia start` - Start a group trivia game\n"
                "• `/faq` - Show frequently asked questions\n"
                "• `/preferences` - Set your personal preferences",
                ephemeral=True
            )


class OnboardingCog(BaseCog):
    """Handles server onboarding and welcome messages."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the onboarding cog."""
        super().__init__(bot, name="Onboarding")
    
    def _create_welcome_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the welcome embed for a new server."""
        embed = create_base_embed(
            title="👋 Thanks for adding Educational Quiz Bot!",
            description=(
                f"Hello, {guild.name}! I'm an educational bot that helps you learn through "
                "interactive quizzes and trivia games. Let's get started!"
            ),
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="📚 Key Features",
            value=(
                "• AI-powered educational quizzes\n"
                "• Interactive group trivia games\n"
                "• Multiple difficulty levels\n"
                "• Custom quiz creation\n"
                "• Server leaderboards and stats"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🚀 Getting Started",
            value=(
                "1. Use `/quiz start` to start your first quiz\n"
                "2. Use `/help` to see all available commands\n"
                "3. Server admins can use `/admin setup` for configuration"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Need Help?",
            value="Click the buttons below for quick access to common features and guides.",
            inline=False
        )
        
        embed.set_footer(text=f"Bot Version: {getattr(self.bot, 'VERSION', '1.0.0')}")
        
        return embed
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Send a welcome message when the bot joins a new server."""
        self.logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

        target_channel: Optional[discord.TextChannel] = None

        # 1. Try to find a channel named 'general'
        for channel in guild.text_channels:
            if channel.name == "general":
                if channel.permissions_for(guild.me).send_messages and channel.permissions_for(guild.me).embed_links:
                    target_channel = channel
                    self.logger.info(f"Found #general channel in {guild.name}: {channel.name} (ID: {channel.id})")
                    break
                else:
                    self.logger.warning(f"Found #general channel in {guild.name} but missing send/embed permissions.")
        
        # 2. If 'general' not found or not usable, find the first available text channel
        if not target_channel:
            self.logger.info(f"#general channel not found or not usable in {guild.name}. Searching for alternative.")
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages and channel.permissions_for(guild.me).embed_links:
                    target_channel = channel
                    self.logger.info(f"Found alternative channel in {guild.name}: {channel.name} (ID: {channel.id})")
                    break
            if not target_channel:
                 self.logger.warning(f"No suitable text channel found in {guild.name} to send welcome message.")

        # 3. Send the message if a channel was found
        if target_channel:
            try:
                welcome_embed = self._create_welcome_embed(guild)
                async with target_channel.typing():
                    await target_channel.send(embed=welcome_embed, view=WelcomeView(self.bot))
                
                # Record onboarding status in database
                if self.db_service:
                    await self.db_service.record_onboarding(guild.id, target_channel.id)
                
                self.logger.info(f"Sent welcome message to {guild.name} in channel {target_channel.name}")
            except discord.errors.Forbidden:
                self.logger.error(f"Forbidden to send welcome message to {target_channel.name} in {guild.name}. Check bot permissions.")
            except Exception as e:
                self.logger.error(f"Error sending welcome message to {guild.name} in {target_channel.name}: {e}", exc_info=True)
        else:
            self.logger.warning(f"Could not send welcome message to {guild.name} as no suitable channel was found.")
    
    @commands.hybrid_command(name="welcome", description="Show the welcome message again.")
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx: commands.Context) -> None:
        """Manually send the welcome message (admin only)."""
        if not await check_admin_permissions(ctx):
            error_embed = create_error_embed(
                description="You need Manage Server permission to use this command."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed, ephemeral=True)
            return
            
        welcome_embed = self._create_welcome_embed(ctx.guild)
        async with ctx.typing():
            await ctx.send(embed=welcome_embed, view=WelcomeView(self.bot))


async def setup(bot: commands.Bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(OnboardingCog(bot))


async def setup_with_context(bot: commands.Bot, context: Any) -> commands.Cog:
    """Setup function that uses the context pattern."""
    cog = OnboardingCog(bot)
    cog.set_context(context)
    await bot.add_cog(cog)
    return cog