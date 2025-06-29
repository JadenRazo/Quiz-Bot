"""Database package for the Quiz Bot."""

from .base_gateway import BaseGateway, TransactionalGateway
from .exceptions import (
    DatabaseError,
    EntityNotFoundError,
    DuplicateEntityError,
    ValidationError,
    TransactionError,
    ConnectionError
)
from .models import (
    User,
    UserStats,
    QuizSession,
    Question,
    Guild,
    Achievement,
    LeaderboardEntry,
    QuizHistory
)
from .unit_of_work import UnitOfWork, SimpleUnitOfWork, UnitOfWorkFactory

__all__ = [
    # Base classes
    'BaseGateway',
    'TransactionalGateway',
    
    # Exceptions
    'DatabaseError',
    'EntityNotFoundError',
    'DuplicateEntityError',
    'ValidationError',
    'TransactionError',
    'ConnectionError',
    
    # Models
    'User',
    'UserStats',
    'QuizSession',
    'Question',
    'Guild',
    'Achievement',
    'LeaderboardEntry',
    'QuizHistory',
    
    # Unit of Work
    'UnitOfWork',
    'SimpleUnitOfWork',
    'UnitOfWorkFactory',
]