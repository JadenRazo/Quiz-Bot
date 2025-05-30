"""
Database operations related to fetching and formatting user statistics.
"""
import logging
import asyncio
from typing import TYPE_CHECKING, Dict, Any, Optional, List

if TYPE_CHECKING:
    from services.database import DatabaseService

logger = logging.getLogger("bot.db_ops.user_stats")

async def get_formatted_user_stats(
    db_service: 'DatabaseService', 
    user_id: int
) -> Optional[Dict[str, Any]]:
    """
    Fetches comprehensive user stats if available, falling back to basic stats.
    
    Handles calling the appropriate db_service methods and returns the data
    in a structure suitable for display (e.g., by StatsCog).

    Args:
        db_service: An instance of the DatabaseService.
        user_id: The Discord user ID.

    Returns:
        A dictionary containing formatted user stats, or None if no stats found
        or an error occurred.
    """
    stats = None
    try:
        logger.info(f"Fetching stats for user {user_id} via user_stats_ops")
        
        # Initialize with basic stats first
        basic_stats = None
        if hasattr(db_service, 'get_basic_user_stats'):
            try:
                # Basic stats should always be available - this is an async method
                basic_stats = await db_service.get_basic_user_stats(user_id)
                logger.info(f"Retrieved basic stats for user {user_id}: {basic_stats}")
            except Exception as e:
                logger.error(f"Error fetching basic stats for user {user_id}: {e}", exc_info=True)
                basic_stats = None
        
        # Get detailed quiz session history
        quiz_history = []
        try:
            if hasattr(db_service, 'get_user_quiz_history'):
                if asyncio.iscoroutinefunction(db_service.get_user_quiz_history):
                    quiz_history = await db_service.get_user_quiz_history(user_id, limit=50)
                else:
                    # Fallback to sync call if needed
                    quiz_history = await asyncio.to_thread(db_service.get_user_quiz_history, user_id, limit=50)
                logger.info(f"Retrieved {len(quiz_history)} quiz history entries for user {user_id}")
        except Exception as e:
            logger.error(f"Error fetching quiz history for user {user_id}: {e}", exc_info=True)
            quiz_history = []
        
        # Try comprehensive stats if available (preferred)
        if hasattr(db_service, 'get_comprehensive_user_stats'):
            logger.debug(f"Attempting get_comprehensive_user_stats for {user_id}")
            try:
                # Ensure this method is actually async or wrap with to_thread if sync
                if asyncio.iscoroutinefunction(db_service.get_comprehensive_user_stats):
                    stats = await db_service.get_comprehensive_user_stats(user_id)
                else:
                    logger.warning("get_comprehensive_user_stats is not async, running in thread.")
                    stats = await asyncio.to_thread(db_service.get_comprehensive_user_stats, user_id)
                logger.debug(f"Comprehensive stats result: {bool(stats)}")
            except Exception as e:
                logger.error(f"Error fetching comprehensive stats for user {user_id}: {e}", exc_info=True)
                stats = None
        
        # If we don't have comprehensive stats yet, build from basic stats
        if not stats and basic_stats:
            # Convert basic stats to the comprehensive structure
            logger.debug(f"Building comprehensive stats from basic stats: {basic_stats}")
            
            # Calculate activity data from quiz history if available
            by_category = {}
            by_difficulty = {}
            recent_activity = []
            
            for entry in quiz_history:
                # Process for category stats
                category = entry.get("category", "general")
                if category not in by_category:
                    by_category[category] = {
                        "name": category.capitalize(),
                        "quizzes": 0,
                        "correct": 0,
                        "wrong": 0,
                        "points": 0
                    }
                by_category[category]["quizzes"] += 1
                by_category[category]["correct"] += entry.get("correct", 0)
                by_category[category]["wrong"] += entry.get("wrong", 0)
                by_category[category]["points"] += entry.get("points", 0)
                
                # Process for difficulty stats
                difficulty = entry.get("difficulty", "medium")
                if difficulty not in by_difficulty:
                    by_difficulty[difficulty] = {
                        "name": difficulty.capitalize(),
                        "quizzes": 0,
                        "correct": 0,
                        "wrong": 0,
                        "points": 0
                    }
                by_difficulty[difficulty]["quizzes"] += 1
                by_difficulty[difficulty]["correct"] += entry.get("correct", 0)
                by_difficulty[difficulty]["wrong"] += entry.get("wrong", 0)
                by_difficulty[difficulty]["points"] += entry.get("points", 0)
                
                # Add to recent activity
                if len(recent_activity) < 5:  # Limit to 5 most recent
                    recent_activity.append({
                        "date": entry.get("date", ""),
                        "topic": entry.get("topic", "Unknown Topic"),
                        "correct": entry.get("correct", 0),
                        "wrong": entry.get("wrong", 0),
                        "points": entry.get("points", 0)
                    })
            
            # Build the comprehensive stats structure
            stats = {
                "user_id": user_id,
                "overall": {
                    "total_quizzes": basic_stats.get("quizzes_taken", 0),
                    "correct_answers": basic_stats.get("correct_answers", 0),
                    "wrong_answers": basic_stats.get("wrong_answers", 0),
                    "total_points": basic_stats.get("points", 0),
                    "accuracy": 0,
                    "level": basic_stats.get("level", 1)
                },
                "by_difficulty": list(by_difficulty.values()),
                "by_category": list(by_category.values()),
                "recent_activity": recent_activity
            }
            
            # Calculate accuracy
            total_answers = stats["overall"]["correct_answers"] + stats["overall"]["wrong_answers"]
            if total_answers > 0:
                stats["overall"]["accuracy"] = round((stats["overall"]["correct_answers"] / total_answers) * 100, 1)
            
            logger.debug(f"Built comprehensive stats structure for user {user_id}")
        
        # Final check if we have valid stats to return
        if stats and isinstance(stats, dict) and stats.get("overall"):
            if stats["overall"].get("total_quizzes", 0) > 0:
                logger.info(f"Returning valid stats for user {user_id}")
                return stats
            else:
                logger.info(f"User {user_id} has no quiz activity")
        else:
            logger.info(f"No valid stats structure found for user {user_id}")
             
        return stats

    except Exception as e:
        logger.error(f"Error fetching formatted user stats for {user_id}: {e}", exc_info=True)
        return None 

