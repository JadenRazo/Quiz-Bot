"""Guild-specific preference management commands."""

import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Optional, Any, Literal
import logging

from cogs.base_cog import BaseCog
from cogs.utils.embeds import create_base_embed, create_success_embed, create_error_embed


class GuildPreferencesCog(BaseCog):
    """Guild-specific preference management commands."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the guild preferences cog."""
        super().__init__(bot, name="GuildPreferences")
    
    @commands.hybrid_group(name="guild", description="Guild-specific settings and preferences")
    @commands.has_permissions(manage_guild=True)
    async def guild_group(self, ctx: commands.Context):
        """Guild preferences group command."""
        if ctx.invoked_subcommand is None:
            async with ctx.typing():
                await ctx.send_help(ctx.command)
    
    @guild_group.command(name="set_quiz_channel", description="Set the default quiz channel")
    @app_commands.describe(channel="The channel where quiz messages should be sent")
    async def set_quiz_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the default quiz channel for this guild."""
        if not self.db_service:
            async with ctx.typing():
                await ctx.send("❌ Database service is not available.")
            return
        
        try:
            # Save to guild settings
            await self.db_service.set_guild_setting(
                guild_id=ctx.guild.id,
                setting_key="quiz_channel_id",
                setting_value=str(channel.id)
            )
            
            embed = create_success_embed(
                title="Quiz Channel Set",
                description=f"Default quiz channel set to {channel.mention}"
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error setting quiz channel: {e}")
            async with ctx.typing():
                await ctx.send("❌ Failed to set quiz channel.")
    
    @guild_group.command(name="set_trivia_channel", description="Set the default trivia channel")
    @app_commands.describe(channel="The channel where trivia games should run")
    async def set_trivia_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the default trivia channel for this guild."""
        if not self.db_service:
            async with ctx.typing():
                await ctx.send("❌ Database service is not available.")
            return
        
        try:
            await self.db_service.set_guild_setting(
                guild_id=ctx.guild.id,
                setting_key="trivia_channel_id",
                setting_value=str(channel.id)
            )
            
            embed = create_success_embed(
                title="Trivia Channel Set",
                description=f"Default trivia channel set to {channel.mention}"
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error setting trivia channel: {e}")
            async with ctx.typing():
                await ctx.send("❌ Failed to set trivia channel.")
    
    @guild_group.command(name="set_admin_role", description="Set the quiz admin role")
    @app_commands.describe(role="The role that can manage quiz settings")
    async def set_admin_role(self, ctx: commands.Context, role: discord.Role):
        """Set the admin role for quiz management in this guild."""
        if not self.db_service:
            async with ctx.typing():
                await ctx.send("❌ Database service is not available.")
            return
        
        try:
            await self.db_service.set_guild_setting(
                guild_id=ctx.guild.id,
                setting_key="admin_role_id",
                setting_value=str(role.id)
            )
            
            embed = create_success_embed(
                title="Admin Role Set",
                description=f"Quiz admin role set to {role.mention}"
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error setting admin role: {e}")
            async with ctx.typing():
                await ctx.send("❌ Failed to set admin role.")
    
    @guild_group.command(name="settings", description="View current guild settings")
    async def view_settings(self, ctx: commands.Context):
        """View current guild settings."""
        if not self.db_service:
            async with ctx.typing():
                await ctx.send("❌ Database service is not available.")
            return
        
        try:
            settings = await self.db_service.get_guild_settings(ctx.guild.id)
            
            embed = create_base_embed(
                title=f"⚙️ Settings for {ctx.guild.name}",
                description="Current guild configuration"
            )
            
            embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
            
            # Channel settings
            channel_settings = []
            
            quiz_channel_id = settings.get("quiz_channel_id")
            if quiz_channel_id:
                channel = ctx.guild.get_channel(int(quiz_channel_id))
                channel_settings.append(f"**Quiz Channel:** {channel.mention if channel else 'Not set'}")
            else:
                channel_settings.append("**Quiz Channel:** Not set")
            
            trivia_channel_id = settings.get("trivia_channel_id")
            if trivia_channel_id:
                channel = ctx.guild.get_channel(int(trivia_channel_id))
                channel_settings.append(f"**Trivia Channel:** {channel.mention if channel else 'Not set'}")
            else:
                channel_settings.append("**Trivia Channel:** Not set")
            
            embed.add_field(
                name="📺 Channel Settings",
                value="\n".join(channel_settings) or "No channels configured",
                inline=False
            )
            
            # Role settings
            role_settings = []
            
            admin_role_id = settings.get("admin_role_id")
            if admin_role_id:
                role = ctx.guild.get_role(int(admin_role_id))
                role_settings.append(f"**Admin Role:** {role.mention if role else 'Not set'}")
            else:
                role_settings.append("**Admin Role:** Not set")
            
            embed.add_field(
                name="👥 Role Settings",
                value="\n".join(role_settings) or "No roles configured",
                inline=False
            )
            
            # Feature flags
            feature_flags = []
            if settings.get("feature_group_quiz", True):
                feature_flags.append("✅ Group Quizzes")
            if settings.get("feature_custom_quiz", True):
                feature_flags.append("✅ Custom Quizzes")
            if settings.get("feature_leaderboard", True):
                feature_flags.append("✅ Leaderboards")
            
            embed.add_field(
                name="🚀 Features",
                value="\n".join(feature_flags) or "Default features enabled",
                inline=False
            )
            
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error viewing settings: {e}")
            async with ctx.typing():
                await ctx.send("❌ Failed to retrieve guild settings.")
    
    @guild_group.command(name="enable_feature", description="Enable a bot feature")
    @app_commands.describe(feature="The feature to enable")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Group Quizzes", value="group_quiz"),
        app_commands.Choice(name="Custom Quizzes", value="custom_quiz"),
        app_commands.Choice(name="Leaderboards", value="leaderboard"),
        app_commands.Choice(name="Auto Quiz Mode", value="auto_quiz")
    ])
    async def enable_feature(self, ctx: commands.Context, feature: str):
        """Enable a specific feature for this guild."""
        if not self.db_service:
            async with ctx.typing():
                await ctx.send("❌ Database service is not available.")
            return
        
        try:
            await self.db_service.set_guild_setting(
                guild_id=ctx.guild.id,
                setting_key=f"feature_{feature}",
                setting_value="true"
            )
            
            feature_name = feature.replace("_", " ").title()
            embed = create_success_embed(
                title="Feature Enabled",
                description=f"✅ {feature_name} has been enabled for this guild."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error enabling feature: {e}")
            async with ctx.typing():
                await ctx.send("❌ Failed to enable feature.")
    
    @guild_group.command(name="disable_feature", description="Disable a bot feature")
    @app_commands.describe(feature="The feature to disable")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Group Quizzes", value="group_quiz"),
        app_commands.Choice(name="Custom Quizzes", value="custom_quiz"),
        app_commands.Choice(name="Leaderboards", value="leaderboard"),
        app_commands.Choice(name="Auto Quiz Mode", value="auto_quiz")
    ])
    async def disable_feature(self, ctx: commands.Context, feature: str):
        """Disable a specific feature for this guild."""
        if not self.db_service:
            async with ctx.typing():
                await ctx.send("❌ Database service is not available.")
            return
        
        try:
            await self.db_service.set_guild_setting(
                guild_id=ctx.guild.id,
                setting_key=f"feature_{feature}",
                setting_value="false"
            )
            
            feature_name = feature.replace("_", " ").title()
            embed = create_success_embed(
                title="Feature Disabled",
                description=f"❌ {feature_name} has been disabled for this guild."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error disabling feature: {e}")
            async with ctx.typing():
                await ctx.send("❌ Failed to disable feature.")


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    cog = GuildPreferencesCog(bot)
    await bot.add_cog(cog)
    return cog

async def setup_with_context(bot: commands.Bot, context):
    """Setup function with context."""
    cog = GuildPreferencesCog(bot)
    cog.set_context(context)
    await bot.add_cog(cog)
    return cog