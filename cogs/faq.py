"""FAQ system with interactive UI elements."""

import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Optional, Any, ClassVar
import logging
import datetime
import asyncio

from cogs.base_cog import BaseCog
from utils.ui import create_embed

logger = logging.getLogger("bot.faq")


class FAQView(discord.ui.View):
    """View for handling FAQ pagination with interactivity controls."""
    
    def __init__(self, embeds: List[discord.Embed], author_id: int, timeout: int = 180):
        """
        Initialize the paginated FAQ view.
        
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
        
        # Update page indicators in all embeds
        self._update_embed_footers()
    
    def _update_buttons(self) -> None:
        """Update button states based on current page position."""
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.total_pages - 1
        self.last_page.disabled = self.current_page == self.total_pages - 1
    
    def _update_embed_footers(self) -> None:
        """Update all embed footers with page information."""
        for i, embed in enumerate(self.embeds):
            # Preserve original footer text if it exists
            original_text = embed.footer.text if embed.footer and embed.footer.text else ""
            
            # Add page indicator to footer
            if "Page" not in original_text:
                page_text = f"Page {i + 1}/{self.total_pages}"
                if original_text:
                    embed.set_footer(text=f"{original_text} | {page_text}")
                else:
                    embed.set_footer(text=page_text)
            else:
                # Update existing page indicator
                import re
                pattern = r"Page \d+/\d+"
                replacement = f"Page {i + 1}/{self.total_pages}"
                new_text = re.sub(pattern, replacement, embed.footer.text)
                embed.set_footer(text=new_text)
    
    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.gray, custom_id="first_page")
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to first page button handler."""
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.gray, custom_id="prev_page")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to previous page button handler."""
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.gray, custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to next page button handler."""
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.gray, custom_id="last_page")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to last page button handler."""
        self.current_page = self.total_pages - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(label="Jump to Topic", style=discord.ButtonStyle.primary, custom_id="jump_topic")
    async def jump_topic(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Show a select menu for jumping to specific topics."""
        # Create a select menu with available topics
        topics = []
        for i, embed in enumerate(self.embeds):
            if embed.title:
                topics.append(discord.SelectOption(label=embed.title[:100], value=str(i)))
        
        if not topics:
            async with interaction.channel.typing():
                await interaction.response.send_message("No topics available to jump to.", ephemeral=True)
            return
        
        select = discord.ui.Select(placeholder="Choose a topic...", options=topics[:25])  # Discord limit
        
        async def select_callback(select_interaction: discord.Interaction):
            selected_page = int(select.values[0])
            self.current_page = selected_page
            self._update_buttons()
            await select_interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
            await interaction.delete_original_response()
        
        select.callback = select_callback
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        async with interaction.channel.typing():
            await interaction.response.send_message("Select a topic to jump to:", view=view, ephemeral=True)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Ensure only the command author can use the buttons.
        
        Args:
            interaction: The interaction that triggered this check
            
        Returns:
            bool: Whether the interaction should proceed
        """
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
            logger.warning(f"Failed to update message on timeout: {e}")


class FAQCog(BaseCog, name="FAQ"):
    """
    FAQ system with comprehensive help topics and interactive UI.
    Provides paginated FAQ sections with navigation controls.
    """
    
    def __init__(self, bot: commands.Bot):
        """Initialize the FAQ cog."""
        super().__init__(bot, "FAQ")
        
        # FAQ data structure - can be moved to config or database later
        self.faq_data = self._initialize_faq_data()
    
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle errors for FAQ cog commands."""
        if isinstance(error, commands.MissingRequiredArgument):
            if ctx.command.name == "search":
                embed = create_embed(
                    title="❌ Missing Search Query",
                    description="Please provide a search term to look for in the FAQ.",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="Usage",
                    value="`!search <query>`\n\nExample: `!search quiz start`",
                    inline=False
                )
                async with ctx.typing():
                    await ctx.send(embed=embed)
                return
        
        # Call parent error handler for other errors
        await super().cog_command_error(ctx, error)
    
    def _initialize_faq_data(self) -> Dict[str, Dict[str, Any]]:
        """Initialize the FAQ data structure."""
        return {
            "getting_started": {
                "title": "Getting Started",
                "description": "Essential information for new users",
                "topics": [
                    {
                        "question": "How do I start a quiz?",
                        "answer": "Use `/quiz start <topic>` to begin a quiz. For example: `/quiz start \"Python Programming\"`"
                    },
                    {
                        "question": "What are the difficulty levels?",
                        "answer": "There are three difficulty levels: **easy**, **medium**, and **hard**. Use the difficulty parameter when starting a quiz."
                    },
                    {
                        "question": "How do points work?",
                        "answer": "Points are awarded based on correct answers and response time. Faster correct answers earn more points."
                    }
                ]
            },
            "quiz_features": {
                "title": "Quiz Features",
                "description": "Advanced quiz functionality",
                "topics": [
                    {
                        "question": "What are quiz templates?",
                        "answer": "Templates provide different quiz styles:\n• **standard** - General knowledge\n• **educational** - Learning focused with explanations\n• **challenge** - Difficult questions for experts\n• **trivia** - Fun facts and interesting knowledge"
                    },
                    {
                        "question": "Can I create private quizzes?",
                        "answer": "Yes! Use `/quiz start <topic> is_private:True` to receive questions in your DMs."
                    },
                    {
                        "question": "What LLM providers are available?",
                        "answer": "The bot supports:\n• **OpenAI** (GPT models)\n• **Anthropic** (Claude models)\n• **Google** (Gemini models)\nUse `/quiz providers` to see available options."
                    }
                ]
            },
            "group_features": {
                "title": "Group Features",
                "description": "Multiplayer and server features",
                "topics": [
                    {
                        "question": "How do group quizzes work?",
                        "answer": "Start a group quiz with `/trivia start <topic>`. All participants compete in real-time with a live leaderboard."
                    },
                    {
                        "question": "What are server leaderboards?",
                        "answer": "Each server has its own leaderboard tracking quiz performance. Use `/leaderboard` to view rankings."
                    },
                    {
                        "question": "Can I customize settings for my server?",
                        "answer": "Server admins can use `/settings` to configure bot behavior, default values, and feature toggles."
                    }
                ]
            },
            "statistics": {
                "title": "Statistics & Progress",
                "description": "Tracking your learning journey",
                "topics": [
                    {
                        "question": "How can I view my stats?",
                        "answer": "Use `/stats` to see your quiz statistics including:\n• Total quizzes taken\n• Accuracy percentage\n• Average score\n• Recent performance"
                    },
                    {
                        "question": "What achievements can I earn?",
                        "answer": "Achievements are earned for various milestones:\n• Quiz streaks\n• Perfect scores\n• Topic mastery\n• Participation milestones"
                    },
                    {
                        "question": "How do I check my quiz history?",
                        "answer": "Use `/history` to view your recent quiz attempts with detailed breakdowns."
                    }
                ]
            },
            "troubleshooting": {
                "title": "Troubleshooting",
                "description": "Common issues and solutions",
                "topics": [
                    {
                        "question": "Bot isn't responding to commands",
                        "answer": "Make sure:\n• Bot has proper permissions\n• You're using the correct prefix\n• Commands are properly formatted\n• Try `/help` for command list"
                    },
                    {
                        "question": "Can't start a quiz",
                        "answer": "Common solutions:\n• End any active quiz with `/quiz stop`\n• Check if you have the required permissions\n• Ensure the topic is properly quoted"
                    },
                    {
                        "question": "Error messages during quiz",
                        "answer": "If you encounter errors:\n• Note the error message\n• Try again with different parameters\n• Report persistent issues to admins"
                    }
                ]
            }
        }
    
    def _create_faq_embeds(self) -> List[discord.Embed]:
        """Create paginated embeds for FAQ content."""
        embeds = []
        
        # Create main index page
        index_embed = create_embed(
            title="📚 Educational Quiz Bot FAQ",
            description="Comprehensive guide to using the quiz bot. Navigate through topics using the buttons below.",
            color=discord.Color.blue()
        )
        
        # Add sections to index
        for section_id, section_data in self.faq_data.items():
            index_embed.add_field(
                name=f"📖 {section_data['title']}",
                value=section_data['description'],
                inline=False
            )
        
        index_embed.add_field(
            name="💡 Navigation Tips",
            value="• Use the arrow buttons to navigate\n• Click 'Jump to Topic' for quick access\n• This view times out after 3 minutes",
            inline=False
        )
        
        embeds.append(index_embed)
        
        # Create pages for each section
        for section_id, section_data in self.faq_data.items():
            section_embed = create_embed(
                title=f"📖 {section_data['title']}",
                description=section_data['description'],
                color=discord.Color.blue()
            )
            
            for topic in section_data['topics']:
                section_embed.add_field(
                    name=f"❓ {topic['question']}",
                    value=topic['answer'],
                    inline=False
                )
            
            embeds.append(section_embed)
        
        return embeds
    
    @commands.hybrid_command(name="faq", description="Show frequently asked questions and bot information.")
    async def faq(self, ctx: commands.Context):
        """Show frequently asked questions and bot information with paginated navigation."""
        # Create FAQ embeds
        embeds = self._create_faq_embeds()
        
        # Create paginated view
        view = FAQView(embeds=embeds, author_id=ctx.author.id)
        
        # Send the first page
        async with ctx.typing():
            message = await ctx.send(embed=embeds[0], view=view)
        
        # Store message reference for timeout updates
        view.message = message
    
    
    @commands.hybrid_command(name="search", description="Search FAQ for specific topics.")
    @app_commands.describe(query="The search term to look for in FAQ")
    async def search_faq(self, ctx: commands.Context, query: str):
        """Search FAQ content for specific keywords."""
        query_lower = query.lower()
        results = []
        
        # Search through all FAQ content
        for section_id, section_data in self.faq_data.items():
            for topic in section_data['topics']:
                if (query_lower in topic['question'].lower() or 
                    query_lower in topic['answer'].lower()):
                    results.append({
                        'section': section_data['title'],
                        'question': topic['question'],
                        'answer': topic['answer']
                    })
        
        # Create results embed
        if results:
            embed = create_embed(
                title=f"🔍 Search Results for '{query}'",
                description=f"Found {len(results)} matching topics",
                color=discord.Color.green()
            )
            
            for i, result in enumerate(results[:5]):  # Limit to 5 results
                embed.add_field(
                    name=f"{result['section']}: {result['question']}",
                    value=result['answer'][:200] + "..." if len(result['answer']) > 200 else result['answer'],
                    inline=False
                )
            
            if len(results) > 5:
                embed.add_field(
                    name="More Results",
                    value=f"Found {len(results) - 5} more results. Try a more specific search term.",
                    inline=False
                )
        else:
            embed = create_embed(
                title=f"🔍 No Results for '{query}'",
                description="No matching topics found. Try different keywords or use `/faq` to browse all topics.",
                color=discord.Color.red()
            )
        
        async with ctx.typing():
            await ctx.send(embed=embed)


async def setup_with_context(bot: commands.Bot, context):
    """Set up the FAQ cog with context."""
    from cogs.base_cog import setup_with_context as base_setup
    return await base_setup(bot, context, FAQCog)


async def setup(bot: commands.Bot):
    """Default setup function for Discord.py."""
    # Create the cog but don't set context yet
    # Context will be set by the bot after loading
    cog = FAQCog(bot)
    await bot.add_cog(cog)
    return cog