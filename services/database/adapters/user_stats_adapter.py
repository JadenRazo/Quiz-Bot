"""
Adapter for user_stats_ops using Strangler Fig pattern.

This adapter provides the exact same interface as the old user_stats_ops
but uses the new repository pattern internally.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bot.database.adapters.user_stats")


class UserStatsAdapter:
    """
    Adapter that mimics the old user_stats_ops interface using existing database service.
    """
    
    def __init__(self, db_service):
        """
        Initialize adapter with database service.
        
        Args:
            db_service: The database service instance
        """
        self._db_service = db_service
    
    async def get_user_stats(self, user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get user statistics."""
        try:
            # Use the existing UserStatsService method through the database service
            if hasattr(self._db_service, 'get_comprehensive_user_stats'):
                stats = await self._db_service.get_comprehensive_user_stats(user_id)
                return stats
            else:
                logger.error("Database service does not have get_comprehensive_user_stats method")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user stats for {user_id}:{guild_id}: {e}", exc_info=True)
            return None
    
    async def create_user_stats(self, user_id: int, guild_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Create user statistics."""
        try:
            # Use the existing database service method to create user
            username = kwargs.get('username', 'Unknown')
            await self._db_service.update_user_stats(user_id, username, 0, 0, 0)
            
            # Return basic stats
            return {
                'user_id': user_id,
                'guild_id': guild_id,
                'total_quizzes': 0,
                'total_correct': 0,
                'total_wrong': 0,
                'total_points': 0,
                'level': 1
            }
                
        except Exception as e:
            logger.error(f"Error creating user stats for {user_id}:{guild_id}: {e}", exc_info=True)
            return None
    
    async def get_or_create_user_stats(self, user_id: int, guild_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Get or create user statistics."""
        try:
            # Try to get existing stats first
            stats = await self.get_user_stats(user_id, guild_id)
            if stats:
                return stats
                
            # Create new stats if not found
            return await self.create_user_stats(user_id, guild_id, **kwargs)
                
        except Exception as e:
            logger.error(f"Error getting/creating user stats for {user_id}:{guild_id}: {e}", exc_info=True)
            return None
    
    async def update_quiz_completion(
        self,
        user_id: int,
        guild_id: int,
        correct_answers: int,
        wrong_answers: int,
        points_earned: int,
        topic: str
    ) -> Optional[Dict[str, Any]]:
        """Update user statistics after quiz completion."""
        try:
            # Use the existing database service method
            if hasattr(self._db_service, 'record_user_quiz_session'):
                await self._db_service.record_user_quiz_session(
                    user_id, f"quiz_{guild_id}_{user_id}", topic, "medium", "general",
                    correct_answers + wrong_answers, correct_answers, wrong_answers, points_earned,
                    guild_id=guild_id
                )
                # Return basic stats
                return await self.get_user_stats(user_id, guild_id)
            else:
                logger.error("Database service does not have record_user_quiz_session method")
                return None
                
        except Exception as e:
            logger.error(f"Error updating quiz completion for {user_id}:{guild_id}: {e}", exc_info=True)
            return None
    
    async def get_leaderboard(
        self,
        guild_id: int,
        limit: int = 10,
        order_by: str = "total_points"
    ) -> List[Dict[str, Any]]:
        """Get leaderboard."""
        try:
            # Use the existing database service method
            if hasattr(self._db_service, 'get_leaderboard'):
                leaderboard = await self._db_service.get_leaderboard(
                    guild_id=guild_id, category=None, timeframe=None
                )
                return leaderboard[:limit]  # Limit the results
            else:
                logger.error("Database service does not have get_leaderboard method")
                return []
                
        except Exception as e:
            logger.error(f"Error getting leaderboard for guild {guild_id}: {e}", exc_info=True)
            return []
    
    async def get_user_rank(self, user_id: int, guild_id: int, order_by: str = "total_points") -> Optional[int]:
        """Get user rank."""
        try:
            # Use the leaderboard to determine rank
            leaderboard = await self.get_leaderboard(guild_id, limit=1000)  # Get larger set to find rank
            for idx, user_data in enumerate(leaderboard):
                if user_data.get('user_id') == user_id:
                    return idx + 1  # Rank is 1-based
            return None
                
        except Exception as e:
            logger.error(f"Error getting user rank for {user_id}:{guild_id}: {e}", exc_info=True)
            return None
    
    async def update_level(self, user_id: int, guild_id: int, new_level: int) -> Optional[Dict[str, Any]]:
        """Update user level."""
        try:
            # Level updates are handled automatically by the database service
            # Just return current stats
            return await self.get_user_stats(user_id, guild_id)
                
        except Exception as e:
            logger.error(f"Error updating level for {user_id}:{guild_id}: {e}", exc_info=True)
            return None
    
    async def reset_streak(self, user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        """Reset user streak."""
        try:
            # Streak resets are handled by the database service automatically
            # Just return current stats
            return await self.get_user_stats(user_id, guild_id)
                
        except Exception as e:
            logger.error(f"Error resetting streak for {user_id}:{guild_id}: {e}", exc_info=True)
            return None


def create_user_stats_adapter(db_service) -> UserStatsAdapter:
    """Create a user stats adapter instance."""
    return UserStatsAdapter(db_service)


# Global adapter instance
_adapter_instance: Optional[UserStatsAdapter] = None


def initialize_adapter(db_service_or_pool) -> None:
    """Initialize the global adapter instance."""
    global _adapter_instance
    
    # For backward compatibility, accept either pool or db_service
    # If it's a pool (has acquire method), we need to get the db_service from somewhere
    if hasattr(db_service_or_pool, 'acquire'):
        # This is a pool, we can't use it directly
        logger.warning("Adapter initialized with pool instead of db_service - adapter will not work")
        _adapter_instance = None
    else:
        # This is a db_service
        _adapter_instance = create_user_stats_adapter(db_service_or_pool)


async def get_user_stats(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Legacy function interface."""
    if _adapter_instance is None:
        logger.error("Adapter not initialized")
        return None
    return await _adapter_instance.get_user_stats(user_id, guild_id)


async def create_user_stats(user_id: int, guild_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    """Legacy function interface."""
    if _adapter_instance is None:
        logger.error("Adapter not initialized")
        return None
    return await _adapter_instance.create_user_stats(user_id, guild_id, **kwargs)


async def get_or_create_user_stats(user_id: int, guild_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    """Legacy function interface."""
    if _adapter_instance is None:
        logger.error("Adapter not initialized")
        return None
    return await _adapter_instance.get_or_create_user_stats(user_id, guild_id, **kwargs)


async def update_quiz_completion(
    user_id: int,
    guild_id: int,
    correct_answers: int,
    wrong_answers: int,
    points_earned: int,
    topic: str
) -> Optional[Dict[str, Any]]:
    """Legacy function interface."""
    if _adapter_instance is None:
        logger.error("Adapter not initialized")
        return None
    return await _adapter_instance.update_quiz_completion(
        user_id, guild_id, correct_answers, wrong_answers, points_earned, topic
    )


async def get_leaderboard(
    guild_id: int,
    limit: int = 10,
    order_by: str = "total_points"
) -> List[Dict[str, Any]]:
    """Legacy function interface."""
    if _adapter_instance is None:
        logger.error("Adapter not initialized")
        return []
    return await _adapter_instance.get_leaderboard(guild_id, limit, order_by)


async def get_user_rank(user_id: int, guild_id: int, order_by: str = "total_points") -> Optional[int]:
    """Legacy function interface."""
    if _adapter_instance is None:
        logger.error("Adapter not initialized")
        return None
    return await _adapter_instance.get_user_rank(user_id, guild_id, order_by)


async def update_level(user_id: int, guild_id: int, new_level: int) -> Optional[Dict[str, Any]]:
    """Legacy function interface."""
    if _adapter_instance is None:
        logger.error("Adapter not initialized")
        return None
    return await _adapter_instance.update_level(user_id, guild_id, new_level)


async def reset_streak(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Legacy function interface."""
    if _adapter_instance is None:
        logger.error("Adapter not initialized")
        return None
    return await _adapter_instance.reset_streak(user_id, guild_id)