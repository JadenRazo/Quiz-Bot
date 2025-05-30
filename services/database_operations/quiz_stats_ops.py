"""
Database operations specifically related to recording and managing quiz statistics.
"""
import logging
import asyncio # Import asyncio
from typing import TYPE_CHECKING, List, Dict, Any

# Use TYPE_CHECKING to avoid circular import issues with DatabaseService
if TYPE_CHECKING:
    from services.database import DatabaseService

logger = logging.getLogger("bot.db_ops.quiz_stats")

async def record_complete_quiz_result_for_user(
    db_service: 'DatabaseService', 
    user_id: int,
    username: str,
    quiz_id: str,
    topic: str,
    correct: int,
    wrong: int,
    points: int,
    difficulty: str,
    category: str,
    guild_id: int = None
) -> bool:
    """
    Records the complete results for a single user after a quiz session.

    Orchestrates calls to the DatabaseService to record session details
    and update aggregate user statistics.

    Args:
        db_service: An instance of the DatabaseService.
        user_id: Discord user ID.
        username: User's display name.
        quiz_id: Unique identifier for the quiz session.
        topic: Quiz topic.
        correct: Number of correct answers in this session.
        wrong: Number of wrong answers in this session.
        points: Points earned in this session.
        difficulty: Quiz difficulty.
        category: Quiz category.

    Returns:
        True if all underlying database operations were reported as successful, 
        False otherwise. Note that underlying methods use safe_execute, so
        errors within them might be logged but not raise exceptions here.
    """
    all_success = True
    try:
        # 1. Record detailed session (this uses the async method from UserStatsService)
        session_recorded = await db_service.record_user_quiz_session(
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
        if not session_recorded:
            all_success = False
            logger.warning(f"Failed to record user quiz session via db_service for user {user_id}, quiz {quiz_id}")

        # Run async database operations directly
        update_task = db_service.update_user_stats(
            user_id=user_id,
            username=username,
            correct=correct,
            wrong=wrong,
            points=points
        )
        
        increment_task = db_service.increment_quizzes_taken(
            user_id=user_id,
            username=username
        )

        # Wait for both background tasks to complete
        # Results are not strictly needed here as errors are logged within the methods
        await asyncio.gather(update_task, increment_task)

        if all_success:
            logger.debug(f"Successfully recorded complete quiz result for user {user_id} ({username}), quiz {quiz_id}")
        else:
            # Only log warning if session recording failed, as sync methods handle their own logs.
            logger.warning(f"Partial success recording quiz result for user {user_id} ({username}), quiz {quiz_id} (session recording failed)")
            
        return all_success

    except Exception as e:
        # This catches errors calling the db_service methods themselves, 
        # not necessarily errors *within* those methods if safe_execute handles them.
        logger.error(f"Error orchestrating quiz result recording for user {user_id}, quiz {quiz_id}: {e}", exc_info=True)
        return False 

async def record_batch_quiz_results(
    db_service: 'DatabaseService', 
    quiz_id: str, 
    topic: str,
    results: List[Dict[str, Any]],
    guild_id: int = None
) -> bool:
    """
    Records the results for multiple users from a single quiz session in batches.

    Args:
        db_service: An instance of the DatabaseService.
        quiz_id: Unique identifier for the quiz session.
        topic: Quiz topic.
        results: A list of dictionaries, where each dictionary represents
                 one user's result and contains keys like 'user_id', 'username',
                 'correct', 'wrong', 'points', 'difficulty', 'category'.

    Returns:
        True if batch operations were submitted successfully, False otherwise.
    """
    if not results:
        logger.info("No results provided to record_batch_quiz_results.")
        return True

    all_session_records_success = True
    users_for_aggregate_update = []
    
    logger.info(f"Starting batch recording for {len(results)} users for quiz {quiz_id}")

    try:
        # 1. Record individual sessions (still async, potentially could be batched further)
        session_tasks = []
        for user_result in results:
            user_id = user_result.get('user_id')
            username = user_result.get('username', 'UnknownUser')
            # Try to update username if it's 'UnknownUser' and we have a member object from Discord
            if username == 'UnknownUser' and ctx and ctx.guild:
                member = ctx.guild.get_member(user_id)
                if member:
                    username = member.display_name
                    logger.info(f"Updated 'UnknownUser' to actual Discord username: {username} for user ID {user_id}")
            correct = user_result.get('correct', 0)
            wrong = user_result.get('wrong', 0)
            points = user_result.get('points', 0)
            difficulty = user_result.get('difficulty', 'unknown')
            category = user_result.get('category', 'unknown')

            if user_id is None:
                logger.warning(f"Skipping result record due to missing user_id in quiz {quiz_id}")
                continue

            # Add data needed for aggregate updates later
            users_for_aggregate_update.append({
                'user_id': user_id,
                'username': username,
                'correct': correct,
                'wrong': wrong,
                'points': points
            })
            
            # Create task for async session recording
            # Check if the record_user_quiz_session method accepts the guild_id parameter
            if hasattr(db_service, 'record_user_quiz_session'):
                try:
                    # Import inspect to check function signature
                    import inspect
                    # Get signature of the record_user_quiz_session method
                    sig = inspect.signature(db_service.record_user_quiz_session)
                    # Check if 'guild_id' is in the parameters
                    if 'guild_id' in sig.parameters:
                        # If guild_id is accepted, include it
                        session_tasks.append(
                            db_service.record_user_quiz_session(
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
                        )
                    else:
                        # If guild_id is not accepted, exclude it
                        session_tasks.append(
                            db_service.record_user_quiz_session(
                                user_id=user_id,
                                username=username,
                                quiz_id=quiz_id,
                                topic=topic,
                                correct=correct,
                                wrong=wrong,
                                points=points,
                                difficulty=difficulty,
                                category=category
                            )
                        )
                except Exception as e:
                    logger.error(f"Error checking record_user_quiz_session method signature: {e}")
                    # Fallback without guild_id
                    session_tasks.append(
                        db_service.record_user_quiz_session(
                            user_id=user_id,
                            username=username,
                            quiz_id=quiz_id,
                            topic=topic,
                            correct=correct,
                            wrong=wrong,
                            points=points,
                            difficulty=difficulty,
                            category=category
                        )
                    )
            else:
                logger.error(f"DatabaseService does not have record_user_quiz_session method")
                # Skip this user
                continue
        
        # Run session recordings concurrently
        session_outcomes = await asyncio.gather(*session_tasks, return_exceptions=True)
        for i, outcome in enumerate(session_outcomes):
            if isinstance(outcome, Exception):
                all_session_records_success = False
                user_id = results[i].get('user_id', 'Unknown')
                logger.error(f"Error recording session for user {user_id} in quiz {quiz_id}: {outcome}")
            elif outcome is False:
                all_session_records_success = False
                user_id = results[i].get('user_id', 'Unknown')
                logger.warning(f"Failed to record session (returned False) for user {user_id} in quiz {quiz_id}")

        if not users_for_aggregate_update:
             logger.warning(f"No valid user data collected for aggregate updates in quiz {quiz_id}. Skipping batch updates.")
             return all_session_records_success # Return success state of session recordings

        # 2. Perform batch updates for aggregate stats directly (these are async methods)
        logger.debug(f"Submitting batch aggregate updates for {len(users_for_aggregate_update)} users for quiz {quiz_id}")
        batch_stats_task = db_service.batch_update_user_stats(users_for_aggregate_update)
        batch_increment_task = db_service.batch_increment_quizzes_taken(users_for_aggregate_update)
        
        # Wait for batch operations to complete
        batch_results = await asyncio.gather(batch_stats_task, batch_increment_task, return_exceptions=True)
        
        batch_success = True
        for outcome in batch_results:
            if isinstance(outcome, Exception):
                 logger.error(f"Exception during batch aggregate update for quiz {quiz_id}: {outcome}", exc_info=outcome)
                 batch_success = False
            elif outcome is False:
                 logger.warning(f"Batch aggregate update method returned False for quiz {quiz_id}")
                 batch_success = False # Consider False return as failure

        overall_success = all_session_records_success and batch_success
        logger.info(f"Batch recording for quiz {quiz_id} completed. Overall success: {overall_success}")
        return overall_success

    except Exception as e:
        logger.error(f"Error orchestrating batch quiz result recording for quiz {quiz_id}: {e}", exc_info=True)
        return False 