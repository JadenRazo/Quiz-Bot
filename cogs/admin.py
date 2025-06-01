"""Administrative commands for bot management."""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import sys
from typing import Optional, Union, List
import logging

from discord import Embed, Color, Member, User
from cogs.base_cog import BaseCog
from cogs.utils import (
    check_admin_permissions,
    create_success_embed,
    create_error_embed,
    create_base_embed,
    admin_only,
    require_context,
    in_guild_only,
    owner_only
)
from utils.feature_flags import FeatureFlag, feature_manager

logger = logging.getLogger("bot.admin")


class AdminCog(BaseCog, name="Admin"):
    """Administrative commands for bot management."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the admin cog."""
        super().__init__(bot, "Admin")
        
        # Admin-specific attributes
        self._admin_roles: List[str] = []
        self._admin_users: List[int] = []
    
    def set_context(self, context) -> None:
        """Set the bot context and extract admin configuration."""
        super().set_context(context)
        
        # Extract admin configuration
        self._admin_roles = getattr(self.config, 'admin_roles', [])
        self._admin_users = getattr(self.config, 'admin_users', [])
        
        self.logger.info(f"Admin roles: {self._admin_roles}")
        self.logger.info(f"Admin users: {self._admin_users}")
    
    async def is_admin(self, user: Union[Member, User]) -> bool:
        """
        Check if a user has admin privileges.
        
        Args:
            user: The user to check
            
        Returns:
            bool: True if user is an admin
        """
        return check_admin_permissions(user, self._admin_users, self._admin_roles)
    
    async def cog_check(self, ctx: commands.Context) -> bool:
        """Check if the user can run admin commands."""
        if not ctx.guild:
            async with ctx.typing():
                await ctx.send("❌ Admin commands can only be used in servers.")
            return False
        
        if not await self.is_admin(ctx.author):
            async with ctx.typing():
                await ctx.send("❌ You don't have permission to use admin commands.")
            return False
        
        return True
    
    # === COMMAND SYNC ===
    @commands.command(name="sync")
    @require_context
    @in_guild_only
    @owner_only
    async def sync_command(self, ctx: commands.Context):
        """Sync commands with Discord and report how many were synced."""
        await ctx.message.add_reaction("🔄")
        
        try:
            # Sync global commands
            global_commands = await self.bot.tree.sync()
            self.logger.info(f"Synced {len(global_commands)} global commands")
            
            # Create success embed
            embed = create_success_embed(
                title="Commands Synced",
                description=f"Successfully synced {len(global_commands)} global commands."
            )
            
            # Add command details
            if global_commands:
                command_list = []
                for cmd in global_commands[:10]:  # Show first 10
                    command_list.append(f"• `/{cmd.name}`")
                
                if len(global_commands) > 10:
                    command_list.append(f"... and {len(global_commands) - 10} more")
                
                embed.add_field(
                    name="Commands",
                    value="\n".join(command_list),
                    inline=False
                )
            
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except discord.HTTPException as e:
            await ctx.message.add_reaction("❌")
            embed = create_error_embed(
                title="Sync Failed",
                description=f"Failed to sync commands: {str(e)}",
                error_details=str(e)
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
        except Exception as e:
            await ctx.message.add_reaction("❌")
            self.logger.error(f"Error syncing commands: {e}", exc_info=True)
            embed = create_error_embed(
                title="Sync Error",
                description="An unexpected error occurred while syncing commands."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
    
    # === BOT RELOAD ===
    @commands.command(name="reload")
    @require_context
    @in_guild_only
    @owner_only
    async def reload_cog(self, ctx: commands.Context, cog_name: str):
        """Reload a specific cog."""
        await ctx.message.add_reaction("🔄")
        
        try:
            # Convert cog name to module path
            module_name = f"cogs.{cog_name.lower()}"
            
            # Try to reload the extension
            try:
                await self.bot.reload_extension(module_name)
                await ctx.message.add_reaction("✅")
                embed = create_success_embed(
                    title="Cog Reloaded",
                    description=f"Successfully reloaded `{cog_name}` cog."
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                self.logger.info(f"Reloaded cog: {module_name}")
                
            except commands.ExtensionNotLoaded:
                # Try to load it if it wasn't loaded
                await self.bot.load_extension(module_name)
                await ctx.message.add_reaction("✅")
                embed = create_success_embed(
                    title="Cog Loaded",
                    description=f"Successfully loaded `{cog_name}` cog."
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                self.logger.info(f"Loaded cog: {module_name}")
                
        except commands.ExtensionNotFound:
            await ctx.message.add_reaction("❌")
            embed = create_error_embed(
                title="Cog Not Found",
                description=f"Could not find cog `{cog_name}`."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
        except Exception as e:
            await ctx.message.add_reaction("❌")
            self.logger.error(f"Error reloading cog {cog_name}: {e}", exc_info=True)
            embed = create_error_embed(
                title="Reload Error",
                description=f"Failed to reload `{cog_name}` cog.",
                error_details=str(e)
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
    
    # === FEATURE FLAGS ===
    @commands.command(name="feature_enable")
    @require_context
    @in_guild_only
    async def enable_feature(self, ctx: commands.Context, feature: str):
        """Enable a feature flag."""
        try:
            # Check if it's a valid feature
            try:
                feature_flag = FeatureFlag[feature.upper()]
            except KeyError:
                available_features = ", ".join([f.name for f in FeatureFlag])
                embed = create_error_embed(
                    title="Invalid Feature",
                    description=f"Unknown feature `{feature}`.\n\nAvailable features: {available_features}"
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                return
            
            # Enable for guild
            feature_manager.set_guild_override(
                guild_id=ctx.guild.id,
                feature=feature_flag,
                enabled=True
            )
            
            embed = create_success_embed(
                title="Feature Enabled",
                description=f"Enabled `{feature}` for this server."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
            self.logger.info(f"Enabled feature {feature} for guild {ctx.guild.id}")
            
        except Exception as e:
            self.logger.error(f"Error enabling feature: {e}", exc_info=True)
            embed = create_error_embed(
                title="Feature Error",
                description="Failed to enable feature.",
                error_details=str(e)
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
    
    @commands.command(name="feature_disable")
    @require_context
    @in_guild_only
    async def disable_feature(self, ctx: commands.Context, feature: str):
        """Disable a feature flag."""
        try:
            # Check if it's a valid feature
            try:
                feature_flag = FeatureFlag[feature.upper()]
            except KeyError:
                available_features = ", ".join([f.name for f in FeatureFlag])
                embed = create_error_embed(
                    title="Invalid Feature",
                    description=f"Unknown feature `{feature}`.\n\nAvailable features: {available_features}"
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                return
            
            # Disable for guild
            feature_manager.set_guild_override(
                guild_id=ctx.guild.id,
                feature=feature_flag,
                enabled=False
            )
            
            embed = create_success_embed(
                title="Feature Disabled",
                description=f"Disabled `{feature}` for this server."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
            self.logger.info(f"Disabled feature {feature} for guild {ctx.guild.id}")
            
        except Exception as e:
            self.logger.error(f"Error disabling feature: {e}", exc_info=True)
            embed = create_error_embed(
                title="Feature Error",
                description="Failed to disable feature.",
                error_details=str(e)
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
    
    @commands.command(name="features")
    @require_context
    @in_guild_only
    async def list_features(self, ctx: commands.Context):
        """List all feature flags and their status."""
        try:
            embed = create_base_embed(
                title="Feature Flags",
                description="Current feature flag status for this server:",
                color='info'
            )
            
            # Get feature states
            feature_states = []
            for feature in FeatureFlag:
                is_enabled = self.is_feature_enabled(feature.value, ctx.guild.id)
                status = "✅ Enabled" if is_enabled else "❌ Disabled"
                feature_states.append(f"**{feature.name}**: {status}")
            
            embed.add_field(
                name="Features",
                value="\n".join(feature_states),
                inline=False
            )
            
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error listing features: {e}", exc_info=True)
            embed = create_error_embed(
                title="Feature Error",
                description="Failed to list features.",
                error_details=str(e)
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
    
    # === BOT STATUS ===
    @commands.command(name="status")
    @require_context
    @in_guild_only
    async def show_bot_status(self, ctx: commands.Context):
        """Show bot status and statistics."""
        try:
            # Gather bot statistics
            guild_count = len(self.bot.guilds)
            user_count = sum(guild.member_count for guild in self.bot.guilds)
            
            # Get cog count
            cog_count = len(self.bot.cogs)
            
            # Get command count
            command_count = len(self.bot.all_commands)
            
            # Get uptime
            if hasattr(self.bot, 'uptime') and self.bot.uptime:
                from datetime import datetime
                uptime = datetime.now() - self.bot.uptime
                uptime_str = str(uptime).split('.')[0]  # Remove microseconds
            else:
                uptime_str = "Unknown"
            
            # Create status embed
            embed = create_base_embed(
                title="Bot Status",
                description=f"**Bot:** {self.bot.user.name}#{self.bot.user.discriminator}",
                color='info',
                timestamp=True
            )
            
            embed.add_field(
                name="Statistics",
                value=(
                    f"**Servers:** {guild_count:,}\n"
                    f"**Users:** {user_count:,}\n"
                    f"**Cogs:** {cog_count}\n"
                    f"**Commands:** {command_count}"
                ),
                inline=True
            )
            
            embed.add_field(
                name="System",
                value=(
                    f"**Uptime:** {uptime_str}\n"
                    f"**Python:** {sys.version.split()[0]}\n"
                    f"**discord.py:** {discord.__version__}"
                ),
                inline=True
            )
            
            # Add memory usage if available
            try:
                import psutil
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024
                embed.add_field(
                    name="Memory",
                    value=f"{memory_mb:.1f} MB",
                    inline=True
                )
            except ImportError:
                pass
            
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error getting bot status: {e}", exc_info=True)
            embed = create_error_embed(
                title="Status Error",
                description="Failed to retrieve bot status.",
                error_details=str(e)
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
    
    # === BOT SHUTDOWN ===
    @commands.command(name="shutdown")
    @require_context
    @in_guild_only
    @owner_only
    async def shutdown_bot(self, ctx: commands.Context):
        """Shutdown the bot gracefully."""
        # Extra confirmation for shutdown
        embed = create_base_embed(
            title="⚠️ Confirm Shutdown",
            description="Are you sure you want to shutdown the bot?\n\nReact with ✅ to confirm or ❌ to cancel.",
            color='warning'
        )
        
        async with ctx.typing():
            message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        
        def check(reaction, user):
            return (
                user == ctx.author and 
                str(reaction.emoji) in ["✅", "❌"] and 
                reaction.message == message
            )
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                embed = create_success_embed(
                    title="Shutting Down",
                    description="Bot is shutting down..."
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                self.logger.warning(f"Bot shutdown initiated by {ctx.author}")
                await self.bot.close()
            else:
                embed = create_base_embed(
                    title="Cancelled",
                    description="Shutdown cancelled.",
                    color='info'
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                
        except asyncio.TimeoutError:
            embed = create_error_embed(
                title="Timeout",
                description="Shutdown confirmation timed out."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
    
    # === BROADCAST ===
    @commands.command(name="broadcast")
    @require_context
    @in_guild_only
    @owner_only
    async def broadcast_message(self, ctx: commands.Context, *, message: str):
        """Broadcast a message to all servers."""
        # Confirmation
        embed = create_base_embed(
            title="⚠️ Confirm Broadcast",
            description=f"Broadcast to {len(self.bot.guilds)} servers?\n\n**Message:**\n{message}",
            color='warning'
        )
        
        async with ctx.typing():
            confirm_msg = await ctx.send(embed=embed)
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return (
                user == ctx.author and 
                str(reaction.emoji) in ["✅", "❌"] and 
                reaction.message == confirm_msg
            )
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # Send broadcast
                successful = 0
                failed = 0
                
                broadcast_embed = create_base_embed(
                    title="📢 Announcement",
                    description=message,
                    color='info',
                    timestamp=True
                )
                
                for guild in self.bot.guilds:
                    try:
                        # Try to find a suitable channel
                        channel = (
                            guild.system_channel or
                            guild.get_channel(guild.id) or  # Default channel
                            next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
                        )
                        
                        if channel:
                            async with channel.typing():
                                await channel.send(embed=broadcast_embed)
                            successful += 1
                        else:
                            failed += 1
                            
                    except Exception as e:
                        failed += 1
                        self.logger.error(f"Failed to broadcast to {guild.name}: {e}")
                
                # Report results
                result_embed = create_success_embed(
                    title="Broadcast Complete",
                    description=f"Successfully sent to {successful} servers.\nFailed: {failed}"
                )
                async with ctx.typing():
                    await ctx.send(embed=result_embed)
                
            else:
                embed = create_base_embed(
                    title="Cancelled",
                    description="Broadcast cancelled.",
                    color='info'
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                
        except asyncio.TimeoutError:
            embed = create_error_embed(
                title="Timeout",
                description="Broadcast confirmation timed out."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)

    # === SAY COMMAND ===
    @commands.command(name="say")
    @require_context
    @owner_only
    async def say_message(self, ctx: commands.Context, channel_id: int, *, message: str):
        """Make the bot say a message in a specific channel using channel ID."""
        try:
            # Get the channel by ID
            channel = self.bot.get_channel(channel_id)
            if not channel:
                embed = create_error_embed(
                    title="Channel Not Found",
                    description=f"Could not find channel with ID `{channel_id}`.\nMake sure the bot has access to this channel."
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                return
            
            # Check if it's a text channel
            if not isinstance(channel, discord.TextChannel):
                embed = create_error_embed(
                    title="Invalid Channel Type",
                    description=f"Channel `{channel.name}` is not a text channel."
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                return
            
            # Check if bot has permission to send messages in the target channel
            if not channel.permissions_for(channel.guild.me).send_messages:
                embed = create_error_embed(
                    title="Permission Error",
                    description=f"I don't have permission to send messages in **{channel.name}** ({channel.mention})."
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                return
            
            # Send the message to the target channel
            async with channel.typing():
                await channel.send(message)
            
            # Confirm to the command issuer
            embed = create_success_embed(
                title="Message Sent",
                description=f"Successfully sent message to **{channel.name}** ({channel.mention})\nChannel ID: `{channel_id}`"
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
            
            self.logger.info(f"Owner {ctx.author} sent message to {channel.name} ({channel.id}): {message[:100]}...")
            
        except discord.HTTPException as e:
            embed = create_error_embed(
                title="Send Failed",
                description=f"Failed to send message to channel ID `{channel_id}`",
                error_details=str(e)
            )
            async with ctx.typing():
                await ctx.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Error in say command: {e}", exc_info=True)
            embed = create_error_embed(
                title="Command Error",
                description="An unexpected error occurred while sending the message."
            )
            async with ctx.typing():
                await ctx.send(embed=embed)

    # === DATABASE DIAGNOSTICS ===
    @commands.command(name="dbstats")
    @require_context
    @in_guild_only
    async def database_stats(self, ctx: commands.Context):
        """Display database statistics and connection status."""
        try:
            # Create initial embed
            embed = create_base_embed(
                title="Database Status",
                description="Checking database connections and statistics...",
                color='info',
                timestamp=True
            )
            
            async with ctx.typing():
                status_message = await ctx.send(embed=embed)
            
            # Determine which database services are available
            db_v1 = self.db_service
            db_v2 = getattr(self.context, 'db_service_v2', None)
            
            # Track overall status
            db_status = "✅ Connected" if (db_v1 or db_v2) else "❌ No database services available"
            
            # Dictionary to hold our status fields
            status_fields = {}
            
            # Check V1 database (original)
            if db_v1:
                try:
                    # Test connection
                    conn = db_v1._get_connection()
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM users")
                        user_count = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(*) FROM user_quiz_sessions")
                        session_count = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(*) FROM achievements") if hasattr(cursor, 'execute') else None
                        achievement_count = cursor.fetchone()[0] if cursor.rowcount > 0 else 0
                        
                    db_v1._return_connection(conn)
                    
                    status_fields["DB v1 Status"] = "✅ Connected"
                    status_fields["DB v1 Users"] = f"{user_count:,}"
                    status_fields["DB v1 Quiz Sessions"] = f"{session_count:,}"
                    status_fields["DB v1 Achievements"] = f"{achievement_count:,}"
                except Exception as e:
                    status_fields["DB v1 Status"] = f"❌ Error: {str(e)[:100]}..."
                    self.logger.error(f"Error checking V1 database: {e}")
            else:
                status_fields["DB v1 Status"] = "⚠️ Not initialized"
            
            # Check V2 database (enhanced)
            if db_v2 and hasattr(db_v2, 'pool'):
                try:
                    async with db_v2.pool.acquire() as conn:
                        # Get table counts
                        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
                        session_count = await conn.fetchval("SELECT COUNT(*) FROM user_quiz_sessions")
                        guild_count = await conn.fetchval("SELECT COUNT(*) FROM guild_settings")
                        leaderboard_count = await conn.fetchval("SELECT COUNT(*) FROM guild_leaderboards") if await conn.fetchval("SELECT to_regclass('guild_leaderboards')") else 0
                        
                        # Get pool status if available
                        pool_status = {
                            "size": db_v2.pool.get_size() if hasattr(db_v2.pool, 'get_size') else 'Unknown',
                            "idle": db_v2.pool.get_idle_size() if hasattr(db_v2.pool, 'get_idle_size') else 'Unknown',
                            "max_size": db_v2.pool.get_max_size() if hasattr(db_v2.pool, 'get_max_size') else 'Unknown'
                        }
                        
                        # Get database server information
                        db_version = await conn.fetchval("SELECT version()")
                        
                    status_fields["DB v2 Status"] = "✅ Connected (Primary)"
                    status_fields["DB v2 Server"] = db_version.split(",")[0] if db_version else "Unknown"
                    status_fields["DB v2 Users"] = f"{user_count:,}"
                    status_fields["DB v2 Quiz Sessions"] = f"{session_count:,}"
                    status_fields["DB v2 Guilds"] = f"{guild_count:,}"
                    status_fields["DB v2 Leaderboards"] = f"{leaderboard_count:,}"
                    
                    # Only add pool stats if we have values
                    if pool_status['size'] != 'Unknown':
                        status_fields["Connection Pool"] = f"Size: {pool_status['size']}/{pool_status['max_size']} (Idle: {pool_status['idle']})"
                except Exception as e:
                    status_fields["DB v2 Status"] = f"❌ Error: {str(e)[:100]}..."
                    self.logger.error(f"Error checking V2 database: {e}")
            else:
                status_fields["DB v2 Status"] = "⚠️ Not initialized" if db_v2 else "❌ Not available"
            
            # Create updated embed
            embed = create_base_embed(
                title="Database Status Report",
                description=f"Overall status: {db_status}",
                color=Color.green() if "✅" in db_status else Color.red(),
                timestamp=True
            )
            
            # Add DB v1 fields
            v1_fields = {k: v for k, v in status_fields.items() if k.startswith("DB v1")}
            if v1_fields:
                embed.add_field(
                    name="Legacy Database (V1)",
                    value="\n".join([f"**{k.replace('DB v1 ', '')}**: {v}" for k, v in v1_fields.items()]),
                    inline=False
                )
            
            # Add DB v2 fields
            v2_fields = {k: v for k, v in status_fields.items() if k.startswith("DB v2")}
            if v2_fields:
                embed.add_field(
                    name="Enhanced Database (V2)",
                    value="\n".join([f"**{k.replace('DB v2 ', '')}**: {v}" for k, v in v2_fields.items()]),
                    inline=False
                )
            
            # Add connection pool info
            if "Connection Pool" in status_fields:
                embed.add_field(
                    name="Connection Pool",
                    value=status_fields["Connection Pool"],
                    inline=False
                )
                
            # Add maintenance suggestions
            suggestions = []
            if "❌" in db_status:
                suggestions.append("• Database connection failed - check configuration and server status")
            elif db_v2 and "✅" in status_fields.get("DB v2 Status", ""):
                if (user_count > 10000 or session_count > 50000):
                    suggestions.append("• Consider running VACUUM ANALYZE for optimal performance")
                    
            if suggestions:
                embed.add_field(
                    name="Maintenance Suggestions",
                    value="\n".join(suggestions),
                    inline=False
                )
            
            # Update the status message
            await status_message.edit(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}", exc_info=True)
            embed = create_error_embed(
                title="Database Stats Error",
                description=f"Failed to retrieve database statistics: {str(e)}",
                error_details=str(e)
            )
            async with ctx.typing():
                await ctx.send(embed=embed)


async def setup(bot):
    """Set up the Admin cog."""
    cog = AdminCog(bot)
    await bot.add_cog(cog)
    return cog


async def setup_with_context(bot, context):
    """Set up the Admin cog with context."""
    from cogs.base_cog import setup_with_context as base_setup
    return await base_setup(bot, context, AdminCog)