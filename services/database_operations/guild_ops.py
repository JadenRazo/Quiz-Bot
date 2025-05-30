"""Guild-specific database operations."""

import logging
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)


async def get_guild_settings(db_service, guild_id: int) -> Dict[str, Any]:
    """Get all settings for a guild."""
    query = """
        SELECT settings, quiz_channel_id, trivia_channel_id, admin_role_id,
               notification_channel_id, default_quiz_difficulty, default_question_count,
               trivia_timeout, allow_custom_quizzes, allow_leaderboards
        FROM guild_settings
        WHERE guild_id = %s
    """
    
    async with db_service.pool.acquire() as conn:
        row = await conn.fetchrow(query, guild_id)
        
        if not row:
            # Return default settings if guild not in database
            return {
                "quiz_channel_id": None,
                "trivia_channel_id": None,
                "admin_role_id": None,
                "notification_channel_id": None,
                "default_quiz_difficulty": "medium",
                "default_question_count": 5,
                "trivia_timeout": 30,
                "allow_custom_quizzes": True,
                "allow_leaderboards": True,
                "feature_group_quiz": True,
                "feature_custom_quiz": True,
                "feature_leaderboard": True
            }
        
        # Merge JSON settings with column values
        settings = row['settings'] or {}
        settings.update({
            "quiz_channel_id": str(row['quiz_channel_id']) if row['quiz_channel_id'] else None,
            "trivia_channel_id": str(row['trivia_channel_id']) if row['trivia_channel_id'] else None,
            "admin_role_id": str(row['admin_role_id']) if row['admin_role_id'] else None,
            "notification_channel_id": str(row['notification_channel_id']) if row['notification_channel_id'] else None,
            "default_quiz_difficulty": row['default_quiz_difficulty'],
            "default_question_count": row['default_question_count'],
            "trivia_timeout": row['trivia_timeout'],
            "allow_custom_quizzes": row['allow_custom_quizzes'],
            "allow_leaderboards": row['allow_leaderboards']
        })
        
        return settings


async def set_guild_setting(db_service, guild_id: int, setting_key: str, setting_value: Any) -> bool:
    """Set a specific guild setting."""
    try:
        # First, ensure guild exists in settings table
        insert_query = """
            INSERT INTO guild_settings (guild_id, settings)
            VALUES (%s, %s)
            ON CONFLICT (guild_id) DO NOTHING
        """
        
        async with db_service.pool.acquire() as conn:
            await conn.execute(insert_query, guild_id, json.dumps({}))
            
            # Update based on the setting key
            if setting_key in ["quiz_channel_id", "trivia_channel_id", "admin_role_id", "notification_channel_id"]:
                # These are direct columns
                update_query = f"""
                    UPDATE guild_settings
                    SET {setting_key} = %s, updated_at = NOW()
                    WHERE guild_id = %s
                """
                await conn.execute(update_query, int(setting_value) if setting_value else None, guild_id)
            
            elif setting_key in ["default_quiz_difficulty", "default_question_count", "trivia_timeout"]:
                # These are also direct columns
                update_query = f"""
                    UPDATE guild_settings
                    SET {setting_key} = %s, updated_at = NOW()
                    WHERE guild_id = %s
                """
                value = setting_value
                if setting_key in ["default_question_count", "trivia_timeout"]:
                    value = int(value)
                await conn.execute(update_query, value, guild_id)
            
            elif setting_key.startswith("feature_"):
                # These go in the JSON settings
                update_query = """
                    UPDATE guild_settings
                    SET settings = jsonb_set(
                        COALESCE(settings, '{}'::jsonb),
                        %s,
                        %s::jsonb
                    ),
                    updated_at = NOW()
                    WHERE guild_id = %s
                """
                await conn.execute(
                    update_query,
                    [setting_key],
                    json.dumps(setting_value == "true"),
                    guild_id
                )
            
            else:
                # General JSON setting
                update_query = """
                    UPDATE guild_settings
                    SET settings = jsonb_set(
                        COALESCE(settings, '{}'::jsonb),
                        %s,
                        %s::jsonb
                    ),
                    updated_at = NOW()
                    WHERE guild_id = %s
                """
                await conn.execute(
                    update_query,
                    [setting_key],
                    json.dumps(setting_value),
                    guild_id
                )
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting guild setting: {e}")
        return False


