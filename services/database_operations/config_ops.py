"""
Database operations related to saving and retrieving user quiz configurations.
"""
import logging
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from services.database import DatabaseService

logger = logging.getLogger("bot.db_ops.config")

def save_user_quiz_config(
    db_service: 'DatabaseService', 
    user_id: int,
    name: str,
    config: Dict[str, Any]
) -> int:
    """
    Saves a quiz configuration for a user.

    Args:
        db_service: An instance of the DatabaseService.
        user_id: Discord user ID.
        name: Name for the saved configuration.
        config: Dictionary containing configuration parameters 
                (topic, category, difficulty, question_count, template, provider).

    Returns:
        The ID of the saved configuration, or -1 on error.
    """
    try:
        # This method uses safe_execute internally
        config_id = db_service.save_quiz_config(
            user_id=user_id,
            name=name,
            **config # Unpack the config dict as keyword arguments
        )
        return config_id
    except Exception as e:
        logger.error(f"Error saving quiz config '{name}' for user {user_id}: {e}", exc_info=True)
        return -1

def get_user_saved_configs(
    db_service: 'DatabaseService', 
    user_id: int
) -> List[Dict[str, Any]]:
    """
    Retrieves all saved quiz configurations for a user.

    Args:
        db_service: An instance of the DatabaseService.
        user_id: Discord user ID.

    Returns:
        A list of saved configuration dictionaries, or an empty list on error.
    """
    try:
        # This method uses safe_execute internally
        configs = db_service.get_saved_configs(user_id=user_id)
        return configs
    except Exception as e:
        logger.error(f"Error retrieving saved configs for user {user_id}: {e}", exc_info=True)
        return [] 