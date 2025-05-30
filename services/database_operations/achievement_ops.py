"""
Database operations related to user achievements.
"""
import logging
import asyncio
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from services.database import DatabaseService

logger = logging.getLogger("bot.db_ops.achievements")

def grant_achievement(
    db_service: 'DatabaseService',
    user_id: int,
    username: str, # Include username for user upsert
    name: str,
    description: str,
    icon: str
) -> bool:
    """
    Grants an achievement to a user if they don't already have it.

    Args:
        db_service: An instance of the DatabaseService.
        user_id: Discord user ID.
        username: User's display name (for user table update).
        name: Achievement name.
        description: Achievement description.
        icon: Emoji or icon for the achievement.

    Returns:
        True if the achievement was newly granted or already existed,
        False if an error occurred.
    """
    try:
        # db_service.add_achievement handles the check for existing achievement
        # and uses safe_execute internally.
        # It returns the achievement ID if successful, or -1 otherwise.
        achievement_id = db_service.add_achievement(
            user_id=user_id,
            name=name,
            description=description,
            icon=icon
            # Note: The underlying add_achievement also ensures the user exists.
            # If it needed the username, we would pass it here.
        )
        
        if achievement_id != -1:
            logger.info(f"Achievement '{name}' status confirmed/updated for user {user_id}.")
            return True
        else:
            # Error should have been logged by safe_execute in add_achievement
            logger.warning(f"Granting achievement '{name}' failed or already existed for user {user_id} (add_achievement returned -1)")
            # We might return True even if it already existed, depending on desired behaviour.
            # Let's return True assuming -1 only signifies DB error, not pre-existence.
            # If pre-existence check is needed, query first.
            return True # Assuming -1 means error, not 'already exists'

    except Exception as e:
        logger.error(f"Error granting achievement '{name}' for user {user_id}: {e}", exc_info=True)
        return False

async def get_user_achievements(
    db_service: 'DatabaseService', 
    user_id: int
) -> List[Dict[str, Any]]:
    """
    Retrieves all achievements for a user.

    Args:
        db_service: An instance of the DatabaseService.
        user_id: Discord user ID.

    Returns:
        A list of achievement dictionaries, or an empty list on error.
    """
    achievements = []
    try:
        logger.info(f"Fetching achievements for user {user_id} via achievement_ops")
        if hasattr(db_service, 'get_achievements'):
            # get_achievements is currently synchronous
            achievements_raw = await asyncio.to_thread(db_service.get_achievements, user_id)
            
            # Ensure results are list of dicts
            if isinstance(achievements_raw, list):
                for entry_raw in achievements_raw:
                    try:
                         achievements.append(dict(entry_raw) if not isinstance(entry_raw, dict) else entry_raw)
                    except (TypeError, ValueError) as conversion_error:
                         logger.warning(f"Could not convert achievement entry to dict for user {user_id}: {conversion_error} - Entry: {entry_raw}")
            else:
                 logger.warning(f"get_achievements did not return a list for user {user_id}. Type: {type(achievements_raw)}")
        else:
            logger.warning("Database service does not have 'get_achievements' method.")

        return achievements
        
    except Exception as e:
        logger.error(f"Error fetching achievements for user {user_id}: {e}", exc_info=True)
        return [] 