async def get_guild_leaderboard(db_service, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get the top performers in a guild."""
    query = """
        SELECT 
            u.user_id,
            u.username,
            gl.total_points,
            gl.total_quizzes,
            gl.total_correct,
            gl.total_wrong,
            gl.win_streak,
            gl.best_streak,
            ROUND(
                CASE 
                    WHEN gl.total_correct + gl.total_wrong > 0 
                    THEN gl.total_correct::numeric / (gl.total_correct + gl.total_wrong) * 100
                    ELSE 0
                END, 2
            ) as accuracy
        FROM guild_leaderboards gl
        JOIN users u ON gl.user_id = u.user_id
        WHERE gl.guild_id = %s
        ORDER BY gl.total_points DESC
        LIMIT %s
    """
    
    async with db_service.pool.acquire() as conn:
        rows = await conn.fetch(query, guild_id, limit)
        
        return [
            {
                "user_id": row['user_id'],
                "username": row['username'],
                "total_points": row['total_points'],
                "total_quizzes": row['total_quizzes'],
                "total_correct": row['total_correct'],
                "total_wrong": row['total_wrong'],
                "win_streak": row['win_streak'],
                "best_streak": row['best_streak'],
                "accuracy": float(row['accuracy'])
            }
            for row in rows
        ]


async def update_guild_user_stats(db_service, guild_id: int, user_id: int, 
                                 points: int, correct: int, wrong: int) -> bool:
    """Update a user's stats for a specific guild."""
    try:
        # Use the stored function
        query = "SELECT update_guild_leaderboard(%s, %s, %s, %s, %s)"
        
        async with db_service.pool.acquire() as conn:
            await conn.execute(query, guild_id, user_id, points, correct, wrong)
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating guild user stats: {e}")
        return False


async def get_guild_user_preferences(db_service, guild_id: int, user_id: int) -> Dict[str, Any]:
    """Get user preferences specific to a guild."""
    query = """
        SELECT preferences
        FROM guild_user_preferences
        WHERE guild_id = %s AND user_id = %s
    """
    
    async with db_service.pool.acquire() as conn:
        row = await conn.fetchrow(query, guild_id, user_id)
        
        if row and row['preferences']:
            return row['preferences']
        
        # Return empty preferences if not found
        return {}


async def set_guild_user_preferences(db_service, guild_id: int, user_id: int, 
                                    preferences: Dict[str, Any]) -> bool:
    """Set user preferences specific to a guild."""
    try:
        query = """
            INSERT INTO guild_user_preferences (guild_id, user_id, preferences)
            VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE
            SET preferences = %s, updated_at = NOW()
        """
        
        prefs_json = json.dumps(preferences)
        
        async with db_service.pool.acquire() as conn:
            await conn.execute(query, guild_id, user_id, prefs_json, prefs_json)
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting guild user preferences: {e}")
        return False


async def get_active_guild_sessions(db_service, guild_id: int) -> List[Dict[str, Any]]:
    """Get all active quiz sessions for a guild."""
    query = """
        SELECT 
            id,
            channel_id,
            host_id,
            topic,
            question_count,
            participant_count,
            status,
            started_at,
            quiz_type
        FROM guild_quiz_sessions
        WHERE guild_id = %s AND status = 'active'
        ORDER BY started_at DESC
    """
    
    async with db_service.pool.acquire() as conn:
        rows = await conn.fetch(query, guild_id)
        
        return [
            {
                "id": row['id'],
                "channel_id": row['channel_id'],
                "host_id": row['host_id'],
                "topic": row['topic'],
                "question_count": row['question_count'],
                "participant_count": row['participant_count'],
                "status": row['status'],
                "started_at": row['started_at'],
                "quiz_type": row['quiz_type']
            }
            for row in rows
        ]