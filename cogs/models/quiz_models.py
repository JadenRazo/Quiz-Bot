"""Data models for quiz functionality."""

from enum import Enum
from typing import Dict, List, Optional, Any
import time
import logging
from dataclasses import dataclass, field

from services import Question

logger = logging.getLogger("bot.quiz.models")


class QuizState(Enum):
    """Enum representing the possible states of a quiz."""
    SETUP = 0
    ACTIVE = 1
    WAITING_FOR_ANSWER = 2
    REVIEWING = 3
    FINISHED = 4


@dataclass
class QuizParticipant:
    """Represents a participant in a quiz."""
    user_id: int
    score: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    
    def record_answer(self, is_correct: bool, points: int = 0) -> None:
        """Record an answer for this participant."""
        if is_correct:
            self.correct_count += 1
            self.score += points
        else:
            self.wrong_count += 1
    
    @property
    def total_answers(self) -> int:
        """Get total number of answers."""
        return self.correct_count + self.wrong_count
    
    @property
    def accuracy(self) -> float:
        """Get accuracy percentage."""
        if self.total_answers == 0:
            return 0.0
        return (self.correct_count / self.total_answers) * 100


class ActiveQuiz:
    """Represents an active quiz session."""
    
    def __init__(
        self,
        guild_id: int,
        channel_id: int,
        host_id: int,
        topic: str,
        questions: List[Question],
        timeout: int = 60,
        llm_provider: str = "openai",
        is_private: bool = False
    ):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.topic = topic
        self.questions = questions
        self.timeout = timeout
        self.current_question_idx = 0
        self.state = QuizState.SETUP
        self.participants: Dict[int, QuizParticipant] = {}
        self.start_time = time.time()
        self.last_activity_time = self.start_time
        self.end_time: Optional[float] = None
        self.current_question_start_time: Optional[float] = None
        self.message_id: Optional[int] = None
        self.llm_provider = llm_provider
        self.is_private = is_private
        self.timer_task = None
        self.questions_asked = 0
        self.questions_answered = 0
        self.correct_answers = 0
        self.wrong_answers = 0
        self.quiz_id = f"quiz_{int(time.time())}_{guild_id}_{channel_id}"
        
        logger.info(f"Created new quiz with ID {self.quiz_id} on topic '{topic}' with {len(questions)} questions")
    
    @property
    def current_question(self) -> Optional[Question]:
        """Get the current question."""
        if 0 <= self.current_question_idx < len(self.questions):
            return self.questions[self.current_question_idx]
        return None
    
    @property
    def is_finished(self) -> bool:
        """Check if the quiz is finished."""
        if self.state == QuizState.FINISHED:
            return True
        if self.current_question_idx >= len(self.questions):
            logger.debug(f"Quiz {self.quiz_id} marked as finished: all questions asked")
            self.state = QuizState.FINISHED
            return True
        return False
    
    @property
    def remaining_questions(self) -> int:
        """Get the number of remaining questions."""
        return max(0, len(self.questions) - self.current_question_idx)
    
    @property
    def progress(self) -> str:
        """Get a string representation of the quiz progress."""
        return f"Question {self.current_question_idx + 1}/{len(self.questions)}"
    
    @property
    def duration(self) -> float:
        """Get the quiz duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def next_question(self) -> Optional[Question]:
        """Move to the next question."""
        self.questions_asked += 1
        logger.debug(f"Moving to next question in quiz {self.quiz_id}: {self.current_question_idx} -> {self.current_question_idx + 1}")
        self.current_question_idx += 1
        
        if self.current_question_idx >= len(self.questions):
            logger.debug(f"No more questions in quiz {self.quiz_id}")
            self.state = QuizState.FINISHED
            self.end_time = time.time()
            return None
            
        current_time = time.time()
        self.current_question_start_time = current_time
        self.last_activity_time = current_time  # Update last activity time
        return self.current_question
    
    def add_participant(self, user_id: int) -> QuizParticipant:
        """Add a participant to the quiz."""
        if user_id not in self.participants:
            self.participants[user_id] = QuizParticipant(user_id=user_id)
            logger.debug(f"Added participant {user_id} to quiz {self.quiz_id}")
        return self.participants[user_id]
    
    def record_answer(self, user_id: int, is_correct: bool, points_awarded: int = 0) -> QuizParticipant:
        """Records an answer attempt for a user."""
        participant = self.add_participant(user_id)
        participant.record_answer(is_correct, points_awarded)
        
        if is_correct:
            self.correct_answers += 1
            logger.debug(f"Correct answer by user {user_id} in quiz {self.quiz_id} (+{points_awarded} points)")
        else:
            self.wrong_answers += 1
            logger.debug(f"Wrong answer by user {user_id} in quiz {self.quiz_id}")
            
        self.questions_answered += 1
        self.last_activity_time = time.time()  # Update last activity time
        return participant
    
    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get the quiz leaderboard."""
        leaderboard = []
        for user_id, participant in sorted(
            self.participants.items(), 
            key=lambda x: x[1].score, 
            reverse=True
        ):
            entry = {
                "user_id": user_id,
                "score": participant.score,
                "correct_answers": participant.correct_count,
                "wrong_answers": participant.wrong_count,
                "total_answers": participant.total_answers,
                "accuracy": participant.accuracy,
                "username": f"User {user_id}"  # Will be filled in by the cog
            }
            leaderboard.append(entry)
        return leaderboard
    
    def get_progress_info(self) -> Dict[str, Any]:
        """Get information about quiz progress."""
        return {
            "current_question": self.current_question_idx + 1,
            "total_questions": len(self.questions),
            "remaining_questions": self.remaining_questions,
            "questions_asked": self.questions_asked,
            "questions_answered": self.questions_answered,
            "correct_answers": self.correct_answers,
            "wrong_answers": self.wrong_answers,
            "progress_percent": ((self.current_question_idx + 1) / len(self.questions)) * 100,
            "state": self.state.name,
            "quiz_id": self.quiz_id,
            "duration": self.duration,
            "participant_count": len(self.participants)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive quiz statistics."""
        total_participants = len(self.participants)
        total_answers = self.questions_answered
        
        return {
            "quiz_id": self.quiz_id,
            "topic": self.topic,
            "total_questions": len(self.questions),
            "questions_asked": self.questions_asked,
            "questions_answered": self.questions_answered,
            "total_participants": total_participants,
            "correct_answers": self.correct_answers,
            "wrong_answers": self.wrong_answers,
            "accuracy": (self.correct_answers / total_answers * 100) if total_answers > 0 else 0,
            "duration": self.duration,
            "llm_provider": self.llm_provider,
            "is_private": self.is_private,
            "state": self.state.name
        }