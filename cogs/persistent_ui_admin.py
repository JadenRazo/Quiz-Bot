"""
Admin commands for managing and debugging persistent UI state.

This cog provides administrative commands for monitoring and managing
the persistent button system, including recovery status and cleanup operations.
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from cogs.base_cog import BaseCog
from utils.context import BotContext


class PersistentUIAdminCog(BaseCog, name="PersistentUIAdmin"):
    """Administrative commands for persistent UI management."""
    
    def __init__(self, bot):
        super().__init__(bot, "PersistentUIAdmin")
        self.ui_service = None
        self.recovery_service = None
    
    async def cog_load(self):
        """Initialize services when cog is loaded."""
        await super().cog_load()
        
        try:
            # Initialize UI services
            from services.persistent_ui_service import PersistentUIService
            from services.ui_recovery_service import UIRecoveryService
            
            self.ui_service = PersistentUIService(self.context)
            self.recovery_service = UIRecoveryService(self.context)
            
            # Make services available through context
            self.context.ui_service = self.ui_service
            self.context.recovery_service = self.recovery_service
            
            self.logger.info("Persistent UI admin services initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize UI services: {e}")
    
    @app_commands.command(name="ui_status", description="Show persistent UI system status")
    @app_commands.describe(detailed="Show detailed statistics")
    async def ui_status(self, interaction: discord.Interaction, detailed: bool = False):
        """Display persistent UI system status and statistics."""
        
        if not await self._check_admin_permissions(interaction):
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get recovery status
            if self.recovery_service:
                status_data = await self.recovery_service.get_recovery_status()
            else:
                status_data = {'error': 'Recovery service not available'}
            
            # Create status embed
            embed = discord.Embed(
                title="🔧 Persistent UI System Status",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            if 'error' not in status_data:
                recovery_stats = status_data.get('recovery_stats', {})
                
                # Basic status
                embed.add_field(
                    name="📊 Current Status",
                    value=(
                        f"**Active Buttons:** {status_data.get('current_active_buttons', 'N/A')}\n"
                        f"**Cleanup Task:** {'✅ Running' if status_data.get('cleanup_task_running') else '❌ Stopped'}\n"
                        f"**Last Recovery:** {recovery_stats.get('last_recovery', 'Never')}"
                    ),
                    inline=False
                )
                
                # Recovery statistics
                if recovery_stats:
                    embed.add_field(
                        name="🔄 Recovery Statistics",
                        value=(
                            f"**Buttons Recovered:** {recovery_stats.get('buttons_recovered', 0)}\n"
                            f"**Messages Scanned:** {recovery_stats.get('messages_scanned', 0)}\n"
                            f"**Recovery Time:** {recovery_stats.get('recovery_time_seconds', 0):.2f}s"
                        ),
                        inline=True
                    )
                
                # Analytics (if detailed)
                if detailed and 'analytics' in status_data:
                    analytics = status_data['analytics']
                    if 'error' not in analytics:
                        handler_stats = analytics.get('handler_stats', [])
                        if handler_stats:
                            top_handlers = sorted(handler_stats, key=lambda x: x['count'], reverse=True)[:3]
                            handler_text = "\n".join([
                                f"• {h['handler_class']}: {h['count']} interactions"
                                for h in top_handlers
                            ])
                            embed.add_field(
                                name="📈 Top Handlers (24h)",
                                value=handler_text or "No interactions",
                                inline=True
                            )
            else:
                embed.add_field(
                    name="❌ Error",
                    value=status_data['error'],
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in ui_status command: {e}")
            await interaction.followup.send(f"Error getting UI status: {e}", ephemeral=True)
    
    @app_commands.command(name="ui_cleanup", description="Clean up expired persistent UI elements")
    async def ui_cleanup(self, interaction: discord.Interaction):
        """Manually trigger cleanup of expired buttons and messages."""
        
        if not await self._check_admin_permissions(interaction):
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not self.ui_service:
                await interaction.followup.send("UI service not available", ephemeral=True)
                return
            
            # Perform cleanup
            cleaned_count = await self.ui_service.cleanup_expired_buttons()
            
            embed = discord.Embed(
                title="🧹 UI Cleanup Complete",
                description=f"Cleaned up {cleaned_count} expired UI elements",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in ui_cleanup command: {e}")
            await interaction.followup.send(f"Error during cleanup: {e}", ephemeral=True)
    
    @app_commands.command(name="ui_recover", description="Force recovery of persistent buttons")
    async def ui_recover(self, interaction: discord.Interaction):
        """Manually trigger recovery of persistent buttons."""
        
        if not await self._check_admin_permissions(interaction):
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not self.recovery_service:
                await interaction.followup.send("Recovery service not available", ephemeral=True)
                return
            
            # Perform recovery
            recovery_result = await self.recovery_service.perform_startup_recovery()
            
            if recovery_result['success']:
                stats = recovery_result['statistics']
                embed = discord.Embed(
                    title="🔄 UI Recovery Complete",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(
                    name="Results",
                    value=(
                        f"**Buttons Recovered:** {stats.get('buttons_recovered', 0)}\n"
                        f"**Messages Scanned:** {stats.get('messages_scanned', 0)}\n"
                        f"**Recovery Time:** {stats.get('recovery_time_seconds', 0):.2f}s"
                    ),
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ UI Recovery Failed",
                    description=recovery_result.get('error', 'Unknown error'),
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in ui_recover command: {e}")
            await interaction.followup.send(f"Error during recovery: {e}", ephemeral=True)
    
    @app_commands.command(name="ui_analytics", description="Show button interaction analytics")
    @app_commands.describe(hours="Number of hours to look back (default: 24)")
    async def ui_analytics(self, interaction: discord.Interaction, hours: int = 24):
        """Display analytics for button interactions."""
        
        if not await self._check_admin_permissions(interaction):
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not self.ui_service:
                await interaction.followup.send("UI service not available", ephemeral=True)
                return
            
            # Validate hours parameter
            if hours < 1 or hours > 168:  # Max 1 week
                await interaction.followup.send("Hours must be between 1 and 168 (1 week)", ephemeral=True)
                return
            
            # Get analytics
            analytics = await self.ui_service.get_button_analytics(hours=hours)
            
            if 'error' in analytics:
                await interaction.followup.send(f"Error getting analytics: {analytics['error']}", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"📊 Button Analytics ({hours}h)",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            
            # Handler statistics
            handler_stats = analytics.get('handler_stats', [])
            if handler_stats:
                # Group by handler class and sum counts
                handler_totals = {}
                for stat in handler_stats:
                    handler = stat['handler_class']
                    if handler not in handler_totals:
                        handler_totals[handler] = {'total': 0, 'avg_response': 0, 'count': 0}
                    handler_totals[handler]['total'] += stat['count']
                    if stat.get('avg_response_time'):
                        handler_totals[handler]['avg_response'] += stat['avg_response_time']
                        handler_totals[handler]['count'] += 1
                
                # Format top handlers
                sorted_handlers = sorted(handler_totals.items(), key=lambda x: x[1]['total'], reverse=True)[:5]
                handler_text = ""
                for handler, data in sorted_handlers:
                    avg_response = data['avg_response'] / max(data['count'], 1)
                    handler_text += f"• **{handler}**: {data['total']} interactions ({avg_response:.0f}ms avg)\n"
                
                embed.add_field(
                    name="🎯 Top Handlers",
                    value=handler_text or "No interactions found",
                    inline=False
                )
            
            # Error statistics
            error_stats = analytics.get('error_stats', [])
            if error_stats:
                error_text = ""
                for stat in error_stats:
                    error_rate = (stat['errors'] / stat['total_interactions']) * 100
                    error_text += f"• **{stat['handler_class']}**: {stat['errors']}/{stat['total_interactions']} ({error_rate:.1f}%)\n"
                
                embed.add_field(
                    name="⚠️ Error Rates",
                    value=error_text or "No errors found",
                    inline=False
                )
            
            if not handler_stats and not error_stats:
                embed.description = f"No button interactions found in the last {hours} hours."
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in ui_analytics command: {e}")
            await interaction.followup.send(f"Error getting analytics: {e}", ephemeral=True)
    
    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions for UI commands."""
        
        # Check if user is bot owner
        if interaction.user.id in self.bot.owner_ids:
            return True
        
        # Check if user has administrator permission in guild
        if interaction.guild and interaction.user.guild_permissions.administrator:
            return True
        
        # Check if user has manage server permission
        if interaction.guild and interaction.user.guild_permissions.manage_guild:
            return True
        
        await interaction.response.send_message(
            "❌ You need administrator permissions to use this command.",
            ephemeral=True
        )
        return False


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(PersistentUIAdminCog(bot))


async def setup_with_context(bot, context):
    """Setup function with context (preferred method)."""
    from cogs.base_cog import setup_with_context as base_setup
    return await base_setup(bot, context, PersistentUIAdminCog)