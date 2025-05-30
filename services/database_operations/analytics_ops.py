"""
Database operations related to fetching server analytics.
"""
import logging
import asyncio
from typing import TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    from services.database import DatabaseService

logger = logging.getLogger("bot.db_ops.analytics")

async def get_formatted_server_analytics(
    db_service: 'DatabaseService', 
    guild_id: int
) -> Optional[Dict[str, Any]]:
    """
    Fetches and cleans server analytics data.

    Args:
        db_service: An instance of the DatabaseService.
        guild_id: The Discord guild ID.

    Returns:
        A dictionary containing cleaned analytics data, or None on error.
    """
    analytics_data = None
    try:
        logger.info(f"Fetching analytics for guild {guild_id} via analytics_ops")
        if not hasattr(db_service, 'get_server_analytics'):
             logger.warning("Database service does not have 'get_server_analytics' method.")
             return None

        # Fetch raw data, handling async/sync
        if asyncio.iscoroutinefunction(db_service.get_server_analytics):
            analytics_data_raw = await db_service.get_server_analytics(guild_id)
        else:
            logger.warning("get_server_analytics is not async, running in thread.")
            analytics_data_raw = await asyncio.to_thread(db_service.get_server_analytics, guild_id)

        if not analytics_data_raw:
            logger.info(f"No analytics data found for guild {guild_id}")
            return None

        # --- Data Cleaning (Moved from Cog) --- 
        logger.debug(f"Raw analytics returned for guild {guild_id}: {type(analytics_data_raw)}")
        
        # Ensure analytics_data is a regular dict
        if not isinstance(analytics_data_raw, dict):
            logger.warning(f"Analytics data from db_service is not a dictionary: {type(analytics_data_raw)}. Attempting conversion.")
            try:
                analytics_data = dict(analytics_data_raw)
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to convert raw analytics data to dictionary for guild {guild_id}: {e}")
                return None # Cannot proceed if base is not dict-like
        else:
             analytics_data = analytics_data_raw

        # Convert nested known structures to regular dicts/lists
        # General Stats
        if "general" in analytics_data and not isinstance(analytics_data.get("general"), dict):
            try:
                analytics_data["general"] = dict(analytics_data["general"])
            except Exception as e:
                logger.warning(f"Failed to convert general stats to dictionary for guild {guild_id}: {e}")
                analytics_data["general"] = {}
        elif "general" not in analytics_data:
             analytics_data["general"] = {}

        # List-based stats
        for list_key in ["by_difficulty", "by_category", "usage_over_time", "popular_topics"]:
            raw_list = analytics_data.get(list_key)
            clean_list = []
            if isinstance(raw_list, list):
                for item_raw in raw_list:
                    try:
                        clean_list.append(dict(item_raw) if not isinstance(item_raw, dict) else item_raw)
                    except Exception as e:
                        logger.warning(f"Failed to convert item in list '{list_key}' to dict for guild {guild_id}: {e}")
                analytics_data[list_key] = clean_list
            elif raw_list is not None:
                 logger.warning(f"Analytics key '{list_key}' was not a list for guild {guild_id}, setting to empty list. Type: {type(raw_list)}")
                 analytics_data[list_key] = []
            else:
                 # Ensure key exists even if empty
                 analytics_data[list_key] = []
        # --- End Data Cleaning ---

        logger.info(f"Successfully fetched and cleaned analytics for guild {guild_id}")
        return analytics_data

    except Exception as e:
        logger.error(f"Error fetching formatted server analytics for {guild_id}: {e}", exc_info=True)
        return None 