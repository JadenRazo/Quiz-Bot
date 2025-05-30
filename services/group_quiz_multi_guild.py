"""
Group quiz service for managing trivia-style group quizzes with proper multi-guild support.
This version properly handles multiple guilds by using composite keys.
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
import time

# Set up logger
logger = logging.getLogger(__name__)


class GroupQuizSession:
    """Represents a single group quiz session."""
    
    def __init__(self, guild_id: int, channel_id: int, host_id: int, topic: str, 
                 questions: List[Any], timeout: int = 30, 
                 time_between_questions: int = 5, provider_info: Optional[Dict[str, Any]] = None,
                 single_answer_mode: bool = False, is_private: bool = False,
                 max_participants: int = 50):
        """Initialize a new group quiz session with guild context."""
        self.guild_id = guild_id  # Add guild ID for proper tracking
        self.channel_id = channel_id
        self.host_id = host_id
        self.topic = topic
        self.questions = questions
        self.timeout = timeout
        self.time_between_questions = time_between_questions
        self.provider_info = provider_info
        self.single_answer_mode = single_answer_mode  
        self.is_private = is_private
        self.max_participants = max_participants
        
        # Session state
        self.is_active = True
        self.start_time = datetime.now()
        self.end_time = None
        self.current_question_idx = 0
        self.current_question_message_id = None
        
        # Participant tracking
        self.participants: Dict[int, Dict[str, Any]] = {}
        self.current_answers: Dict[int, str] = {}
        
        # Special tracking for single answer mode
        self.correct_answerers_this_question: Set[int] = set()
        self.results_message_sent = False
        self._timer_cancelled = False
    
    # ... rest of the GroupQuizSession methods remain the same ...
    

class GroupQuizManager:
    """Manager for handling multiple group quiz sessions with multi-guild support."""
    
    def __init__(self, bot=None):
        # Use composite key: (guild_id, channel_id) for proper multi-guild support
        self.active_sessions: Dict[Tuple[int, int], GroupQuizSession] = {}
        self._db_service = None
        self.bot = bot
    
    def set_db_service(self, db_service):
        """Set the database service."""
        self._db_service = db_service
    
    def create_session(self, guild_id: int, channel_id: int, host_id: int, 
                      topic: str, questions: List[Any], 
                      timeout: int = 30, time_between_questions: int = 5, 
                      provider_info: Optional[Dict[str, Any]] = None,
                      single_answer_mode: bool = False,
                      is_private: bool = False) -> GroupQuizSession:
        """Create a new group quiz session with guild context."""
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
        """Get an active session for a guild/channel if it exists."""
        return self.active_sessions.get((guild_id, channel_id))
    
    def end_session(self, guild_id: int, channel_id: int) -> bool:
        """End a quiz session and remove it from active sessions."""
        if (guild_id, channel_id) in self.active_sessions:
            session = self.active_sessions[(guild_id, channel_id)]
            session.is_active = False
            session.end_time = datetime.now()
            
            # Save results to database with guild context
            if self._db_service:
                self._save_session_results(session)
            
            # Remove from active sessions
            del self.active_sessions[(guild_id, channel_id)]
            return True
        return False
    
    def _save_session_results(self, session: GroupQuizSession) -> None:
        """Save the results of a session to the database with guild context."""
        if not self._db_service:
            logger.warning("Database service not available, can't save session results")
            return
            
        try:
            # Record the quiz with guild ID
            logger.info(f"Recording group quiz: guild={session.guild_id}, topic={session.topic}, host={session.host_id}")
            
            # First, ensure all participants are in guild_members table
            for user_id in session.participants:
                try:
                    self._db_service.add_guild_member(session.guild_id, user_id)
                except Exception as e:
                    logger.warning(f"Failed to add guild member {user_id} to guild {session.guild_id}: {e}")
            
            # Record the quiz
            quiz_id = self._db_service.record_quiz(
                host_id=session.host_id,
                topic=session.topic,
                category=session.questions[0].category if session.questions else "general",
                difficulty=session.questions[0].difficulty if session.questions else "medium",
                question_count=len(session.questions),
                template="group_quiz",
                provider="unknown",
                is_private=False,
                is_group=True,
                guild_id=session.guild_id  # Pass guild ID for guild-specific tracking
            )
            
            # Update user stats with guild context
            for user_id, data in session.participants.items():
                try:
                    # Record session with guild context
                    self._db_service.record_user_quiz_session(
                        user_id=user_id,
                        username=data["username"],
                        quiz_id=str(quiz_id),
                        topic=session.topic,
                        correct=data["correct_answers"],
                        wrong=data["incorrect_answers"],
                        points=data["score"],
                        difficulty=session.questions[0].difficulty if session.questions else "medium",
                        category=session.questions[0].category if session.questions else "general",
                        guild_id=session.guild_id  # Add guild context
                    )
                except Exception as e:
                    logger.error(f"Failed to record stats for user {user_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to save session results: {e}")
    
    def get_active_sessions_for_guild(self, guild_id: int) -> List[GroupQuizSession]:
        """Get all active sessions for a specific guild."""
        return [
            session for (g_id, _), session in self.active_sessions.items()
            if g_id == guild_id and session.is_active
        ]
    
    def cleanup_inactive_sessions(self, timeout_minutes: int = 30) -> int:
        """Clean up sessions that have been inactive for too long."""
        cleaned = 0
        current_time = datetime.now()
        
        for (guild_id, channel_id), session in list(self.active_sessions.items()):
            if session.start_time:
                time_diff = (current_time - session.start_time).total_seconds() / 60
                if time_diff > timeout_minutes and not session.is_finished:
                    self.end_session(guild_id, channel_id)
                    cleaned += 1
                    logger.info(f"Cleaned up inactive session in guild {guild_id}, channel {channel_id}")
        
        return cleaned