"""Quiz commands for educational learning through LLM-generated questions."""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import time
from typing import Dict, List, Optional, Literal
import logging
from datetime import datetime, timedelta

from discord import Embed, Color, User, Member
from cogs.base_cog import BaseCog
from cogs.models.quiz_models import ActiveQuiz, QuizState, QuizParticipant
from services import llm_service, Question, quiz_generator
from services.database_operations.quiz_stats_ops import record_complete_quiz_result_for_user
from utils.ui import create_embed, create_progress_bar, get_color_for_difficulty, format_leaderboard_entry, REACTION_EMOJIS
from cogs.utils.decorators import require_context, in_guild_only, cooldown_with_bypass

logger = logging.getLogger("bot.quiz")


class QuizCog(BaseCog, name="Quiz"):
    """Quiz commands for educational learning through LLM-generated questions."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the quiz cog."""
        super().__init__(bot, "Quiz")
        
        # Quiz-specific attributes
        self.active_quizzes: Dict[tuple[int, int], ActiveQuiz] = {}  # (guild_id, channel_id) -> ActiveQuiz
        self.user_settings: Dict[int, Dict] = {}  # user_id -> settings
        self.session_recovery_data = {}  # For recovery after bot restarts
        
        # Configuration will be set by set_context
        self.quiz_config = None
        self.llm_config = None
    
    def set_context(self, context) -> None:
        """Set the bot context and extract quiz configuration."""
        super().set_context(context)
        
        self.quiz_config = self.config.quiz
        self.llm_config = self.config.llm
    
    async def cog_load(self) -> None:
        """Initialize the cog when it's loaded."""
        await super().cog_load()
        
        # Start background tasks
        self.cleanup_expired_quizzes.start()
        
        # Initialize database tables if needed
        if self.db_service:
            await self._ensure_stats_tables()
            
        # Try to recover any active sessions
        await self._recover_active_sessions()
    
    async def cog_unload(self) -> None:
        """Clean up when the cog is unloaded."""
        self.cleanup_expired_quizzes.cancel()
        
        # Stop all active quiz timers and save state for potential recovery
        for session_key, quiz in self.active_quizzes.items():
            if quiz.timer_task:
                quiz.timer_task.cancel()
                
            # Save recovery data
            if quiz.state == QuizState.ACTIVE:
                self._save_session_recovery_data(quiz)
        
        await super().cog_unload()
    
    async def _ensure_stats_tables(self) -> bool:
        """Ensure all necessary database tables exist."""
        self.logger.info("Ensuring database tables exist")
        try:
            if hasattr(self.db_service, '_ensure_tables_exist'):
                result = await self.db_service._ensure_tables_exist()
                if result:
                    self.logger.info("Database tables check successful")
                    return True
            
            if hasattr(self.db_service, '_initialize_tables'):
                await self.db_service._initialize_tables()
                self.logger.info("Database tables initialized")
                return True
            
            self.logger.warning("No table initialization methods found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error ensuring database tables: {e}", exc_info=True)
            return False
    
    @tasks.loop(minutes=5)
    async def cleanup_expired_quizzes(self):
        """Clean up expired quizzes."""
        current_time = time.time()
        expired_sessions = []
        
        for (guild_id, channel_id), quiz in self.active_quizzes.items():
            # Check if the quiz is finished
            if quiz.is_finished: 
                expired_sessions.append((guild_id, channel_id))
                if quiz.timer_task:
                    quiz.timer_task.cancel()
                continue
                
            # Check for inactivity (30 minutes)
            inactive_time = current_time - quiz.last_activity_time
            if inactive_time > 1800:  # 30 minutes of inactivity
                self.logger.info(f"Quiz in guild {guild_id}, channel {channel_id} abandoned due to inactivity (last activity: {inactive_time/60:.1f} minutes ago)")
                expired_sessions.append((guild_id, channel_id))
                if quiz.timer_task:
                    quiz.timer_task.cancel()
                
                # Try to send an inactivity message
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        async with channel.typing():
                            await channel.send("⏰ Quiz has been canceled due to inactivity (30 minutes without activity).")
                except Exception as e:
                    self.logger.error(f"Error sending inactivity message: {e}")
                continue
                
            # Check if it's been running too long (1 hour max total time)
            if (current_time - quiz.start_time) > 3600:  # 1 hour timeout
                expired_sessions.append((guild_id, channel_id))
                if quiz.timer_task:
                    quiz.timer_task.cancel()
        
        # Remove all expired sessions
        for session_key in expired_sessions:
            if session_key in self.active_quizzes:
                del self.active_quizzes[session_key]
                guild_id, channel_id = session_key
                self.logger.info(f"Cleaned up expired quiz in guild {guild_id}, channel {channel_id}")
    
    @cleanup_expired_quizzes.before_loop
    async def before_cleanup(self):
        """Wait until the bot is ready before starting the task loop."""
        await self.bot.wait_until_ready()
    
    async def _topic_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Provide autocomplete suggestions for quiz topics."""
        # Popular topics from various categories
        all_topics = [
            # Science & Technology
            "Python Programming", "JavaScript", "Web Development", "Machine Learning", "Data Science",
            "Space Exploration", "Artificial Intelligence", "Biology", "Chemistry", "Physics",
            "Computer Science", "Environmental Science", "Astronomy", "Robotics", "Quantum Physics",
            
            # History & Geography
            "World History", "Ancient Civilizations", "Geography", "American History", "European History",
            "World War II", "Ancient Egypt", "Medieval Times", "Renaissance", "Cold War",
            
            # Entertainment & Pop Culture
            "Movies", "Music", "Video Games", "Marvel Comics", "Star Wars", "Harry Potter",
            "Lord of the Rings", "Television Shows", "90s Culture", "Disney",
            
            # Sports & Games
            "Football", "Basketball", "Olympics", "Soccer", "Baseball", "Chess", "Board Games",
            "Tennis", "Golf", "Cricket",
            
            # Literature & Arts
            "Classic Literature", "Poetry", "Shakespeare", "Modern Literature", "Art History",
            "Famous Artists", "Architecture", "Book Characters", "Mythology",
            
            # General Knowledge
            "General Knowledge", "Trivia", "Current Events", "Famous People", "Capital Cities",
            "Languages", "Inventions", "Food & Cooking", "Animals", "Nature"
        ]
        
        # Filter topics based on current input (case-insensitive)
        current_lower = current.lower()
        matching_topics = [
            topic for topic in all_topics 
            if current_lower in topic.lower()
        ]
        
        # Sort by relevance (topics starting with the current string come first)
        matching_topics.sort(key=lambda x: (not x.lower().startswith(current_lower), x))
        
        # Return up to 25 choices (Discord's limit)
        return [
            app_commands.Choice(name=topic, value=topic)
            for topic in matching_topics[:25]
        ]
    
    # === QUIZ COMMANDS ===
    
    @commands.hybrid_group(name="quiz", description="Commands for starting and managing quizzes.")
    async def quiz_group(self, ctx: commands.Context):
        """Base quiz command group."""
        if ctx.invoked_subcommand is None:
            async with ctx.typing():
                await ctx.send_help(ctx.command)
    
    @quiz_group.command(name="start", description="Start a new quiz on a specific topic.")
    @app_commands.describe(
        topic="The topic for the quiz (e.g., 'Python Programming')",
        question_count="Number of questions (default: 5)",
        difficulty="Difficulty level (easy, medium, hard)",
        question_type="Question type (multiple_choice, true_false, short_answer)",
        provider="LLM provider to use (e.g., openai)",
        category="Question category (e.g., science)",
        template="Quiz template to use (e.g., educational)",
        is_private="Send quiz questions to DM instead of channel"
    )
    @app_commands.autocomplete(topic=_topic_autocomplete)
    @require_context
    @in_guild_only
    @cooldown_with_bypass(rate=1, per=60, bypass_roles=["admin", "moderator", "bot_admin"])
    async def quiz_start(
        self,
        ctx: commands.Context,
        topic: str,
        question_count: Optional[int] = None,
        difficulty: Literal["easy", "medium", "hard"] = "medium",
        question_type: Literal["multiple_choice", "true_false", "short_answer"] = "multiple_choice",
        provider: Optional[str] = None,
        category: Optional[str] = None,
        template: Optional[str] = None,
        is_private: bool = False
    ):
        """Start a new quiz on a topic."""
        # Defer the response for slash commands
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        
        # Get guild ID (or use 0 for DMs)
        guild_id = ctx.guild.id if ctx.guild else 0
        channel_id = ctx.channel.id
        session_key = (guild_id, channel_id)
        
        # Check for existing quiz using composite key
        if session_key in self.active_quizzes:
            quiz = self.active_quizzes[session_key]
            if quiz.state != QuizState.FINISHED:
                if isinstance(ctx, discord.Interaction):
                    async with ctx.channel.typing():
                        await ctx.followup.send("❌ There's already an active quiz in this channel. Finish it with `/quiz stop` before starting a new one.")
                else:
                    async with ctx.typing():
                        await ctx.send("❌ There's already an active quiz in this channel. Finish it with `/quiz stop` before starting a new one.")
                return
            else:
                del self.active_quizzes[session_key]
        
        # Apply user settings and defaults
        if ctx.author.id in self.user_settings:
            settings = self.user_settings[ctx.author.id]
            question_count = question_count or settings.get('question_count', 5)
            difficulty = settings.get('difficulty', difficulty)
            question_type = settings.get('question_type', question_type)
            category = category or settings.get('category', 'general')
            template = template or settings.get('template', 'standard')
        else:
            question_count = question_count or 5
            category = category or 'general'
            template = template or 'standard'
        
        provider = provider or self.llm_config.default_provider
        
        # Validate inputs
        if question_count < 1 or question_count > 20:
            if isinstance(ctx, discord.Interaction):
                async with ctx.channel.typing():
                    await ctx.followup.send("❌ Question count must be between 1 and 20.")
            else:
                async with ctx.typing():
                    await ctx.send("❌ Question count must be between 1 and 20.")
            return
        
        # Validate provider
        available_providers = llm_service.get_available_providers()
        if provider not in available_providers:
            providers_list = ", ".join(f"`{p}`" for p in available_providers)
            if isinstance(ctx, discord.Interaction):
                async with ctx.channel.typing():
                    await ctx.followup.send(f"❌ Invalid LLM provider. Available providers: {providers_list}")
            else:
                async with ctx.typing():
                    await ctx.send(f"❌ Invalid LLM provider. Available providers: {providers_list}")
            return
        
        # Validate template
        available_templates = quiz_generator.get_available_quiz_types()
        template_names = [t['name'] for t in available_templates]
        if template not in template_names:
            templates_list = ", ".join(f"`{t}`" for t in template_names)
            if isinstance(ctx, discord.Interaction):
                async with ctx.channel.typing():
                    await ctx.followup.send(f"❌ Invalid template. Available templates: {templates_list}")
            else:
                async with ctx.typing():
                    await ctx.send(f"❌ Invalid template. Available templates: {templates_list}")
            return
        
        # Start generating questions
        generating_embed = create_embed(
            title="🤔 Generating Quiz Questions...",
            description=f"Creating {question_count} {difficulty} questions about {topic}",
            color=Color.blue()
        )
        generating_embed.add_field(name="Provider", value=provider, inline=True)
        generating_embed.add_field(name="Template", value=template, inline=True)
        generating_embed.add_field(name="Type", value=question_type, inline=True)
        
        if isinstance(ctx, discord.Interaction):
            async with ctx.channel.typing():
                generating_msg = await ctx.followup.send(embed=generating_embed)
        else:
            async with ctx.typing():
                generating_msg = await ctx.send(embed=generating_embed)
        
        try:
            # Generate questions
            questions = await quiz_generator.generate_quiz(
                topic=topic,
                question_count=question_count,
                question_type=question_type,
                difficulty=difficulty,
                provider=provider,
                category=category,
                template=template
            )
            
            if not questions:
                await generating_msg.edit(
                    embed=create_embed(
                        title="❌ Quiz Generation Failed",
                        description="Failed to generate quiz questions. Please try again.",
                        color=Color.red()
                    )
                )
                return
            
            # Get guild ID (or use 0 for DMs)
            guild_id = ctx.guild.id if ctx.guild else 0
            channel_id = ctx.channel.id
            
            # Create the quiz with guild_id
            quiz = ActiveQuiz(
                guild_id=guild_id,
                channel_id=channel_id,
                host_id=ctx.author.id,
                topic=topic,
                questions=questions,
                timeout=self.quiz_config.default_timeout,
                llm_provider=provider,
                is_private=is_private
            )
            
            # Store using composite key
            session_key = (guild_id, channel_id)
            self.active_quizzes[session_key] = quiz
            quiz.state = QuizState.ACTIVE
            
            # Store recovery data
            self._save_session_recovery_data(quiz)
            
            # Update the message
            success_embed = create_embed(
                title="✅ Quiz Started!",
                description=f"Quiz on **{topic}** has begun!",
                color=Color.green()
            )
            success_embed.add_field(name="Questions", value=str(len(questions)), inline=True)
            success_embed.add_field(name="Difficulty", value=difficulty.capitalize(), inline=True)
            success_embed.add_field(name="Time per Question", value=f"{quiz.timeout}s", inline=True)
            
            await generating_msg.edit(embed=success_embed)
            
            # Start the first question
            await self._send_question(ctx, quiz)
            
        except Exception as e:
            self.logger.error(f"Error starting quiz: {e}", exc_info=True)
            try:
                await generating_msg.edit(
                    embed=create_embed(
                        title="❌ Error",
                        description=f"An error occurred while starting the quiz: {str(e)}",
                        color=Color.red()
                    )
                )
            except Exception as edit_error:
                # If editing fails, try to send a new message
                self.logger.error(f"Error editing message: {edit_error}")
                if isinstance(ctx, discord.Interaction):
                    async with ctx.channel.typing():
                        await ctx.followup.send(
                            embed=create_embed(
                                title="❌ Error",
                                description=f"An error occurred while starting the quiz: {str(e)}",
                                color=Color.red()
                            )
                        )
                else:
                    async with ctx.typing():
                        await ctx.send(
                            embed=create_embed(
                                title="❌ Error",
                                description=f"An error occurred while starting the quiz: {str(e)}",
                                color=Color.red()
                            )
                        )
            
            # Clean up
            guild_id = ctx.guild.id if ctx.guild else 0
            channel_id = ctx.channel.id
            session_key = (guild_id, channel_id)
            if session_key in self.active_quizzes:
                del self.active_quizzes[session_key]
                # Remove from recovery data
                if session_key in self.session_recovery_data:
                    del self.session_recovery_data[session_key]
    
    @quiz_group.command(name="stop", description="Stop the current quiz.")
    async def quiz_stop(self, ctx: commands.Context):
        """Stop the current quiz."""
        # Get guild ID (or use 0 for DMs)
        guild_id = ctx.guild.id if ctx.guild else 0
        channel_id = ctx.channel.id
        session_key = (guild_id, channel_id)
        
        quiz = self.active_quizzes.get(session_key)
        if not quiz:
            async with ctx.typing():
                await ctx.send("❌ There's no active quiz in this channel.")
            return
        
        # Check permissions
        if ctx.author.id != quiz.host_id and not ctx.author.guild_permissions.manage_messages:
            async with ctx.typing():
                await ctx.send("❌ Only the quiz host or moderators can stop the quiz.")
            return
        
        # Stop the quiz
        quiz.state = QuizState.FINISHED
        quiz.end_time = time.time()
        
        if quiz.timer_task:
            quiz.timer_task.cancel()
        
        # Send final results
        await self._send_final_results(ctx, quiz)
        
        # Clean up
        del self.active_quizzes[session_key]
        # Remove from recovery data
        if session_key in self.session_recovery_data:
            del self.session_recovery_data[session_key]
    
    @quiz_group.command(name="providers", description="Show available LLM providers.")
    async def quiz_providers(self, ctx: commands.Context):
        """Show available LLM providers for quiz generation."""
        providers = llm_service.get_available_providers()
        
        if not providers:
            async with ctx.typing():
                await ctx.send("❌ No LLM providers are available. Please configure at least one API key.")
            return
        
        default_provider = self.llm_config.default_provider
        
        embed = create_embed(
            title="Available LLM Providers",
            description="The following AI providers can be used to generate quiz questions:",
            color=Color.blue()
        )
        
        for provider in providers:
            name = provider.capitalize()
            if provider == default_provider:
                name += " (Default)"
            
            embed.add_field(
                name=name,
                value=f"Use with: `/quiz start topic:<topic> provider:{provider}`",
                inline=False
            )
        
        embed.set_footer(text="If no provider is specified, the default will be used.")
        async with ctx.typing():
            await ctx.send(embed=embed)
    
    @quiz_group.command(name="templates", description="Show available quiz templates.")
    async def quiz_templates(self, ctx: commands.Context):
        """Show available quiz templates for generation."""
        templates = quiz_generator.get_available_quiz_types()
        
        if not templates:
            async with ctx.typing():
                await ctx.send("❌ No quiz templates are currently available.")
            return
        
        embed = create_embed(
            title="Available Quiz Templates",
            description="Here are the available quiz templates you can use:",
            color=Color.blue()
        )
        
        for template in templates:
            name = template["name"]
            description = template.get("description", "No description available")
            embed.add_field(
                name=name.capitalize(),
                value=description,
                inline=False
            )
        
        embed.set_footer(text="Use `/quiz start <topic> template:<template>` to use a specific template.")
        async with ctx.typing():
            await ctx.send(embed=embed)
    
    @quiz_group.command(name="topics", description="Show suggested quiz topics.")
    async def quiz_topics(self, ctx: commands.Context):
        """Show suggested quiz topics."""
        topics = self.quiz_config.suggested_topics
        
        embed = create_embed(
            title="Suggested Quiz Topics",
            description="Here are some topics you can use for quizzes:",
            color=Color.blue()
        )
        
        # Group topics by category
        categorized_topics = {}
        for topic in topics:
            category = topic.get('category', 'General')
            if category not in categorized_topics:
                categorized_topics[category] = []
            categorized_topics[category].append(topic['name'])
        
        for category, topic_list in sorted(categorized_topics.items()):
            embed.add_field(
                name=category,
                value="\n".join([f"• {topic}" for topic in topic_list[:5]]),
                inline=True
            )
        
        embed.set_footer(text="Use `/quiz start <topic>` to start a quiz on any topic!")
        async with ctx.typing():
            await ctx.send(embed=embed)
    
    @quiz_group.command(name="scores", description="View your quiz scores.")
    async def quiz_scores(self, ctx: commands.Context):
        """View personal quiz statistics."""
        if not self.db_service:
            async with ctx.typing():
                await ctx.send("❌ Database service is not available.")
            return
        
        try:
            stats = await self.db_service.get_user_stats(ctx.author.id)
            
            if not stats or stats.get('quizzes_taken', 0) == 0:
                async with ctx.typing():
                    await ctx.send("📊 You haven't taken any quizzes yet!")
                return
            
            embed = create_embed(
                title="📊 Your Quiz Statistics",
                description=f"Stats for {ctx.author.mention}",
                color=Color.blue()
            )
            
            # Basic stats
            embed.add_field(name="Quizzes Taken", value=stats.get('quizzes_taken', 0), inline=True)
            embed.add_field(name="Total Score", value=stats.get('total_score', 0), inline=True)
            embed.add_field(name="Average Score", value=f"{stats.get('average_score', 0):.1f}", inline=True)
            
            # Answer stats
            correct = stats.get('correct_answers', 0)
            wrong = stats.get('wrong_answers', 0)
            total = correct + wrong
            accuracy = (correct / total * 100) if total > 0 else 0
            
            embed.add_field(name="Correct Answers", value=correct, inline=True)
            embed.add_field(name="Wrong Answers", value=wrong, inline=True)
            embed.add_field(name="Accuracy", value=f"{accuracy:.1f}%", inline=True)
            
            # Recent performance
            if 'recent_scores' in stats and stats['recent_scores']:
                recent = stats['recent_scores'][-5:]  # Last 5 quizzes
                recent_text = "\n".join([f"• {score} points" for score in recent])
                embed.add_field(name="Recent Scores", value=recent_text, inline=False)
            
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error retrieving quiz scores: {e}", exc_info=True)
            async with ctx.typing():
                await ctx.send("❌ An error occurred while retrieving your scores.")
    
    # === HELPER METHODS ===
    
    async def _send_question(self, ctx: commands.Context, quiz: ActiveQuiz):
        """Send a quiz question."""
        # Import content truncation utilities
        from utils.content import truncate_content
        
        question = quiz.current_question
        if not question:
            return
        
        # Create question embed with truncated content
        embed = create_embed(
            title=f"❓ {quiz.progress}",
            description=truncate_content(question.question, "question"),
            color=get_color_for_difficulty(question.difficulty) if hasattr(question, 'difficulty') else Color.blue()
        )
        
        # Add progress bar with custom emojis
        progress_bar = create_progress_bar(
            quiz.current_question_idx + 1,
            len(quiz.questions),
            length=10,
            use_emoji=True
        )
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        
        # Add options for multiple choice with truncated content
        if question.type == "multiple_choice" and question.options:
            options_text = ""
            for i, option in enumerate(question.options):
                emoji = REACTION_EMOJIS[i]
                truncated_option = truncate_content(option, "choice")
                options_text += f"{emoji} {truncated_option}\n"
            embed.add_field(name="Options", value=options_text, inline=False)
        
        # Add timer info
        embed.set_footer(text=f"⏱️ You have {quiz.timeout} seconds to answer!")
        
        # Send the question
        if quiz.is_private and ctx.author:
            # Send to DM
            try:
                dm_channel = ctx.author.dm_channel or await ctx.author.create_dm()
                async with dm_channel.typing():
                    msg = await dm_channel.send(embed=embed)
                async with ctx.typing():
                    await ctx.send(f"📬 Question sent to your DMs, {ctx.author.mention}!")
            except discord.Forbidden:
                async with ctx.typing():
                    await ctx.send("❌ Couldn't send DM. Please check your privacy settings.")
                    msg = await ctx.send(embed=embed)
        else:
            async with ctx.typing():
                msg = await ctx.send(embed=embed)
        
        quiz.message_id = msg.id
        quiz.current_question_start_time = time.time()
        
        # Add reaction options for multiple choice
        if question.type == "multiple_choice" and question.options:
            for i in range(len(question.options)):
                await msg.add_reaction(REACTION_EMOJIS[i])
        
        # Start timer
        quiz.timer_task = asyncio.create_task(
            self._question_timer(ctx, quiz, quiz.timeout)
        )
    
    async def _question_timer(self, ctx: commands.Context, quiz: ActiveQuiz, timeout: int):
        """Timer for a quiz question."""
        try:
            await asyncio.sleep(timeout)
            
            # Check if quiz still exists and hasn't moved on
            guild_id = ctx.guild.id if ctx.guild else 0
            channel_id = ctx.channel.id
            session_key = (guild_id, channel_id)
            
            if session_key not in self.active_quizzes:
                return
            
            current_quiz = self.active_quizzes[session_key]
            if current_quiz.quiz_id != quiz.quiz_id:
                return
            
            # Time's up!
            await self._handle_timeout(ctx, quiz)
            
        except asyncio.CancelledError:
            pass
    
    async def _handle_timeout(self, ctx: commands.Context, quiz: ActiveQuiz):
        """Handle question timeout."""
        from utils.content import truncate_content
        
        question = quiz.current_question
        if not question:
            return
        
        # Create timeout embed with truncated content
        embed = create_embed(
            title="⏰ Time's Up!",
            description=f"The correct answer was: **{truncate_content(question.correct_answer, 'answer')}**",
            color=Color.red()
        )
        
        if hasattr(question, 'explanation') and question.explanation:
            truncated_explanation = truncate_content(question.explanation, "explanation")
            embed.add_field(name="Explanation", value=truncated_explanation, inline=False)
        
        async with ctx.typing():
            await ctx.send(embed=embed)
        
        # Move to next question
        if quiz.next_question():
            await self._send_question(ctx, quiz)
        else:
            await self._send_final_results(ctx, quiz)
            guild_id = ctx.guild.id if ctx.guild else 0
            channel_id = ctx.channel.id
            session_key = (guild_id, channel_id)
            if session_key in self.active_quizzes:
                del self.active_quizzes[session_key]
                # Remove from recovery data
                if session_key in self.session_recovery_data:
                    del self.session_recovery_data[session_key]
    
    async def _send_final_results(self, ctx: commands.Context, quiz: ActiveQuiz):
        """Send final quiz results."""
        leaderboard = quiz.get_leaderboard()
        stats = quiz.get_stats()
        
        # Create results embed
        embed = create_embed(
            title="🏁 Quiz Complete!",
            description=f"Quiz on **{quiz.topic}** has ended!",
            color=Color.gold()
        )
        
        # Add overall stats
        embed.add_field(name="Total Questions", value=stats['total_questions'], inline=True)
        embed.add_field(name="Total Participants", value=stats['total_participants'], inline=True)
        embed.add_field(name="Overall Accuracy", value=f"{stats['accuracy']:.1f}%", inline=True)
        
        # Add leaderboard
        if leaderboard:
            leaderboard_text = ""
            for i, entry in enumerate(leaderboard[:10]):  # Top 10
                # Get user object
                try:
                    user = self.bot.get_user(entry['user_id']) or await self.bot.fetch_user(entry['user_id'])
                    username = user.display_name
                except:
                    username = entry['username']
                
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                xp_earned = entry['correct_answers'] * 10  # Calculate XP earned
                
                # Add XP to the leaderboard entry
                formatted_entry = format_leaderboard_entry(
                    position=medal,
                    username=username,
                    score=entry['score'],
                    correct=entry['correct_answers'],
                    total=entry['total_answers']
                )
                leaderboard_text += f"{formatted_entry} • +{xp_earned} XP\n"
            
            if leaderboard_text:
                embed.add_field(name="🏆 Leaderboard", value=leaderboard_text, inline=False)
        
        # Calculate total XP awarded
        total_xp = sum(entry['correct_answers'] * 10 for entry in leaderboard) if leaderboard else 0
        
        # Add duration
        duration = timedelta(seconds=int(stats['duration']))
        embed.set_footer(text=f"Duration: {duration} | Powered by {stats['llm_provider']} | 💫 Total XP awarded: {total_xp}")
        
        async with ctx.typing():
            await ctx.send(embed=embed)
        
        # Save results to database
        if self.db_service:
            for participant_id, participant in quiz.participants.items():
                try:
                    # Get the guild_id if we're in a guild channel
                    guild_id = ctx.guild.id if hasattr(ctx, 'guild') and ctx.guild else None
                    
                    # Get participant data
                    username = ""
                    try:
                        user = self.bot.get_user(participant_id) or await self.bot.fetch_user(participant_id)
                        username = user.name
                    except:
                        username = f"User{participant_id}"
                    
                    await record_complete_quiz_result_for_user(
                        db_service=self.db_service,
                        user_id=participant_id,
                        username=username,
                        quiz_id=f"quiz_{ctx.channel.id}_{int(time.time())}",
                        topic=quiz.topic,
                        correct=participant.correct_count,
                        wrong=participant.wrong_count,
                        points=participant.score,
                        difficulty=quiz.difficulty if hasattr(quiz, 'difficulty') else "medium",
                        category=quiz.category if hasattr(quiz, 'category') else "general",
                        guild_id=guild_id
                    )
                except Exception as e:
                    self.logger.error(f"Error saving quiz results for user {participant_id}: {e}")
    
    # === EVENT HANDLERS ===
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle quiz answers in messages."""
        if message.author.bot:
            return
        
        # Get guild ID (or use 0 for DMs)
        guild_id = message.guild.id if message.guild else 0
        channel_id = message.channel.id
        session_key = (guild_id, channel_id)
        
        # Check if there's an active quiz in this channel
        quiz = self.active_quizzes.get(session_key)
        if not quiz or quiz.state != QuizState.ACTIVE:
            return
        
        question = quiz.current_question
        if not question or question.type != "short_answer":
            return
        
        # Check answer
        answer = message.content.strip().lower()
        correct_answer = question.correct_answer.lower()
        
        is_correct = answer == correct_answer
        if is_correct:
            # Calculate points based on speed
            time_taken = time.time() - quiz.current_question_start_time
            base_points = 100
            time_bonus = max(0, int(base_points * (1 - time_taken / quiz.timeout)))
            points = base_points + time_bonus
            
            participant = quiz.record_answer(message.author.id, True, points)
            
            # Send response
            embed = create_embed(
                title="✅ Correct!",
                description=f"{message.author.mention} got it right! +{points} points",
                color=Color.green()
            )
            if hasattr(question, 'explanation') and question.explanation:
                embed.add_field(name="Explanation", value=question.explanation, inline=False)
        else:
            participant = quiz.record_answer(message.author.id, False)
            
            # Don't reveal answer yet for short answer
            embed = create_embed(
                title="❌ Incorrect",
                description=f"{message.author.mention}, that's not quite right.",
                color=Color.red()
            )
        
        async with message.channel.typing():
            await message.channel.send(embed=embed)
        
        # If correct, move to next question
        if is_correct:
            if quiz.timer_task:
                quiz.timer_task.cancel()
            
            await asyncio.sleep(2)  # Brief pause
            
            if quiz.next_question():
                await self._send_question(message.channel, quiz)
            else:
                await self._send_final_results(message.channel, quiz)
                # Get guild ID (or use 0 for DMs)
                guild_id = message.guild.id if message.guild else 0
                channel_id = message.channel.id
                session_key = (guild_id, channel_id)
                if session_key in self.active_quizzes:
                    del self.active_quizzes[session_key]
                    # Remove from recovery data
                    if session_key in self.session_recovery_data:
                        del self.session_recovery_data[session_key]
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle quiz answers via reactions."""
        if payload.user_id == self.bot.user.id:
            return
        
        # Get channel to find guild_id
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
            
        # Get guild ID (or use 0 for DMs)
        guild_id = channel.guild.id if hasattr(channel, 'guild') and channel.guild else 0
        channel_id = payload.channel_id
        session_key = (guild_id, channel_id)
        
        # Check if there's an active quiz in this channel
        quiz = self.active_quizzes.get(session_key)
        if not quiz or quiz.state != QuizState.ACTIVE:
            return
        
        question = quiz.current_question
        if not question or question.type != "multiple_choice":
            return
        
        # Check if this is the right message
        if payload.message_id != quiz.message_id:
            return
        
        # Check if it's a valid option
        emoji = str(payload.emoji)
        if emoji not in REACTION_EMOJIS[:len(question.options)]:
            return
        
        # Get the selected option
        option_index = REACTION_EMOJIS.index(emoji)
        selected_answer = question.options[option_index]
        
        # Check if correct
        is_correct = selected_answer == question.correct_answer
        
        # Calculate points
        if is_correct:
            time_taken = time.time() - quiz.current_question_start_time
            base_points = 100
            time_bonus = max(0, int(base_points * (1 - time_taken / quiz.timeout)))
            points = base_points + time_bonus
        else:
            points = 0
        
        participant = quiz.record_answer(payload.user_id, is_correct, points)
        
        # Get channel and user
        channel = self.bot.get_channel(payload.channel_id)
        user = self.bot.get_user(payload.user_id)
        
        if channel and user:
            if is_correct:
                embed = create_embed(
                    title="✅ Correct!",
                    description=f"{user.mention} got it right! +{points} points",
                    color=Color.green()
                )
            else:
                embed = create_embed(
                    title="❌ Incorrect",
                    description=f"{user.mention} selected: {selected_answer}\nCorrect answer: {question.correct_answer}",
                    color=Color.red()
                )
            
            if hasattr(question, 'explanation') and question.explanation:
                embed.add_field(name="Explanation", value=question.explanation, inline=False)
            
            async with channel.typing():
                await channel.send(embed=embed)
            
            # If correct, move to next question
            if is_correct:
                if quiz.timer_task:
                    quiz.timer_task.cancel()
                
                await asyncio.sleep(2)
                
                if quiz.next_question():
                    await self._send_question(channel, quiz)
                else:
                    await self._send_final_results(channel, quiz)
                    guild_id = channel.guild.id if hasattr(channel, 'guild') and channel.guild else 0
                    channel_id = payload.channel_id
                    session_key = (guild_id, channel_id)
                    if session_key in self.active_quizzes:
                        del self.active_quizzes[session_key]
                        # Remove from recovery data
                        if session_key in self.session_recovery_data:
                            del self.session_recovery_data[session_key]


    def _save_session_recovery_data(self, quiz: ActiveQuiz) -> None:
        """Save session data for recovery after bot restarts."""
        session_key = (quiz.guild_id, quiz.channel_id)
        
        # Store minimal data needed for recovery
        recovery_data = {
            'quiz_id': quiz.quiz_id,
            'guild_id': quiz.guild_id,
            'channel_id': quiz.channel_id,
            'host_id': quiz.host_id,
            'topic': quiz.topic,
            'llm_provider': quiz.llm_provider,
            'start_time': quiz.start_time,
            'last_activity_time': quiz.last_activity_time,
            'current_question_idx': quiz.current_question_idx,
            'total_questions': len(quiz.questions),
            'saved_at': time.time()
        }
        
        self.session_recovery_data[session_key] = recovery_data
        
        # Log recovery data saved
        self.logger.info(
            f"Saved recovery data for quiz session {quiz.quiz_id} in guild {quiz.guild_id}, channel {quiz.channel_id}"
        )
    
    async def _recover_active_sessions(self) -> None:
        """Try to recover any active sessions after bot restart."""
        if not self.session_recovery_data:
            return
            
        recovered_count = 0
        current_time = time.time()
        
        # Process all saved recovery data
        for session_key, recovery_data in list(self.session_recovery_data.items()):
            try:
                guild_id, channel_id = session_key
                
                # Skip if session is too old (no recovery after 30 minutes)
                saved_at = recovery_data.get('saved_at', 0)
                if current_time - saved_at > 1800:  # 30 minutes
                    del self.session_recovery_data[session_key]
                    continue
                    
                # Get channel
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    self.logger.warning(f"Can't recover session: channel {channel_id} not found")
                    del self.session_recovery_data[session_key]
                    continue
                
                # Inform channel that we're recovering a session
                try:
                    async with channel.typing():
                        await channel.send(f"⚠️ Recovering quiz on topic **{recovery_data['topic']}** that was interrupted due to bot restart.")
                    async with channel.typing():
                        await channel.send("The quiz will need to be restarted. Please use `/quiz stop` and then start a new quiz.")
                    recovered_count += 1
                except Exception as e:
                    self.logger.error(f"Error sending recovery message: {e}")
                
                # We don't actually restart the quiz automatically since we'd need the questions
                # Instead, we notify the channel and let them restart manually
                
            except Exception as e:
                self.logger.error(f"Error recovering session {session_key}: {e}")
                
        if recovered_count > 0:
            self.logger.info(f"Notified {recovered_count} channels about interrupted quiz sessions")
        
        # Clear all recovery data
        self.session_recovery_data.clear()


async def setup_with_context(bot: commands.Bot, context):
    """Set up the quiz cog with context."""
    from cogs.base_cog import setup_with_context as base_setup
    return await base_setup(bot, context, QuizCog)


async def setup(bot: commands.Bot):
    """Default setup function for Discord.py."""
    # Create the cog but don't set context yet
    # Context will be set by the bot after loading
    cog = QuizCog(bot)
    await bot.add_cog(cog)
    return cog