"""
Data validation utilities for quiz bot to ensure consistency and prevent corruption.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("bot.data_validation")


def validate_quiz_result_data(
    user_id: int,
    quiz_id: str,
    correct: int,
    wrong: int,
    points: int,
    topic: str,
    difficulty: str,
    category: str
) -> Dict[str, Any]:
    """
    Validate and sanitize quiz result data before database storage.
    
    Args:
        user_id: Discord user ID
        quiz_id: Unique quiz session identifier
        correct: Number of correct answers
        wrong: Number of wrong answers
        points: Points earned
        topic: Quiz topic
        difficulty: Quiz difficulty
        category: Quiz category
    
    Returns:
        Dict with 'valid' bool and 'data' dict or 'errors' list
    """
    errors = []
    
    # Validate user_id
    if not isinstance(user_id, int) or user_id <= 0:
        errors.append(f"Invalid user_id: {user_id}")
    
    # Validate quiz_id
    if not quiz_id or not isinstance(quiz_id, str):
        errors.append(f"Invalid quiz_id: {quiz_id}")
    elif len(quiz_id) > 100:
        errors.append(f"Quiz ID too long: {len(quiz_id)} characters (max 100)")
    
    # Validate numeric values
    if not isinstance(correct, int) or correct < 0:
        errors.append(f"Invalid correct answers: {correct}")
        correct = max(0, int(correct)) if isinstance(correct, (int, float)) else 0
    
    if not isinstance(wrong, int) or wrong < 0:
        errors.append(f"Invalid wrong answers: {wrong}")
        wrong = max(0, int(wrong)) if isinstance(wrong, (int, float)) else 0
    
    if not isinstance(points, int) or points < 0:
        errors.append(f"Invalid points: {points}")
        points = max(0, int(points)) if isinstance(points, (int, float)) else 0
    
    # Validate total answers makes sense
    total_answers = correct + wrong
    if total_answers == 0:
        errors.append("No answers recorded (correct + wrong = 0)")
    elif total_answers > 50:  # Sanity check
        errors.append(f"Unusually high answer count: {total_answers}")
    
    # Validate points are reasonable relative to answers
    if total_answers > 0 and points > (total_answers * 200):  # Max 200 points per question
        errors.append(f"Points too high: {points} for {total_answers} questions")
    
    # Validate string fields
    if not topic or len(topic.strip()) == 0:
        errors.append("Topic is empty")
        topic = "Unknown"
    elif len(topic) > 255:
        topic = topic[:255]
    
    if difficulty not in ['easy', 'medium', 'hard']:
        errors.append(f"Invalid difficulty: {difficulty}")
        difficulty = 'medium'
    
    if not category or len(category.strip()) == 0:
        category = 'general'
    elif len(category) > 100:
        category = category[:100]
    
    # Return validation result
    if errors:
        logger.warning(f"Data validation errors for user {user_id}: {errors}")
        return {
            'valid': False,
            'errors': errors,
            'sanitized_data': {
                'user_id': user_id,
                'quiz_id': quiz_id,
                'correct': correct,
                'wrong': wrong,
                'points': points,
                'topic': topic.strip(),
                'difficulty': difficulty,
                'category': category.strip()
            }
        }
    
    return {
        'valid': True,
        'data': {
            'user_id': user_id,
            'quiz_id': quiz_id,
            'correct': correct,
            'wrong': wrong,
            'points': points,
            'topic': topic.strip(),
            'difficulty': difficulty,
            'category': category.strip()
        }
    }


def calculate_accuracy(correct: int, wrong: int) -> float:
    """
    Standard accuracy calculation used across all components.
    
    Args:
        correct: Number of correct answers
        wrong: Number of wrong answers
    
    Returns:
        Accuracy percentage (0.0 to 100.0)
    """
    total = correct + wrong
    if total == 0:
        return 0.0
    return round((correct / total) * 100.0, 1)


def calculate_xp_from_points(points: int) -> int:
    """
    Standard XP calculation. XP = Points earned.
    
    Args:
        points: Points earned in quiz
    
    Returns:
        XP earned (same as points)
    """
    return max(0, int(points))


def calculate_level_from_total_points(total_points: int) -> int:
    """
    Calculate level based on total points accumulated.
    
    Args:
        total_points: Total points across all quizzes
    
    Returns:
        Current level (1-based)
    """
    if total_points <= 0:
        return 1
    
    # Level progression: 100 points per level
    return (total_points // 100) + 1


def calculate_current_xp_in_level(total_points: int) -> int:
    """
    Calculate current XP within current level.
    
    Args:
        total_points: Total points accumulated
    
    Returns:
        Current XP within level (0-99)
    """
    if total_points <= 0:
        return 0
    
    return total_points % 100


async def validate_database_consistency(db_service, user_id: int) -> Dict[str, Any]:
    """
    Check for data consistency issues for a specific user.
    
    Args:
        db_service: Database service instance
        user_id: User ID to check
    
    Returns:
        Dict with consistency check results
    """
    issues = []
    
    try:
        conn = await db_service.get_connection()
        try:
            # Get user table stats
            user_query = """
            SELECT quizzes_taken, correct_answers, wrong_answers, points
            FROM users WHERE user_id = $1
            """
            user_stats = await conn.fetchrow(user_query, user_id)
            
            # Get session table aggregates
            session_query = """
            SELECT 
                COUNT(DISTINCT quiz_id) as session_count,
                SUM(correct_answers) as session_correct,
                SUM(wrong_answers) as session_wrong,
                SUM(points) as session_points
            FROM user_quiz_sessions WHERE user_id = $1
            """
            session_stats = await conn.fetchrow(session_query, user_id)
            
            if user_stats and session_stats:
                user_data = dict(user_stats)
                session_data = dict(session_stats)
                
                # Check for mismatches
                if user_data['quizzes_taken'] != session_data['session_count']:
                    issues.append(f"Quiz count mismatch: users table={user_data['quizzes_taken']}, sessions={session_data['session_count']}")
                
                if user_data['correct_answers'] != session_data['session_correct']:
                    issues.append(f"Correct answers mismatch: users table={user_data['correct_answers']}, sessions={session_data['session_correct']}")
                
                if user_data['wrong_answers'] != session_data['session_wrong']:
                    issues.append(f"Wrong answers mismatch: users table={user_data['wrong_answers']}, sessions={session_data['session_wrong']}")
                
                if user_data['points'] != session_data['session_points']:
                    issues.append(f"Points mismatch: users table={user_data['points']}, sessions={session_data['session_points']}")
            
            # Check for duplicate sessions
            duplicate_query = """
            SELECT quiz_id, COUNT(*) as count
            FROM user_quiz_sessions 
            WHERE user_id = $1
            GROUP BY quiz_id
            HAVING COUNT(*) > 1
            """
            duplicates = await conn.fetch(duplicate_query, user_id)
            
            if duplicates:
                for dup in duplicates:
                    issues.append(f"Duplicate session: quiz_id={dup['quiz_id']}, count={dup['count']}")
            
        finally:
            await db_service.release_connection(conn)
            
    except Exception as e:
        logger.error(f"Error checking consistency for user {user_id}: {e}")
        issues.append(f"Database error: {e}")
    
    return {
        'user_id': user_id,
        'issues': issues,
        'consistent': len(issues) == 0,
        'checked_at': datetime.utcnow().isoformat()
    }


def log_data_discrepancy(component: str, user_id: int, expected: Any, actual: Any, context: str = ""):
    """
    Log data discrepancies for debugging and monitoring.
    
    Args:
        component: Component where discrepancy was found
        user_id: User ID affected
        expected: Expected value
        actual: Actual value
        context: Additional context
    """
    logger.warning(f"Data discrepancy in {component} for user {user_id}: expected={expected}, actual={actual}. Context: {context}")