"""User statistics and leaderboard commands."""

import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Optional, Any, Literal, ClassVar
import logging
import datetime

from cogs.base_cog import BaseCog
from cogs.utils.embeds import create_base_embed, create_success_embed, create_error_embed
from cogs.utils.decorators import require_context, in_guild_only, cooldown_with_bypass
from cogs.utils.permissions import check_admin_permissions
from utils.progress_bars import create_progress_bar, create_xp_bar, create_accuracy_bar, create_level_display, create_streak_display, get_rank_emoji

# Import database operation functions
from services.database_operations.leaderboard_ops import get_formatted_leaderboard
from services.database_operations.user_stats_ops import get_formatted_user_stats
from services.database_operations.history_ops import get_formatted_quiz_history
from services.database_operations.analytics_ops import get_formatted_server_analytics
from services.database_operations.achievement_ops import get_user_achievements


class StatsPaginatedView(discord.ui.View):
    """View for paginated stats display."""
    
    def __init__(self, embeds: List[discord.Embed], author_id: int, timeout: int = 180):
        """
        Initialize the paginated stats view.
        
        Args:
            embeds: List of embed pages to display
            author_id: ID of the user who initiated the command
            timeout: Time in seconds before the view times out
        """
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0
        self.total_pages = len(embeds)
        self.author_id = author_id
        
        # Update button states for initial view
        self._update_buttons()
    
    def _update_buttons(self) -> None:
        """Update button states based on current page position."""
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.total_pages - 1
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use the buttons."""
        if interaction.user.id != self.author_id:
            async with interaction.channel.typing():
                await interaction.response.send_message(
                    "You cannot use these controls as you didn't run the command.",
                    ephemeral=True
                )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Handle view timeout by disabling all buttons."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        
        # Try to update the message if possible
        try:
            message = self.message
            if message:
                await message.edit(view=self)
        except Exception as e:
            logger = logging.getLogger("bot.stats")
            logger.warning(f"Failed to update message on timeout: {e}")
    
    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.gray, custom_id="stats_prev_page")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to previous page button handler."""
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.gray, custom_id="stats_next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to next page button handler."""
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)


