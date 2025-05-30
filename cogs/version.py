"""Version management commands for the bot."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, Literal

from cogs.base_cog import BaseCog
from cogs.utils.decorators import owner_only
from services.version_service import VersionService
from utils.ui import create_embed

logger = logging.getLogger("bot.version")


class VersionCog(BaseCog, name="Version"):
    """Version management commands."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the version cog."""
        super().__init__(bot, "Version")
        self.version_service: Optional[VersionService] = None
    
    def set_context(self, context) -> None:
        """Set the bot context."""
        super().set_context(context)
        
        # Initialize version service
        self.version_service = context.version_service
    
    async def cog_load(self) -> None:
        """Initialize the cog when it's loaded."""
        await super().cog_load()
        
        # Ensure version tables are initialized
        if self.version_service:
            await self.version_service.initialize()
    
    @commands.hybrid_group(name="version", description="Bot version management commands")
    async def version_group(self, ctx: commands.Context):
        """Version management group command."""
        if ctx.invoked_subcommand is None:
            # Show current version when just /version is used
            await self.show_current_version(ctx)
    
    @version_group.command(name="current", description="Show the current bot version")
    async def version_current(self, ctx: commands.Context):
        """Show the current bot version."""
        await self.show_current_version(ctx)
    
    async def show_current_version(self, ctx: commands.Context):
        """Helper method to show current version."""
        if not self.version_service:
            async with ctx.typing():
                await ctx.send("❌ Version service not initialized.")
            return
        
        version_data = await self.version_service.get_current_version()
        
        if not version_data:
            embed = create_embed(
                title="📦 Bot Version",
                description="No version information available.",
                color=discord.Color.red()
            )
        else:
            embed = create_embed(
                title=f"📦 Bot Version {version_data['version']}",
                description=version_data['description'],
                color=discord.Color.blue()
            )
            
            # Format release date
            release_date = version_data.get('release_date')
            if release_date:
                date_str = release_date.strftime("%Y-%m-%d %H:%M UTC")
                embed.add_field(name="Released", value=date_str, inline=True)
            
            # Add author if available
            if version_data.get('author_id'):
                try:
                    author = await self.bot.fetch_user(version_data['author_id'])
                    embed.add_field(name="Author", value=author.mention, inline=True)
                except:
                    pass
            
            embed.set_footer(text="Use /version info <version> for detailed information")
        
        async with ctx.typing():
            await ctx.send(embed=embed)
    
    @version_group.command(name="info", description="Get detailed information about a specific version")
    @app_commands.describe(version="The version to get information about (e.g., 1.0.0)")
    async def version_info(self, ctx: commands.Context, version: str):
        """Get detailed information about a specific version."""
        if not self.version_service:
            async with ctx.typing():
                await ctx.send("❌ Version service not initialized.")
            return
        
        # Get version information
        version_data = await self.version_service.get_version_info(version)
        
        if not version_data:
            async with ctx.typing():
                await ctx.send(f"❌ Version {version} not found.")
            return
        
        # Create embed
        embed = create_embed(
            title=f"📦 Version {version_data['version']} Details",
            description=version_data['description'],
            color=discord.Color.green() if version_data.get('is_current') else discord.Color.blue()
        )
        
        # Add release date
        release_date = version_data.get('release_date')
        if release_date:
            date_str = release_date.strftime("%Y-%m-%d %H:%M UTC")
            embed.add_field(name="Released", value=date_str, inline=True)
        
        # Add current status
        if version_data.get('is_current'):
            embed.add_field(name="Status", value="✅ Current Version", inline=True)
        
        # Add author if available
        if version_data.get('author_id'):
            try:
                author = await self.bot.fetch_user(version_data['author_id'])
                embed.add_field(name="Author", value=author.mention, inline=True)
            except:
                pass
        
        # Add changelog if available
        changelog = version_data.get('changelog', [])
        if changelog:
            # Group by change type
            grouped = {}
            for entry in changelog:
                change_type = entry['change_type']
                if change_type not in grouped:
                    grouped[change_type] = []
                grouped[change_type].append(entry['description'])
            
            # Type emojis
            type_emojis = {
                'feature': '✨',
                'fix': '🐛',
                'improvement': '🔧',
                'breaking': '⚠️'
            }
            
            # Add each change type as a field
            for change_type, changes in grouped.items():
                emoji = type_emojis.get(change_type, '•')
                type_name = f"{emoji} {change_type.capitalize()}"
                
                # Format changes
                change_text = '\n'.join(f"• {change}" for change in changes[:1024])  # Discord field limit
                
                # Truncate if too long
                if len(change_text) > 1024:
                    change_text = change_text[:1021] + "..."
                
                embed.add_field(name=type_name, value=change_text, inline=False)
        
        async with ctx.typing():
            await ctx.send(embed=embed)
    
    @version_group.command(name="list", description="List all available versions")
    @app_commands.describe(limit="Maximum number of versions to show (default: 10)")
    async def version_list(self, ctx: commands.Context, limit: int = 10):
        """List all available versions."""
        if not self.version_service:
            async with ctx.typing():
                await ctx.send("❌ Version service not initialized.")
            return
        
        # Clamp limit
        limit = max(1, min(limit, 25))
        
        # Get versions
        versions = await self.version_service.list_versions(limit)
        
        if not versions:
            async with ctx.typing():
                await ctx.send("No versions found.")
            return
        
        # Create embed
        embed = create_embed(
            title="📦 Bot Versions",
            description=f"Showing the latest {len(versions)} versions",
            color=discord.Color.blue()
        )
        
        # Add version list
        for version in versions:
            version_str = version['version']
            if version.get('is_current'):
                version_str += " (Current)"
            
            # Truncate description if needed
            description = version['description']
            if len(description) > 100:
                description = description[:97] + "..."
            
            # Format date
            release_date = version.get('release_date')
            if release_date:
                date_str = release_date.strftime("%Y-%m-%d")
            else:
                date_str = "Unknown"
            
            embed.add_field(
                name=version_str,
                value=f"{description}\nReleased: {date_str}",
                inline=False
            )
        
        embed.set_footer(text="Use /version info <version> for detailed information")
        async with ctx.typing():
            await ctx.send(embed=embed)
    
    @version_group.command(name="change", description="Change or create a new version (Owner Only)")
    @app_commands.describe(
        version="The version string (e.g., 1.1.0)",
        description="Description of the version (supports \\n for new lines)",
        set_current="Whether to set this as the current version"
    )
    @owner_only
    async def version_change(
        self, 
        ctx: commands.Context, 
        version: str,
        description: str,
        set_current: bool = True
    ):
        """Change or create a new version."""
        if not self.version_service:
            async with ctx.typing():
                await ctx.send("❌ Version service not initialized.")
            return
        
        # Process description to handle \n
        description = description.replace('\\n', '\n')
        
        # Check if version already exists
        existing = await self.version_service.get_version_info(version)
        
        if existing:
            # Update existing version
            success = await self.version_service.update_version(
                version=version,
                description=description,
                set_current=set_current
            )
            
            if success:
                embed = create_embed(
                    title="✅ Version Updated",
                    description=f"Version {version} has been updated.",
                    color=discord.Color.green()
                )
            else:
                embed = create_embed(
                    title="❌ Update Failed",
                    description=f"Failed to update version {version}.",
                    color=discord.Color.red()
                )
        else:
            # Create new version
            success = await self.version_service.create_version(
                version=version,
                description=description,
                author_id=ctx.author.id,
                set_current=set_current
            )
            
            if success:
                embed = create_embed(
                    title="✅ Version Created",
                    description=f"Version {version} has been created.",
                    color=discord.Color.green()
                )
            else:
                embed = create_embed(
                    title="❌ Creation Failed",
                    description=f"Failed to create version {version}.",
                    color=discord.Color.red()
                )
        
        # Add version details to embed
        if success:
            embed.add_field(name="Version", value=version, inline=True)
            embed.add_field(name="Current", value="✅" if set_current else "❌", inline=True)
            embed.add_field(name="Description", value=description[:1024], inline=False)
        
        async with ctx.typing():
            await ctx.send(embed=embed)
    
    @version_group.command(name="changelog", description="Add a changelog entry to a version (Owner Only)")
    @owner_only
    @app_commands.describe(
        version="The version to add the changelog to",
        change_type="Type of change",
        description="Description of the change"
    )
    async def version_changelog(
        self,
        ctx: commands.Context,
        version: str,
        change_type: Literal["feature", "fix", "improvement", "breaking"],
        description: str
    ):
        """Add a changelog entry to a version."""
        if not self.version_service:
            async with ctx.typing():
                await ctx.send("❌ Version service not initialized.")
            return
        
        # Add changelog entry
        success = await self.version_service.add_changelog_entry(
            version=version,
            change_type=change_type,
            description=description
        )
        
        if success:
            # Type emojis
            type_emojis = {
                'feature': '✨',
                'fix': '🐛',
                'improvement': '🔧',
                'breaking': '⚠️'
            }
            
            emoji = type_emojis.get(change_type, '•')
            
            embed = create_embed(
                title="✅ Changelog Entry Added",
                description=f"Added {emoji} {change_type} entry to version {version}",
                color=discord.Color.green()
            )
            embed.add_field(name="Change", value=description, inline=False)
        else:
            embed = create_embed(
                title="❌ Failed to Add Changelog",
                description=f"Could not add changelog entry to version {version}",
                color=discord.Color.red()
            )
        
        async with ctx.typing():
            await ctx.send(embed=embed)
    
    @version_group.command(name="set", description="Set a specific version as current (Owner Only)")
    @app_commands.describe(version="The version to set as current")
    @owner_only
    async def version_set(self, ctx: commands.Context, version: str):
        """Set a specific version as the current version."""
        if not self.version_service:
            async with ctx.typing():
                await ctx.send("❌ Version service not initialized.")
            return
        
        # Update version to set as current
        success = await self.version_service.update_version(
            version=version,
            set_current=True
        )
        
        if success:
            embed = create_embed(
                title="✅ Current Version Updated",
                description=f"Version {version} is now the current version.",
                color=discord.Color.green()
            )
        else:
            embed = create_embed(
                title="❌ Update Failed",
                description=f"Failed to set version {version} as current.",
                color=discord.Color.red()
            )
        
        async with ctx.typing():
            await ctx.send(embed=embed)


async def setup_with_context(bot: commands.Bot, context):
    """Set up the version cog with context."""
    from cogs.base_cog import setup_with_context as base_setup
    return await base_setup(bot, context, VersionCog)


async def setup(bot: commands.Bot):
    """Default setup function for Discord.py."""
    cog = VersionCog(bot)
    await bot.add_cog(cog)
    return cog