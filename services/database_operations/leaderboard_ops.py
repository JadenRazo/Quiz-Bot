"""
Database operations related to fetching and formatting leaderboards.
"""
import logging
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from services.database import DatabaseService

logger = logging.getLogger("bot.db_ops.leaderboard")

def get_formatted_leaderboard(
    db_service: 'DatabaseService', 
    limit: int = 10,
    guild_id: Optional[int] = None, # Used for guild-specific leaderboards
    # category: Optional[str] = None, # Keep placeholder
    # timeframe: str = "all-time"   # Keep placeholder
) -> List[Dict[str, Any]]:
    """
    Fetches and returns leaderboard data, supporting global or guild-specific scope.

    Args:
        db_service: An instance of the DatabaseService.
        limit: Maximum number of users to return.
        guild_id: If provided, fetches the leaderboard for this specific guild.
                  If None, fetches the global leaderboard.
        # category: Optional category filter (not yet implemented).
        # timeframe: Timeframe filter (not yet implemented).

    Returns:
        A list of dictionaries, each representing a user on the leaderboard.
        Returns empty list on error (errors logged by underlying db service).
    """
    try:
        # TODO: Implement filtering based on category, timeframe if needed later.
        # if category or timeframe != "all-time":
        #     logger.warning(f"Leaderboard filtering by category/timeframe not yet implemented.")
        
        leaderboard_data = []
        if guild_id:
            logger.info(f"Fetching guild-specific leaderboard for guild {guild_id} (limit {limit})")
            # Fetch guild-specific leaderboard
            if hasattr(db_service, 'get_guild_leaderboard'):
                leaderboard_data = db_service.get_guild_leaderboard(guild_id=guild_id, limit=limit)
            else:
                logger.error("Database service missing 'get_guild_leaderboard' method.")
        else:
            logger.info(f"Fetching global leaderboard (limit {limit})")
            # Fetch global leaderboard using the existing basic method
            if hasattr(db_service, 'get_leaderboard'):
                leaderboard_data = db_service.get_leaderboard(limit=limit)
            else:
                logger.error("Database service missing 'get_leaderboard' method.")
        
        # The data from underlying methods should already be list of dicts via safe_execute handling
        return leaderboard_data
        
    except Exception as e:
        logger.error(f"Error fetching leaderboard data (guild: {guild_id}, limit: {limit}): {e}", exc_info=True)
        return [] 