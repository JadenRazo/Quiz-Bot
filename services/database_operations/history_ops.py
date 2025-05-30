"""
Database operations related to fetching user quiz history.
"""
import logging
import asyncio
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from services.database import DatabaseService

logger = logging.getLogger("bot.db_ops.history")

async def get_formatted_quiz_history(
    db_service: 'DatabaseService',
    user_id: int,
    limit: int = 50 # Add a sensible default limit
) -> List[Dict[str, Any]]:
    """
    Fetches quiz history for a user.

    Args:
        db_service: An instance of the DatabaseService.
        user_id: The Discord user ID.
        limit: Maximum number of history entries to return.

    Returns:
        A list of dictionaries representing quiz history entries,
        or an empty list on error or if no history found.
    """
    history = []
    try:
        logger.info(f"Fetching history for user {user_id} via history_ops")
        if hasattr(db_service, 'get_user_quiz_history'):
            # Check if the underlying method is async
            if asyncio.iscoroutinefunction(db_service.get_user_quiz_history):
                history_raw = await db_service.get_user_quiz_history(user_id, limit=limit)
            else:
                logger.warning("get_user_quiz_history is not async, running in thread.")
                history_raw = await asyncio.to_thread(db_service.get_user_quiz_history, user_id, limit=limit)
            
            # Ensure history is a list and entries are dicts
            if isinstance(history_raw, list):
                for entry_raw in history_raw:
                    try:
                        if isinstance(entry_raw, dict):
                            history.append(entry_raw)
                        else:
                             # Attempt conversion if not a dict (e.g., RealDictRow)
                            history.append(dict(entry_raw))
                    except (TypeError, ValueError) as conversion_error:
                         logger.warning(f"Could not convert history entry to dict for user {user_id}: {conversion_error} - Entry: {entry_raw}")
            else:
                 logger.warning(f"get_user_quiz_history did not return a list for user {user_id}. Type: {type(history_raw)}")

        else:
            logger.warning("Database service does not have 'get_user_quiz_history' method.")
            
        logger.info(f"Found {len(history)} history entries for user {user_id}")
        return history

    except Exception as e:
        logger.error(f"Error fetching formatted quiz history for {user_id}: {e}", exc_info=True)
        return [] 