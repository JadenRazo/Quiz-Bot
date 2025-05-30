"""
Helper utilities for database operations.
These functions help with migration from DatabaseService to DatabaseServiceV2
by providing common operations in a way that works with both services.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple, Union, Callable

logger = logging.getLogger("bot.db_helpers")

async def get_user_stats(context, user_id: int, guild_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get user statistics from either V2 or legacy database service.
    
    Args:
        context: The BotContext object
        user_id: Discord user ID
        guild_id: Optional guild ID for guild-specific stats
    
    Returns:
        Dictionary of user statistics
    """
    # Try V2 service first
    if hasattr(context, 'db_service_v2') and context.db_service_v2:
        try:
            stats = await context.db_service_v2.get_user_stats(user_id, guild_id)
            if stats:
                return stats
        except Exception as e:
            logger.warning(f"Error getting user stats from V2 service: {e}")
    
    # Fall back to legacy service
    if context.db_service:
        try:
            # For legacy service, handle guild ID differently
            if guild_id:
                # First ensure user exists in guild
                await asyncio.to_thread(
                    context.db_service.add_guild_member,
                    guild_id=guild_id,
                    user_id=user_id
                )
                
                # Get stats (guild filtering happens in SQL for old service)
                return await asyncio.to_thread(context.db_service.get_basic_user_stats, user_id)
            else:
                # Just get global stats
                return await asyncio.to_thread(context.db_service.get_basic_user_stats, user_id)
        except Exception as e:
            logger.error(f"Error getting user stats from legacy service: {e}")
    
    # Return empty stats if both methods fail
    return {
        "user_id": user_id,
        "username": f"User_{user_id}",
        "quizzes_taken": 0,
        "correct_answers": 0,
        "wrong_answers": 0,
        "points": 0,
        "level": 1,
        "error": True
    }

async def record_quiz_result(context, user_id: int, username: str, quiz_id: str, 
                           topic: str, correct: int, wrong: int, points: int,
                           difficulty: str, category: str, 
                           guild_id: Optional[int] = None) -> bool:
    """
    Record a quiz result using either V2 or legacy database service.
    
    Args:
        context: The BotContext object
        user_id: Discord user ID
        username: User's display name
        quiz_id: Unique identifier for the quiz session
        topic: Quiz topic
        correct: Number of correct answers
        wrong: Number of wrong answers
        points: Points earned
        difficulty: Quiz difficulty
        category: Quiz category
        guild_id: Optional guild ID
    
    Returns:
        True if the record was saved successfully, False otherwise
    """
    # Try V2 service first
    if hasattr(context, 'db_service_v2') and context.db_service_v2:
        try:
            # Format data for V2 service
            xp = correct * 10  # Calculate XP the same way as displayed in UI
            total_questions = correct + wrong
            accuracy = 100 * correct / max(1, total_questions)
            is_perfect = (wrong == 0 and correct > 0)
            
            # Record the quiz session
            session_id = await context.db_service_v2.record_quiz_session(
                user_id=user_id,
                guild_id=guild_id,
                quiz_data={
                    'quiz_id': quiz_id,
                    'quiz_type': 'standard',
                    'topic': topic,
                    'difficulty': difficulty,
                    'category': category,
                    'total_questions': total_questions,
                    'correct_answers': correct,
                    'wrong_answers': wrong,
                    'points': points,
                    'xp': xp,
                    'accuracy': accuracy,
                    'is_completed': True,
                    'is_perfect': is_perfect,
                    'username': username
                }
            )
            
            if session_id:
                # Check for achievements
                await context.db_service_v2.check_and_award_achievements(
                    user_id=user_id,
                    guild_id=guild_id,
                    context={
                        'perfect_score': is_perfect,
                        'first_quiz': True  # Let the DB function check this
                    }
                )
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error recording quiz result with V2 service: {e}")
    
    # Fall back to legacy service
    if context.db_service:
        try:
            from services.database_operations.quiz_stats_ops import record_complete_quiz_result_for_user
            
            # Use the existing function to record results with the legacy service
            success = await record_complete_quiz_result_for_user(
                db_service=context.db_service,
                user_id=user_id,
                username=username,
                quiz_id=quiz_id,
                topic=topic,
                correct=correct,
                wrong=wrong,
                points=points,
                difficulty=difficulty,
                category=category,
                guild_id=guild_id
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error recording quiz result with legacy service: {e}")
    
    return False

async def get_leaderboard(context, guild_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get leaderboard using either V2 or legacy database service.
    
    Args:
        context: The BotContext object
        guild_id: Optional guild ID for guild-specific leaderboard
        limit: Maximum number of users to return
    
    Returns:
        List of top users
    """
    # Try V2 service first
    if hasattr(context, 'db_service_v2') and context.db_service_v2:
        try:
            if guild_id:
                return await context.db_service_v2.get_guild_leaderboard(guild_id, limit)
            else:
                return await context.db_service_v2.get_global_leaderboard(limit)
        except Exception as e:
            logger.warning(f"Error getting leaderboard from V2 service: {e}")
    
    # Fall back to legacy service
    if context.db_service:
        try:
            if guild_id:
                return await asyncio.to_thread(
                    context.db_service.get_guild_leaderboard,
                    guild_id=guild_id,
                    limit=limit
                )
            else:
                return await asyncio.to_thread(
                    context.db_service.get_leaderboard,
                    limit=limit
                )
        except Exception as e:
            logger.error(f"Error getting leaderboard from legacy service: {e}")
    
    return []

async def ensure_guild_member(context, guild_id: int, user_id: int, username: str = None) -> bool:
    """
    Ensure a user is a member of a guild using either V2 or legacy database service.
    
    Args:
        context: The BotContext object
        guild_id: Discord guild ID
        user_id: Discord user ID
        username: Optional username to register if user doesn't exist
    
    Returns:
        True if successful, False otherwise
    """
    if username is None:
        username = f"User_{user_id}"
    
    # Try V2 service first
    if hasattr(context, 'db_service_v2') and context.db_service_v2:
        try:
            # Ensure user exists
            await context.db_service_v2.get_or_create_user(
                user_id=user_id,
                username=username,
                guild_id=guild_id
            )
            return True
        except Exception as e:
            logger.warning(f"Error ensuring guild member with V2 service: {e}")
    
    # Fall back to legacy service
    if context.db_service:
        try:
            # Add user to guild using legacy service
            success = await asyncio.to_thread(
                context.db_service.add_guild_member,
                guild_id=guild_id,
                user_id=user_id
            )
            return success
        except Exception as e:
            logger.error(f"Error ensuring guild member with legacy service: {e}")
    
    return False

async def with_retry(operation, max_retries=3, retry_delay=1.0):
    """
    Execute a database operation with retry logic.
    
    Args:
        operation: Async function to execute
        max_retries: Maximum number of retry attempts
        retry_delay: Seconds to wait between retries
        
    Returns:
        Result of the operation
        
    Raises:
        Exception: If all retries fail
    """
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_retries - 1:
                # Last attempt failed, re-raise
                raise
            
            # Log and retry after delay
            logger.warning(f"Database operation failed (attempt {attempt+1}/{max_retries}): {e}")
            await asyncio.sleep(retry_delay)