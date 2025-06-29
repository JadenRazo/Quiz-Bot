"""Pydantic data models for the Quiz Bot database entities."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator


class User(BaseModel):
    """User entity model."""
    
    user_id: int = Field(..., description="Discord user ID")
    guild_id: int = Field(..., description="Discord guild ID")
    username: str = Field(..., max_length=100, description="Discord username")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_active: Optional[datetime] = Field(None, description="Last activity timestamp")
    is_active: bool = Field(True, description="Whether user is active")
    
    class Config:
        from_attributes = True  # For Pydantic v2 compatibility with asyncpg records


class UserStats(BaseModel):
    """User statistics model."""
    
    user_id: int = Field(..., description="Discord user ID")
    guild_id: int = Field(..., description="Discord guild ID")
    total_quizzes: int = Field(0, ge=0, description="Total quizzes taken")
    total_correct: int = Field(0, ge=0, description="Total correct answers")
    total_wrong: int = Field(0, ge=0, description="Total wrong answers")
    total_points: int = Field(0, ge=0, description="Total points earned")
    level: int = Field(1, ge=1, description="User level")
    experience: int = Field(0, ge=0, description="Experience points")
    streak: int = Field(0, ge=0, description="Current correct answer streak")
    best_streak: int = Field(0, ge=0, description="Best streak achieved")
    favorite_topic: Optional[str] = Field(None, max_length=200, description="Most played topic")
    last_quiz_date: Optional[datetime] = Field(None, description="Last quiz participation")
    created_at: datetime = Field(..., description="Stats creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    @property
    def total_answers(self) -> int:
        """Total number of answers given."""
        return self.total_correct + self.total_wrong
    
    @property
    def accuracy(self) -> float:
        """Accuracy percentage (0-100)."""
        if self.total_answers == 0:
            return 0.0
        return round((self.total_correct / self.total_answers) * 100, 2)
    
    @property
    def average_points_per_quiz(self) -> float:
        """Average points per quiz."""
        if self.total_quizzes == 0:
            return 0.0
        return round(self.total_points / self.total_quizzes, 2)
    
    class Config:
        from_attributes = True


class QuizSession(BaseModel):
    """Quiz session model."""
    
    session_id: str = Field(..., max_length=50, description="Unique session identifier")
    user_id: int = Field(..., description="Discord user ID")
    guild_id: int = Field(..., description="Discord guild ID")
    channel_id: int = Field(..., description="Discord channel ID")
    topic: str = Field(..., max_length=200, description="Quiz topic")
    difficulty: str = Field(..., max_length=20, description="Quiz difficulty level")
    question_count: int = Field(..., ge=1, le=50, description="Number of questions")
    current_question: int = Field(0, ge=0, description="Current question index")
    score: int = Field(0, ge=0, description="Current score")
    correct_answers: int = Field(0, ge=0, description="Correct answers count")
    wrong_answers: int = Field(0, ge=0, description="Wrong answers count")
    is_completed: bool = Field(False, description="Whether session is completed")
    start_time: datetime = Field(..., description="Session start time")
    end_time: Optional[datetime] = Field(None, description="Session end time")
    llm_provider: str = Field(..., max_length=50, description="LLM provider used")
    created_at: datetime = Field(..., description="Record creation timestamp")
    
    @validator('difficulty')
    def validate_difficulty(cls, v):
        """Validate difficulty level."""
        valid_difficulties = {'easy', 'medium', 'hard'}
        if v.lower() not in valid_difficulties:
            raise ValueError(f"Difficulty must be one of: {', '.join(valid_difficulties)}")
        return v.lower()
    
    @property
    def accuracy(self) -> float:
        """Session accuracy percentage."""
        total = self.correct_answers + self.wrong_answers
        if total == 0:
            return 0.0
        return round((self.correct_answers / total) * 100, 2)
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """Session duration in seconds."""
        if self.end_time is None:
            return None
        return int((self.end_time - self.start_time).total_seconds())
    
    class Config:
        from_attributes = True


class Question(BaseModel):
    """Quiz question model."""
    
    question_id: str = Field(..., max_length=50, description="Unique question identifier")
    session_id: str = Field(..., max_length=50, description="Associated session ID")
    question_text: str = Field(..., description="Question content")
    question_type: str = Field(..., max_length=20, description="Question type")
    correct_answer: str = Field(..., description="Correct answer")
    user_answer: Optional[str] = Field(None, description="User's answer")
    options: Optional[List[str]] = Field(None, description="Multiple choice options")
    is_correct: Optional[bool] = Field(None, description="Whether answer was correct")
    points_awarded: int = Field(0, ge=0, description="Points awarded for this question")
    time_taken: Optional[int] = Field(None, ge=0, description="Time taken to answer (seconds)")
    answered_at: Optional[datetime] = Field(None, description="Answer timestamp")
    created_at: datetime = Field(..., description="Question creation timestamp")
    
    @validator('question_type')
    def validate_question_type(cls, v):
        """Validate question type."""
        valid_types = {'multiple_choice', 'true_false', 'short_answer'}
        if v.lower() not in valid_types:
            raise ValueError(f"Question type must be one of: {', '.join(valid_types)}")
        return v.lower()
    
    class Config:
        from_attributes = True


class Guild(BaseModel):
    """Guild (Discord server) model."""
    
    guild_id: int = Field(..., description="Discord guild ID")
    guild_name: str = Field(..., max_length=100, description="Guild name")
    owner_id: int = Field(..., description="Guild owner Discord ID")
    is_active: bool = Field(True, description="Whether guild is active")
    command_prefix: str = Field("!", max_length=5, description="Bot command prefix")
    admin_roles: List[str] = Field(default_factory=list, description="Admin role names")
    admin_users: List[int] = Field(default_factory=list, description="Admin user IDs")
    features_enabled: Dict[str, bool] = Field(default_factory=dict, description="Feature flags")
    created_at: datetime = Field(..., description="Guild creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        from_attributes = True


class Achievement(BaseModel):
    """User achievement model."""
    
    achievement_id: str = Field(..., max_length=50, description="Achievement identifier")
    user_id: int = Field(..., description="Discord user ID")
    guild_id: int = Field(..., description="Discord guild ID")
    achievement_name: str = Field(..., max_length=100, description="Achievement name")
    achievement_description: str = Field(..., max_length=500, description="Achievement description")
    icon: Optional[str] = Field(None, max_length=100, description="Achievement icon")
    points_value: int = Field(0, ge=0, description="Points awarded for achievement")
    unlocked_at: datetime = Field(..., description="Achievement unlock timestamp")
    
    class Config:
        from_attributes = True


class LeaderboardEntry(BaseModel):
    """Leaderboard entry model."""
    
    rank: int = Field(..., ge=1, description="Leaderboard rank")
    user_id: int = Field(..., description="Discord user ID")
    username: str = Field(..., max_length=100, description="Discord username")
    score: int = Field(..., ge=0, description="Total score")
    accuracy: float = Field(..., ge=0.0, le=100.0, description="Accuracy percentage")
    total_quizzes: int = Field(..., ge=0, description="Total quizzes taken")
    level: int = Field(..., ge=1, description="User level")
    
    class Config:
        from_attributes = True


class QuizHistory(BaseModel):
    """Quiz history entry model."""
    
    history_id: str = Field(..., max_length=50, description="History entry identifier")
    user_id: int = Field(..., description="Discord user ID")
    guild_id: int = Field(..., description="Discord guild ID")
    session_id: str = Field(..., max_length=50, description="Quiz session ID")
    topic: str = Field(..., max_length=200, description="Quiz topic")
    difficulty: str = Field(..., max_length=20, description="Quiz difficulty")
    score: int = Field(..., ge=0, description="Final score")
    correct_answers: int = Field(..., ge=0, description="Correct answers")
    total_questions: int = Field(..., ge=1, description="Total questions")
    accuracy: float = Field(..., ge=0.0, le=100.0, description="Accuracy percentage")
    completed_at: datetime = Field(..., description="Completion timestamp")
    
    class Config:
        from_attributes = True