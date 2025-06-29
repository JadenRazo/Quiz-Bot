"""
Specialized Button Handlers for Quiz Bot

This module contains specialized implementations of ButtonHandler that match
the existing button patterns in the codebase. These handlers provide seamless
migration from the current button implementations.
"""

from typing import Dict, Any, Optional, List
from datetime import timedelta
import discord
import traceback
import logging

from utils.unified_persistent_ui import (
    ButtonHandler, ButtonState, ButtonAction, PersistentView
)
from utils.context import BotContext
from utils.ui_config import get_ui_config, get_timeout, get_toggle_timeout
from utils.ui_constants import (
    ui_emojis, ui_colors, ui_messages, button_styles,
    get_emoji, get_color, get_button_config, get_message
)


class StatsNavigationHandler(ButtonHandler):
    """Specialized handler for stats pagination buttons."""
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        import time
        start_time = time.time()
        
        direction = state.data.get('direction', 'next')
        current_page = state.data.get('page', 0)
        total_pages = state.data.get('total', 1)
        target_user_id = state.data.get('target_user_id', state.user_id)
        
        self.logger.info(f"StatsNavigationHandler called: direction={direction}, page={current_page}, target_user={target_user_id}")
        
        # Calculate new page
        if direction == 'prev':
            new_page = max(0, current_page - 1)
        elif direction == 'next':
            new_page = min(total_pages - 1, current_page + 1)
        else:
            new_page = current_page
        
        try:
            # Get the target user
            target_user = None
            if interaction.guild:
                target_user = interaction.guild.get_member(target_user_id)
            if not target_user:
                # Try to get from bot users if not in guild
                target_user = self.context.bot.get_user(target_user_id)
            
            if not target_user:
                await interaction.response.send_message("❌ User not found.", ephemeral=True)
                return
            
            # Get the stats cog to regenerate embeds
            stats_cog = interaction.client.get_cog('Stats')
            if not stats_cog:
                # Try alternative cog names if the primary fails
                for possible_name in ['StatsCog', 'stats', 'Stats']:
                    stats_cog = interaction.client.get_cog(possible_name)
                    if stats_cog:
                        self.logger.info(f"Found stats cog with name: {possible_name}")
                        break
                
                if not stats_cog:
                    # Debug: Log available cogs
                    available_cogs = list(interaction.client.cogs.keys())
                    self.logger.error(f"Stats cog not found. Available cogs: {available_cogs}")
                    await interaction.response.send_message("❌ Stats system not available.", ephemeral=True)
                    return
                
            # Get user stats data
            guild_id = interaction.guild.id if interaction.guild else None
            
            # Check if stats cog has the db_service
            if not hasattr(stats_cog, 'db_service') or stats_cog.db_service is None:
                self.logger.error(f"Stats cog does not have db_service: {hasattr(stats_cog, 'db_service')}")
                await interaction.response.send_message("❌ Stats database service not available.", ephemeral=True)
                return
                
            if hasattr(stats_cog.db_service, 'get_comprehensive_user_stats'):
                db_start = time.time()
                stats_data = await stats_cog.db_service.get_comprehensive_user_stats(target_user_id, guild_id=guild_id)
                db_elapsed = time.time() - db_start
                self.logger.info(f"Database call took {db_elapsed:.2f}s")
            else:
                self.logger.error(f"Stats db_service does not have get_comprehensive_user_stats method")
                await interaction.response.send_message("❌ Stats data not available.", ephemeral=True)
                return
            
            if not stats_data:
                await interaction.response.send_message("❌ No stats data found.", ephemeral=True)
                return
            
            # Regenerate all embeds
            if not hasattr(stats_cog, '_create_stats_embeds'):
                self.logger.error(f"Stats cog does not have _create_stats_embeds method")
                await interaction.response.send_message("❌ Stats embed generation not available.", ephemeral=True)
                return
                
            embeds = stats_cog._create_stats_embeds(target_user, stats_data)
            
            if new_page < len(embeds):
                embed = embeds[new_page]
                
                # Create new navigation view
                view = await self._create_stats_navigation_view(state, new_page, len(embeds))
                
                await interaction.response.edit_message(embed=embed, view=view)
                elapsed = time.time() - start_time
                self.logger.info(f"StatsNavigationHandler completed successfully in {elapsed:.2f}s")
            else:
                await interaction.response.send_message("❌ Page not found.", ephemeral=True)
                
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"Error updating stats page after {elapsed:.2f}s: {e}")
            import traceback
            self.logger.error(f"Full traceback:\n{traceback.format_exc()}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error loading stats page.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error loading stats page.", ephemeral=True)
            except Exception as followup_error:
                self.logger.error(f"Failed to send error response: {followup_error}")
    
    def get_button_config(self, state: ButtonState) -> Dict[str, Any]:
        direction = state.data.get('direction', 'next')
        current_page = state.data.get('page', 0)
        total_pages = state.data.get('total', 1)
        
        configs = {
            'prev': {'style': discord.ButtonStyle.gray, 'emoji': '◀️'},
            'next': {'style': discord.ButtonStyle.gray, 'emoji': '▶️'}
        }
        
        config = configs.get(direction, configs['next'])
        
        # Disable if at edge
        if direction == 'prev' and current_page == 0:
            config['disabled'] = True
        elif direction == 'next' and current_page >= total_pages - 1:
            config['disabled'] = True
            
        return config
    
    async def _create_stats_embed(self, achievements_data: Dict[str, Any], page: int, total_pages: int) -> discord.Embed:
        """Create stats embed for specific page."""
        embed = discord.Embed(
            title=f"📊 Achievement Progress - Page {page + 1}",
            color=discord.Color.blue()
        )
        
        if achievements_data.get('achievements'):
            for achievement in achievements_data['achievements']:
                embed.add_field(
                    name=f"{achievement.get('emoji', '🏆')} {achievement['name']}",
                    value=f"{achievement['description']}\nProgress: {achievement['progress']}/{achievement['target']}",
                    inline=False
                )
        else:
            embed.description = "No achievements found for this page."
        
        embed.set_footer(text=f"Page {page + 1} of {total_pages}")
        return embed
    
    async def _create_stats_navigation_view(self, state: ButtonState, new_page: int, total_pages: int) -> PersistentView:
        """Create navigation view for stats."""
        view = PersistentView(self.context)
        
        target_user_id = state.data.get('target_user_id', state.user_id)
        
        # Add previous button if not on first page
        if new_page > 0:
            view.add_button(
                'StatsNavigationHandler', state.user_id, ButtonAction.NAVIGATE,
                {
                    'direction': 'prev',
                    'page': new_page,
                    'total': total_pages,
                    'target_user_id': target_user_id
                },
                state.guild_id, get_timeout('stats')
            )
        
        # Add next button if not on last page
        if new_page < total_pages - 1:
            view.add_button(
                'StatsNavigationHandler', state.user_id, ButtonAction.NAVIGATE,
                {
                    'direction': 'next',
                    'page': new_page,
                    'total': total_pages,
                    'target_user_id': target_user_id
                },
                state.guild_id, get_timeout('stats')
            )
        
        return view


