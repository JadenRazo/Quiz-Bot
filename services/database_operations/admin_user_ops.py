"""
Database operations for admin user management functionality.

This module provides comprehensive user management capabilities for administrators,
including user data modification, deletion, search, and statistics reset operations.
"""

import logging
import re
from typing import TYPE_CHECKING, Dict, Any, Optional, List, Union, Tuple
import discord
from discord.ext import commands

if TYPE_CHECKING:
    from services.database import DatabaseService

logger = logging.getLogger("bot.db_ops.admin_user")


async def resolve_user_identifier(
    identifier: str,
    guild: discord.Guild,
    bot: commands.Bot,
    db_service: 'DatabaseService'
) -> Optional[Dict[str, Any]]:
    """
    Resolve a user identifier through multiple methods.
    
    Supports:
    - Discord mentions (@user)
    - User IDs (123456789)
    - Username searches (partial matching)
    - Display name searches
    - Leaderboard positions (#1, #2, etc.)
    
    Args:
        identifier: The user identifier to resolve
        guild: The Discord guild context
        bot: The Discord bot instance
        db_service: Database service instance
        
    Returns:
        Dictionary with user info if found, None otherwise
        Format: {
            'user_id': int,
            'username': str,
            'display_name': str,
            'discord_user': discord.User (if found),
            'source': str (how they were found)
        }
    """
    logger.info(f"Resolving user identifier: '{identifier}' in guild {guild.id}")
    
    # Method 1: Discord mention or raw user ID
    if identifier.startswith('<@') and identifier.endswith('>'):
        # Extract user ID from mention
        user_id_str = identifier[2:-1]
        if user_id_str.startswith('!'):
            user_id_str = user_id_str[1:]
        try:
            user_id = int(user_id_str)
            discord_user = await bot.fetch_user(user_id)
            return {
                'user_id': user_id,
                'username': discord_user.name,
                'display_name': discord_user.display_name,
                'discord_user': discord_user,
                'source': 'mention'
            }
        except (ValueError, discord.NotFound):
            pass
    
    # Method 2: Raw user ID
    if identifier.isdigit():
        try:
            user_id = int(identifier)
            discord_user = await bot.fetch_user(user_id)
            return {
                'user_id': user_id,
                'username': discord_user.name,
                'display_name': discord_user.display_name,
                'discord_user': discord_user,
                'source': 'user_id'
            }
        except (ValueError, discord.NotFound):
            pass
    
    # Method 3: Leaderboard position (#1, #2, etc.)
    if identifier.startswith('#') and identifier[1:].isdigit():
        try:
            position = int(identifier[1:])
            # Get leaderboard for this guild
            from services.database_operations.leaderboard_ops import get_formatted_leaderboard
            leaderboard = await get_formatted_leaderboard(db_service, limit=position, guild_id=guild.id)
            
            if leaderboard and len(leaderboard) >= position:
                entry = leaderboard[position - 1]  # Convert to 0-based index
                user_id = entry.get('user_id')
                if user_id:
                    try:
                        discord_user = await bot.fetch_user(user_id)
                        return {
                            'user_id': user_id,
                            'username': entry.get('username', discord_user.name),
                            'display_name': discord_user.display_name,
                            'discord_user': discord_user,
                            'source': f'leaderboard_position_{position}'
                        }
                    except discord.NotFound:
                        # User not found on Discord, but exists in database
                        return {
                            'user_id': user_id,
                            'username': entry.get('username', 'Unknown'),
                            'display_name': entry.get('username', 'Unknown'),
                            'discord_user': None,
                            'source': f'leaderboard_position_{position}'
                        }
        except (ValueError, Exception) as e:
            logger.debug(f"Error resolving leaderboard position {identifier}: {e}")
    
    # Method 4: Username/display name search in guild members
    guild_members = guild.members
    matches = []
    
    # Exact username matches first
    for member in guild_members:
        if member.name.lower() == identifier.lower():
            matches.append({
                'user_id': member.id,
                'username': member.name,
                'display_name': member.display_name,
                'discord_user': member,
                'source': 'exact_username',
                'match_quality': 100
            })
    
    # Exact display name matches
    for member in guild_members:
        if member.display_name.lower() == identifier.lower():
            matches.append({
                'user_id': member.id,
                'username': member.name,
                'display_name': member.display_name,
                'discord_user': member,
                'source': 'exact_display_name',
                'match_quality': 95
            })
    
    # Partial username matches
    for member in guild_members:
        if identifier.lower() in member.name.lower():
            matches.append({
                'user_id': member.id,
                'username': member.name,
                'display_name': member.display_name,
                'discord_user': member,
                'source': 'partial_username',
                'match_quality': 80
            })
    
    # Partial display name matches
    for member in guild_members:
        if identifier.lower() in member.display_name.lower():
            matches.append({
                'user_id': member.id,
                'username': member.name,
                'display_name': member.display_name,
                'discord_user': member,
                'source': 'partial_display_name',
                'match_quality': 75
            })
    
    # Method 5: Database username search
    try:
        conn = await db_service.get_connection()
        try:
            # Search for users in database with similar usernames
            query = """
            SELECT user_id, username 
            FROM users 
            WHERE LOWER(username) LIKE LOWER(%s)
            ORDER BY 
                CASE 
                    WHEN LOWER(username) = LOWER(%s) THEN 1
                    WHEN LOWER(username) LIKE LOWER(%s) THEN 2
                    ELSE 3
                END
            LIMIT 10
            """
            search_pattern = f"%{identifier}%"
            exact_match = identifier
            starts_with = f"{identifier}%"
            
            results = await conn.fetch(query, search_pattern, exact_match, starts_with)
            
            for row in results:
                user_id = row['user_id']
                username = row['username']
                
                # Try to get Discord user info
                try:
                    discord_user = await bot.fetch_user(user_id)
                    matches.append({
                        'user_id': user_id,
                        'username': username,
                        'display_name': discord_user.display_name,
                        'discord_user': discord_user,
                        'source': 'database_search',
                        'match_quality': 70 if username.lower() == identifier.lower() else 60
                    })
                except discord.NotFound:
                    # User exists in database but not on Discord
                    matches.append({
                        'user_id': user_id,
                        'username': username,
                        'display_name': username,
                        'discord_user': None,
                        'source': 'database_search',
                        'match_quality': 65 if username.lower() == identifier.lower() else 55
                    })
        finally:
            await db_service.release_connection(conn)
    except Exception as e:
        logger.error(f"Error searching database for user '{identifier}': {e}")
    
    # Remove duplicates and sort by match quality
    unique_matches = {}
    for match in matches:
        user_id = match['user_id']
        if user_id not in unique_matches or match['match_quality'] > unique_matches[user_id]['match_quality']:
            unique_matches[user_id] = match
    
    sorted_matches = sorted(unique_matches.values(), key=lambda x: x['match_quality'], reverse=True)
    
    # Return the best match if we have one
    if sorted_matches:
        best_match = sorted_matches[0]
        logger.info(f"Resolved '{identifier}' to user {best_match['user_id']} ({best_match['username']}) via {best_match['source']}")
        return best_match
    
    logger.warning(f"Could not resolve user identifier: '{identifier}'")
    return None


