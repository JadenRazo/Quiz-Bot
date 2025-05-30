import discord
import logging
import asyncio
from typing import Dict, List, Optional, Union, Any, Callable, Coroutine
from discord import Embed, Color, User, Member, Message, TextChannel, DMChannel
import re

logger = logging.getLogger("bot.message_service")

class MessageRouter:
    """Routes messages to the appropriate channel (public or private)."""
    
    def __init__(self, bot):
        self.bot = bot
        self.pending_dms: Dict[int, List[Dict[str, Any]]] = {}  # user_id -> list of pending messages
    
    async def send_message(self, destination: Union[TextChannel, User, Member, int], 
                          content: Optional[str] = None, embed: Optional[Embed] = None, 
                          is_private: bool = False) -> Optional[Message]:
        """
        Send a message to the appropriate destination.
        
        Args:
            destination: The channel, user, or ID to send the message to
            content: The text content of the message
            embed: An optional embed to send
            is_private: Whether to send as a private message
            
        Returns:
            The sent message or None if sending failed
        """
        try:
            # If destination is an ID, resolve it
            if isinstance(destination, int):
                # Try to find a channel with this ID first
                channel = self.bot.get_channel(destination)
                if channel:
                    destination = channel
                else:
                    # Try to find a user with this ID
                    try:
                        destination = await self.bot.fetch_user(destination)
                    except discord.NotFound:
                        logger.error(f"Could not find channel or user with ID {destination}")
                        return None
            
            # Send to DM if private or if destination is already a user
            if is_private or isinstance(destination, (User, Member)):
                if isinstance(destination, (User, Member)):
                    # Get or create DM channel
                    if not destination.dm_channel:
                        await destination.create_dm()
                    
                    # Send to DM channel
                    return await destination.dm_channel.send(content=content, embed=embed)
                else:
                    logger.error(f"Cannot send private message to {destination}")
                    return None
            else:
                # Send to regular channel
                return await destination.send(content=content, embed=embed)
                
        except discord.Forbidden:
            # Log error and add to pending DMs if this was a DM attempt
            logger.warning(f"Failed to send message: Missing permissions")
            if isinstance(destination, (User, Member)):
                user_id = destination.id
                if user_id not in self.pending_dms:
                    self.pending_dms[user_id] = []
                    
                self.pending_dms[user_id].append({
                    "content": content,
                    "embed": embed
                })
                logger.info(f"Added message to pending DMs for user {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    async def send_quiz_question(self, destination: Union[TextChannel, User, Member, int],
                               question: Any, progress_info: Dict[str, Any], 
                               is_private: bool = False, timeout: int = 30) -> Optional[Message]:
        """
        Send a formatted quiz question.
        
        Args:
            destination: Where to send the question
            question: The question object
            progress_info: Information about quiz progress
            is_private: Whether to send as private message
            timeout: Time limit for the question in seconds
            
        Returns:
            The sent message or None if sending failed
        """
        try:
            # Validate question data before creating embed
            if not hasattr(question, 'question') or not question.question:
                logger.error("Invalid question: missing question text")
                return None
                
            # Create question embed
            embed = Embed(
                title=f"Question {progress_info['current']}/{progress_info['total']}",
                description=question.question,
                color=Color.blue()
            )
            
            # Detect true/false questions by content if not already marked as such
            is_true_false = False
            if hasattr(question, 'question_type') and question.question_type == "true_false":
                is_true_false = True
            elif isinstance(question.question, str) and question.question.lower().startswith("true or false"):
                is_true_false = True
                # Set the question type if available
                if hasattr(question, 'question_type'):
                    question.question_type = "true_false"
            
            # Handle options based on question type
            if is_true_false:
                # For true/false questions, show simple True/False options without letter prefixes
                embed.add_field(name="Options", value="True\nFalse", inline=False)
            elif hasattr(question, 'question_type') and question.question_type == "multiple_choice":
                if hasattr(question, 'options') and question.options and len(question.options) > 0:
                    # Filter out any None or empty options
                    valid_options = [opt for opt in question.options if opt and isinstance(opt, str)]
                    
                    if valid_options:
                        # Enhanced placeholder detection regex patterns
                        placeholder_patterns = [
                            r'^.*\s(answer|option)\s*\d+$',          # "answer X" pattern
                            r'^option\s*\d+.*$',                     # "option X" pattern
                            r'^alternative\s*\d+.*$',                # "alternative X" pattern
                            r'^alternative\s*option.*$',             # "alternative option" pattern
                            r'.*placeholder.*',                      # Contains "placeholder"
                            r'^(first|second|third|fourth) answer option$', # Generic fallback options
                        ]
                        
                        # Check for generic placeholder options
                        placeholder_count = 0
                        generic_options = True
                        
                        for opt in valid_options:
                            # Check each option against placeholder patterns
                            is_placeholder = False
                            for pattern in placeholder_patterns:
                                if re.match(pattern, opt.lower().strip()):
                                    placeholder_count += 1
                                    is_placeholder = True
                                    break
                            
                            if not is_placeholder:
                                generic_options = False
                        
                        # If all options are generic/placeholders, try to regenerate them
                        if generic_options and placeholder_count >= len(valid_options):
                            try:
                                # Try to regenerate better options using quiz_generator
                                from services.quiz_generator import quiz_generator
                                topic = getattr(question, 'category', 'general')
                                question_text = getattr(question, 'question', '')
                                
                                # Generate better options using the current question
                                new_options = quiz_generator._generate_fallback_options(question_text, topic, topic)
                                
                                # If we got meaningful options, use them
                                if new_options and len(new_options) >= 2:
                                    valid_options = new_options
                                    
                                    # Update the question object with these improved options
                                    if hasattr(question, 'options'):
                                        question.options = new_options
                                    
                                    logger.info(f"Regenerated better options for question: {question_text[:30]}...")
                            except Exception as e:
                                logger.error(f"Failed to regenerate options: {e}")
                        
                        # Clean any duplicated letter prefixes in options to avoid "A. A. Option"
                        options_text = []
                        
                        for i, option in enumerate(valid_options):
                            # Skip this option if it looks like a placeholder after all our filtering
                            if re.match(r'^(option|alternative|answer)\s+\d+$', option.lower().strip()):
                                logger.warning(f"Skipping placeholder option after filtering: {option}")
                                continue
                                
                            # Skip if the option is empty
                            if not option or not option.strip():
                                continue
                                
                            # Remove existing letter prefixes if present
                            clean_option = re.sub(r'^[A-D]\.\s*', '', option)
                            clean_option = re.sub(r'^[A-D]\)\s*', '', clean_option)
                            
                            # Also handle numeric prefixes
                            clean_option = re.sub(r'^\d+\.\s*', '', clean_option)
                            clean_option = re.sub(r'^\d+\)\s*', '', clean_option)
                            
                            # Add the correct letter prefix
                            options_text.append(f"{chr(65 + len(options_text))}. {clean_option.strip()}")
                            
                        # If we have too few or no options after filtering, try again
                        if len(options_text) < 2:
                            try:
                                # More aggressive refresh of options
                                from services.quiz_generator import quiz_generator
                                topic = getattr(question, 'category', 'general')
                                question_text = getattr(question, 'question', '')
                                
                                # Direct call for better options with the domain info if we can extract it
                                domain_keywords = {
                                    "virtualization": ["vm", "virtual", "vmware", "docker", "container", "hypervisor"],
                                    "programming": ["code", "function", "class", "method", "programming", "language"],
                                    "security": ["security", "encryption", "malware", "virus", "attack", "firewall"],
                                    "networking": ["network", "router", "protocol", "ip", "tcp", "ethernet"],
                                    "database": ["database", "sql", "query", "table", "join", "index"],
                                    "os": ["windows", "linux", "unix", "boot", "kernel", "system"]
                                }
                                
                                # Try to detect domain
                                detected_domain = None
                                for domain, keywords in domain_keywords.items():
                                    if any(keyword in question_text.lower() for keyword in keywords):
                                        detected_domain = domain
                                        break
                                
                                # Create hard-coded options based on domain and question for VMware question
                                question_lower = question_text.lower()
                                if "vmware" in question_lower and "disk" in question_lower and "extension" in question_lower:
                                    new_options = [
                                        ".vmdk (Virtual Machine Disk)",
                                        ".vhd (Virtual Hard Disk)",
                                        ".iso (Disk Image File)",
                                        ".ova (Open Virtualization Archive)"
                                    ]
                                    
                                    # Update question options
                                    if hasattr(question, 'options'):
                                        question.options = new_options
                                        
                                    # Display these options
                                    options_text = []
                                    for i, option in enumerate(new_options):
                                        options_text.append(f"{chr(65 + i)}. {option}")
                                        
                                    logger.info(f"Used domain-specific options for VMware disk question")
                                else:
                                    # Try the regular fallback generator
                                    new_options = quiz_generator._generate_fallback_options(question_text, topic, topic)
                                    
                                    if new_options and len(new_options) >= 2:
                                        # Update the options
                                        question.options = new_options
                                        
                                        # Create display text with letter prefixes
                                        options_text = []
                                        for i, option in enumerate(new_options):
                                            if option and isinstance(option, str) and len(option.strip()) > 0:
                                                options_text.append(f"{chr(65 + i)}. {option.strip()}")
                                        
                                        logger.info(f"Used fallback options for question: {question_text[:30]}...")
                            except Exception as e:
                                logger.error(f"Failed to generate better options: {e}")
                                
                        # Display the options
                        if options_text:
                            embed.add_field(name="Options", value="\n".join(options_text), inline=False)
                        else:
                            # Log error for debugging
                            logger.warning(f"Multiple choice question has filtered out all options: {question.question}")
                            embed.add_field(name="Note", value="⚠️ This question's options appear to be invalid. Please try again.", inline=False)
                    else:
                        # Log error for debugging
                        logger.warning(f"Multiple choice question has no valid options: {question.question}")
                        embed.add_field(name="Note", value="⚠️ This question appears to be missing its options.", inline=False)
                else:
                    # Log error for debugging
                    logger.warning(f"Multiple choice question has no options: {question.question}")
                    embed.add_field(name="Note", value="⚠️ This question appears to be missing its options.", inline=False)
            
            # Add progress bar
            progress_percent = progress_info.get('progress_percent', 0)
            progress_bar = self._create_progress_bar(progress_percent, length=8, use_emoji=True)
            
            embed.add_field(
                name="Progress", 
                value=progress_bar,
                inline=False
            )
            
            # Add time remaining with rotating clock emoji
            clock_emoji = self._get_clock_emoji(timeout, timeout)
            time_display = f"{clock_emoji} {timeout}s remaining"
            
            embed.add_field(
                name="Time",
                value=time_display,
                inline=False
            )
                    
            # Add difficulty and category if available
            difficulty = getattr(question, 'difficulty', 'Unknown')
            category = getattr(question, 'category', 'General')
        
            embed.set_footer(
                text=f"Difficulty: {difficulty} | Category: {category}"
            )
            
            # Send the message
            message = await self.send_message(
                destination=destination,
                embed=embed,
                is_private=is_private
            )
                    
            # Log successful question sending
            if message:
                logger.info(f"Sent question {progress_info['current']}/{progress_info['total']} to {destination} (private: {is_private})")
            
            return message
            
        except Exception as e:
            logger.error(f"Error sending quiz question: {e}")
            return None
    
    async def send_answer_feedback(self, destination: Union[TextChannel, User, Member, int],
                                 question: Any, user_answer: str, is_correct: bool,
                                 points_earned: int = 0, is_private: bool = False) -> Optional[Message]:
        """
        Send feedback about an answer.
        
        Args:
            destination: Where to send the feedback
            question: The question that was answered
            user_answer: The user's answer
            is_correct: Whether the answer was correct
            points_earned: Points earned for this answer
            is_private: Whether to send as private message
            
        Returns:
            The sent message or None if sending failed
        """
        color = Color.green() if is_correct else Color.red()
        title = "✅ Correct!" if is_correct else "❌ Incorrect"
        
        embed = Embed(
            title=title,
            description=f"**Question:** {question.question}",
            color=color
        )
        
        embed.add_field(
            name="Your Answer",
            value=user_answer,
            inline=True
        )
        
        embed.add_field(
            name="Correct Answer",
            value=question.answer,
            inline=True
        )
        
        if is_correct and points_earned > 0:
            embed.add_field(
                name="Points Earned",
                value=f"+{points_earned} points",
                inline=False
            )
        
        if question.explanation:
            embed.add_field(
                name="Explanation",
                value=question.explanation,
                inline=False
            )
        
        # Send the message
        return await self.send_message(
            destination=destination,
            embed=embed,
            is_private=is_private
        )
    
    async def update_quiz_time(self, message: Message, seconds_remaining: int, total_seconds: int) -> None:
        """
        Update a quiz question message with new time remaining.
        
        Args:
            message: The message to update
            seconds_remaining: Current seconds remaining
            total_seconds: Total seconds for the question
        """
        try:
            if not message or not message.embeds:
                return
                
            embed = message.embeds[0]
            
            # Update the time field
            clock_emoji = self._get_clock_emoji(seconds_remaining, total_seconds)
            time_display = f"{clock_emoji} {seconds_remaining}s remaining"
            
            # Find and update the time field
            for i, field in enumerate(embed.fields):
                if field.name == "Time":
                    embed.set_field_at(i, name="Time", value=time_display, inline=False)
                    break
            
            # Update the message
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.warning(f"Failed to update quiz time: {e}")
    
    async def send_quiz_results(self, destination: Union[TextChannel, User, Member, int],
                              topic: str, leaderboard: List[Dict[str, Any]], 
                              quiz_stats: Dict[str, Any],
                              is_private: bool = False) -> Optional[Message]:
        """
        Send quiz results with leaderboard.
        
        Args:
            destination: Where to send the results
            topic: The quiz topic
            leaderboard: List of participants and their scores
            quiz_stats: Statistics about the quiz
            is_private: Whether to send as private message
            
        Returns:
            The sent message or None if sending failed
        """
        embed = Embed(
            title="Quiz Completed!",
            description=f"Topic: **{topic}**\n"
                       f"Questions: **{quiz_stats.get('total_questions', 0)}**\n"
                       f"Duration: **{quiz_stats.get('duration_str', '0m 0s')}**",
            color=Color.green()
        )
        
        # Add leaderboard
        if leaderboard:
            leaderboard_text = []
            for i, entry in enumerate(leaderboard[:10]):  # Show top 10
                username = entry.get("username", f"User {entry.get('user_id', 'Unknown')}")
                score = entry.get("score", 0)
                correct = entry.get("correct", 0)
                total = quiz_stats.get("total_questions", 0)
                
                medal = ""
                if i == 0:
                    medal = "🥇 "
                elif i == 1:
                    medal = "🥈 "
                elif i == 2:
                    medal = "🥉 "
                
                # Calculate XP earned (assuming base XP = correct * 10)
                xp_earned = correct * 10
                
                leaderboard_text.append(
                    f"{medal}**{i+1}.** {username}: {score} points ({correct}/{total} correct) • +{xp_earned} XP"
                )
            
            embed.add_field(
                name="Leaderboard",
                value="\n".join(leaderboard_text) if leaderboard_text else "No participants",
                inline=False
            )
        else:
            embed.add_field(
                name="Results",
                value="No one participated in this quiz.",
                inline=False
            )
        
        # Calculate total XP awarded
        total_xp = sum(entry.get("correct", 0) * 10 for entry in leaderboard) if leaderboard else 0
        
        # Add quiz stats
        if quiz_stats.get("host_name"):
            embed.set_footer(
                text=f"Quiz hosted by {quiz_stats.get('host_name')} | "
                    f"Generated by {quiz_stats.get('provider', 'Unknown').capitalize()} | "
                    f"💫 Total XP awarded: {total_xp}"
            )
        
        # Send the message
        return await self.send_message(
            destination=destination,
            embed=embed,
            is_private=is_private
        )
    
    def _create_progress_bar(self, percent: float, length: int = 10, use_emoji: bool = True) -> str:
        """Create a progress bar with custom emojis or text characters."""
        from utils.progress_bars import create_progress_bar
        
        # Convert percent (0-100) to current/max format
        current = int(percent * length / 100)
        maximum = length
        
        # Use the central progress bar implementation
        return create_progress_bar(
            current=current,
            maximum=maximum,
            length=length,
            show_percentage=True,
            use_emoji=use_emoji
        )
    
    def _get_clock_emoji(self, seconds_remaining: int, total_seconds: int) -> str:
        """Get the appropriate clock emoji based on time remaining."""
        # Clock emojis representing each hour position (12:00 to 11:00)
        clock_emojis = [
            "🕐", "🕑", "🕒", "🕓", "🕔", "🕕",  # 1:00 to 6:00
            "🕖", "🕗", "🕘", "🕙", "🕚", "🕛"   # 7:00 to 12:00
        ]
        
        # Calculate position based on time remaining
        if total_seconds > 0:
            # Calculate progress (0 = start, 1 = end)
            progress = 1 - (seconds_remaining / total_seconds)
            
            # Map progress to clock position (12 positions)
            # When starting (progress=0), show 12:00 (🕛)
            # As time passes, move clockwise through the hours
            position = int(progress * 12)
            
            # Ensure we don't go beyond the array bounds
            if position >= 12:
                position = 11
                
            # Start from 12:00 (last emoji) and move clockwise
            index = (11 + position) % 12
        else:
            index = 11  # 12:00 position when time is up
            
        return clock_emojis[index]
    
    async def process_pending_dms(self) -> None:
        """Process any pending DMs that failed to send previously."""
        for user_id, messages in list(self.pending_dms.items()):
            try:
                user = await self.bot.fetch_user(user_id)
                if not user.dm_channel:
                    await user.create_dm()
                
                for message_data in messages:
                    try:
                        await user.dm_channel.send(
                            content=message_data.get("content"),
                            embed=message_data.get("embed")
                        )
                    except Exception as e:
                        logger.error(f"Failed to send pending DM to user {user_id}: {e}")
                        continue
                
                # Remove from pending list
                del self.pending_dms[user_id]
                
            except Exception as e:
                logger.error(f"Failed to process pending DMs for user {user_id}: {e}")
    
    async def process_message(self, message: discord.Message) -> None:
        """
        Process a non-command message for interactive features.
        
        Args:
            message: The Discord message to process
        """
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Check if this is a reply to an active quiz or trivia
        if self.bot.context and hasattr(self.bot.context, 'group_quiz_manager'):
            group_quiz = self.bot.context.group_quiz_manager
            if group_quiz:
                # Fixed to include guild_id parameter which is required by GroupQuizManager.get_session
                guild_id = message.guild.id if message.guild else None
                if guild_id is not None:
                    session = group_quiz.get_session(guild_id, message.channel.id)
                else:
                    # Skip DM message processing since this is likely a direct message
                    session = None
                if session and session.is_active and not session.is_finished:
                    # This could be an answer to the current question
                    # Process trivia answers here if needed
                    return
        
        # Could add more message processing features here, like:
        # - Responding to keywords
        # - Processing natural language inquiries
        # - Handling interactive tutorials
        
        # For now, we'll just pass and not process non-command messages further
        return


# This will be instantiated in the main bot initialization
message_router = None 