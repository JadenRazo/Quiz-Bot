"""Unit of Work pattern implementation for database operations."""

import logging
from typing import Optional

import asyncpg

from .base_gateway import TransactionalGateway
from .exceptions import ConnectionError, TransactionError
from .repositories.user_stats_repository import UserStatsRepository

logger = logging.getLogger("bot.database.uow")


class UnitOfWork:
    """
    Unit of Work pattern implementation for managing database transactions.
    
    Provides a clean interface for atomic operations across multiple repositories
    while ensuring proper transaction lifecycle management.
    """
    
    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize Unit of Work with database connection pool.
        
        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool
        self._connection: Optional[asyncpg.Connection] = None
        self._transaction: Optional[asyncpg.Transaction] = None
        
        # Repository instances (will be initialized when transaction starts)
        self.user_stats: Optional[UserStatsRepository] = None
        # Additional repositories will be added as needed
        # self.quizzes: Optional[QuizRepository] = None
        # self.guilds: Optional[GuildRepository] = None
        # self.achievements: Optional[AchievementRepository] = None
    
    async def __aenter__(self) -> 'UnitOfWork':
        """
        Context manager entry - acquire connection and start transaction.
        
        Returns:
            Self for use in async with statement
            
        Raises:
            ConnectionError: If connection cannot be acquired
            TransactionError: If transaction cannot be started
        """
        try:
            # Acquire connection from pool
            self._connection = await self._pool.acquire()
            logger.debug("Acquired database connection from pool")
            
            # Start transaction
            self._transaction = self._connection.transaction()
            await self._transaction.start()
            logger.debug("Started database transaction")
            
            # Initialize repositories with the transactional connection
            self._initialize_repositories()
            
            return self
            
        except asyncpg.PostgresError as e:
            logger.error(f"PostgreSQL error during UoW initialization: {e}", exc_info=True)
            await self._cleanup()
            raise ConnectionError(f"Failed to initialize database transaction: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during UoW initialization: {e}", exc_info=True)
            await self._cleanup()
            raise TransactionError("Failed to initialize Unit of Work", "initialization", e)
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Context manager exit - commit or rollback transaction and release connection.
        
        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        try:
            if exc_type is not None:
                # Exception occurred, rollback transaction
                if self._transaction is not None:
                    await self._transaction.rollback()
                    logger.debug(f"Rolled back transaction due to {exc_type.__name__}: {exc_val}")
                else:
                    logger.warning("Exception occurred but no transaction to rollback")
            else:
                # No exception, commit transaction
                if self._transaction is not None:
                    await self._transaction.commit()
                    logger.debug("Committed transaction successfully")
                else:
                    logger.warning("No transaction to commit")
                    
        except asyncpg.PostgresError as e:
            logger.error(f"PostgreSQL error during transaction finalization: {e}", exc_info=True)
            # Try to rollback if commit failed
            if self._transaction is not None:
                try:
                    await self._transaction.rollback()
                    logger.debug("Rolled back transaction after commit failure")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback after commit error: {rollback_error}")
        except Exception as e:
            logger.error(f"Unexpected error during transaction finalization: {e}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def commit(self) -> None:
        """
        Manually commit the transaction.
        
        Note: This is typically not needed when using the context manager,
        but can be useful for complex workflows.
        
        Raises:
            TransactionError: If commit fails or no transaction is active
        """
        if self._transaction is None:
            raise TransactionError("No active transaction to commit", "manual_commit")
        
        try:
            await self._transaction.commit()
            logger.debug("Manually committed transaction")
            
            # Start a new transaction to continue operations
            self._transaction = self._connection.transaction()
            await self._transaction.start()
            logger.debug("Started new transaction after manual commit")
            
        except asyncpg.PostgresError as e:
            logger.error(f"Failed to commit transaction: {e}", exc_info=True)
            raise TransactionError("Failed to commit transaction", "manual_commit", e)
    
    async def rollback(self) -> None:
        """
        Manually rollback the transaction.
        
        Note: This is typically not needed when using the context manager,
        but can be useful for complex workflows.
        
        Raises:
            TransactionError: If rollback fails or no transaction is active
        """
        if self._transaction is None:
            raise TransactionError("No active transaction to rollback", "manual_rollback")
        
        try:
            await self._transaction.rollback()
            logger.debug("Manually rolled back transaction")
            
            # Start a new transaction to continue operations
            self._transaction = self._connection.transaction()
            await self._transaction.start()
            logger.debug("Started new transaction after manual rollback")
            
        except asyncpg.PostgresError as e:
            logger.error(f"Failed to rollback transaction: {e}", exc_info=True)
            raise TransactionError("Failed to rollback transaction", "manual_rollback", e)
    
    def _initialize_repositories(self) -> None:
        """Initialize all repository instances with the transactional connection."""
        if self._connection is None:
            raise TransactionError("Cannot initialize repositories without connection", "initialization")
        
        # Initialize repositories with the shared transactional connection
        self.user_stats = UserStatsRepository(self._connection)
        
        # Additional repositories will be initialized as needed
        # self.quizzes = QuizRepository(self._connection)
        # self.guilds = GuildRepository(self._connection)
        # self.achievements = AchievementRepository(self._connection)
        
        logger.debug("Initialized repositories with transactional connection")
    
    async def _cleanup(self) -> None:
        """Clean up connection and transaction resources."""
        # Clear repository references
        self.user_stats = None
        
        # Clear transaction reference
        self._transaction = None
        
        # Release connection back to pool
        if self._connection is not None:
            try:
                await self._pool.release(self._connection)
                logger.debug("Released connection back to pool")
            except Exception as e:
                logger.error(f"Error releasing connection: {e}", exc_info=True)
            finally:
                self._connection = None


class SimpleUnitOfWork:
    """
    Simplified Unit of Work for operations that don't require transactions.
    
    This provides the same repository interface but uses the connection pool
    directly without transaction management. Use this for simple read operations
    or when you don't need atomicity across multiple operations.
    """
    
    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize Simple Unit of Work with database connection pool.
        
        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool
        
        # Initialize repositories with the pool (they will acquire connections as needed)
        self.user_stats = UserStatsRepository(pool)
        
        # Additional repositories will be initialized as needed
        # self.quizzes = QuizRepository(pool)
        # self.guilds = GuildRepository(pool)
        # self.achievements = AchievementRepository(pool)
    
    async def __aenter__(self) -> 'SimpleUnitOfWork':
        """Context manager entry - no setup needed for simple UoW."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - no cleanup needed for simple UoW."""
        pass


class UnitOfWorkFactory:
    """
    Factory for creating Unit of Work instances.
    
    This factory provides a clean interface for the dependency injection system
    and allows easy switching between transactional and simple UoW patterns.
    """
    
    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize factory with database connection pool.
        
        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool
    
    def create_transactional(self) -> UnitOfWork:
        """
        Create a transactional Unit of Work.
        
        Use this when you need atomic operations across multiple tables
        or when you want to ensure data consistency.
        
        Returns:
            UnitOfWork instance for transactional operations
        """
        return UnitOfWork(self._pool)
    
    def create_simple(self) -> SimpleUnitOfWork:
        """
        Create a simple Unit of Work.
        
        Use this for read operations or simple single-table operations
        where transaction overhead is not needed.
        
        Returns:
            SimpleUnitOfWork instance for simple operations
        """
        return SimpleUnitOfWork(self._pool)


# Example usage in a cog command:
#
# @commands.command()
# async def start_quiz(self, ctx, topic: str):
#     async with self.context.uow.create_transactional() as uow:
#         # All operations within this block are atomic
#         user_stats = await uow.user_stats.get_or_create_user_stats(
#             ctx.author.id, ctx.guild.id
#         )
#         
#         # Create quiz session
#         quiz_session = await uow.quizzes.create_session(
#             user_id=ctx.author.id,
#             guild_id=ctx.guild.id,
#             topic=topic
#         )
#         
#         # If any operation fails, all changes are rolled back automatically
#         await ctx.send(f"Started quiz: {quiz_session.topic}")
#
# # For simple read operations:
# @commands.command()
# async def stats(self, ctx, user: discord.User = None):
#     user = user or ctx.author
#     
#     async with self.context.uow.create_simple() as uow:
#         user_stats = await uow.user_stats.get_user_stats(user.id, ctx.guild.id)
#         if user_stats:
#             await ctx.send(f"{user.display_name} has {user_stats.total_points} points!")
#         else:
#             await ctx.send(f"{user.display_name} hasn't played any quizzes yet.")