import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import time
from typing import Dict, List, Optional, Union, Any, Literal
from datetime import datetime, timedelta
import random
import logging
import re
import uuid
import json

from discord import Embed, Color, User, Member
from config import load_config

# Simple context wrapper to avoid followup attribute errors
class SimpleContextWrapper:
    """A simple wrapper around a context object that provides safe versions of common methods."""
    
    def __init__(self, original_ctx, channel=None):
        """Initialize with the original context and optional channel override."""
        self.original_ctx = original_ctx
        self.channel = channel or getattr(original_ctx, 'channel', None)
        self.author = getattr(original_ctx, 'author', None)
        self.guild = getattr(original_ctx, 'guild', None)
        self.bot = getattr(original_ctx, 'bot', None)
        self.command = getattr(original_ctx, 'command', None)
        
        # Set guild and channel IDs if available
        self.guild_id = getattr(self.guild, 'id', None) if self.guild else None
        self.channel_id = getattr(self.channel, 'id', None) if self.channel else None
    
    async def send(self, content=None, embed=None, **kwargs):
        """Safe send method that uses the channel directly."""
        if self.channel:
            async with self.channel.typing():
                return await self.channel.send(content=content, embed=embed, **kwargs)
        else:
            # Try original context's send method as fallback
            if hasattr(self.original_ctx, 'send'):
                async with self.original_ctx.typing():
                    return await self.original_ctx.send(content=content, embed=embed, **kwargs)
            # Last resort - log error
            logging.getLogger("bot.group_quiz").error("No viable send method found in SimpleContextWrapper")
            return None
    
    # Pass through any attributes not found to the original context
    def __getattr__(self, name):
        return getattr(self.original_ctx, name)

# Import local utilities
from utils import (
    create_embed,
    create_progress_bar,
    get_color_for_difficulty,
    format_leaderboard_entry,
    REACTION_EMOJIS
)
# Import the new database operation functions
from services.database_operations.quiz_stats_ops import ( 
    record_batch_quiz_results
)
# Import decorators for cooldowns
from cogs.utils.decorators import require_context, in_guild_only, cooldown_with_bypass

logger = logging.getLogger("bot.group_quiz")