async def search_users(
    db_service: 'DatabaseService',
    guild: discord.Guild,
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for users by various criteria.
    
    Args:
        db_service: Database service instance
        guild: Discord guild context
        query: Search query
        limit: Maximum number of results
        
    Returns:
        List of user dictionaries matching the search
    """
    logger.info(f"Searching users with query: '{query}' in guild {guild.id}")
    
    try:
        conn = await db_service.get_connection()
        try:
            # Multi-criteria search query
            search_query = """
            SELECT DISTINCT u.user_id, u.username, u.quizzes_taken, u.points, u.level,
                   u.correct_answers, u.wrong_answers, u.last_active
            FROM users u
            LEFT JOIN guild_members gm ON u.user_id = gm.user_id AND gm.guild_id = %s
            WHERE (
                LOWER(u.username) LIKE LOWER(%s) OR
                u.user_id::text LIKE %s OR
                u.points::text LIKE %s OR
                u.level::text LIKE %s
            )
            ORDER BY 
                CASE 
                    WHEN LOWER(u.username) = LOWER(%s) THEN 1
                    WHEN LOWER(u.username) LIKE LOWER(%s) THEN 2
                    ELSE 3
                END,
                u.points DESC
            LIMIT %s
            """
            
            search_pattern = f"%{query}%"
            exact_match = query
            starts_with = f"{query}%"
            
            results = await conn.fetch(
                search_query,
                guild.id,
                search_pattern,
                search_pattern,
                search_pattern,
                search_pattern,
                exact_match,
                starts_with,
                limit
            )
            
            users = []
            for row in results:
                users.append({
                    'user_id': row['user_id'],
                    'username': row['username'],
                    'quizzes_taken': row['quizzes_taken'] or 0,
                    'points': row['points'] or 0,
                    'level': row['level'] or 1,
                    'correct_answers': row['correct_answers'] or 0,
                    'wrong_answers': row['wrong_answers'] or 0,
                    'last_active': row['last_active']
                })
            
            logger.info(f"Found {len(users)} users matching query '{query}'")
            return users
            
        finally:
            await db_service.release_connection(conn)
    except Exception as e:
        logger.error(f"Error searching users with query '{query}': {e}")
        return []


async def get_admin_user_info(
    db_service: 'DatabaseService',
    user_id: int,
    guild_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive user information for admin purposes.
    
    Args:
        db_service: Database service instance
        user_id: User ID to get info for
        guild_id: Optional guild ID for guild-specific stats
        
    Returns:
        Comprehensive user information dictionary
    """
    logger.info(f"Getting admin info for user {user_id} in guild {guild_id}")
    
    try:
        conn = await db_service.get_connection()
        try:
            # Get basic user info
            user_query = """
            SELECT user_id, username, discriminator, display_name, avatar_url,
                   quizzes_taken, correct_answers, wrong_answers, skipped_questions,
                   points, level, last_active, created_at, is_banned, ban_reason
            FROM users
            WHERE user_id = %s
            """
            user_info = await conn.fetchrow(user_query, user_id)
            
            if not user_info:
                return None
            
            # Get guild-specific info if guild_id provided
            guild_info = None
            if guild_id:
                guild_query = """
                SELECT guild_xp, guild_level, quiz_count, correct_answers as guild_correct,
                       wrong_answers as guild_wrong, total_points as guild_points,
                       current_streak, best_streak, last_quiz_date, joined_at
                FROM guild_members
                WHERE user_id = %s AND guild_id = %s
                """
                guild_info = await conn.fetchrow(guild_query, user_id, guild_id)
            
            # Get recent quiz sessions
            sessions_query = """
            SELECT quiz_id, topic, difficulty, correct_answers, wrong_answers,
                   skipped_answers, points, created_at
            FROM user_quiz_sessions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
            """
            recent_sessions = await conn.fetch(sessions_query, user_id)
            
            # Get achievements count
            achievements_query = """
            SELECT COUNT(*) as achievement_count
            FROM user_achievements
            WHERE user_id = %s
            """
            achievements_row = await conn.fetchrow(achievements_query, user_id)
            achievement_count = achievements_row['achievement_count'] if achievements_row else 0
            
            # Compile comprehensive info
            info = {
                'user_id': user_info['user_id'],
                'username': user_info['username'],
                'discriminator': user_info['discriminator'],
                'display_name': user_info['display_name'],
                'avatar_url': user_info['avatar_url'],
                'global_stats': {
                    'quizzes_taken': user_info['quizzes_taken'] or 0,
                    'correct_answers': user_info['correct_answers'] or 0,
                    'wrong_answers': user_info['wrong_answers'] or 0,
                    'skipped_questions': user_info['skipped_questions'] or 0,
                    'points': user_info['points'] or 0,
                    'level': user_info['level'] or 1,
                    'achievement_count': achievement_count
                },
                'account_info': {
                    'last_active': user_info['last_active'],
                    'created_at': user_info['created_at'],
                    'is_banned': user_info['is_banned'] or False,
                    'ban_reason': user_info['ban_reason']
                },
                'recent_sessions': [
                    {
                        'quiz_id': session['quiz_id'],
                        'topic': session['topic'],
                        'difficulty': session['difficulty'],
                        'correct': session['correct_answers'] or 0,
                        'wrong': session['wrong_answers'] or 0,
                        'skipped': session['skipped_answers'] or 0,
                        'points': session['points'] or 0,
                        'date': session['created_at']
                    }
                    for session in recent_sessions
                ]
            }
            
            # Add guild-specific info if available
            if guild_info:
                info['guild_stats'] = {
                    'guild_xp': guild_info['guild_xp'] or 0,
                    'guild_level': guild_info['guild_level'] or 1,
                    'quiz_count': guild_info['quiz_count'] or 0,
                    'correct_answers': guild_info['guild_correct'] or 0,
                    'wrong_answers': guild_info['guild_wrong'] or 0,
                    'total_points': guild_info['guild_points'] or 0,
                    'current_streak': guild_info['current_streak'] or 0,
                    'best_streak': guild_info['best_streak'] or 0,
                    'last_quiz_date': guild_info['last_quiz_date'],
                    'joined_at': guild_info['joined_at']
                }
            
            return info
            
        finally:
            await db_service.release_connection(conn)
    except Exception as e:
        logger.error(f"Error getting admin info for user {user_id}: {e}")
        return None


async def reset_user_stats(
    db_service: 'DatabaseService',
    user_id: int,
    guild_id: Optional[int] = None,
    reset_options: Optional[Dict[str, bool]] = None
) -> Dict[str, Any]:
    """
    Reset user statistics with various options.
    
    Args:
        db_service: Database service instance
        user_id: User ID to reset
        guild_id: Optional guild ID for guild-specific reset
        reset_options: Dictionary of reset options:
            - full_reset: Reset everything including account
            - stats_only: Reset only quiz statistics
            - keep_achievements: Preserve achievements
            - keep_history: Preserve quiz history
            - guild_only: Reset only guild-specific stats
            
    Returns:
        Result dictionary with operation status
    """
    if reset_options is None:
        reset_options = {'stats_only': True, 'keep_achievements': True}
    
    logger.info(f"Resetting user {user_id} stats with options: {reset_options}")
    
    result = {
        'success': False,
        'operations': [],
        'errors': [],
        'user_id': user_id
    }
    
    try:
        conn = await db_service.get_connection()
        try:
            # Start transaction
            await conn.execute("BEGIN")
            
            # Reset global user stats
            if not reset_options.get('guild_only', False):
                try:
                    reset_query = """
                    UPDATE users 
                    SET quizzes_taken = 0,
                        correct_answers = 0,
                        wrong_answers = 0,
                        skipped_questions = 0,
                        points = 0,
                        level = 1
                    WHERE user_id = %s
                    """
                    await conn.execute(reset_query, user_id)
                    result['operations'].append('global_stats_reset')
                except Exception as e:
                    result['errors'].append(f"Failed to reset global stats: {str(e)}")
            
            # Reset guild-specific stats if specified
            if guild_id and (reset_options.get('guild_only', False) or reset_options.get('full_reset', False)):
                try:
                    guild_reset_query = """
                    UPDATE guild_members
                    SET guild_xp = 0,
                        guild_level = 1,
                        quiz_count = 0,
                        correct_answers = 0,
                        wrong_answers = 0,
                        total_points = 0,
                        current_streak = 0,
                        best_streak = 0,
                        last_quiz_date = NULL
                    WHERE user_id = %s AND guild_id = %s
                    """
                    await conn.execute(guild_reset_query, user_id, guild_id)
                    result['operations'].append('guild_stats_reset')
                except Exception as e:
                    result['errors'].append(f"Failed to reset guild stats: {str(e)}")
            
            # Delete quiz history if requested
            if not reset_options.get('keep_history', True):
                try:
                    if guild_id:
                        history_query = "DELETE FROM user_quiz_sessions WHERE user_id = %s AND quiz_id LIKE %s"
                        await conn.execute(history_query, user_id, f"%_{guild_id}_%")
                    else:
                        history_query = "DELETE FROM user_quiz_sessions WHERE user_id = %s"
                        await conn.execute(history_query, user_id)
                    result['operations'].append('history_deleted')
                except Exception as e:
                    result['errors'].append(f"Failed to delete history: {str(e)}")
            
            # Delete achievements if requested
            if not reset_options.get('keep_achievements', True):
                try:
                    achievements_query = "DELETE FROM user_achievements WHERE user_id = %s"
                    await conn.execute(achievements_query, user_id)
                    result['operations'].append('achievements_deleted')
                except Exception as e:
                    result['errors'].append(f"Failed to delete achievements: {str(e)}")
            
            # Delete user completely if full reset requested
            if reset_options.get('full_reset', False) and reset_options.get('delete_user', False):
                try:
                    # Delete from all related tables first
                    await conn.execute("DELETE FROM user_achievements WHERE user_id = %s", user_id)
                    await conn.execute("DELETE FROM user_quiz_sessions WHERE user_id = %s", user_id)
                    await conn.execute("DELETE FROM guild_members WHERE user_id = %s", user_id)
                    await conn.execute("DELETE FROM users WHERE user_id = %s", user_id)
                    result['operations'].append('user_deleted')
                except Exception as e:
                    result['errors'].append(f"Failed to delete user: {str(e)}")
            
            # Commit transaction if no errors
            if not result['errors']:
                await conn.execute("COMMIT")
                result['success'] = True
                logger.info(f"Successfully reset user {user_id} with operations: {result['operations']}")
            else:
                await conn.execute("ROLLBACK")
                logger.error(f"Failed to reset user {user_id}, rolled back. Errors: {result['errors']}")
            
        finally:
            await db_service.release_connection(conn)
    except Exception as e:
        logger.error(f"Error resetting user {user_id}: {e}")
        result['errors'].append(f"Database error: {str(e)}")
    
    return result


async def modify_user_field(
    db_service: 'DatabaseService',
    user_id: int,
    field_name: str,
    new_value: Any,
    guild_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Modify a specific user field with validation.
    
    Args:
        db_service: Database service instance
        user_id: User ID to modify
        field_name: Field name to modify
        new_value: New value for the field
        guild_id: Optional guild ID for guild-specific fields
        
    Returns:
        Result dictionary with operation status
    """
    logger.info(f"Modifying user {user_id} field '{field_name}' to '{new_value}'")
    
    # Define valid fields and their constraints
    VALID_GLOBAL_FIELDS = {
        'username': {'type': str, 'max_length': 100},
        'quizzes_taken': {'type': int, 'min': 0, 'max': 1000000},
        'correct_answers': {'type': int, 'min': 0, 'max': 10000000},
        'wrong_answers': {'type': int, 'min': 0, 'max': 10000000},
        'skipped_questions': {'type': int, 'min': 0, 'max': 10000000},
        'points': {'type': int, 'min': 0, 'max': 100000000},
        'level': {'type': int, 'min': 1, 'max': 1000},
        'is_banned': {'type': bool},
        'ban_reason': {'type': str, 'max_length': 500, 'nullable': True}
    }
    
    VALID_GUILD_FIELDS = {
        'guild_xp': {'type': int, 'min': 0, 'max': 100000000},
        'guild_level': {'type': int, 'min': 1, 'max': 1000},
        'quiz_count': {'type': int, 'min': 0, 'max': 1000000},
        'current_streak': {'type': int, 'min': 0, 'max': 10000},
        'best_streak': {'type': int, 'min': 0, 'max': 10000},
        'total_points': {'type': int, 'min': 0, 'max': 100000000}
    }
    
    result = {
        'success': False,
        'field_name': field_name,
        'old_value': None,
        'new_value': new_value,
        'error': None
    }
    
    # Determine if this is a guild field
    is_guild_field = field_name in VALID_GUILD_FIELDS
    is_global_field = field_name in VALID_GLOBAL_FIELDS
    
    if not is_guild_field and not is_global_field:
        result['error'] = f"Invalid field name: {field_name}"
        return result
    
    if is_guild_field and not guild_id:
        result['error'] = f"Guild ID required for guild field: {field_name}"
        return result
    
    # Validate the new value
    field_config = VALID_GUILD_FIELDS.get(field_name) or VALID_GLOBAL_FIELDS.get(field_name)
    
    try:
        # Type validation
        expected_type = field_config['type']
        if expected_type == int:
            new_value = int(new_value)
        elif expected_type == str:
            new_value = str(new_value)
        elif expected_type == bool:
            new_value = str(new_value).lower() in ('true', '1', 'yes', 'on')
        
        # Range validation
        if 'min' in field_config and new_value < field_config['min']:
            result['error'] = f"Value {new_value} is below minimum {field_config['min']}"
            return result
        
        if 'max' in field_config and new_value > field_config['max']:
            result['error'] = f"Value {new_value} is above maximum {field_config['max']}"
            return result
        
        # Length validation for strings
        if expected_type == str and 'max_length' in field_config:
            if len(new_value) > field_config['max_length']:
                result['error'] = f"String too long (max {field_config['max_length']} characters)"
                return result
        
        # Nullable validation
        if new_value is None and not field_config.get('nullable', False):
            result['error'] = f"Field {field_name} cannot be null"
            return result
            
    except (ValueError, TypeError) as e:
        result['error'] = f"Invalid value type: {str(e)}"
        return result
    
    try:
        conn = await db_service.get_connection()
        try:
            # Get current value
            if is_guild_field:
                current_query = f"SELECT {field_name} FROM guild_members WHERE user_id = %s AND guild_id = %s"
                current_row = await conn.fetchrow(current_query, user_id, guild_id)
                if current_row:
                    result['old_value'] = current_row[field_name]
                
                # Update guild field
                update_query = f"UPDATE guild_members SET {field_name} = %s WHERE user_id = %s AND guild_id = %s"
                await conn.execute(update_query, new_value, user_id, guild_id)
                
            else:
                current_query = f"SELECT {field_name} FROM users WHERE user_id = %s"
                current_row = await conn.fetchrow(current_query, user_id)
                if current_row:
                    result['old_value'] = current_row[field_name]
                
                # Update global field
                update_query = f"UPDATE users SET {field_name} = %s WHERE user_id = %s"
                await conn.execute(update_query, new_value, user_id)
            
            result['success'] = True
            result['new_value'] = new_value
            logger.info(f"Successfully modified user {user_id} field {field_name}: {result['old_value']} -> {new_value}")
            
        finally:
            await db_service.release_connection(conn)
    except Exception as e:
        logger.error(f"Error modifying user {user_id} field {field_name}: {e}")
        result['error'] = f"Database error: {str(e)}"
    
    return result


async def delete_user_completely(
    db_service: 'DatabaseService',
    user_id: int,
    guild_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Completely delete a user from the database.
    
    Args:
        db_service: Database service instance
        user_id: User ID to delete
        guild_id: Optional guild ID for guild-only deletion
        
    Returns:
        Result dictionary with operation status
    """
    logger.info(f"Deleting user {user_id} completely (guild_id: {guild_id})")
    
    result = {
        'success': False,
        'deleted_records': {},
        'errors': []
    }
    
    try:
        conn = await db_service.get_connection()
        try:
            await conn.execute("BEGIN")
            
            if guild_id:
                # Guild-specific deletion
                try:
                    # Delete guild membership
                    result_gm = await conn.execute(
                        "DELETE FROM guild_members WHERE user_id = %s AND guild_id = %s",
                        user_id, guild_id
                    )
                    result['deleted_records']['guild_members'] = result_gm
                    
                    # Delete guild-specific quiz sessions (if quiz_id contains guild_id)
                    result_qs = await conn.execute(
                        "DELETE FROM user_quiz_sessions WHERE user_id = %s AND quiz_id LIKE %s",
                        user_id, f"%_{guild_id}_%"
                    )
                    result['deleted_records']['guild_quiz_sessions'] = result_qs
                    
                except Exception as e:
                    result['errors'].append(f"Error deleting guild data: {str(e)}")
            else:
                # Complete deletion
                try:
                    # Delete in dependency order
                    result_ua = await conn.execute("DELETE FROM user_achievements WHERE user_id = %s", user_id)
                    result['deleted_records']['user_achievements'] = result_ua
                    
                    result_uqs = await conn.execute("DELETE FROM user_quiz_sessions WHERE user_id = %s", user_id)
                    result['deleted_records']['user_quiz_sessions'] = result_uqs
                    
                    result_gm = await conn.execute("DELETE FROM guild_members WHERE user_id = %s", user_id)
                    result['deleted_records']['guild_members'] = result_gm
                    
                    result_u = await conn.execute("DELETE FROM users WHERE user_id = %s", user_id)
                    result['deleted_records']['users'] = result_u
                    
                except Exception as e:
                    result['errors'].append(f"Error deleting user data: {str(e)}")
            
            if not result['errors']:
                await conn.execute("COMMIT")
                result['success'] = True
                logger.info(f"Successfully deleted user {user_id} (guild: {guild_id}). Records: {result['deleted_records']}")
            else:
                await conn.execute("ROLLBACK")
                logger.error(f"Failed to delete user {user_id}, rolled back. Errors: {result['errors']}")
            
        finally:
            await db_service.release_connection(conn)
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        result['errors'].append(f"Database error: {str(e)}")
    
    return result