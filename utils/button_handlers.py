"""
Concrete implementations of persistent button handlers for the quiz bot.

This module contains all the specific button handlers that implement the
PersistentButtonHandler interface for various bot functionality.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from utils.persistent_buttons import PersistentButtonHandler, ButtonState, ButtonType
from utils.context import BotContext


class NavigationButtonHandler(PersistentButtonHandler):
    """Base handler for pagination/navigation buttons."""
    
    def __init__(self, context: BotContext, direction: str, emoji: str, label: str):
        super().__init__(context)
        self.direction = direction
        self.emoji = emoji  
        self.label = label
    
    def get_button_config(self) -> Dict[str, Any]:
        return {
            'style': discord.ButtonStyle.primary,
            'emoji': self.emoji,
            'label': self.label
        }
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        """Handle navigation button interaction."""
        try:
            # Get current page from state data
            current_page = state.data.get('current_page', 0)
            total_pages = state.data.get('total_pages', 1)
            
            # Calculate new page
            if self.direction == 'prev':
                new_page = max(0, current_page - 1)
            elif self.direction == 'next':
                new_page = min(total_pages - 1, current_page + 1)
            elif self.direction == 'first':
                new_page = 0
            elif self.direction == 'last':
                new_page = total_pages - 1
            else:
                new_page = current_page
            
            # Update page data
            state.data['current_page'] = new_page
            
            # Get the appropriate data for this page
            await self._update_page_content(interaction, state, new_page)
            
        except Exception as e:
            await self.on_error(interaction, e, state)
    
    async def _update_page_content(self, interaction: discord.Interaction, state: ButtonState, page: int) -> None:
        """Update the message content for the new page. Override in subclasses."""
        await interaction.response.edit_message(content=f"Page {page + 1}")


class StatsPaginationHandler(NavigationButtonHandler):
    """Handler for stats pagination buttons."""
    
    def __init__(self, context: BotContext, direction: str):
        emoji_map = {
            'prev': '⬅️',
            'next': '➡️',
            'first': '⏮️', 
            'last': '⏭️'
        }
        label_map = {
            'prev': 'Previous',
            'next': 'Next',
            'first': 'First',
            'last': 'Last'
        }
        super().__init__(context, direction, emoji_map[direction], label_map[direction])
    
    async def _update_page_content(self, interaction: discord.Interaction, state: ButtonState, page: int) -> None:
        """Update stats page content."""
        try:
            # Get user ID from state data
            user_id = state.data.get('user_id')
            guild_id = state.guild_id
            
            if not user_id:
                await interaction.response.send_message("Unable to load user stats.", ephemeral=True)
                return
            
            # Get stats data from database
            from services.database_operations.user_stats_ops import get_user_achievements_paginated
            
            achievements_data = await get_user_achievements_paginated(
                self.context.database, user_id, guild_id, page, 5
            )
            
            # Create embed
            embed = discord.Embed(
                title=f"📊 Achievement Progress - Page {page + 1}",
                color=discord.Color.blue()
            )
            
            if achievements_data['achievements']:
                for achievement in achievements_data['achievements']:
                    embed.add_field(
                        name=f"{achievement['emoji']} {achievement['name']}",
                        value=f"{achievement['description']}\nProgress: {achievement['progress']}/{achievement['target']}",
                        inline=False
                    )
            else:
                embed.description = "No achievements found for this page."
            
            # Update button states
            view = self._create_navigation_view(interaction, state, page, achievements_data['total_pages'])
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            self.logger.error(f"Error updating stats page: {e}")
            await interaction.response.send_message("Error loading stats page.", ephemeral=True)
    
    def _create_navigation_view(self, interaction: discord.Interaction, state: ButtonState, current_page: int, total_pages: int) -> discord.ui.View:
        """Create navigation view with updated button states."""
        view = discord.ui.View(timeout=300)
        
        # Add navigation buttons
        if current_page > 0:
            prev_button = discord.ui.Button(
                custom_id=f"stats_prev_{state.message_id}",
                style=discord.ButtonStyle.primary,
                emoji='⬅️',
                label='Previous'
            )
            view.add_item(prev_button)
        
        if current_page < total_pages - 1:
            next_button = discord.ui.Button(
                custom_id=f"stats_next_{state.message_id}",
                style=discord.ButtonStyle.primary,
                emoji='➡️',
                label='Next'
            )
            view.add_item(next_button)
        
        return view


class LeaderboardToggleHandler(PersistentButtonHandler):
    """Handler for leaderboard scope toggle button."""
    
    def get_button_config(self) -> Dict[str, Any]:
        return {
            'style': discord.ButtonStyle.secondary,
            'emoji': '🌐',
            'label': 'Toggle Scope'
        }
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        """Handle leaderboard scope toggle."""
        try:
            # Get current scope from state
            is_global = state.data.get('is_global', False)
            new_scope = not is_global
            
            # Update state
            state.data['is_global'] = new_scope
            
            # Get leaderboard data
            from services.database_operations.leaderboard_ops import get_leaderboard_data
            
            if new_scope:
                # Global leaderboard
                leaderboard_data = await get_leaderboard_data(
                    self.context.database, None, 'total_score', 'all_time', 10
                )
                title = "🌐 Global Leaderboard"
                scope_text = "Global"
            else:
                # Server leaderboard
                leaderboard_data = await get_leaderboard_data(
                    self.context.database, state.guild_id, 'total_score', 'all_time', 10
                )
                title = "🏆 Server Leaderboard"
                scope_text = "Server"
            
            # Create embed
            embed = discord.Embed(title=title, color=discord.Color.gold())
            
            if leaderboard_data:
                leaderboard_text = ""
                for i, entry in enumerate(leaderboard_data, 1):
                    user = self.bot.get_user(entry['user_id'])
                    username = user.display_name if user else f"User {entry['user_id']}"
                    leaderboard_text += f"{i}. {username} - {entry['total_score']} points\n"
                
                embed.description = leaderboard_text
            else:
                embed.description = "No leaderboard data available."
            
            # Update button
            view = discord.ui.View(timeout=300)
            toggle_button = discord.ui.Button(
                custom_id=f"toggle_leaderboard_{state.message_id}",
                style=discord.ButtonStyle.secondary,
                emoji='🌐' if new_scope else '🏠',
                label=f"Switch to {'Server' if new_scope else 'Global'}"
            )
            view.add_item(toggle_button)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            await self.on_error(interaction, e, state)


class WelcomeActionHandler(PersistentButtonHandler):
    """Handler for welcome message action buttons."""
    
    def __init__(self, context: BotContext, action_type: str):
        super().__init__(context)
        self.action_type = action_type
    
    def get_button_config(self) -> Dict[str, Any]:
        configs = {
            'quiz': {
                'style': discord.ButtonStyle.success,
                'emoji': '🎯',
                'label': 'Start Quiz'
            },
            'guide': {
                'style': discord.ButtonStyle.primary,
                'emoji': '📖',
                'label': 'Setup Guide'
            },
            'commands': {
                'style': discord.ButtonStyle.secondary,
                'emoji': '📋',
                'label': 'Commands'
            }
        }
        return configs.get(self.action_type, {})
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        """Handle welcome action button."""
        try:
            if self.action_type == 'quiz':
                embed = discord.Embed(
                    title="🎯 Getting Started with Quizzes",
                    description=(
                        "Here's how to start your first quiz:\n\n"
                        "**Basic Commands:**\n"
                        "`/quiz start <topic>` - Start a quiz on any topic\n"
                        "`/quiz topics` - See popular quiz topics\n"
                        "`/quiz stop` - Stop current quiz\n\n"
                        "**Examples:**\n"
                        "• `/quiz start science` - Science quiz\n"
                        "• `/quiz start history 10 medium` - 10 medium history questions\n"
                        "• `/trivia start` - Group trivia session\n\n"
                        "Try starting your first quiz now!"
                    ),
                    color=discord.Color.green()
                )
                
            elif self.action_type == 'guide':
                embed = discord.Embed(
                    title="📖 Admin Setup Guide",
                    description=(
                        "**Initial Setup:**\n"
                        "1. Set up quiz channels with `/admin setup`\n"
                        "2. Configure server preferences with `/settings`\n"
                        "3. Test the bot with `/quiz start test`\n\n"
                        "**Permissions:**\n"
                        "• Bot needs `Send Messages`, `Embed Links`, `Add Reactions`\n"
                        "• Admins can use `/admin` commands\n"
                        "• Users can use quiz commands in allowed channels\n\n"
                        "**Features:**\n"
                        "• Enable/disable features with `/admin features`\n"
                        "• View server analytics with `/admin analytics`\n"
                        "• Manage user stats and leaderboards"
                    ),
                    color=discord.Color.blue()
                )
                
            elif self.action_type == 'commands':
                embed = discord.Embed(
                    title="📋 Available Commands",
                    color=discord.Color.purple()
                )
                embed.add_field(
                    name="🎯 Quiz Commands",
                    value=(
                        "`/quiz start <topic>` - Start a quiz\n"
                        "`/quiz stop` - Stop current quiz\n"
                        "`/quiz topics` - Popular topics\n"
                        "`/quiz scores` - Your statistics"
                    ),
                    inline=False
                )
                embed.add_field(
                    name="🏆 Trivia & Stats",
                    value=(
                        "`/trivia start` - Group trivia\n"
                        "`/stats` - View your stats\n"
                        "`/leaderboard` - Server rankings\n"
                        "`/history` - Quiz history"
                    ),
                    inline=False
                )
                embed.add_field(
                    name="⚙️ Settings",
                    value=(
                        "`/preferences` - User preferences\n"
                        "`/help` - Detailed help\n"
                        "`/admin` - Admin commands"
                    ),
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self.on_error(interaction, e, state)


class FAQNavigationHandler(NavigationButtonHandler):
    """Handler for FAQ pagination buttons."""
    
    def __init__(self, context: BotContext, direction: str):
        emoji_map = {
            'first': '⏮️',
            'prev': '⬅️',
            'next': '➡️',
            'last': '⏭️'
        }
        label_map = {
            'first': '',
            'prev': '',
            'next': '',
            'last': ''
        }
        super().__init__(context, direction, emoji_map[direction], label_map[direction])
    
    async def _update_page_content(self, interaction: discord.Interaction, state: ButtonState, page: int) -> None:
        """Update FAQ page content."""
        try:
            # Get FAQ data from state
            faq_data = state.data.get('faq_data', [])
            total_pages = len(faq_data)
            
            if page >= total_pages or page < 0:
                await interaction.response.send_message("Invalid page number.", ephemeral=True)
                return
            
            # Get current FAQ item
            faq_item = faq_data[page]
            
            # Create embed
            embed = discord.Embed(
                title=f"❓ {faq_item['question']}",
                description=faq_item['answer'],
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"FAQ {page + 1} of {total_pages}")
            
            # Create navigation view
            view = self._create_faq_navigation_view(state, page, total_pages)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            await self.on_error(interaction, e, state)
    
    def _create_faq_navigation_view(self, state: ButtonState, current_page: int, total_pages: int) -> discord.ui.View:
        """Create FAQ navigation view."""
        view = discord.ui.View(timeout=300)
        
        # First page button
        if current_page > 0:
            first_button = discord.ui.Button(
                custom_id=f"faq_first_{state.message_id}",
                style=discord.ButtonStyle.secondary,
                emoji='⏮️'
            )
            view.add_item(first_button)
        
        # Previous button
        if current_page > 0:
            prev_button = discord.ui.Button(
                custom_id=f"faq_prev_{state.message_id}",
                style=discord.ButtonStyle.primary,
                emoji='⬅️'
            )
            view.add_item(prev_button)
        
        # Next button
        if current_page < total_pages - 1:
            next_button = discord.ui.Button(
                custom_id=f"faq_next_{state.message_id}",
                style=discord.ButtonStyle.primary,
                emoji='➡️'
            )
            view.add_item(next_button)
        
        # Last page button
        if current_page < total_pages - 1:
            last_button = discord.ui.Button(
                custom_id=f"faq_last_{state.message_id}",
                style=discord.ButtonStyle.secondary,
                emoji='⏭️'
            )
            view.add_item(last_button)
        
        return view


class HelpActionHandler(PersistentButtonHandler):
    """Handler for help menu action buttons."""
    
    def __init__(self, context: BotContext, action_type: str):
        super().__init__(context)
        self.action_type = action_type
    
    def get_button_config(self) -> Dict[str, Any]:
        configs = {
            'guide': {
                'style': discord.ButtonStyle.success,
                'emoji': '📘',
                'label': 'Commands Guide'
            },
            'support': {
                'style': discord.ButtonStyle.primary,
                'emoji': '🎧',
                'label': 'Support'
            },
            'menu': {
                'style': discord.ButtonStyle.secondary,
                'emoji': '📋',
                'label': 'Main Menu'
            },
            'close': {
                'style': discord.ButtonStyle.danger,
                'emoji': '❌',
                'label': 'Close'
            }
        }
        return configs.get(self.action_type, {})
    
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        """Handle help action button."""
        try:
            if self.action_type == 'close':
                # Delete the message
                await interaction.response.edit_message(
                    content="Help menu closed.",
                    embed=None,
                    view=None
                )
                return
            
            # For other actions, show appropriate content
            if self.action_type == 'guide':
                embed = await self._create_commands_guide_embed()
            elif self.action_type == 'support':
                embed = await self._create_support_embed()
            elif self.action_type == 'menu':
                embed = await self._create_main_menu_embed()
            else:
                embed = discord.Embed(title="Unknown Action", color=discord.Color.red())
            
            await interaction.response.edit_message(embed=embed)
            
        except Exception as e:
            await self.on_error(interaction, e, state)
    
    async def _create_commands_guide_embed(self) -> discord.Embed:
        """Create commands guide embed."""
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
        
        return embed
    
    async def _create_support_embed(self) -> discord.Embed:
        """Create support information embed."""
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
        
        return embed
    
    async def _create_main_menu_embed(self) -> discord.Embed:
        """Create main menu embed."""
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
        
        return embed