class GroupQuizCog(commands.Cog, name="Group Quiz"):
    """Commands for interactive group quizzes that work like trivia games."""

    def __init__(self, bot):
        self.bot = bot
        self.config = load_config().quiz
        self.llm_config = load_config().llm
        
        # Set in set_context
        self.context = None
        self.db_service = None
        self.message_router = None
        self.group_quiz_manager = None
    
    def set_context(self, context):
        """Set the bot context."""
        self.context = context
        self.config = context.config.quiz
        self.trivia_config = context.config.trivia
        self.llm_config = context.config.llm
        self.db_service = context.db_service
        self.message_router = context.message_router
        self.group_quiz_manager = context.group_quiz_manager
        
        # Import quiz_generator here to avoid circular imports
        from services.quiz_generator import quiz_generator
        self.quiz_generator = quiz_generator
        
        # Set LLM service for quiz generator if not already set
        if self.quiz_generator and not self.quiz_generator.llm_service:
            from services.llm_service import llm_service
            self.quiz_generator.llm_service = llm_service
            
        # Also set llm_service for cog to use directly
        from services.llm_service import llm_service
        self.llm_service = llm_service
    
    async def cog_load(self):
        """Called when the cog is loaded."""
        # Setup tasks
        try:
            if not hasattr(self, '_task_started') and not self.check_inactive_sessions.is_running():
                self.check_inactive_sessions.start()
                self._task_started = True
                logger.debug("Started check_inactive_sessions task")
            else:
                logger.debug("check_inactive_sessions task is already running or was previously started, not starting again")
        except Exception as e:
            logger.error(f"Error starting task: {e}")
    
    async def cog_unload(self):
        """Called when the cog is unloaded."""
        self.check_inactive_sessions.cancel()
    
    @tasks.loop(minutes=5)
    async def check_inactive_sessions(self):
        """Check for and clean up inactive group quiz sessions."""
        if not self.group_quiz_manager:
            return
            
        # Loop through active sessions and end any that have been inactive for too long
        for (guild_id, channel_id), session in list(self.group_quiz_manager.active_sessions.items()):
            try:
                if session.start_time:
                    # End sessions that have been inactive for more than 30 minutes
                    inactive_time = datetime.now() - session.start_time
                    if inactive_time > timedelta(minutes=30) and not session.is_finished:
                        # Get the channel
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            async with channel.typing():
                                await channel.send("⏰ Trivia game expired due to inactivity.")
                            
                        # End the session
                        self.group_quiz_manager.end_session(guild_id, channel_id)
                        logger.info(f"Ended inactive group quiz session in guild {guild_id}, channel {channel_id}")
            except Exception as e:
                logger.error(f"Error checking inactive session: {e}")
    
    @check_inactive_sessions.before_loop
    async def before_check_inactive(self):
        """Wait until the bot is ready before starting the task loop."""
        await self.bot.wait_until_ready()
    
    async def _topic_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Provide autocomplete suggestions for quiz topics."""
        # Popular topics from various categories
        all_topics = [
            # Science & Technology
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
    
    @commands.hybrid_group(name="trivia", description="Group quiz commands for interactive trivia games.")
    async def trivia_group(self, ctx):
        """Group quiz commands for interactive trivia games."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
    
    async def _generate_quiz_questions(self, ctx, topic, question_count, difficulty, provider, category, template):
        """Generate quiz questions with multiple attempts if needed to ensure we get enough questions."""
        # Helper function to send messages properly based on context type
        async def send_message(content=None, embed=None):
            """Helper function that handles sending messages correctly based on context type"""
            try:
                # Check if this is an Interaction context with followup
                if hasattr(ctx, 'interaction') and ctx.interaction and hasattr(ctx.interaction, 'response') and ctx.interaction.response.is_done():
                    # This is a slash command that has already had its initial response (deferred)
                    async with ctx.typing():
                        return await ctx.followup.send(content=content, embed=embed)
                elif hasattr(ctx, 'followup') and hasattr(ctx, 'responded') and ctx.responded:
                    # Direct interaction context with followup
                    async with ctx.typing():
                        return await ctx.followup.send(content=content, embed=embed)
                else:
                    # Regular context or unresponded interaction
                    async with ctx.typing():
                        return await ctx.send(content=content, embed=embed)
            except Exception as e:
                logger.error(f"Error sending message in _generate_quiz_questions: {e}")
                # Final fallback attempt
                if hasattr(ctx, 'channel'):
                    try:
                        async with ctx.channel.typing():
                            return await ctx.channel.send(content=content, embed=embed)
                    except Exception:
                        pass  # Give up if this fails too
                
        max_attempts = 3
        min_success_ratio = 0.6  # Consider at least 60% of requested questions as acceptable
        
        # Enforce maximum of 5 questions
        original_question_count = question_count
        question_count = min(question_count, 5)
        if original_question_count > 5:
            await send_message(f"⚠️ Question count has been limited to 5 maximum.")
        
        # Try multiple providers if the first one fails
        available_providers = []
        try:
            if self.llm_service:
                available_providers = self.llm_service.get_available_providers()
            if not provider and available_providers:
                provider = available_providers[0]  # Use first available if none specified
        except Exception as e:
            logger.warning(f"Error getting available providers: {e}")
            # Fallback to the provided provider
        
        # Make sure provider is valid or use a default
        if not provider:
            provider = "openai"  # Default fallback
        
        questions = []
        used_provider = provider
        provider_info = {"provider_name": provider}
        
        # Try multiple attempts to generate questions
        for attempt in range(1, max_attempts + 1):
            try:
                # Try with the current provider
                logger.info(f"Generating quiz questions attempt {attempt}/{max_attempts} using provider: {used_provider}")
                
                # Generate questions using the quiz generator
                generated_questions = await self.quiz_generator.generate_quiz(
                    topic=topic,
                    quiz_type=template or "trivia",
                    num_questions=question_count,
                    difficulty=difficulty,
                    category=category or "general",
                    provider=used_provider
                )
                
                # Add generated questions to our collection
                questions.extend(generated_questions)
                
                # If we have enough questions, exit the loop
                if len(questions) >= question_count:
                    break
                    
                # If we don't have enough questions but have more than the minimum ratio, continue
                if len(questions) >= int(question_count * min_success_ratio):
                    # Try to generate the remaining questions
                    remaining = question_count - len(questions)
                    logger.info(f"Generated {len(generated_questions)} questions, attempting to generate {remaining} more")
                    
                    # Generate the remaining questions
                    more_questions = await self.quiz_generator.generate_quiz(
                        topic=topic,
                        quiz_type=template or "trivia",
                        num_questions=remaining,
                        difficulty=difficulty,
                        category=category or "general",
                        provider=used_provider
                    )
                    
                    # Add the additional questions
                    questions.extend(more_questions)
                    
                    # If we have enough now, exit
                    if len(questions) >= question_count:
                        break
                    
            except Exception as e:
                logger.error(f"Error generating quiz questions (attempt {attempt}): {e}")
                
                # If we already have some questions and we're on the last attempt, use what we have
                if questions and attempt == max_attempts:
                    logger.warning(f"Using partial set of {len(questions)} questions after {attempt} failed attempts")
                    break
                
                # Try a different provider for the next attempt
                if available_providers and len(available_providers) > 1:
                    # Rotate to next provider
                    current_index = available_providers.index(used_provider) if used_provider in available_providers else -1
                    next_index = (current_index + 1) % len(available_providers)
                    used_provider = available_providers[next_index]
                    provider_info = {"provider_name": used_provider}
                    logger.info(f"Switching to provider: {used_provider} for next attempt")
        
        # If we still don't have enough questions, adjust the question count to match what we have
        final_question_count = len(questions)
        
        # Make sure we don't exceed the requested number
        if final_question_count > question_count:
            questions = questions[:question_count]
            final_question_count = question_count
        
        # If we have no questions, raise an error
        if final_question_count == 0:
            error_msg = f"Failed to generate any valid questions about '{topic}' after multiple attempts"
            logger.error(error_msg)
            try:
                await send_message(f"❌ {error_msg}")
            except Exception as msg_error:
                logger.error(f"Failed to send error message: {msg_error}")
            raise ValueError(error_msg)
        
        # Validate questions and sort them (problematic ones at the end)
        valid_questions = []
        problematic_questions = []
        
        for q in questions:
            # Check if it has all required attributes
            is_valid = (
                hasattr(q, 'question') and q.question and
                hasattr(q, 'answer') and q.answer and 
                q.answer not in ["Unable to parse from response", "Answer unavailable"]
            )
            
            # For multiple choice, check if options exist
            if hasattr(q, 'question_type') and q.question_type == "multiple_choice":
                has_options = hasattr(q, 'options') and q.options and len(q.options) > 0
                is_valid = is_valid and has_options
            
            if is_valid:
                valid_questions.append(q)
            else:
                # Try to fix problematic questions if possible
                if hasattr(q, 'question') and q.question:
                    if not hasattr(q, 'answer') or not q.answer or q.answer in ["Unable to parse from response", "Answer unavailable"]:
                        # If it has options, use first option as answer
                        if hasattr(q, 'options') and q.options and len(q.options) > 0:
                            q.answer = q.options[0]
                            problematic_questions.append(q)
                        else:
                            continue  # Skip completely invalid questions
                    else:
                        problematic_questions.append(q)
        
        # Combine valid questions first, then append problematic ones
        sorted_questions = valid_questions + problematic_questions
        
        # If we still have no questions after validation, raise an error
        if not sorted_questions:
            error_msg = f"Failed to generate any valid questions with both question text and answer about '{topic}'"
            logger.error(error_msg)
            try:
                await send_message(f"❌ {error_msg}")
            except Exception as msg_error:
                logger.error(f"Failed to send error message: {msg_error}")
            raise ValueError(error_msg)
        
        # Update question IDs to ensure they're sequential
        for i, q in enumerate(sorted_questions):
            q.question_id = i
            
        return sorted_questions, provider_info
        
    @trivia_group.command(name="start", description="Start a new group trivia quiz on a specific topic")
    @app_commands.describe(
        topic="The topic for the quiz (e.g., 'Space Exploration')",
        question_count="Number of questions (default: 5, max: 5)",
        difficulty="Difficulty level (easy, medium, hard)",
        provider="LLM provider to use (openai, anthropic, google)",
        category="Question category (e.g., science)",
        template="Quiz template to use (e.g., trivia)",
        timeout="Time limit for each question in seconds (default: 30)",
        single_answer_mode="If True, only the first correct answer wins and advances to next question (default: False)",
        is_private="If True, sends questions and answers via DM instead of public chat (default: False)"
    )
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy", value="easy"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="Hard", value="hard")
    ])
    @app_commands.choices(provider=[
        app_commands.Choice(name="OpenAI", value="openai"),
        app_commands.Choice(name="Anthropic", value="anthropic"),
        app_commands.Choice(name="Google", value="google")
    ])
    @app_commands.autocomplete(topic=_topic_autocomplete)
    @cooldown_with_bypass(rate=1, per=90, bypass_roles=["admin", "moderator", "bot_admin"])
    @require_context
    @in_guild_only
    async def trivia_start(
        self,
        ctx: commands.Context,
        topic: str,
        question_count: Optional[int] = 5,
        difficulty: str = "medium",
        provider: str = "openai",
        category: Optional[str] = None,
        template: Optional[str] = None,
        timeout: Optional[int] = 30,
        single_answer_mode: bool = False,
        is_private: bool = False
    ):
        """Start a new group trivia quiz on a specific topic."""
        try:
            # Send a message directly to the channel to avoid any ctx.followup issues
            initial_message = None
            
            # Try to get the channel in a safe way
            channel = None
            if hasattr(ctx, 'channel'):
                channel = ctx.channel
            
            # Initial message will be handled above based on command type
            
            # For slash commands, send initial response instead of deferring
            if hasattr(ctx, 'interaction') and ctx.interaction:
                try:
                    # Send the initial "thinking" response
                    if not ctx.interaction.response.is_done():
                        await ctx.interaction.response.send_message("Quiz Bot is thinking...")
                        initial_message = None  # We'll use edit_original_response instead
                except Exception as response_error:
                    logger.error(f"Failed to send interaction response: {response_error}")
            else:
                # For non-slash commands, send the initial message to the channel
                if channel:
                    try:
                        async with channel.typing():
                            initial_message = await channel.send("Quiz Bot is thinking...")
                    except Exception as channel_error:
                        logger.error(f"Failed to send initial message via channel: {channel_error}")
            
            # Create a simple context wrapper to avoid followup issues
            safe_ctx = SimpleContextWrapper(ctx, channel)
            
            # Call the implementation method with our safe context and initial message
            # The _trivia_start_impl will handle editing the initial_message through all stages
            await self._trivia_start_impl(
                safe_ctx, 
                topic=topic,
                question_count=question_count,
                difficulty=difficulty,
                provider=provider,
                category=category,
                template=template,
                timeout=timeout,
                single_answer_mode=single_answer_mode,
                is_private=is_private,
                initial_message=initial_message
            )
        except Exception as e:
            # Handle any error at the top level
            logger.error(f"Top-level error in trivia_start: {e}")
            # Try to send a message without using followup, directly to the channel
            if channel:
                try:
                    async with channel.typing():
                        await channel.send("❌ An error occurred while starting the trivia quiz. Please try again.")
                except Exception as channel_error:
                    logger.error(f"Failed to send channel error message: {channel_error}")
            # Ensure the session is cleaned up
            if hasattr(self, 'group_quiz_manager') and self.group_quiz_manager and channel and hasattr(ctx, 'guild'):
                try:
                    guild_id = getattr(ctx.guild, 'id', None)
                    channel_id = getattr(channel, 'id', None)
                    if guild_id and channel_id:
                        self.group_quiz_manager.end_session(guild_id, channel_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up session: {cleanup_error}")
                    pass  # Ignore if cleanup fails
        
    async def _trivia_start_impl(
        self,
        ctx,
        topic: str,
        question_count: Optional[int] = None,
        difficulty: str = "medium",
        provider: str = "openai",
        category: Optional[str] = None,
        template: Optional[str] = None,
        timeout: Optional[int] = None,
        single_answer_mode: bool = False,
        is_private: bool = False,
        initial_message = None
    ):
        """Implementation of trivia start that works with both command types."""
        try:
            # First, edit the response to show generating status
            # Check if this is a slash command interaction
            if hasattr(ctx, 'interaction') and ctx.interaction:
                try:
                    await ctx.interaction.edit_original_response(content=f"🤔 Generating {difficulty} difficulty trivia questions about **{topic}**...")
                except Exception as edit_error:
                    logger.error(f"Failed to edit interaction response to generating status: {edit_error}")
            elif initial_message:
                try:
                    await initial_message.edit(content=f"🤔 Generating {difficulty} difficulty trivia questions about **{topic}**...")
                except Exception as edit_error:
                    logger.error(f"Failed to edit initial message to generating status: {edit_error}")
            
            # COMPLETELY FAIL-SAFE message sending function that won't trigger followup errors
            # Modified to edit the interaction response or initial message
            async def send_message(content=None, embed=None):
                """100% fail-safe message sending that edits the interaction response or initial message"""
                try:
                    # For slash commands, edit the original interaction response
                    if hasattr(ctx, 'interaction') and ctx.interaction:
                        try:
                            if embed:
                                return await ctx.interaction.edit_original_response(content=content, embed=embed)
                            else:
                                return await ctx.interaction.edit_original_response(content=content)
                        except Exception as edit_error:
                            logger.warning(f"Failed to edit interaction response: {edit_error}")
                            # Fall through to other methods if editing fails
                    
                    # If we have the initial message, try to edit it
                    elif initial_message:
                        try:
                            if embed:
                                return await initial_message.edit(content=content, embed=embed)
                            else:
                                return await initial_message.edit(content=content)
                        except Exception as edit_error:
                            logger.warning(f"Failed to edit initial message: {edit_error}")
                            # Fall through to sending a new message if editing fails
                    
                    # Try the normal send first - this works for regular commands
                    if hasattr(ctx, 'send'):
                        try:
                            async with ctx.typing():
                                return await ctx.send(content=content, embed=embed)
                        except Exception:
                            pass  # Fall through to next method if this fails
                            
                    # Try using channel directly if available
                    if hasattr(ctx, 'channel'):
                        try:
                            async with ctx.channel.typing():
                                return await ctx.channel.send(content=content, embed=embed)
                        except Exception:
                            pass  # Fall through to next method if this fails
                            
                    # Only try followup as a last resort, with maximum safety checks
                    if hasattr(ctx, 'followup') and callable(getattr(ctx.followup, 'send', None)):
                        try:
                            async with ctx.typing():
                                return await ctx.followup.send(content=content, embed=embed)
                        except Exception:
                            pass  # Fall through if this fails
                    
                    logger.warning("All message sending methods failed in _trivia_start_impl")
                    return None  # Return None if all methods fail
                except Exception as e:
                    logger.error(f"Emergency fail-safe message handler caught exception: {e}")
                    return None  # Absolutely never crash here
                    
            # Check if required services are available
            if not self.quiz_generator or not self.group_quiz_manager:
                await send_message("❌ Quiz services are not fully initialized. Please try again later.")
                logger.error("Quiz services not initialized in trivia_start")
                return
            
            # Check if there's already an active quiz in this channel
            active_session = self.group_quiz_manager.get_session(ctx.guild.id, ctx.channel.id)
            if active_session and active_session.is_active and not active_session.is_finished:
                await send_message("❌ There's already an active trivia quiz in this channel. Please wait for it to finish or use `/trivia stop` to end it.")
                return
            
            # Set defaults
            if question_count is None:
                question_count = 5  # Default to 5 questions
            
            # Cap at 5 questions maximum
            original_count = question_count
            question_count = min(question_count, 5)
            if original_count > 5:
                await send_message(f"⚠️ Question count has been limited to 5 maximum.")
            
            if timeout is None:
                timeout = 30
            
            # Validate inputs
            if question_count < 1:
                await send_message("❌ Question count must be at least 1.")
                return
            
            if timeout < 5 or timeout > 120:
                await send_message("❌ Timeout must be between 5 and 120 seconds.")
                return
            
            # The initial message is already sent and passed from the parent method
            # Keep the reference to update it as we progress
            
            # Generate questions
            try:
                questions, provider_info = await self._generate_quiz_questions(
                    ctx=ctx,
                    topic=topic,
                    question_count=question_count,
                    difficulty=difficulty,
                    provider=provider,
                    category=category,
                    template=template
                )
                # Edit the response to show questions are ready
                await send_message(f"✅ Questions ready! Starting trivia with {len(questions)} questions...")
                # Small delay to let users see this status before showing the game introduction
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Failed to generate quiz questions: {e}")
                from utils.messages import create_error_embed
                error_embed = create_error_embed(
                    title="Quiz Generation Failed",
                    error_key="generation_failed",
                    topic=topic
                )
                # Don't try to edit, just send a new error message
                try:
                    await send_message(embed=error_embed)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
                    # Try direct channel send as last resort
                    if hasattr(ctx, 'channel') and ctx.channel:
                        try:
                            async with ctx.channel.typing():
                                await ctx.channel.send("❌ Failed to generate quiz questions. Please try again.")
                        except Exception:
                            pass
                return
            
            # Create a new quiz session
            session = self.group_quiz_manager.create_session(
                guild_id=ctx.guild.id,
                channel_id=ctx.channel.id,
                host_id=ctx.author.id,
                topic=topic,
                questions=questions,
                timeout=timeout,
                provider_info=provider_info,
                single_answer_mode=single_answer_mode,
                is_private=is_private
            )
            
            # Start the quiz session, passing the initial message
            await self._start_trivia_session(ctx, session, initial_message)
            
        except Exception as e:
            logger.error(f"Error starting trivia: {e}")
            
            # Use the helper function for sending messages - more safely this time
            try:
                await send_message(f"❌ An error occurred while starting the trivia quiz: {str(e)}")
            except Exception as msg_error:
                logger.error(f"Failed to send error message: {msg_error}")
                # Final fallback - if everything else fails
                if hasattr(ctx, 'channel'):
                    try:
                        async with ctx.channel.typing():
                            await ctx.channel.send(f"❌ An error occurred while starting the trivia quiz. Please try again.")
                    except Exception:
                        pass  # Nothing more we can do
            
            # Ensure no incomplete session is left
            if self.group_quiz_manager:
                try:
                    if hasattr(ctx, 'guild') and hasattr(ctx, 'channel'):
                        self.group_quiz_manager.end_session(ctx.guild.id, ctx.channel.id)
                    else:
                        logger.warning("Could not end group quiz session - guild or channel ID not available")
                except Exception as cleanup_error:
                    logger.error(f"Error ending incomplete session: {cleanup_error}")
    
    async def _start_trivia_session(self, ctx, session, initial_message=None):
        """Start a trivia session."""
        try:
            # Get the channel in a safe way
            channel = None
            if hasattr(ctx, 'channel'):
                channel = ctx.channel
            elif isinstance(ctx, SimpleContextWrapper) and ctx.channel:
                channel = ctx.channel
                
            # Super safe message sending function that uses the channel directly
            # Modified to edit the interaction response or initial message
            async def send_message(content=None, embed=None):
                """100% fail-safe message sending that works with any context type
                Will edit the interaction response or initial message if available"""
                # For slash commands, edit the original interaction response
                if hasattr(ctx, 'interaction') and ctx.interaction:
                    try:
                        if embed:
                            return await ctx.interaction.edit_original_response(content=content, embed=embed)
                        else:
                            return await ctx.interaction.edit_original_response(content=content)
                    except Exception as edit_error:
                        logger.warning(f"Failed to edit interaction response: {edit_error}")
                        # Fall through to other methods if editing fails
                
                # If we have the initial message, try to edit it
                elif initial_message:
                    try:
                        if embed:
                            return await initial_message.edit(content=content, embed=embed)
                        else:
                            return await initial_message.edit(content=content)
                    except Exception as edit_error:
                        logger.warning(f"Failed to edit initial message: {edit_error}")
                        # Fall through to sending a new message if editing fails
                
                if channel:
                    try:
                        async with channel.typing():
                            return await channel.send(content=content, embed=embed)
                    except Exception as channel_error:
                        logger.error(f"Error sending message via channel: {channel_error}")
                
                # Only as a backup, try ctx.send
                if hasattr(ctx, 'send'):
                    try:
                        async with ctx.typing():
                            return await ctx.send(content=content, embed=embed)
                    except Exception as send_error:
                        logger.error(f"Error sending message via ctx.send: {send_error}")
                
                # Don't even attempt to use followup
                return None
                    
            # Ensure we have all required services
            if not self.message_router:
                logger.error("Message router not available in _start_trivia_session")
                await send_message("❌ Critical service unavailable. Unable to start trivia session. Please try again later.")
                # Get IDs in a safe way
                guild_id = getattr(session, 'guild_id', None)
                channel_id = getattr(session, 'channel_id', None)
                if guild_id and channel_id: 
                    self.group_quiz_manager.end_session(guild_id, channel_id)
                return
                
            session.is_active = True
            session.start_time = datetime.now()
            
            # Create announcement embed
            embed = Embed(
                title=f"Trivia Game: {session.topic}",
                description=(
                    f"Starting a new trivia game with {len(session.questions)} questions!\n\n"
                    f"**How to play:**\n"
                    f"• {'Reply to the DM from the bot' if session.is_private else 'Type your answer in the chat'} when a question appears\n"
                    f"• For multiple choice, type the letter (A, B, C, D) or the answer text\n"
                    f"• Be fast! Quicker answers earn more points\n"
                    f"• Everyone can participate - no sign-up needed\n"
                ),
                color=Color.gold()
            )
            
            # Additional game settings
            settings_text = (
                f"**Questions:** {len(session.questions)}\n"
                f"**Difficulty:** {session.questions[0].difficulty.capitalize()}\n"
                f"**Category:** {session.questions[0].category.capitalize()}\n"
                f"**Time per question:** {session.timeout} seconds\n"
            )
            
            # Add special game modes if applicable
            game_modes = []
            if session.single_answer_mode:
                game_modes.append("🥇 **One Winner Mode:** Only the first correct answer earns points!")
            if session.is_private:
                game_modes.append("📱 **Private Mode:** Questions sent via DM")
                
            if game_modes:
                settings_text += "\n**Special Game Modes:**\n" + "\n".join(game_modes)
            
            embed.add_field(
                name="Settings",
                value=settings_text,
                inline=False
            )
            
            # If this is a private trivia, add instructions
            if session.is_private:
                embed.add_field(
                    name="Private Trivia Instructions",
                    value=(
                        "Questions will be sent to your DMs. You must interact with the bot at least once "
                        "for the bot to be able to message you. If you haven't received questions, please make sure "
                        "you have DMs enabled for this server."
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"Hosted by {ctx.author.display_name} | Type `/trivia stop` to end early")
            
            await send_message(embed=embed)
            
            # If private mode, pre-register the host
            if session.is_private:
                session.register_participant(ctx.author.id, ctx.author.name)
                
                # Send a welcome DM to the host
                try:
                    host = await self.bot.fetch_user(ctx.author.id)
                    async with host.typing():
                        await host.send(f"**Welcome to your trivia game on {session.topic}!** Questions will appear here shortly.")
                except Exception as e:
                    logger.error(f"Failed to send welcome DM to host: {e}")
                    await send_message(f"⚠️ {ctx.author.mention} I couldn't send you a DM. Please make sure you have DMs enabled for this server.")
            
            # Wait a moment before starting the first question
            await asyncio.sleep(3)
            
            # Start asking questions
            await self._ask_next_trivia_question(ctx, session, initial_message)
            
        except Exception as e:
            logger.error(f"Error in _start_trivia_session: {e}")
            await send_message(f"❌ An error occurred while starting the trivia session.")
            # Make sure to end the session if it exists
            if self.group_quiz_manager:
                try:
                    # Get guild ID and channel ID safely
                    guild_id = getattr(session, 'guild_id', None)
                    channel_id = getattr(session, 'channel_id', None)
                    if guild_id and channel_id:
                        self.group_quiz_manager.end_session(guild_id, channel_id)
                    elif hasattr(ctx, 'guild') and hasattr(ctx, 'channel'):
                        # Fallback to context
                        guild_id = getattr(ctx.guild, 'id', None)
                        channel_id = getattr(ctx.channel, 'id', None)
                        if guild_id and channel_id:
                            self.group_quiz_manager.end_session(guild_id, channel_id)
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up session: {cleanup_error}")
    
    async def _ask_next_trivia_question(self, ctx, session, initial_message=None):
        """Ask the next question in the trivia session."""
        # Get the channel in a safe way
        channel = None
        if hasattr(ctx, 'channel'):
            channel = ctx.channel
        elif isinstance(ctx, SimpleContextWrapper) and ctx.channel:
            channel = ctx.channel
            
        # Super safe message sending function that uses the channel directly
        # Or edits interaction response/initial message if available for the first question
        async def send_message(content=None, embed=None):
            """100% fail-safe message sending that works with any context type
            Will edit the interaction response or initial message for the first question if available"""
            # Only try to edit for the very first question
            # After that, we need new messages for each question
            if session.current_question_idx == 0:
                # For slash commands, edit the original interaction response
                if hasattr(ctx, 'interaction') and ctx.interaction:
                    try:
                        if embed:
                            return await ctx.interaction.edit_original_response(content=content, embed=embed)
                        else:
                            return await ctx.interaction.edit_original_response(content=content)
                    except Exception as edit_error:
                        logger.warning(f"Failed to edit interaction response: {edit_error}")
                        # Fall through to sending a new message
                
                # For regular commands, edit the initial message
                elif initial_message:
                    try:
                        if embed:
                            return await initial_message.edit(content=content, embed=embed)
                        else:
                            return await initial_message.edit(content=content)
                    except Exception as edit_error:
                        logger.warning(f"Failed to edit initial message: {edit_error}")
                        # Fall through to sending a new message
            
            if channel:
                try:
                    async with channel.typing():
                        return await channel.send(content=content, embed=embed)
                except Exception as channel_error:
                    logger.error(f"Error sending message via channel: {channel_error}")
            
            # Only as a backup, try ctx.send
            if hasattr(ctx, 'send'):
                try:
                    async with ctx.typing():
                        return await ctx.send(content=content, embed=embed)
                except Exception as send_error:
                    logger.error(f"Error sending message via ctx.send: {send_error}")
            
            # Don't even attempt to use followup
            return None
                
        if session.is_finished:
            await self._end_trivia_session(ctx, session)
            return
        
        question = session.current_question
        if not question:
            await self._end_trivia_session(ctx, session)
            return
        
        # Validate the current question before proceeding
        is_valid = (
            hasattr(question, 'question') and question.question and 
            hasattr(question, 'answer') and question.answer and 
            question.answer not in ["Unable to parse from response", "Answer unavailable"]
        )
        
        # For multiple choice, make sure options exist
        if hasattr(question, 'question_type') and question.question_type == "multiple_choice":
            has_options = hasattr(question, 'options') and question.options and len(question.options) > 0
            is_valid = is_valid and has_options
        
        # If question is invalid, try to fix it or skip
        if not is_valid:
            try:
                logger.warning(f"Found invalid question: {question.question if hasattr(question, 'question') else 'Unknown'}")
                
                # Try to fix the question if possible
                fixed = False
                if hasattr(question, 'question') and question.question:
                    if not hasattr(question, 'answer') or not question.answer or question.answer in ["Unable to parse from response", "Answer unavailable"]:
                        # If it has options, use first option as answer
                        if hasattr(question, 'options') and question.options and len(question.options) > 0:
                            question.answer = question.options[0]
                            fixed = True
                            logger.info(f"Fixed invalid question by setting answer to first option: {question.answer}")
                
                # If not fixed or not fixable, skip this question
                if not fixed:
                    logger.warning("Skipping invalid question that couldn't be fixed")
                    # Move to next question
                    session.next_question()
                    await self._ask_next_trivia_question(ctx, session, initial_message)
                    return
            except Exception as e:
                logger.error(f"Error processing invalid question: {e}")
                # Move to next question
                session.next_question()
                await self._ask_next_trivia_question(ctx, session, initial_message)
                return
        
        # Get progress info
        progress_info = session.get_progress_info()
        
        # Check if message_router is available
        if not self.message_router:
            logger.error("Message router not available. Please make sure it's properly initialized.")
            await send_message("❌ An error occurred while sending the quiz question. Please try again later.")
            self.group_quiz_manager.end_session(ctx.guild.id, ctx.channel.id)
            return
        
        try:
            # Determine the destination based on whether this is a private or public trivia
            if session.is_private:
                # For private trivia, send the question to all registered participants
                for user_id in session.participants:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        await self.message_router.send_quiz_question(
                            destination=user,
                            question=question,
                            progress_info=progress_info,
                            is_private=True,
                            timeout=session.timeout
                        )
                    except Exception as e:
                        logger.error(f"Failed to send private question to user {user_id}: {e}")
                
                # Send a notification in the channel that questions were sent privately
                await send_message(f"📝 Question {progress_info['current']}/{progress_info['total']} sent to all participants in DMs. Reply to the bot in DM.")
                message = None  # No public message was sent
            else:
                # For public trivia, send to the channel
                message = await self.message_router.send_quiz_question(
                    destination=ctx.channel,
                    question=question,
                    progress_info=progress_info,
                    is_private=False,
                    timeout=session.timeout
                )
            
            if message:
                session.current_question_message_id = message.id
            
            # Set question start time
            question_start_time = time.time()
            
            # Reset timer cancelled flag for this question
            session._timer_cancelled = False
            
            # Set up a task to handle the timeout
            timer_task = asyncio.create_task(
                self._handle_question_timeout(ctx, session, question_start_time)
            )
            
            # Set up a task to update the time display (only for public messages)
            update_task = None
            if message:
                update_task = asyncio.create_task(
                    self._update_question_timer(message, session, question_start_time)
                )
            
            # Dictionary to track who has already answered
            answered_users = set()
            
            # Wait for answers until timeout
            try:
                while time.time() - question_start_time < session.timeout:
                    try:
                        if session.is_private:
                            # In private mode, wait for DM responses
                            def check_private_msg(m):
                                if not (
                                    isinstance(m.channel, discord.DMChannel) and
                                    m.author.id != self.bot.user.id and
                                    m.author.id in session.participants and
                                    m.author.id not in answered_users
                                ):
                                    return False
                                
                                # Validate answer format based on question type
                                current_q = session.current_question
                                question_type = getattr(current_q, 'question_type', 'multiple_choice')
                                content = m.content.strip().upper()
                                
                                if question_type == "multiple_choice":
                                    # Accept A, B, C, D (letters) or 1, 2, 3, 4 (numbers)
                                    return content in ["A", "B", "C", "D", "1", "2", "3", "4"]
                                elif question_type == "true_false":
                                    # Accept various forms of true/false
                                    return content.lower() in ["true", "false", "t", "f", "yes", "no", "y", "n", "1", "0"]
                                else:
                                    # For short answer, accept any non-empty response
                                    return len(m.content.strip()) > 0
                            
                            message = await self.bot.wait_for(
                                "message",
                                check=check_private_msg,
                                timeout=1.0
                            )
                        else:
                            # In public mode, wait for channel responses
                            def check_public_msg(m):
                                if not (
                                    m.channel.id == ctx.channel.id and
                                    m.author.id != self.bot.user.id and
                                    m.author.id not in answered_users
                                ):
                                    return False
                                
                                # Validate answer format based on question type
                                current_q = session.current_question
                                question_type = getattr(current_q, 'question_type', 'multiple_choice')
                                content = m.content.strip().upper()
                                
                                if question_type == "multiple_choice":
                                    # Accept A, B, C, D (letters) or 1, 2, 3, 4 (numbers)
                                    return content in ["A", "B", "C", "D", "1", "2", "3", "4"]
                                elif question_type == "true_false":
                                    # Accept various forms of true/false
                                    return content.lower() in ["true", "false", "t", "f", "yes", "no", "y", "n", "1", "0"]
                                else:
                                    # For short answer, accept any non-empty response
                                    return len(m.content.strip()) > 0
                            
                            message = await self.bot.wait_for(
                                "message",
                                check=check_public_msg,
                                timeout=1.0
                            )
                        
                        # Register user if not already participating
                        session.register_participant(message.author.id, message.author.name)
                        
                        # Record answer and response time
                        response_time = time.time() - question_start_time
                        is_answer_correct = session.record_answer(message.author.id, message.content, response_time)
                        
                        # Add user to answered set
                        answered_users.add(message.author.id)
                        
                        # React to acknowledge receipt of answer (only for valid answers)
                        try:
                            if is_answer_correct:
                                await message.add_reaction("✅")
                            else:
                                await message.add_reaction("❌")
                        except discord.Forbidden:
                            logger.warning(f"Missing permissions to add reactions in {message.channel.id}")
                        except discord.HTTPException as e_react:
                            logger.warning(f"Failed to add reaction: {e_react}")
                        except Exception as e_gen_react:
                            logger.error(f"General error adding reaction: {e_gen_react}", exc_info=True)
                        
                        # In one winner mode, check if this answer is correct and reveal immediately if it is
                        if session.single_answer_mode and is_answer_correct:
                            # Cancel the timer since we have a correct answer
                            timer_task.cancel()
                            # Cancel the update task if it exists
                            if update_task:
                                update_task.cancel()
                            # Mark the timer task as complete to avoid showing "Time's up" after correct answer
                            session._timer_cancelled = True
                            # We found a correct answer, exit the loop - scores will be calculated in _show_trivia_answers
                            break
                        
                    except asyncio.TimeoutError:
                        # This is just the short timeout, continue the loop
                        continue
                        
            except Exception as e:
                logger.error(f"Error during trivia question: {e}")
            
            # Cancel the timer task
            timer_task.cancel()
            
            # Cancel the update task if it exists
            if update_task:
                update_task.cancel()
            
            # Mark timer as cancelled to prevent any remaining updates
            session._timer_cancelled = True
            
            # Small delay to ensure any pending timer updates complete before we edit the message
            await asyncio.sleep(0.1)
            
            # Only show answers if the session is still active (not stopped)
            if session.is_active:
                # Process answers and show results
                await self._show_trivia_answers(ctx, session)
            
            # Only continue if session is still active
            if session.is_active:
                # Wait between questions
                await asyncio.sleep(session.time_between_questions)
                
                # Move to next question
                session.next_question()
                await self._ask_next_trivia_question(ctx, session, initial_message)
        
        except Exception as e:
            logger.error(f"Error in _ask_next_trivia_question: {e}")
            async with ctx.typing():
                await ctx.send(f"❌ An error occurred while processing the trivia question: {str(e)}")
            # Don't end the session on error, try to continue with the next question
            session.next_question()
            await self._ask_next_trivia_question(ctx, session, initial_message)
    
    async def _update_question_timer(self, message, session, start_time):
        """Update the time display in the quiz question message with improved accuracy."""
        try:
            # Only update public messages
            if not message or not self.message_router:
                return
            
            # Calculate initial time remaining
            total_timeout = session.timeout
            
            # More frequent updates for better accuracy
            update_intervals = {
                5: 0.2,     # Update every 0.2 seconds when under 5 seconds remaining
                10: 0.5,    # Update every 0.5 seconds when under 10 seconds remaining
                30: 1.0,    # Update every 1.0 seconds when under 30 seconds
                60: 2.0,    # Update every 2.0 seconds when under 60 seconds
                120: 3.0    # Update every 3.0 seconds when under 120 seconds
            }
            
            last_displayed_seconds = -1  # Force first update
            
            while True:
                # Check if timer was cancelled early
                if hasattr(session, '_timer_cancelled') and session._timer_cancelled:
                    logger.debug("Timer cancelled, stopping updates")
                    return
                
                # Calculate precise remaining time
                current_time = time.time()
                elapsed = current_time - start_time
                remaining = max(0, total_timeout - elapsed)
                
                # Stop if time is up
                if remaining <= 0:
                    break
                
                current_seconds = int(remaining)
                
                # Determine update interval based on remaining time
                update_interval = 3.0  # Default
                for threshold, interval in sorted(update_intervals.items()):
                    if remaining <= threshold:
                        update_interval = interval
                        break
                
                # Update display when seconds change
                if current_seconds != last_displayed_seconds:
                    try:
                        await self.message_router.update_quiz_time(message, current_seconds, total_timeout)
                        last_displayed_seconds = current_seconds
                        logger.debug(f"Updated timer to {current_seconds}s remaining")
                    except Exception as update_error:
                        logger.warning(f"Failed to update timer: {update_error}")
                        # If we can't update the message, it might have been deleted/edited
                        # Check if timer was cancelled and break if so
                        if hasattr(session, '_timer_cancelled') and session._timer_cancelled:
                            return
                
                # Dynamic sleep based on remaining time and update interval
                sleep_time = min(update_interval, 0.5)
                await asyncio.sleep(sleep_time)
            
            # Final update to show 0 seconds (if timer wasn't cancelled)
            if not (hasattr(session, '_timer_cancelled') and session._timer_cancelled):
                try:
                    await self.message_router.update_quiz_time(message, 0, total_timeout)
                    logger.debug("Final timer update: 0s remaining")
                except Exception as final_update_error:
                    logger.warning(f"Failed to do final timer update: {final_update_error}")
                
        except asyncio.CancelledError:
            # Task was cancelled, do nothing
            pass
        except Exception as e:
            logger.warning(f"Error updating question timer: {e}")
    
    async def _handle_question_timeout(self, ctx, session, start_time):
        """Handle the timeout for a trivia question with improved accuracy."""
        try:
            # Get the initial timeout duration
            timeout = session.timeout
            
            # Use precise timing with shorter sleep intervals for better responsiveness
            while True:
                # Check if timer was cancelled
                if hasattr(session, '_timer_cancelled') and session._timer_cancelled:
                    logger.debug("Timeout handler cancelled")
                    return
                
                # Calculate precise remaining time
                current_time = time.time()
                elapsed = current_time - start_time
                remaining = timeout - elapsed
                
                # If time is up, break the loop
                if remaining <= 0:
                    break
                
                # Sleep for short intervals to maintain responsiveness
                sleep_time = min(0.5, remaining)
                await asyncio.sleep(sleep_time)
            
            # Time is up - check one more time if we were cancelled
            if not (hasattr(session, '_timer_cancelled') and session._timer_cancelled):
                # Only send "Time's up" message if we're not in single answer mode
                # or if no one got the answer yet
                if not session.single_answer_mode:
                    logger.debug("Time's up - triggering timeout")
                    # Don't send separate "Time's up" message since the answer reveal will show
                    # We'll let the answer reveal handle showing that time expired
                else:
                    logger.debug("Time's up in single answer mode")
            else:
                logger.debug("Timeout handler was cancelled before completion")
            
        except asyncio.CancelledError:
            # Task was cancelled, do nothing
            pass
        except Exception as e:
            logger.error(f"Error in question timeout handler: {e}")
    
    async def _show_trivia_answers(self, ctx, session):
        """Show the answers and scores for the current question."""
        from utils.content import truncate_content
        
        question = session.current_question
        
        # Calculate scores based on answers
        correct_responders = session.calculate_scores()
        
        # Create embed for showing the answer with truncated content
        # Check if time expired by looking at session state
        # Timer cancelled means someone answered correctly or it was manually stopped
        # Timer not cancelled means time ran out naturally
        time_expired = not (hasattr(session, '_timer_cancelled') and session._timer_cancelled)
        someone_answered = len(correct_responders) > 0 if correct_responders else False
        
        # Determine the appropriate title based on what happened
        if time_expired and not someone_answered:
            title = "⏰ Time's Up - Answer Revealed!"
            embed_color = Color.orange()
        elif someone_answered:
            title = "✅ Answer Revealed!"
            embed_color = Color.green()
        else:
            title = "📝 Answer Revealed!"
            embed_color = Color.blue()
        embed = Embed(
            title=title,
            description=f"**Question:** {truncate_content(question.question, 'question')}",
            color=embed_color
        )
        
        # Check if this is a true/false question
        is_true_false = False
        if hasattr(question, 'question_type') and question.question_type == "true_false":
            is_true_false = True
        elif isinstance(question.question, str) and question.question.lower().startswith("true or false"):
            is_true_false = True
        
        # Add correct answer - improved handling with content truncation
        if hasattr(question, 'answer') and question.answer and question.answer not in ["Unable to parse from response", "Answer unavailable"]:
            # Truncate answer text before processing
            answer_text = truncate_content(question.answer, 'answer')
            
            # For true/false questions, ensure we display just "True" or "False" without the A/B prefix
            if is_true_false:
                # Clean up answer text for true/false questions
                if answer_text.upper() in ["A", "A. TRUE", "A.TRUE"]:
                    answer_text = "True"
                elif answer_text.upper() in ["B", "B. FALSE", "B.FALSE"]:
                    answer_text = "False"
                elif "true" in answer_text.lower():
                    answer_text = "True"
                elif "false" in answer_text.lower():
                    answer_text = "False"
        elif hasattr(question, 'options') and question.options and len(question.options) > 0:
            # If answer is missing but we have options, use the first option as fallback
            answer_text = question.options[0]
            embed.add_field(name="Note", value="⚠️ The correct answer couldn't be fully determined. This is our best guess.", inline=False)
        else:
            # Last resort
            answer_text = "Unable to determine the correct answer"
        
        # For multiple choice questions, try to display answer with the letter format
        if hasattr(question, 'question_type') and question.question_type == "multiple_choice" and hasattr(question, 'options') and question.options:
            # Clean the options of any letter prefixes
            cleaned_options = []
            for opt in question.options:
                if isinstance(opt, str):
                    # Remove letter prefixes if present
                    cleaned_opt = re.sub(r'^[A-D]\.\s*', '', opt)
                    cleaned_opt = re.sub(r'^[A-D]\)\s*', '', cleaned_opt)
                    cleaned_options.append(cleaned_opt.strip())
                else:
                    cleaned_options.append(opt)
            
            # Try to find the matching option for the answer
            found_match = False
            for i, option in enumerate(cleaned_options):
                if option and isinstance(option, str) and answer_text and isinstance(answer_text, str):
                    if option.lower() == answer_text.lower():
                        answer_text = f"{chr(65 + i)}. {option}"
                        found_match = True
                        break
            
            # If no match found but answer is just a letter, convert it to the option
            if not found_match and isinstance(answer_text, str) and answer_text.upper() in ["A", "B", "C", "D"]:
                idx = ord(answer_text.upper()) - ord("A")
                if 0 <= idx < len(cleaned_options):
                    answer_text = f"{answer_text.upper()}. {cleaned_options[idx]}"
        
        embed.add_field(name="Correct Answer", value=answer_text, inline=False)
        
        # Show explanation if available
        if (
            hasattr(question, 'explanation') and 
            question.explanation and 
            isinstance(question.explanation, str) and
            not question.explanation.lower() in [
                "json parsing error occurred", 
                "no explanation available",
                "unable to parse from original response"
            ]
        ):
            # Clean up the explanation if needed and apply content truncation
            explanation_text = truncate_content(question.explanation, "explanation")
            
            # Fix common "Unable to parse" issues
            if "unable to parse" in explanation_text.lower():
                # Replace with a generic explanation if we can't determine a good one
                if is_true_false:
                    if answer_text.lower() == "true":
                        explanation_text = "The statement is correct."
                    else:
                        explanation_text = "The statement is incorrect."
                else:
                    # Try to generate a simple explanation from the answer
                    explanation_text = f"The correct answer is {answer_text.strip()}."
            
            embed.add_field(name="Explanation", value=explanation_text, inline=False)
        else:
            # Generate a basic explanation if none exists
            if is_true_false:
                if answer_text.lower() == "true":
                    explanation_text = "The statement is correct."
                else:
                    explanation_text = "The statement is incorrect."
                embed.add_field(name="Explanation", value=explanation_text, inline=False)
        
        # Show correct responders with truncated usernames
        if correct_responders:
            responders_text = []
            for i, responder in enumerate(correct_responders[:5]):  # Show top 5 to avoid clutter
                username = truncate_content(responder["username"], "username")
                points = responder["points"]
                total = responder["total_score"]
                time_taken = round(responder["response_time"], 2)
                
                responders_text.append(
                    f"{i+1}. **{username}** (+{points} pts, total: {total}) - {time_taken}s"
                )
            
            embed.add_field(
                name=f"Correct Responders ({len(correct_responders)} total)",
                value="\n".join(responders_text) if responders_text else "None",
                inline=False
            )
        else:
            embed.add_field(
                name="Correct Responders",
                value="No one answered correctly!",
                inline=False
            )
        
        # Show current standings
        leaderboard = session.get_leaderboard(5)  # Top 5
        if leaderboard:
            leaderboard_text = []
            for i, entry in enumerate(leaderboard):
                leaderboard_text.append(
                    f"{i+1}. **{entry['username']}**: {entry['score']} pts"
                )
            
            embed.add_field(
                name="Current Standings",
                value="\n".join(leaderboard_text),
                inline=False
            )
        
        # Show progress
        progress = session.get_progress_info()
        embed.set_footer(text=f"Question {progress['current']}/{progress['total']} | {progress['remaining']} questions remaining")
        
        # Store message reference before editing (in case we need it)
        original_message_id = getattr(session, 'current_question_message_id', None)
        
        # Edit the original question message to show the answer reveal
        # This reduces clutter by replacing the question with the answer
        if session.is_private:
            for user_id in session.participants:
                try:
                    user = await self.bot.fetch_user(user_id)
                    async with user.typing():
                        await user.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send private answer to user {user_id}: {e}")
            
            # Also send a summary in the channel
            summary_embed = Embed(
                title="Question Complete!",
                description=f"Question {progress['current']}/{progress['total']} results have been sent to all participants via DM.",
                color=Color.blue()
            )
            async with ctx.typing():
                await ctx.send(embed=summary_embed)
        else:
            # Try to edit the original question message instead of sending a new one
            if hasattr(session, 'current_question_message_id') and session.current_question_message_id:
                try:
                    # Get the channel where the message was sent
                    channel = ctx.channel if hasattr(ctx, 'channel') else None
                    if channel:
                        # Fetch the original question message
                        original_message = await channel.fetch_message(session.current_question_message_id)
                        # Edit it to show the answer (this will replace the timer and question)
                        await original_message.edit(embed=embed)
                        logger.info(f"Successfully edited question message {session.current_question_message_id} to show answer")
                        
                        # Clear the message ID since we've transformed it to an answer
                        session.current_question_message_id = None
                    else:
                        logger.warning("No channel available to fetch message for editing")
                        # Fall back to sending a new message
                        async with ctx.typing():
                            await ctx.send(embed=embed)
                except Exception as e:
                    logger.warning(f"Failed to edit original question message: {e}")
                    # Fall back to sending a new message if editing fails
                    async with ctx.typing():
                        await ctx.send(embed=embed)
            else:
                # No message ID stored, send a new message
                logger.warning("No question message ID available for editing")
                async with ctx.typing():
                    await ctx.send(embed=embed)
    
    async def _end_trivia_session(self, ctx, session):
        """End a trivia session and show final results."""
        try:
            # Helper function to send messages properly based on context type
            async def send_message(content=None, embed=None):
                """Helper function that handles sending messages correctly based on context type"""
                # Check if this is an Interaction context with followup
                if hasattr(ctx, 'interaction') and ctx.interaction and hasattr(ctx.interaction, 'response') and ctx.interaction.response.is_done():
                    # This is a slash command that has already had its initial response (deferred)
                    return await ctx.followup.send(content=content, embed=embed)
                elif hasattr(ctx, 'followup') and hasattr(ctx, 'responded') and ctx.responded:
                    # Direct interaction context with followup
                    return await ctx.followup.send(content=content, embed=embed)
                else:
                    # Regular context or unresponded interaction
                    return await ctx.send(content=content, embed=embed)
                    
            if session.results_message_sent:
                logger.info(f"Results for session {session.channel_id} already sent. Skipping duplicate send.")
                # Still ensure session is cleaned up by the manager if it wasn't already
                if session.is_active: # Only call manager end if it might still be considered active
                    self.group_quiz_manager.end_session(ctx.guild.id, ctx.channel.id)
                return

            # Mark the session as finished
            session.is_active = False
            session.end_time = datetime.now()
            
            # Calculate duration
            duration = session.end_time - session.start_time
            duration_seconds = duration.total_seconds()
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            duration_str = f"{minutes}m {seconds}s"
            
            # Get provider info from session or use defaults
            provider_name = "Unknown"
            if hasattr(session, 'provider_info') and session.provider_info:
                provider_name = session.provider_info.get("provider_name", "Unknown").capitalize()
            
            # Get final statistics
            quiz_stats = {
                "host_id": session.host_id,
                "host_name": ctx.guild.get_member(session.host_id).display_name if ctx.guild.get_member(session.host_id) else "Unknown",
                "total_questions": len(session.questions),
                "duration": duration_seconds,
                "duration_str": duration_str,
                "provider": provider_name
            }
            
            # Get final leaderboard
            leaderboard = session.get_leaderboard()

            # Generate a unique ID for this quiz instance for database logging
            # Note: Consider if session object should already have a persistent unique ID
            db_quiz_id = f"trivia_{session.channel_id}_{int(session.start_time.timestamp())}"

            # --- BEGIN DATABASE RECORDING (BATCH) ---
            if self.db_service and session.participants:
                logger.info(f"Preparing batch recording for quiz {db_quiz_id} in channel {session.channel_id}")
                
                # Collect results for all participants into a list
                batch_results_data = []
                for user_id, participant_data in session.participants.items():
                    try:
                        username = participant_data.get("username", "UnknownUser")
                        # Try to update username if it's 'UnknownUser' and we have a member object
                        if username == "UnknownUser":
                            try:
                                member = ctx.guild.get_member(user_id)
                                if member:
                                    username = member.display_name
                                    logger.info(f"Updated 'UnknownUser' to actual Discord username: {username} for user ID {user_id}")
                            except Exception as name_e:
                                logger.warning(f"Failed to update username for user {user_id}: {name_e}")
                        correct = participant_data.get("correct_answers", 0)
                        wrong = participant_data.get("incorrect_answers", 0)
                        points = participant_data.get("score", 0)
                        difficulty = session.questions[0].difficulty if session.questions else "unknown"
                        category = session.questions[0].category if session.questions else "unknown"
                        
                        batch_results_data.append({
                            'user_id': user_id,
                            'username': username,
                            'correct': correct,
                            'wrong': wrong,
                            'points': points,
                            'difficulty': difficulty,
                            'category': category
                        })
                    except Exception as data_error:
                         logger.error(f"Error preparing data for user {user_id} in batch recording for quiz {db_quiz_id}: {data_error}", exc_info=True)
                
                # Call the batch recording function if we have data
                if batch_results_data:
                    await record_batch_quiz_results(
                        db_service=self.db_service,
                        quiz_id=db_quiz_id,
                        topic=session.topic,
                        results=batch_results_data,
                        guild_id=ctx.guild.id if ctx.guild else None
                    )
                else:
                    logger.warning(f"No participant data collected for batch recording in quiz {db_quiz_id}")

            elif not self.db_service:
                logger.warning("Database service not available. Skipping statistics recording.")

            # Check if message_router is available
            if not self.message_router:
                logger.error("Message router not available in _end_trivia_session")
                await send_message("❌ An error occurred while ending the trivia game. The session has been closed.")
                # Ensure session is ended by manager even on error before sending results
                self.group_quiz_manager.end_session(ctx.guild.id, ctx.channel.id) 
                return
            
            # Mark that we are about to send the results message
            session.results_message_sent = True

            # Show results - either privately to each participant and summarized to the channel, or just to the channel
            if session.is_private:
                # Send detailed results to each participant
                for user_id in session.participants:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        await self.message_router.send_quiz_results(
                            destination=user,
                            topic=session.topic,
                            leaderboard=leaderboard,
                            quiz_stats=quiz_stats,
                            is_private=True
                        )
                    except Exception as e:
                        logger.error(f"Failed to send private results to user {user_id}: {e}")
                
                # Also send a summary to the channel
                await self.message_router.send_quiz_results(
                    destination=ctx.channel,
                    topic=session.topic,
                    leaderboard=leaderboard,
                    quiz_stats=quiz_stats,
                    is_private=False
                )
            else:
                # Send results to the channel only
                await self.message_router.send_quiz_results(
                    destination=ctx.channel,
                    topic=session.topic,
                    leaderboard=leaderboard,
                    quiz_stats=quiz_stats,
                    is_private=False
                )
            
            # End the session in the manager to clean up resources
            self.group_quiz_manager.end_session(ctx.guild.id, ctx.channel.id)
            
        except Exception as e:
            logger.error(f"Error ending trivia session: {e}")
            await send_message("❌ An error occurred while ending the trivia game, but the session has been closed.")
            # Ensure the session is ended even if there's an error
            self.group_quiz_manager.end_session(ctx.guild.id, ctx.channel.id)
    
    # Hybrid command for trivia stop
    @trivia_group.command(name="stop", description="Stop the currently active trivia quiz in this channel")
    async def trivia_stop(self, ctx: commands.Context):
        """Stop the currently active trivia quiz in this channel."""
        # For slash commands, we need to handle the interaction properly
        if hasattr(ctx, 'interaction') and ctx.interaction:
            # Defer the response to avoid the "interaction already responded to" error
            if not ctx.interaction.response.is_done():
                await ctx.interaction.response.defer(ephemeral=False)
                
        # Call implementation
        await self._trivia_stop_impl(ctx)
    
    # Shared implementation method
    async def _trivia_stop_impl(self, ctx):
        """Implementation of trivia stop that works with both command types."""
        try:
            # Helper function to send messages properly based on context type
            async def send_message(content=None, embed=None):
                """Helper function that handles sending messages correctly based on context type"""
                # Check if this is an Interaction context with followup
                if hasattr(ctx, 'interaction') and ctx.interaction and hasattr(ctx.interaction, 'response') and ctx.interaction.response.is_done():
                    # This is a slash command that has already had its initial response (deferred)
                    return await ctx.followup.send(content=content, embed=embed)
                elif hasattr(ctx, 'followup') and hasattr(ctx, 'responded') and ctx.responded:
                    # Direct interaction context with followup
                    return await ctx.followup.send(content=content, embed=embed)
                else:
                    # Regular context or unresponded interaction
                    return await ctx.send(content=content, embed=embed)
                    
            if not self.group_quiz_manager:
                await send_message("❌ Group quiz manager is not initialized. Please try again later.")
                logger.error("Group quiz manager not initialized in trivia_stop")
                return
                
            # Check if there's an active quiz in this channel
            active_session = self.group_quiz_manager.get_session(ctx.guild.id, ctx.channel.id)
            if not active_session or active_session.is_finished:
                await send_message("❌ There's no active trivia game in this channel.")
                return
            
            # Check if the user is the host or has manage channels permission
            if ctx.author.id != active_session.host_id and not ctx.author.guild_permissions.manage_channels:
                await send_message("❌ Only the host or a moderator can stop this trivia game.")
                return
            
            # Set flags to prevent any future answer processing
            active_session.is_active = False
            active_session._timer_cancelled = True
            
            # Don't end the session here directly - instead show results first
            await send_message("✅ Trivia game stopped.")
            
            # Call the _end_trivia_session method to show results properly
            try:
                # This properly calculates stats and shows the leaderboard
                await self._end_trivia_session(ctx, active_session)
            except Exception as e:
                logger.error(f"Error ending trivia session from stop command: {e}")
                await send_message("❌ An error occurred while ending the trivia game, but the session has been closed.")
                # Fallback if _end_trivia_session fails
                self.group_quiz_manager.end_session(ctx.guild.id, ctx.channel.id)
                
        except Exception as e:
            logger.error(f"Error in trivia_stop command: {e}")
            # Try to respond to the user regardless of the error
            try:
                await send_message("❌ An unexpected error occurred while stopping the trivia game.")
            except Exception as final_error:
                logger.error(f"Failed to send final error message: {final_error}")
                pass
    
    # Hybrid command for trivia leaderboard
    @trivia_group.command(name="leaderboard", description="Show the leaderboard for the current trivia game")
    async def trivia_leaderboard(self, ctx: commands.Context):
        """Show the leaderboard for the current trivia game."""
        # For slash commands, we need to handle the interaction properly
        if hasattr(ctx, 'interaction') and ctx.interaction:
            # Defer the response to avoid the "interaction already responded to" error
            if not ctx.interaction.response.is_done():
                await ctx.interaction.response.defer(ephemeral=False)
                
        # Call implementation
        await self._trivia_leaderboard_impl(ctx)
    
    # Shared implementation method
    async def _trivia_leaderboard_impl(self, ctx):
        """Implementation of trivia leaderboard that works with both command types."""
        try:
            if not self.group_quiz_manager:
                async with ctx.typing():
                    await ctx.send("❌ Group quiz manager is not initialized. Please try again later.")
                logger.error("Group quiz manager not initialized in trivia_leaderboard")
                return
                
            # Check if there's an active quiz in this channel
            active_session = self.group_quiz_manager.get_session(ctx.guild.id, ctx.channel.id)
            if not active_session:
                async with ctx.typing():
                    await ctx.send("❌ There's no active trivia game in this channel.")
                return
            
            # Get the leaderboard
            leaderboard = active_session.get_leaderboard()
            
            if not leaderboard:
                async with ctx.typing():
                    await ctx.send("No participants in this trivia game yet.")
                return
                
            # Create an embed with the leaderboard
            embed = create_embed(
                title="📊 Trivia Leaderboard",
                description=f"Current standings for trivia on topic **{active_session.topic}**",
                color=Color.blue()
            )
            
            # Add leaderboard entries
            for i, entry in enumerate(leaderboard[:10], 1):
                username = entry["username"]
                score = entry["score"]
                correct = entry.get("correct", 0)
                wrong = entry.get("incorrect", 0)
                
                embed.add_field(
                    name=f"{i}. {username}",
                    value=f"Score: **{score}** points\nCorrect: {correct} | Wrong: {wrong}",
                    inline=False
                )
            
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in trivia_leaderboard command: {e}")
            # Try to respond to the user regardless of the error
            try:
                async with ctx.typing():
                    await ctx.send("❌ An unexpected error occurred while getting the leaderboard.")
            except:
                pass
async def setup(bot):
    """Setup function for the cog."""
    try:
        # Create and add cog
        cog = GroupQuizCog(bot)
        await bot.add_cog(cog)
        logger.debug("GroupQuizCog loaded via setup function")
        return cog
    except Exception as e:
        logger.error(f"Error loading GroupQuizCog: {e}")
        raise


async def setup_with_context(bot, context):
    """Setup function that uses the context pattern."""
    try:
        # Create and add cog with context
        cog = GroupQuizCog(bot)
        cog.set_context(context)
        await bot.add_cog(cog)
        logger.debug("GroupQuizCog loaded via setup_with_context function")
        return cog
    except Exception as e:
        logger.error(f"Error loading GroupQuizCog with context: {e}")
        raise