async def reset_user_stats(
    db_service: 'DatabaseService',
    user_id: int,
    username: Optional[str] = None,
    keep_achievements: bool = False,
    reset_history: bool = True
) -> Dict[str, Any]:
    """
    Reset a user's stats in the database.
    
    Args:
        db_service: An instance of the DatabaseService.
        user_id: The Discord user ID to reset stats for.
        username: User's current username (if provided, will be updated in the record).
        keep_achievements: If True, achievements won't be reset.
        reset_history: If True, quiz history will be deleted as well.
        
    Returns:
        A dictionary with the operation results:
        {
            "success": bool,
            "stats_reset": bool,
            "history_reset": bool,
            "achievements_reset": bool,
            "error": Optional[str]
        }
    """
    result = {
        "success": False,
        "stats_reset": False,
        "history_reset": False,
        "achievements_reset": False,
        "error": None
    }
    
    logger.info(f"Resetting stats for user_id: {user_id}, keep_achievements: {keep_achievements}, reset_history: {reset_history}")
    
    try:
        # Check if db_service has the necessary methods
        if not hasattr(db_service, 'get_connection') or not hasattr(db_service, 'release_connection'):
            result["error"] = "Database service doesn't have required methods"
            logger.error(f"Database service missing required methods for resetting user stats: {user_id}")
            return result
            
        # Get database connection
        conn = await db_service.get_connection()
        try:
            # 1. Reset user stats in the users table
            try:
                update_query = """
                UPDATE users
                SET correct_answers = 0,
                    wrong_answers = 0,
                    points = 0,
                    quizzes_taken = 0,
                    level = 1
                """
                
                # Conditionally update username if provided
                if username:
                    update_query += ", username = %s WHERE user_id = %s"
                    params = (username, user_id)
                else:
                    update_query += " WHERE user_id = %s"
                    params = (user_id,)
                
                await conn.execute(update_query, params)
                result["stats_reset"] = True
                logger.info(f"Reset core stats for user {user_id}")
            except Exception as e:
                logger.error(f"Error resetting core stats for user {user_id}: {e}", exc_info=True)
                result["error"] = f"Error resetting stats: {str(e)}"
            
            # 2. Reset quiz history if requested
            if reset_history:
                try:
                    # Check if table exists first
                    table_check = await conn.fetchval(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_quiz_sessions')"
                    )
                    
                    if table_check:
                        delete_query = "DELETE FROM user_quiz_sessions WHERE user_id = %s"
                        await conn.execute(delete_query, (user_id,))
                        result["history_reset"] = True
                        logger.info(f"Reset quiz history for user {user_id}")
                    else:
                        logger.warning(f"user_quiz_sessions table doesn't exist, skipping history reset for user {user_id}")
                except Exception as e:
                    logger.error(f"Error resetting quiz history for user {user_id}: {e}", exc_info=True)
            
            # 3. Reset achievements if requested
            if not keep_achievements:
                try:
                    # Check if table exists first
                    table_check = await conn.fetchval(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_achievements')"
                    )
                    
                    if table_check:
                        delete_query = "DELETE FROM user_achievements WHERE user_id = %s"
                        await conn.execute(delete_query, (user_id,))
                        result["achievements_reset"] = True
                        logger.info(f"Reset achievements for user {user_id}")
                    else:
                        logger.warning(f"user_achievements table doesn't exist, skipping achievement reset for user {user_id}")
                except Exception as e:
                    logger.error(f"Error resetting achievements for user {user_id}: {e}", exc_info=True)
            
            # Set overall success if at least the stats were reset
            result["success"] = result["stats_reset"]
        finally:
            # Return the connection to the pool
            await db_service.release_connection(conn)
            
    except Exception as e:
        logger.error(f"Error in reset_user_stats for user {user_id}: {e}", exc_info=True)
        result["error"] = f"Unexpected error: {str(e)}"
        
    return result 