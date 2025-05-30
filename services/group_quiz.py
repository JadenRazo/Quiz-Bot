import discord
import asyncio
import logging
import random
from typing import Dict, List, Optional, Union, Any, Set, Tuple
from datetime import datetime, timedelta

from discord import Embed, Color, User, Member

logger = logging.getLogger("bot.group_quiz")

class GroupQuizSession:
    """Manages a group quiz session that works like a trivia game."""
    
    def __init__(
        self, 
        guild_id: int,
        channel_id: int,
        host_id: int,
        topic: str,
        questions: List[Any],
        timeout: int = 30,
        time_between_questions: int = 5,
        max_participants: int = 20,
        provider_info: Optional[Dict[str, Any]] = None,
        single_answer_mode: bool = False,
        is_private: bool = False
    ):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.topic = topic
        self.questions = questions
        self.timeout = timeout
        self.time_between_questions = time_between_questions
        self.max_participants = max_participants
        self.provider_info = provider_info or {}
        self.single_answer_mode = single_answer_mode
        self.is_private = is_private
        
        # Session data
        self.participants: Dict[int, Any] = {}  # user_id -> {score, correct_answers, etc.}
        self.current_question_idx = 0
        self.is_active = False
        self.start_time = None
        self.end_time = None
        
        # Question tracking
        self.current_answers: Dict[int, str] = {}  # user_id -> answer
        self.current_question_message_id = None
        self.question_timer = None
        self.correct_answerers_this_question: Set[int] = set()  # Track users who've already answered correctly
        self.results_message_sent = False # Flag to prevent duplicate result messages
        self._timer_cancelled = False  # Flag for timer cancellation
    
    @property
    def current_question(self) -> Optional[Any]:
        """Get the current question."""
        if 0 <= self.current_question_idx < len(self.questions):
            return self.questions[self.current_question_idx]
        return None
    
    @property
    def is_finished(self) -> bool:
        """Check if the quiz is finished."""
        return not self.is_active or self.current_question_idx >= len(self.questions)
    
    @property
    def remaining_questions(self) -> int:
        """Get the number of remaining questions."""
        return max(0, len(self.questions) - self.current_question_idx - 1)
    
    def register_participant(self, user_id: int, username: str) -> bool:
        """Register a participant for the quiz session."""
        if len(self.participants) >= self.max_participants:
            return False
            
        if user_id not in self.participants:
            self.participants[user_id] = {
                "username": username,
                "score": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "response_times": []
            }
            return True
        return False
    
    def record_answer(self, user_id: int, answer: str, response_time: float) -> bool:
        """Record a user's answer to the current question and determine if it's correct."""
        if user_id not in self.participants or self.is_finished or not self.current_question:
            return False # Indicates failure to record or no basis for correctness

        # Record the answer and response time regardless of correctness
        self.current_answers[user_id] = answer
        self.participants[user_id]["response_times"].append(response_time)

        # Determine correctness
        is_correct = False
        current_q = self.current_question
        
        # Get the correct answer, handling potential issues
        if hasattr(current_q, 'answer') and current_q.answer and current_q.answer not in ["Unable to parse from response", "Answer unavailable"]:
            correct_answer_text = current_q.answer.lower()
        elif hasattr(current_q, 'options') and current_q.options and len(current_q.options) > 0:
            correct_answer_text = current_q.options[0].lower() # Fallback to first option
        else:
            return False # Cannot determine correctness if question has no answer

        if not answer: # Empty answer is incorrect
            return False

        question_type = getattr(current_q, 'question_type', 'multiple_choice')

        if question_type == "multiple_choice":
            options = getattr(current_q, 'options', [])
            user_ans_upper = answer.upper()
            if user_ans_upper in ["A", "B", "C", "D"] and options:
                index = ord(user_ans_upper) - ord("A")
                if 0 <= index < len(options):
                    is_correct = options[index].lower() == correct_answer_text
            elif answer in ["1", "2", "3", "4"] and options:
                index = int(answer) - 1
                if 0 <= index < len(options):
                    is_correct = options[index].lower() == correct_answer_text
            else:
                is_correct = answer.lower() == correct_answer_text
                if not is_correct and options:
                    for opt_text in options:
                        if answer.lower() == opt_text.lower():
                            is_correct = opt_text.lower() == correct_answer_text
                            break
        
        elif question_type == "true_false":
            normalized_user_answer = "true" if answer.lower() in ["true", "t", "yes", "y", "1"] else "false"
            normalized_correct_answer = "true" if correct_answer_text.lower() in ["true", "t", "yes", "y", "1"] else "false"
            is_correct = normalized_user_answer == normalized_correct_answer
            
        else:  # short_answer
            user_answer_normalized = answer.lower().strip().replace(".", "").replace(",", "")
            correct_answer_normalized = correct_answer_text.lower().strip().replace(".", "").replace(",", "")
            is_correct = user_answer_normalized == correct_answer_normalized
            if not is_correct:
                if (user_answer_normalized in correct_answer_normalized or
                        correct_answer_normalized in user_answer_normalized):
                    is_correct = True
        
        # Mark as correct answer immediately for single answer mode
        if is_correct and self.single_answer_mode:
            self.correct_answerers_this_question.add(user_id)

        return is_correct
    
    def calculate_scores(self) -> List[Dict[str, Any]]:
        """Calculate scores for the current question and return list of correct responders."""
        if not self.current_question:
            return []
            
        # Get the correct answer, handling potential issues
        if hasattr(self.current_question, 'answer') and self.current_question.answer and self.current_question.answer not in ["Unable to parse from response", "Answer unavailable"]:
            correct_answer = self.current_question.answer.lower()
        elif hasattr(self.current_question, 'options') and self.current_question.options and len(self.current_question.options) > 0:
            # If answer is missing but we have options, use the first option as fallback
            correct_answer = self.current_question.options[0].lower()
        else:
            # No valid answer available, can't score this question
            return []
        
        correct_responders = []
        
        # Only reset if not in single answer mode (in single answer mode, we track during answer recording)
        if not self.single_answer_mode:
            self.correct_answerers_this_question = set()
        
        # Sort answers by timestamp if in single answer mode (fastest answer first)
        answer_items = list(self.current_answers.items())
        if self.single_answer_mode:
            # Sort by response time
            answer_items = sorted(
                [(user_id, answer) for user_id, answer in answer_items],
                key=lambda item: self.participants[item[0]]["response_times"][-1]
            )
        
        for user_id, answer in answer_items:
            # In single answer mode, we need to determine if this user should get points
            should_award_points = True
            if self.single_answer_mode and self.correct_answerers_this_question:
                # Someone already answered correctly in single answer mode
                # This user won't get points, but we still need to process their answer for stats
                should_award_points = False
                
            is_correct = False
            
            # Skip processing if the answer is empty
            if not answer:
                continue
                
            # Check if the answer is correct based on question type
            question_type = getattr(self.current_question, 'question_type', 'multiple_choice')
            
            if question_type == "multiple_choice":
                options = getattr(self.current_question, 'options', [])
                
                # Convert letter answers (A, B, C, D) to the actual option
                if answer.upper() in ["A", "B", "C", "D"] and options:
                    index = ord(answer.upper()) - ord("A")
                    if 0 <= index < len(options):
                        option = options[index]
                        is_correct = option.lower() == correct_answer.lower()
                # Handle numeric answers (1, 2, 3, 4)
                elif answer in ["1", "2", "3", "4"] and options:
                    index = int(answer) - 1
                    if 0 <= index < len(options):
                        option = options[index]
                        is_correct = option.lower() == correct_answer.lower()
                # Direct answer text comparison
                else:
                    # Try direct match first
                    is_correct = answer.lower() == correct_answer.lower()
                    
                    # If not matched and we have options, try to match against options
                    if not is_correct and options:
                        # Check if answer matches any of the options
                        for i, option in enumerate(options):
                            if answer.lower() == option.lower():
                                # If this option matches the correct answer
                                is_correct = option.lower() == correct_answer.lower()
                                break
                        
            elif question_type == "true_false":
                normalized_answer = "true" if answer.lower() in ["true", "t", "yes", "y", "1"] else "false"
                normalized_correct = "true" if correct_answer.lower() in ["true", "t", "yes", "y", "1"] else "false"
                is_correct = normalized_answer == normalized_correct
                
            else:  # short_answer
                # More flexible matching for short answers
                user_answer_normalized = answer.lower().strip().replace(".", "").replace(",", "")
                correct_answer_normalized = correct_answer.lower().strip().replace(".", "").replace(",", "")
                
                # Exact match
                is_correct = user_answer_normalized == correct_answer_normalized
                
                # If not exact, try more flexible matching for short answers
                if not is_correct:
                    # Check if user answer contains the correct answer or vice versa
                    if (user_answer_normalized in correct_answer_normalized or 
                        correct_answer_normalized in user_answer_normalized):
                        is_correct = True
            
            # Update participant's stats
            if is_correct:
                # Mark this user as having answered correctly
                self.correct_answerers_this_question.add(user_id)
                
                # Always increment correct answer count for stats
                self.participants[user_id]["correct_answers"] += 1
                
                # Only award points if allowed (in single answer mode, only first correct gets points)
                if should_award_points:
                    # Calculate points (faster answers = more points)
                    response_time = self.participants[user_id]["response_times"][-1]
                    time_factor = max(0, 1 - (response_time / self.timeout))
                    
                    # Base points from difficulty
                    difficulty = getattr(self.current_question, 'difficulty', 'medium')
                    difficulty_multiplier = {
                        "easy": 1,
                        "medium": 2,
                        "hard": 3
                    }.get(difficulty.lower(), 1)
                    
                    points = int(10 * difficulty_multiplier * (0.5 + 0.5 * time_factor))
                    
                    # Award points
                    self.participants[user_id]["score"] += points
                    
                    # Add to correct responders list
                    correct_responders.append({
                        "user_id": user_id,
                        "username": self.participants[user_id]["username"],
                        "points": points,
                        "total_score": self.participants[user_id]["score"],
                        "response_time": response_time
                    })
                else:
                    # User was correct but doesn't get points (someone else was faster in single answer mode)
                    # Still add them to correct responders list with 0 points to show they were correct
                    response_time = self.participants[user_id]["response_times"][-1]
                    correct_responders.append({
                        "user_id": user_id,
                        "username": self.participants[user_id]["username"],
                        "points": 0,
                        "total_score": self.participants[user_id]["score"],
                        "response_time": response_time
                    })
            else:
                # Always increment incorrect answer count
                self.participants[user_id]["incorrect_answers"] += 1
        
        # Sort correct responders by response time (fastest first)
        correct_responders.sort(key=lambda x: x["response_time"])
        
        # Clear current answers for next question
        self.current_answers = {}
        
        return correct_responders
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the current leaderboard for this quiz session."""
        leaderboard = [
            {
                "user_id": user_id,
                "username": data["username"],
                "score": data["score"],
                "correct": data["correct_answers"],
                "incorrect": data["incorrect_answers"]
            }
            for user_id, data in self.participants.items()
        ]
        
        # Sort by score (highest first)
        leaderboard.sort(key=lambda x: x["score"], reverse=True)
        
        return leaderboard[:limit]
    
    def next_question(self) -> Optional[Any]:
        """Move to the next question and return it."""
        self.current_question_idx += 1
        # Reset the correct answerers set for the new question
        self.correct_answerers_this_question = set()
        return self.current_question
    
    def get_progress_info(self) -> Dict[str, Any]:
        """Get information about quiz progress."""
        return {
            "current": self.current_question_idx + 1,
            "total": len(self.questions),
            "remaining": len(self.questions) - self.current_question_idx - 1,
            "progress_percent": ((self.current_question_idx + 1) / len(self.questions)) * 100
        }


class GroupQuizManager:
    """Manager for handling multiple group quiz sessions."""
    
    def __init__(self, bot=None):
        self.active_sessions: Dict[Tuple[int, int], GroupQuizSession] = {}  # (guild_id, channel_id) -> session
        self._db_service = None  # Will be set by the context
        self.bot = bot
    
    def set_db_service(self, db_service):
        """Set the database service."""
        self._db_service = db_service
    
    def create_session(self, guild_id: int, channel_id: int, host_id: int, topic: str, questions: List[Any], 
                      timeout: int = 30, time_between_questions: int = 5, 
                      provider_info: Optional[Dict[str, Any]] = None,
                      single_answer_mode: bool = False,
                      is_private: bool = False) -> GroupQuizSession:
        """Create a new group quiz session."""
        session = GroupQuizSession(
            guild_id=guild_id,
            channel_id=channel_id,
            host_id=host_id,
            topic=topic,
            questions=questions,
            timeout=timeout,
            time_between_questions=time_between_questions,
            provider_info=provider_info,
            single_answer_mode=single_answer_mode,
            is_private=is_private
        )
        
        self.active_sessions[(guild_id, channel_id)] = session
        return session
    
    def get_session(self, guild_id: int, channel_id: int) -> Optional[GroupQuizSession]:
        """Get an active session for a channel if it exists."""
        return self.active_sessions.get((guild_id, channel_id))
    
    def end_session(self, guild_id: int, channel_id: int) -> bool:
        """End a quiz session and remove it from active sessions."""
        if (guild_id, channel_id) in self.active_sessions:
            session = self.active_sessions[(guild_id, channel_id)]
            session.is_active = False
            session.end_time = datetime.now()
            
            # Save results to database
            if self._db_service:
                self._save_session_results(session)
            
            # Remove from active sessions
            del self.active_sessions[(guild_id, channel_id)]
            return True
        return False
    
    def _save_session_results(self, session: GroupQuizSession) -> None:
        """Save the results of a session to the database."""
        if not self._db_service:
            logger.warning("Database service not available, can't save session results")
            return
            
        try:
            # Record the quiz
            logger.info(f"Recording group quiz: topic={session.topic}, host={session.host_id}, participants={len(session.participants)}")
            quiz_id = self._db_service.record_quiz(
                host_id=session.host_id,
                topic=session.topic,
                category=session.questions[0].category if session.questions else "general",
                difficulty=session.questions[0].difficulty if session.questions else "medium",
                question_count=len(session.questions),
                template="group_quiz",
                provider="unknown",  # This should be passed from the quiz generator
                is_private=False,
                is_group=True
            )
            logger.info(f"Successfully recorded group quiz with ID: {quiz_id}")
            
            # Update user stats for all participants
            for user_id, data in session.participants.items():
                try:
                    logger.info(f"Updating stats for user {user_id} ({data['username']}): " +
                              f"score={data['score']}, correct={data['correct_answers']}, wrong={data['incorrect_answers']}")
                    
                    # Check for the new comprehensive method first
                    if hasattr(self._db_service, 'record_user_quiz_session'):
                        # Use the async version with comprehensive tracking - need to run in an event loop
                        import asyncio
                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        loop.run_until_complete(
                            self._db_service.record_user_quiz_session(
                                user_id=user_id,
                                username=data["username"],
                                quiz_id=str(quiz_id),
                                topic=session.topic,
                                correct=data["correct_answers"],
                                wrong=data["incorrect_answers"],
                                points=data["score"],
                                difficulty=session.questions[0].difficulty if session.questions else "medium",
                                category=session.questions[0].category if session.questions else "general"
                            )
                        )
                        logger.info(f"Recorded group quiz session via comprehensive method for user {user_id}")
                    # Fallback to old async update_user_stats if new one not found
                    elif hasattr(self._db_service, 'update_user_stats') and callable(getattr(self._db_service.update_user_stats, '__awaitable__', None)):
                        import asyncio
                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            self._db_service.update_user_stats(
                                user_id=user_id, username=data["username"], quiz_id=str(quiz_id),
                                topic=session.topic, correct=data["correct_answers"], wrong=data["incorrect_answers"], points=data["score"],
                                difficulty=session.questions[0].difficulty if session.questions else "medium",
                                category=session.questions[0].category if session.questions else "general"
                            )
                        )
                        logger.info(f"Recorded group quiz session via older async update_user_stats for user {user_id}")
                    else:
                        # Fall back to simpler synchronous version that updates the main users table
                        self._db_service.update_user_stats(
                            user_id=user_id,
                            username=data["username"],
                            correct=data["correct_answers"],
                            wrong=data["incorrect_answers"],
                            points=data["score"]
                        )
                        logger.info(f"Updated basic group quiz user stats via simple sync method for user {user_id}")
                    
                    # Also increment quizzes taken count
                    self._db_service.increment_quizzes_taken(
                        user_id=user_id,
                        username=data["username"]
                    )
                    logger.info(f"Incremented quizzes taken for user {user_id}")
                except Exception as participant_error:
                    logger.error(f"Error updating stats for group quiz participant {user_id}: {participant_error}", exc_info=True)
        except Exception as e:
            logger.error(f"Error saving group quiz session results: {e}", exc_info=True)

# Create a singleton instance
group_quiz_manager = GroupQuizManager() 