class LeaderboardToggleHandler(ButtonHandler):
    """Specialized handler for leaderboard scope toggle."""
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        # Support both old 'scope' and new shortened 's' keys for backwards compatibility
        current_scope = state.data.get('s', state.data.get('scope', 'server'))
        new_scope = 'global' if current_scope == 'server' else 'server'
        
        try:
            from services.database_operations.leaderboard_ops import get_formatted_leaderboard
            
            # Get leaderboard data for new scope
            guild_id = None if new_scope == 'global' else state.guild_id
            # Use the same db_service reference as the stats cog
            db_service = getattr(self.context, 'db_service', None)
            if not db_service:
                raise RuntimeError("Database service not available in context")
                
            leaderboard_data = await get_formatted_leaderboard(
                db_service=db_service,
                limit=10,
                guild_id=guild_id,
                user_id=state.user_id  # Pass user ID for own ranking in global leaderboard
            )
            
            # Create updated embed using the stats cog's method
            # Import the stats cog to access its embed creation method
            from cogs.stats import StatsCog
            stats_cog = None
            for cog_name, cog in self.context.bot.cogs.items():
                if isinstance(cog, StatsCog):
                    stats_cog = cog
                    break
            
            if stats_cog:
                # Use the existing embed creation method from StatsCog
                guild_name = None
                if state.guild_id and interaction.guild:
                    guild_name = interaction.guild.name
                    
                embed = stats_cog._create_leaderboard_embed(
                    leaderboard=leaderboard_data,
                    scope=new_scope,
                    guild_name=guild_name,
                    ctx=None  # No context needed for this method
                )
            else:
                # Fallback embed creation
                embed = discord.Embed(
                    title=f"🏆 {'Global' if new_scope == 'global' else 'Server'} Leaderboard",
                    color=discord.Color.gold()
                )
                
                if leaderboard_data:
                    # Format leaderboard data properly as it's a list of dicts
                    leaderboard_text = []
                    for i, entry in enumerate(leaderboard_data[:10]):  # Top 10
                        username = entry.get("username", "Unknown")
                        points = entry.get("points", 0)
                        quizzes = entry.get("quizzes", 0)
                        accuracy = entry.get("accuracy", 0)
                        
                        # Add medal emoji for top 3
                        medal = ""
                        if i == 0:
                            medal = "🥇 "
                        elif i == 1:
                            medal = "🥈 "
                        elif i == 2:
                            medal = "🥉 "
                        
                        leaderboard_text.append(
                            f"{medal}**{i+1}.** {username} - {points} points | {quizzes} quizzes | {accuracy}% accuracy"
                        )
                    
                    embed.add_field(
                        name="📊 Rankings",
                        value="\n".join(leaderboard_text) if leaderboard_text else "No rankings available.",
                        inline=False
                    )
                else:
                    embed.description = "No leaderboard data available."
            
            # Create new view with updated toggle using shortened key
            view = PersistentView(self.context)
            view.add_button(
                'LeaderboardToggleHandler', state.user_id, ButtonAction.TOGGLE,
                {'s': new_scope},  # Use shortened key to reduce encoding size
                state.guild_id, timedelta(hours=1)
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            tb_str = traceback.format_exc()
            self.logger.error(f"Error toggling leaderboard: {e}")
            self.logger.error(f"Full traceback:\n{tb_str}")
            # Only send error response if interaction hasn't been acknowledged yet
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Error loading leaderboard: {str(e)[:100]}", ephemeral=True)
                else:
                    # If already acknowledged, use followup instead
                    await interaction.followup.send(f"❌ Error loading leaderboard: {str(e)[:100]}", ephemeral=True)
            except Exception as followup_error:
                self.logger.error(f"Failed to send error response: {followup_error}")
                self.logger.error(f"Followup error traceback:\n{traceback.format_exc()}")
    
    def get_button_config(self, state: ButtonState) -> Dict[str, Any]:
        # Support both old 'scope' and new shortened 's' keys for backwards compatibility
        scope = state.data.get('s', state.data.get('scope', 'server'))
        
        if scope == 'global':
            return {
                'style': discord.ButtonStyle.success,
                'emoji': '🌐',
                'label': 'Switch to Server'
            }
        else:
            return {
                'style': discord.ButtonStyle.secondary,
                'emoji': '🏠',
                'label': 'Switch to Global'
            }


class FAQNavigationHandler(ButtonHandler):
    """Specialized handler for FAQ pagination with advanced navigation."""
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        direction = state.data.get('direction', 'next')
        current_page = state.data.get('page', 0)
        total_pages = state.data.get('total', 1)
        
        # Calculate new page
        if direction == 'first':
            new_page = 0
        elif direction == 'prev':
            new_page = max(0, current_page - 1)
        elif direction == 'next':
            new_page = min(total_pages - 1, current_page + 1)
        elif direction == 'last':
            new_page = total_pages - 1
        else:
            new_page = current_page
        
        # Get the FAQ cog to regenerate the embeds
        try:
            faq_cog = interaction.client.get_cog('FAQ')
            if not faq_cog:
                await interaction.response.send_message("❌ FAQ system not available.", ephemeral=True)
                return
            
            # Regenerate the embeds
            embeds = faq_cog._create_faq_embeds()
            
            if new_page < len(embeds):
                embed = embeds[new_page]
                # Update footer with current page info
                embed.set_footer(text=f"Page {new_page + 1}/{total_pages}")
            else:
                embed = discord.Embed(
                    title="❓ FAQ Not Found",
                    description="The requested FAQ page could not be found.",
                    color=discord.Color.red()
                )
            
            # Create new navigation view
            view = await self._create_faq_navigation_view(state, new_page, total_pages)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            self.logger.error(f"Error navigating FAQ: {e}")
            await interaction.response.send_message("❌ Error navigating FAQ.", ephemeral=True)
    
    def get_button_config(self, state: ButtonState) -> Dict[str, Any]:
        direction = state.data.get('direction', 'next')
        current_page = state.data.get('page', 0)
        total_pages = state.data.get('total', 1)
        
        configs = {
            'first': {'style': discord.ButtonStyle.gray, 'emoji': '⏮️'},
            'prev': {'style': discord.ButtonStyle.gray, 'emoji': '◀️'},
            'next': {'style': discord.ButtonStyle.gray, 'emoji': '▶️'},
            'last': {'style': discord.ButtonStyle.gray, 'emoji': '⏭️'}
        }
        
        config = configs.get(direction, configs['next'])
        
        # Disable if at edges
        if direction in ['first', 'prev'] and current_page == 0:
            config['disabled'] = True
        elif direction in ['last', 'next'] and current_page >= total_pages - 1:
            config['disabled'] = True
            
        return config
    
    async def _create_faq_navigation_view(self, state: ButtonState, new_page: int, 
                                        total_pages: int) -> PersistentView:
        """Create FAQ navigation view with all buttons."""
        view = PersistentView(self.context)
        
        # First page button
        if new_page > 0:
            view.add_button(
                'FAQNavigationHandler', state.user_id, ButtonAction.NAVIGATE,
                {
                    'direction': 'first',
                    'page': new_page,
                    'total': total_pages
                },
                state.guild_id, timedelta(minutes=15)
            )
        
        # Previous button
        if new_page > 0:
            view.add_button(
                'FAQNavigationHandler', state.user_id, ButtonAction.NAVIGATE,
                {
                    'direction': 'prev',
                    'page': new_page,
                    'total': total_pages
                },
                state.guild_id, timedelta(minutes=15)
            )
        
        # Next button
        if new_page < total_pages - 1:
            view.add_button(
                'FAQNavigationHandler', state.user_id, ButtonAction.NAVIGATE,
                {
                    'direction': 'next',
                    'page': new_page,
                    'total': total_pages
                },
                state.guild_id, timedelta(minutes=15)
            )
        
        # Last page button
        if new_page < total_pages - 1:
            view.add_button(
                'FAQNavigationHandler', state.user_id, ButtonAction.NAVIGATE,
                {
                    'direction': 'last',
                    'page': new_page,
                    'total': total_pages
                },
                state.guild_id, timedelta(minutes=15)
            )
        
        return view



class WelcomeActionHandler(ButtonHandler):
    """Specialized handler for welcome message action buttons."""
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        action = state.data.get('action', 'unknown')
        
        if action == 'quiz':
            await self._handle_quiz_start_info(interaction)
        elif action == 'guide':
            await self._handle_setup_guide(interaction)
        elif action == 'commands':
            await self._handle_command_list(interaction)
        else:
            await interaction.response.send_message(f"Unknown action: {action}", ephemeral=True)
    
    def get_button_config(self, state: ButtonState) -> Dict[str, Any]:
        action = state.data.get('action', 'unknown')
        
        configs = {
            'quiz': {'style': discord.ButtonStyle.primary, 'emoji': '🎯', 'label': 'Start a Quiz'},
            'guide': {'style': discord.ButtonStyle.secondary, 'emoji': '📖', 'label': 'Setup Guide'},
            'commands': {'style': discord.ButtonStyle.secondary, 'emoji': '📋', 'label': 'Command List'}
        }
        
        return configs.get(action, {'style': discord.ButtonStyle.secondary, 'label': 'Action'})
    
    async def _handle_quiz_start_info(self, interaction: discord.Interaction) -> None:
        """Handle quiz start information."""
        embed = discord.Embed(
            title="🎯 Starting a Quiz",
            description=(
                "To start a quiz, use the `/quiz start` command. "
                "You'll need to specify a topic and optionally set the difficulty and question count.\n\n"
                "**Examples:**\n"
                "• `/quiz start science`\n"
                "• `/quiz start history 10 medium`\n"
                "• `/quiz start programming`\n\n"
                "Use `/quiz topics` to see popular quiz topics!"
            ),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _handle_setup_guide(self, interaction: discord.Interaction) -> None:
        """Handle setup guide information."""
        embed = discord.Embed(
            title="📖 Setup Guide for Administrators",
            description=(
                "**Initial Setup:**\n"
                "1. Make sure the bot has the required permissions\n"
                "2. Use `/admin setup` to configure server-specific settings\n"
                "3. Use `/admin permissions` to set up role permissions\n\n"
                "**Required Permissions:**\n"
                "• Send Messages\n"
                "• Embed Links\n"
                "• Add Reactions\n"
                "• Use Slash Commands\n\n"
                "For more detailed instructions, check out our documentation."
            ),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _handle_command_list(self, interaction: discord.Interaction) -> None:
        """Handle command list information."""
        embed = discord.Embed(
            title="📋 Available Commands",
            description=(
                "Use `/help` to see the full list of commands. "
                "Here are some of the most commonly used ones:\n\n"
                "**Quiz Commands:**\n"
                "• `/quiz start` - Start a new quiz\n"
                "• `/quiz stop` - Stop current quiz\n"
                "• `/quiz topics` - View popular topics\n"
                "• `/quiz scores` - View your statistics\n\n"
                "**Other Commands:**\n"
                "• `/trivia start` - Start a group trivia game\n"
                "• `/faq` - Show frequently asked questions\n"
                "• `/preferences` - Set your personal preferences\n"
                "• `/admin` - Admin commands (admins only)"
            ),
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class FAQJumpHandler(ButtonHandler):
    """Handler for FAQ jump to topic functionality."""
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        """Handle jump to topic action."""
        try:
            # Get the FAQ cog to get section data
            faq_cog = interaction.client.get_cog('FAQ')
            if not faq_cog:
                await interaction.response.send_message("❌ FAQ system not available.", ephemeral=True)
                return
            
            # Get the FAQ sections
            faq_sections = faq_cog.faq_data
            
            # Create select options from FAQ sections
            topics = []
            page_index = 0
            
            # First option for index page
            topics.append(discord.SelectOption(
                label="📚 Main Index",
                value="0",
                description="Return to the FAQ main page"
            ))
            page_index += 1
            
            # Add sections
            for section_id, section_data in faq_sections.items():
                if len(topics) >= 25:  # Discord limit
                    break
                    
                label = f"📖 {section_data['title']}"[:100]
                description = section_data['description'][:100]
                topics.append(discord.SelectOption(
                    label=label,
                    value=str(page_index),
                    description=description
                ))
                page_index += 1
            
            if not topics:
                await interaction.response.send_message("No topics available to jump to.", ephemeral=True)
                return
            
            # Create select menu
            select = discord.ui.Select(placeholder="Choose a section to jump to...", options=topics)
            
            async def select_callback(select_interaction: discord.Interaction):
                selected_page = int(select.values[0])
                
                # Get all embeds
                embeds = faq_cog._create_faq_embeds()
                
                if selected_page < len(embeds):
                    embed = embeds[selected_page]
                    # Update footer with current page info
                    embed.set_footer(text=f"Page {selected_page + 1}/{len(embeds)}")
                    
                    # Import FAQView to create updated view
                    from cogs.faq import FAQView
                    
                    # Get context from the handler
                    new_view = FAQView(
                        embeds=embeds,
                        author_id=state.user_id,
                        context=self.context,
                        current_page=selected_page,
                        guild_id=state.guild_id
                    )
                    
                    # Update the original message
                    await interaction.message.edit(embed=embed, view=new_view)
                    await select_interaction.response.defer()
                    await select_interaction.delete_original_response()
                else:
                    await select_interaction.response.send_message("❌ Invalid page selected.", ephemeral=True)
            
            select.callback = select_callback
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            
            await interaction.response.send_message("Select a section to jump to:", view=view, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error in FAQ jump handler: {e}")
            await interaction.response.send_message("❌ Error loading topic selection.", ephemeral=True)
    
    def get_button_config(self, state: ButtonState) -> Dict[str, Any]:
        """Get button configuration."""
        return {
            'style': discord.ButtonStyle.primary,
            'label': 'Jump to Topic',
            'emoji': '📍'
        }


class HelpActionHandler(ButtonHandler):
    """Specialized handler for help menu action buttons."""
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        action = state.data.get('action', 'unknown')
        
        if action == 'guide':
            await self._handle_commands_guide(interaction)
        elif action == 'support':
            await self._handle_support_info(interaction)
        elif action == 'menu':
            await self._handle_main_menu(interaction)
        elif action == 'close':
            await self._handle_close(interaction)
        else:
            await interaction.response.send_message(f"Unknown action: {action}", ephemeral=True)
    
    def get_button_config(self, state: ButtonState) -> Dict[str, Any]:
        action = state.data.get('action', 'unknown')
        
        configs = {
            'guide': {'style': discord.ButtonStyle.success, 'emoji': '📘', 'label': 'Commands Guide'},
            'support': {'style': discord.ButtonStyle.primary, 'emoji': '🎧', 'label': 'Support'},
            'menu': {'style': discord.ButtonStyle.secondary, 'emoji': '📋', 'label': 'Main Menu'},
            'close': {'style': discord.ButtonStyle.danger, 'emoji': '❌', 'label': 'Close'}
        }
        
        return configs.get(action, {'style': discord.ButtonStyle.secondary, 'label': 'Action'})
    
    async def _handle_commands_guide(self, interaction: discord.Interaction) -> None:
        """Handle commands guide display."""
        # Fallback embed since we don't have access to state data here
        embed = discord.Embed(
            title="📘 Commands Guide",
            description="Here are all the available commands organized by category:",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🎯 Quiz Commands",
            value=(
                "`/quiz start <topic>` - Start a quiz on any topic\n"
                "`/quiz stop` - Stop the current quiz\n"
                "`/quiz topics` - View popular quiz topics\n"
                "`/quiz scores` - View your quiz statistics"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🏆 Competition & Stats",
            value=(
                "`/trivia start` - Start group trivia session\n"
                "`/stats [user]` - View detailed statistics\n"
                "`/leaderboard` - View server leaderboard\n"
                "`/history` - View your quiz history"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Configuration",
            value=(
                "`/preferences` - Manage your preferences\n"
                "`/help` - Show this help menu\n"
                "`/admin` - Admin commands (admins only)"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed)
    
    async def _handle_support_info(self, interaction: discord.Interaction) -> None:
        """Handle support information display."""
        # Fallback embed since we don't have access to state data here
        embed = discord.Embed(
            title="🎧 Support Information",
            description="Need help? Here's how to get support:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📖 Documentation",
            value="Use `/help` to access the complete help system with detailed guides.",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Common Issues",
            value=(
                "• **Bot not responding?** Check bot permissions\n"
                "• **Quiz not starting?** Ensure you have the right permissions\n"
                "• **Stats not updating?** Try using `/stats` to refresh"
            ),
            inline=False
        )
        
        embed.add_field(
            name="👥 Community",
            value="Ask questions in your server's general chat - other users might help!",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed)
    
    async def _handle_main_menu(self, interaction: discord.Interaction) -> None:
        """Handle main menu display."""
        # Fallback embed since we don't have access to state data here
        embed = discord.Embed(
            title="📋 Quiz Bot - Main Menu",
            description="Welcome to the Educational Quiz Bot! Choose an option below:",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🚀 Quick Start",
            value="New to the bot? Start with `/quiz start` followed by any topic!",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Popular Features",
            value=(
                "• **Individual Quizzes** - `/quiz start <topic>`\n"
                "• **Group Trivia** - `/trivia start`\n"
                "• **Statistics** - `/stats` and `/leaderboard`\n"
                "• **Custom Preferences** - `/preferences`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📚 Learning Resources",
            value="The bot supports quizzes on virtually any topic - from science to history to pop culture!",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed)
    
    async def _handle_close(self, interaction: discord.Interaction) -> None:
        """Handle close action."""
        await interaction.response.edit_message(
            content="Help menu closed.",
            embed=None,
            view=None
        )