class StatsCog(BaseCog):
    """User statistics and leaderboard commands."""
    
    # Class variables for embed customization
    EMBED_COLORS: ClassVar[Dict[str, discord.Color]] = {
        "stats": discord.Color.blue(),
        "leaderboard": discord.Color.gold(),
        "history": discord.Color.green(),
        "achievements": discord.Color.purple(),
        "analytics": discord.Color.teal(),
        "admin": discord.Color.red()
    }
    
    def __init__(self, bot: commands.Bot):
        """Initialize the stats cog."""
        super().__init__(bot, name="Stats")
    
    def _create_embed(self, title: str, description: str, color_key: str = "stats") -> discord.Embed:
        """Create a standardized embed with consistent styling."""
        color = self.EMBED_COLORS.get(color_key, discord.Color.blue())
        return create_base_embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.now()
        )
    
    def _create_stats_embeds(self, user: discord.Member, stats: Dict[str, Any]) -> List[discord.Embed]:
        """Create stats embed pages for a user."""
        embeds = []
        
        # Ensure stats is a standard dictionary
        if not isinstance(stats, dict):
            self.logger.error(f"Stats object is not a dictionary: {type(stats)}")
            try:
                # Try to convert to a regular dict if it's dict-like
                stats = dict(stats)
                self.logger.info("Successfully converted stats to regular dictionary")
            except Exception as e:
                self.logger.error(f"Failed to convert stats to dictionary: {e}")
                # Create a fallback stats object
                stats = {
                    "user_id": user.id,
                    "overall": {},
                    "by_difficulty": [],
                    "by_category": [],
                    "recent_activity": []
                }
        
        # Page 1: Overview
        overview_embed = self._create_embed(
            f"📊 Stats for {user.display_name}",
            "User quiz statistics and performance overview.",
            "stats"
        )
        
        # Set user avatar as thumbnail
        overview_embed.set_thumbnail(url=user.display_avatar.url)
        
        # Add overall stats - ensure this is a regular dict
        overall_raw = stats.get("overall", {})
        # Convert to regular dict if necessary
        overall = dict(overall_raw) if hasattr(overall_raw, "items") else {}
        
        if overall:
            total_quizzes = overall.get("total_quizzes", 0)
            total_correct = overall.get("correct_answers", 0)
            total_wrong = overall.get("wrong_answers", 0)
            total_points = overall.get("total_points", 0)
            accuracy = overall.get("accuracy", 0)
            current_level = overall.get("current_level", 1)
            xp = overall.get("current_xp", 0)
            xp_needed = overall.get("xp_for_next_level", 100)
            streak = overall.get("current_streak", 0)
            best_streak = overall.get("best_streak", 0)
            
            # Create visual level display (includes progress bar)
            level_display = create_level_display(current_level, xp, xp_needed, use_emoji=True)
            
            # Create accuracy visual bar
            accuracy_bar = create_accuracy_bar(total_correct, total_correct + total_wrong, use_emoji=True)
            
            # Create streak display with flame emoji
            streak_display = create_streak_display(streak, best_streak)
            
            # Split overview into multiple fields to avoid Discord's 1024 character limit
            # Field 1: Level and XP
            overview_embed.add_field(
                name="📈 Level Progress",
                value=level_display,
                inline=False
            )
            
            # Field 2: Quiz stats
            overview_embed.add_field(
                name="🎯 Quiz Performance",
                value=(
                    f"**Quizzes Completed:** {total_quizzes}\n"
                    f"**Total Points:** {total_points:,} 🏆\n"
                    f"**Accuracy:** {accuracy}%\n"
                    f"{accuracy_bar}"
                ),
                inline=False
            )
            
            # Field 3: Streak
            overview_embed.add_field(
                name="🔥 Streak",
                value=f"{streak_display}",
                inline=False
            )
        else:
            overview_embed.add_field(
                name="📈 Overview",
                value="No quiz data available yet. Start a quiz to see your stats!",
                inline=False
            )
        
        # Add recent activity - ensure this is a regular list
        recent_raw = stats.get("recent_activity", [])
        # Convert to list of dicts if necessary
        recent = [dict(item) for item in recent_raw] if recent_raw and hasattr(recent_raw, "__iter__") else []
        
        if recent:
            recent_text = []
            for i, activity in enumerate(recent[:3]):  # Show top 3
                topic = activity.get("topic", "Unknown")
                correct = activity.get("correct_answers", 0)
                wrong = activity.get("wrong_answers", 0)
                points = activity.get("points", 0)
                difficulty = activity.get("difficulty", "Unknown").capitalize()
                
                recent_text.append(
                    f"**{i+1}.** {topic} ({difficulty}) - {correct} correct, {wrong} wrong, {points} points"
                )
            
            overview_embed.add_field(
                name="🕒 Recent Activity",
                value="\n".join(recent_text) if recent_text else "No recent activity",
                inline=False
            )
        
        embeds.append(overview_embed)
        
        # Page 2: Performance by difficulty
        difficulty_embed = self._create_embed(
            f"📊 Performance by Difficulty",
            f"How {user.display_name} performs across different difficulty levels.",
            "stats"
        )
        
        difficulty_embed.set_thumbnail(url=user.display_avatar.url)
        
        # Ensure by_difficulty is a regular list
        by_difficulty_raw = stats.get("by_difficulty", [])
        # Convert to list of dicts if necessary
        by_difficulty = [dict(item) for item in by_difficulty_raw] if by_difficulty_raw and hasattr(by_difficulty_raw, "__iter__") else []
        
        if by_difficulty:
            try:
                for difficulty_stat in sorted(by_difficulty, key=lambda x: {"easy": 1, "medium": 2, "hard": 3}.get(x.get("difficulty", ""), 4)):
                    difficulty = difficulty_stat.get("difficulty", "unknown").capitalize()
                    quizzes = difficulty_stat.get("quizzes", 0)
                    correct = difficulty_stat.get("correct", 0)
                    wrong = difficulty_stat.get("wrong", 0)
                    points = difficulty_stat.get("points", 0)
                    
                    total = correct + wrong
                    accuracy = round((correct / total) * 100, 1) if total > 0 else 0
                    
                    emoji = "🟢" if difficulty.lower() == "easy" else "🟡" if difficulty.lower() == "medium" else "🔴"
                    
                    # Create visual accuracy bar for each difficulty
                    accuracy_visual = create_accuracy_bar(correct, total, use_emoji=True)
                    
                    difficulty_embed.add_field(
                        name=f"{emoji} {difficulty}",
                        value=(
                            f"**Quizzes:** {quizzes}\n"
                            f"**Points:** {points}\n"
                            f"**Correct/Wrong:** {correct}/{wrong}\n"
                            f"**Accuracy:** {accuracy}%\n"
                            f"{accuracy_visual}"
                        ),
                        inline=True
                        )
            except Exception as e:
                self.logger.error(f"Error processing difficulty stats: {e}")
                difficulty_embed.add_field(
                    name="Error",
                    value="There was an error processing difficulty stats.",
                    inline=False
                )
        else:
            difficulty_embed.add_field(
                name="No Data",
                value="You haven't completed any quizzes yet. Start playing to see your performance!",
                inline=False
            )
        
        embeds.append(difficulty_embed)
        
        # Page 3: Performance by category
        category_embed = self._create_embed(
            f"📊 Performance by Category",
            f"How {user.display_name} performs across different knowledge categories.",
            "stats"
        )
        
        category_embed.set_thumbnail(url=user.display_avatar.url)
        
        # Ensure by_category is a regular list
        by_category_raw = stats.get("by_category", [])
        # Convert to list of dicts if necessary
        by_category = [dict(item) for item in by_category_raw] if by_category_raw and hasattr(by_category_raw, "__iter__") else []
        
        if by_category:
            try:
                # Sort categories by quiz count
                sorted_categories = sorted(by_category, key=lambda x: x.get("quizzes", 0), reverse=True)
                
                for category_stat in sorted_categories[:6]:  # Show top 6 categories
                    category = category_stat.get("category", "unknown").capitalize()
                    quizzes = category_stat.get("quizzes", 0)
                    correct = category_stat.get("correct", 0)
                    wrong = category_stat.get("wrong", 0)
                    points = category_stat.get("points", 0)
                    
                    total = correct + wrong
                    accuracy = round((correct / total) * 100, 1) if total > 0 else 0
                    
                    # Create mini progress bar for accuracy
                    accuracy_mini = create_progress_bar(int(accuracy), 100, length=5, filled_char="▰", empty_char="▱", use_emoji=True)
                    
                    category_embed.add_field(
                        name=f"{category}",
                        value=(
                            f"**Quizzes:** {quizzes}\n"
                            f"**Points:** {points}\n"
                            f"**Accuracy:** {accuracy}%\n"
                            f"{accuracy_mini}"
                        ),
                        inline=True
                        )
            except Exception as e:
                self.logger.error(f"Error processing category stats: {e}")
                category_embed.add_field(
                    name="Error",
                    value="There was an error processing category stats.",
                    inline=False
                )
        else:
            category_embed.add_field(
                name="No Data",
                value="You haven't completed any quizzes yet. Start playing to see your category performance!",
                inline=False
            )
        
        embeds.append(category_embed)
        
        # Add page indicators with help text
        for i, embed in enumerate(embeds):
            footer_text = f"Page {i+1}/{len(embeds)} • "
            if i == 0:
                footer_text += "Progress bars show your advancement"
            elif i == 1:
                footer_text += "Colored indicators show difficulty levels"
            elif i == 2:
                footer_text += "Visual bars represent accuracy rates"
            embed.set_footer(text=footer_text)
        
        return embeds
    
    def _create_leaderboard_embed(self, leaderboard: List[Dict[str, Any]], 
                               scope: Literal["server", "global"] = "server",
                               guild_name: Optional[str] = None, 
                               # category: Optional[str] = None, # Keep placeholders for future
                               # timeframe: str = "all-time" # Keep placeholders for future
                               ) -> discord.Embed:
        """Create a leaderboard embed with scope awareness and emojis."""
        
        # Determine title and description based on scope
        if scope == "server":
            scope_name = f"in {guild_name}" if guild_name else "in this server"
            title = f"🏆 Server Quiz Leaderboard ({guild_name or 'Current Server'})"
        else:
            scope_name = "globally"
            title = "🏆 Global Quiz Leaderboard"
            
        # Base description
        description = f"Top quiz performers {scope_name}."
        
        # Create embed
        embed = self._create_embed(
            title,
            description,
            "leaderboard"
        )
        
        # Ensure leaderboard is a list of dicts
        processed_leaderboard = []
        if isinstance(leaderboard, list):
            for i, entry_raw in enumerate(leaderboard):
                try:
                    entry = dict(entry_raw) if not isinstance(entry_raw, dict) else entry_raw
                    # Add rank if not present (assuming list is sorted)
                    entry['rank'] = i + 1 
                    processed_leaderboard.append(entry)
                except Exception as e:
                    self.logger.error(f"Failed to convert leaderboard entry to dict or add rank: {e} - Entry: {entry_raw}")
        else:
             self.logger.error(f"Leaderboard data provided is not a list: {type(leaderboard)}")

        if processed_leaderboard:
            leaderboard_text = []
            for entry in processed_leaderboard:
                try:
                    rank = entry.get("rank", 0)
                    username = entry.get("username", "Unknown")
                    points = entry.get("points", 0)
                    correct = entry.get("correct_answers", 0)
                    quizzes = entry.get("quizzes_taken", 0)
                    
                    # Add medal emoji for top 3
                    medal = ""
                    if rank == 1:
                        medal = "🥇 "
                    elif rank == 2:
                        medal = "🥈 "
                    elif rank == 3:
                        medal = "🥉 "
                    
                    # Enhanced display with more stats
                    # Calculate average accuracy for this user
                    total_questions = correct + (quizzes * 10 - correct)  # Assuming 10 questions per quiz as default
                    avg_accuracy = round((correct / total_questions) * 100) if total_questions > 0 else 0
                    
                    leaderboard_text.append(
                        f"{medal}**{rank}.** {username} - {points} points | {quizzes} quizzes | {avg_accuracy}% accuracy"
                    )
                except Exception as e:
                    self.logger.error(f"Error processing leaderboard entry: {e} - Entry: {entry}")
            
            if leaderboard_text:
                embed.add_field(
                        name="📊 Rankings",
                        value="\n".join(leaderboard_text),
                    inline=False
                )
            else:
                 # This case should be rare if processed_leaderboard was not empty
                 embed.description += "\n\nCould not format leaderboard entries."
                 embed.add_field(name="No Data", value=f"No rankings available {scope_name}.", inline=False)
        else:
            # Update description and add field if no data
            embed.description += "\n\nThe leaderboard is currently empty."
            if scope == "server":
                embed.add_field(
                    name="🎮 Getting Started", 
                    value=(
                        f"No quiz data for this server yet!\n\n"
                        f"Start your first quiz with `/quiz start <topic>` or "
                        f"`/trivia start <topic>` to begin climbing the leaderboard!"
                    ),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎮 Getting Started", 
                    value=f"No global quiz data yet! Be the first to complete a quiz and claim the top spot!",
                    inline=False
                )
        
        return embed
    
    def _create_history_embeds(self, user: discord.Member, history: List[Dict[str, Any]]) -> List[discord.Embed]:
        """Create quiz history embeds for a user."""
        embeds = []
        
        # Create main embed
        history_embed = self._create_embed(
            f"📜 Quiz History for {user.display_name}",
            "Recent quiz sessions and results.",
            "history"
        )
        
        history_embed.set_thumbnail(url=user.display_avatar.url)
        
        if history:
            # Group quizzes by date (YYYY-MM-DD)
            grouped_history = {}
            for entry in history:
                date_str = entry.get("date", "")
                if date_str:
                    date_key = date_str.split("T")[0]  # Get YYYY-MM-DD part
                    if date_key not in grouped_history:
                        grouped_history[date_key] = []
                    grouped_history[date_key].append(entry)
            
            # Add each date group as a field
            for date_key, entries in sorted(grouped_history.items(), reverse=True):
                try:
                    date_obj = datetime.datetime.fromisoformat(date_key)
                    date_display = date_obj.strftime("%B %d, %Y")
                except:
                    date_display = date_key
                
                entries_text = []
                for entry in entries:
                    topic = entry.get("topic", "Unknown")
                    difficulty = entry.get("difficulty", "unknown").capitalize()
                    correct = entry.get("correct", 0)
                    wrong = entry.get("wrong", 0)
                    points = entry.get("points", 0)
                    
                    # Add difficulty emoji
                    diff_emoji = "🟢" if difficulty.lower() == "easy" else "🟡" if difficulty.lower() == "medium" else "🔴"
                    
                    # Calculate accuracy
                    total = correct + wrong
                    accuracy = round((correct / total) * 100) if total > 0 else 0
                    
                    entries_text.append(
                        f"• **{topic}** {diff_emoji} ({difficulty})\n"
                        f"  {correct}✅ {wrong}❌ • {points} pts • {accuracy}% accuracy"
                    )
                
                history_embed.add_field(
                    name=date_display,
                    value="\n".join(entries_text),
                    inline=False
                )
        else:
            history_embed.add_field(
                name="No History",
                value="You haven't completed any quizzes yet. Start playing to build your quiz history!",
                inline=False
            )
        
        embeds.append(history_embed)
        
        return embeds
    
    def _create_analytics_embeds(self, guild: discord.Guild, analytics: Dict[str, Any], include_global: bool = False) -> List[discord.Embed]:
        """Create analytics embed pages for server usage."""
        embeds = []
        
        # Page 1: Server Overview
        overview_embed = self._create_embed(
            f"📊 Analytics for {guild.name}",
            "Server quiz and usage analytics.",
            "analytics"
        )
        
        # Set server icon as thumbnail
        overview_embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        
        # Add server overview
        server_stats = analytics.get("server", {})
        if server_stats:
            total_quizzes = server_stats.get("total_quizzes", 0)
            total_questions = server_stats.get("total_questions", 0)
            unique_users = server_stats.get("unique_users", 0)
            most_popular_category = server_stats.get("most_popular_category", "N/A")
            
            overview_embed.add_field(
                name="📈 Server Overview",
                value=(
                    f"**Quizzes Completed:** {total_quizzes}\n"
                    f"**Questions Answered:** {total_questions}\n"
                    f"**Unique Users:** {unique_users}\n"
                    f"**Most Popular Category:** {most_popular_category}"
                ),
                inline=False
            )
        else:
            overview_embed.add_field(
                name="📈 Server Overview",
                value="No quiz data available yet. Encourage users to start quizzes!",
                inline=False
            )
        
        # Add usage metrics
        usage = analytics.get("usage", {})
        if usage:
            channel_count = len(guild.text_channels)
            active_channels = usage.get("active_channels", 0)
            
            active_channel_percent = round((active_channels / channel_count) * 100, 1) if channel_count > 0 else 0
            
            overview_embed.add_field(
                name="📊 Usage Metrics",
                value=(
                    f"**Active Channels:** {active_channels}/{channel_count} ({active_channel_percent}%)\n"
                    f"**Commands Used:** {usage.get('commands_used', 0)}\n"
                    f"**Command Success Rate:** {usage.get('command_success_rate', 0)}%\n"
                    f"**Most Used Command:** {usage.get('most_used_command', 'N/A')}"
                ),
                inline=False
            )
        
        # Add bot activity period
        if include_global and hasattr(self.bot, 'uptime'):
            uptime = datetime.datetime.now() - self.bot.uptime
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
            
            overview_embed.add_field(
                name="🤖 Bot Information",
                value=(
                    f"**Uptime:** {uptime_str}\n"
                    f"**Active Servers:** {len(self.bot.guilds)}\n"
                    f"**Total Users:** {sum(g.member_count for g in self.bot.guilds)}\n"
                    f"**Global Commands Used:** {analytics.get('global', {}).get('total_commands', 0)}"
                ),
                inline=False
            )
        
        embeds.append(overview_embed)
        
        # Page 2: Category Analytics
        category_embed = self._create_embed(
            f"📊 Category Analytics",
            f"Quiz category statistics for {guild.name}.",
            "analytics"
        )
        
        category_embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        
        categories = analytics.get("categories", [])
        if categories:
            for i, category in enumerate(sorted(categories, key=lambda x: x.get("quizzes", 0), reverse=True)):
                if i >= 6:  # Only show top 6 categories
                    break
                    
                name = category.get("name", "Unknown").capitalize()
                quizzes = category.get("quizzes", 0)
                questions = category.get("questions", 0)
                correct_rate = category.get("correct_rate", 0)
                
                # Visual representation of correct answer rate
                correct_visual = create_progress_bar(int(correct_rate), 100, length=5, use_emoji=True)
                
                category_embed.add_field(
                    name=f"{name}",
                    value=(
                        f"**Quizzes:** {quizzes}\n"
                        f"**Questions:** {questions}\n"
                        f"**Correct Rate:** {correct_rate}%\n"
                        f"{correct_visual}"
                    ),
                inline=True
            )
        else:
            category_embed.add_field(
                name="No Data",
                value="No category data available yet.",
                inline=False
            )
        
        embeds.append(category_embed)
        
        # Add a new server activity embed if the user is an admin and global stats requested
        if include_global and self.bot.owner_id == guild.owner_id:
            server_activity_embed = self._create_embed(
                "🌐 Global Server Analytics",
                "Information about all servers where the bot is active.",
                "analytics"
            )
            
            # Get server activity data
            active_servers = self.bot.guilds
            
            # Sort servers by member count
            sorted_servers = sorted(active_servers, key=lambda g: g.member_count, reverse=True)
            
            # Display global stats
            server_activity_embed.add_field(
                name="📊 Global Stats",
                value=(
                    f"**Total Servers:** {len(active_servers)}\n"
                    f"**Total Users:** {sum(g.member_count for g in active_servers)}\n"
                    f"**Average Users Per Server:** {sum(g.member_count for g in active_servers) // len(active_servers) if active_servers else 0}"
                ),
                inline=False
            )
            
            # Display top 6 servers by size
            server_list = []
            for i, server in enumerate(sorted_servers[:6]):
                server_list.append(
                    f"**{i+1}.** {server.name} - {server.member_count} members"
                )
            
            if server_list:
                server_activity_embed.add_field(
                    name="🔝 Top Servers by Size",
                    value="\n".join(server_list),
                    inline=False
                )
            
            # Add recently joined servers
            recent_servers = sorted(active_servers, key=lambda g: g.me.joined_at or datetime.datetime.now(), reverse=True)
            recent_list = []
            
            for i, server in enumerate(recent_servers[:3]):
                joined_at = server.me.joined_at or datetime.datetime.now()
                days_ago = (datetime.datetime.now(datetime.timezone.utc) - joined_at).days
                recent_list.append(
                    f"**{i+1}.** {server.name} - {server.member_count} members, joined {days_ago} days ago"
                )
            
            if recent_list:
                server_activity_embed.add_field(
                    name="🆕 Recently Joined Servers",
                    value="\n".join(recent_list),
                    inline=False
                )
            
            embeds.append(server_activity_embed)
        
        return embeds
    
    @commands.hybrid_command(name="stats", description="View your quiz statistics and learning progress.")
    @app_commands.describe(user="The user to view stats for (defaults to yourself)")
    @require_context
    @cooldown_with_bypass(rate=3, per=60, bypass_roles=["admin", "moderator", "bot_admin"])
    async def stats(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """View quiz statistics for a user."""
        target_user = user or ctx.author
        
        try:
            # Use the new operations function to get stats
            stats_data = await get_formatted_user_stats(self.db_service, target_user.id)

            if not stats_data:
                # Handle case where no stats are found
                no_stats_embed = self._create_embed(
                    f"📊 Stats for {target_user.display_name}",
                    f"{target_user.mention} hasn't completed any quizzes yet, or no detailed stats are recorded.",
                    "stats"
                )
                no_stats_embed.set_thumbnail(url=target_user.display_avatar.url)
                async with ctx.typing():
                    await ctx.send(embed=no_stats_embed)
                return

            # Create embeds using the fetched data
            embeds = self._create_stats_embeds(target_user, stats_data)
            if not embeds:
                 error_embed = create_error_embed(
                     description=f"Could not generate stats display for {target_user.display_name}."
                 )
                 async with ctx.typing():
                     await ctx.send(embed=error_embed)
                 return
                 
            view = StatsPaginatedView(embeds, ctx.author.id)
            async with ctx.typing():
                view.message = await ctx.send(embed=embeds[0], view=view)
                
        except Exception as e:
            self.logger.error(f"Error in stats command for {target_user.id}: {e}", exc_info=True)
            error_embed = create_error_embed(
                description="An error occurred while fetching stats. Please try again later."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed)

    @commands.hybrid_command(name="leaderboard", description="View the quiz leaderboard.")
    @app_commands.describe(
        limit="Number of users to show (default: 10)",
        scope="Leaderboard scope (server or global, default: server)"
        # category="Filter leaderboard by category (optional)", # TODO
        # timeframe="Timeframe (all-time, weekly, monthly) (optional)" # TODO
    )
    @require_context
    @cooldown_with_bypass(rate=3, per=60, bypass_roles=["admin", "moderator", "bot_admin"])
    async def leaderboard(self, ctx: commands.Context, 
                         limit: int = 10, 
                         scope: Literal["server", "global"] = "server"):
        """Display the quiz leaderboard for the server or globally."""
        limit = max(1, min(limit, 25)) # Clamp limit between 1 and 25
         
        current_guild_id = ctx.guild.id if ctx.guild else None
        guild_name = ctx.guild.name if ctx.guild else None
         
         # Server scope requires being in a guild
        if scope == "server" and not current_guild_id:
            error_embed = create_error_embed(
                description="Server leaderboard can only be viewed within a server."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed)
            return
        
        try:
             # Determine guild_id to pass based on scope
            target_guild_id = current_guild_id if scope == "server" else None
             
            self.logger.info(f"Requesting leaderboard: scope={scope}, guild_id={target_guild_id}, limit={limit}")

             # Use the operations function, passing the target guild_id
            leaderboard_data = get_formatted_leaderboard(
                 db_service=self.db_service, 
                 limit=limit,
                 guild_id=target_guild_id
                 # category=category, # Pass if using
                 # timeframe=timeframe # Pass if using
                )
                
             # Create embed using the data and scope
            embed = self._create_leaderboard_embed(
                 leaderboard=leaderboard_data,
                 scope=scope,
                 guild_name=guild_name # Pass guild name for context in embed
             )
            async with ctx.typing():
                await ctx.send(embed=embed)         
        except Exception as e:
            self.logger.error(f"Error in leaderboard command (scope: {scope}): {e}", exc_info=True)
            error_embed = create_error_embed(
                description="An error occurred while fetching the leaderboard."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed)

    @commands.hybrid_command(name="history", description="View your quiz history.")
    @require_context
    @cooldown_with_bypass(rate=3, per=60, bypass_roles=["admin", "moderator", "bot_admin"])
    async def history(self, ctx: commands.Context):
        """Show a user's quiz history with detailed statistics."""
        target_user = ctx.author
        # Send typing indicator while fetching history
        async with ctx.typing():
            try:
                self.logger.info(f"Fetching history for user: {target_user.id} ({target_user.display_name}) via StatsCog")
                # Use the new operations function
                history_data = await get_formatted_quiz_history(self.db_service, target_user.id)
                
                # Create history embeds
                # The _create_history_embeds function expects a list of dicts, which get_formatted_quiz_history provides.
                history_embeds = self._create_history_embeds(target_user, history_data)
                
                if not history_embeds: # Should only happen if _create_history_embeds has issues
                     self.logger.error(f"_create_history_embeds returned empty list for user {target_user.id}")
                     error_embed = create_error_embed(
                         description="Could not display quiz history."
                     )
                     await ctx.send(embed=error_embed)
                     return
                
                # Create paginated view if multiple pages (usually only 1 page for history)
                if len(history_embeds) > 1:
                    view = StatsPaginatedView(history_embeds, target_user.id)
                    message = await ctx.send(embed=history_embeds[0], view=view)
                    view.message = message
                elif history_embeds: # Check if list is not empty
                    await ctx.send(embed=history_embeds[0])
                # If history_data was empty, _create_history_embeds should handle the "No History" message inside the embed.
                
            except Exception as e:
                self.logger.error(f"Error in history command for {target_user.id}: {e}", exc_info=True)
                error_embed = create_error_embed(
                    description="Error fetching quiz history. Please try again later."
                )
                await ctx.send(embed=error_embed, ephemeral=True)
    
    @commands.hybrid_command(name="analytics", description="View bot usage analytics for your server.")
    @app_commands.checks.has_permissions(administrator=True)
    @require_context
    @in_guild_only
    async def analytics(self, ctx: commands.Context, show_global: bool = False):
        """
        View usage analytics for this server.
        
        Args:
            show_global: Whether to include global statistics (bot owner only)
        """
        # Check permissions for global stats
        include_global = show_global
        is_owner = await self.bot.is_owner(ctx.author)
        if show_global and not is_owner:
            include_global = False
            async with ctx.typing():
                await ctx.send("⚠️ Only the bot owner can view global statistics. Showing server statistics only.", ephemeral=True)
        
        try:
            # Use the new operations function to get cleaned analytics data
            analytics_data = await get_formatted_server_analytics(self.db_service, ctx.guild.id)

            if not analytics_data:
                self.logger.warning(f"No analytics data returned for guild {ctx.guild.id} from analytics_ops")
                async with ctx.typing():
                    await ctx.send("📊 No analytics data available for this server yet.")
                return
            
            # Create embeds (passing include_global for potential owner-specific sections)
            # Note: _create_analytics_embeds needs the owner check logic if it adds owner-only fields.
            # It might be cleaner to pass is_owner flag to _create_analytics_embeds as well.
            embeds = self._create_analytics_embeds(ctx.guild, analytics_data, include_global)
            
            if not embeds:
                error_embed = create_error_embed(
                    description="Failed to generate analytics display. No data available."
                )
                async with ctx.typing():
                    await ctx.send(embed=error_embed)
                return
                
            # Send the paginated view
            view = StatsPaginatedView(embeds, ctx.author.id)
            async with ctx.typing():
                response = await ctx.send(embed=embeds[0], view=view)
            view.message = response
                
        except Exception as e:
            self.logger.error(f"Error in analytics command for guild {ctx.guild.id}: {e}", exc_info=True)
            error_embed = create_error_embed(
                description="An error occurred while retrieving analytics."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed)
    
    @commands.hybrid_command(name="active_servers", description="View information about all active servers (bot owner only).")
    @commands.is_owner()
    async def active_servers(self, ctx: commands.Context):
        """
        View information about all servers where the bot is active.
        This command is restricted to the bot owner.
        """
        if not await self.bot.is_owner(ctx.author):
            error_embed = create_error_embed(
                description="This command is restricted to the bot owner."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed)
            return
            
        try:
            # Create an embed to display server information
            embed = self._create_embed(
                "🌐 Active Servers Overview",
                "Information about all servers where the bot is active.",
                "analytics"
            )
            
            # Get all active servers
            active_servers = self.bot.guilds
            
            # Display summary statistics
            embed.add_field(
                name="📊 Summary",
                value=(
                    f"**Total Servers:** {len(active_servers)}\n"
                    f"**Total Users:** {sum(g.member_count for g in active_servers)}\n"
                    f"**Average Users Per Server:** {sum(g.member_count for g in active_servers) // len(active_servers) if active_servers else 0}"
                ),
                inline=False
            )
            
            # Sort servers by member count
            sorted_servers = sorted(active_servers, key=lambda g: g.member_count, reverse=True)
            
            # Display top 10 servers by size
            server_list = []
            for i, server in enumerate(sorted_servers[:10]):
                server_list.append(
                    f"**{i+1}.** {server.name} - {server.member_count} members"
                )
            
            if server_list:
                embed.add_field(
                    name="🔝 Top Servers by Size",
                    value="\n".join(server_list),
                    inline=False
                )
            
            # Send the embed
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in active_servers command: {e}", exc_info=True)
            error_embed = create_error_embed(
                description=f"An error occurred while retrieving server information: {e}"
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed)

    async def cog_check(self, ctx):
        """Check if the user can run stats commands."""
        # Check if this is an admin command by name pattern
        # instead of checking for a non-existent admin_group attribute
        if ctx.command.name in ["active_servers", "analytics"]:
            # For admin commands, check permissions
            if not ctx.guild and ctx.command.name == "analytics":
                return False
                
            # Check if user is a bot owner
            if await self.bot.is_owner(ctx.author):
                return True
                
            # Check if user has administrator permission
            if ctx.guild and ctx.author.guild_permissions.administrator:
                return True
                
            error_embed = create_error_embed(
                description="You don't have permission to use admin commands."
            )
            async with ctx.typing():
                await ctx.send(embed=error_embed)
            return False
        
        # For regular stats commands, allow everyone
        return True


async def setup(bot: commands.Bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(StatsCog(bot))


async def setup_with_context(bot: commands.Bot, context: Any) -> commands.Cog:
    """Setup function that uses the context pattern."""
    cog = StatsCog(bot)
    cog.set_context(context)
    await bot.add_cog(cog)
    return cog