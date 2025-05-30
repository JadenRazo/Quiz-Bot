from typing import Dict, List, Optional, Any, Union
import asyncio
import logging
import json
import datetime

logger = logging.getLogger("bot.database.user_stats")

class UserStatsService:
    """Extension for the DatabaseService to handle user statistics and preferences."""
    
    def __init__(self, db_service):
        """
        Initialize the user stats service with a reference to the database service.
        
        Args:
            db_service: The DatabaseService instance to use
        """
        self.db_service = db_service
        self.timestamp_column = "last_seen"  # Default to last_seen since that's what our db has
        
    def set_timestamp_column(self, column_name):
        """Set the timestamp column name to use for users table."""
        logger.info(f"Setting timestamp column to '{column_name}' for UserStatsService")
        self.timestamp_column = column_name
        
    async def get_comprehensive_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Dict containing user stats
        """
        logger.info(f"Attempting to get comprehensive stats for user_id: {user_id}")
        try:
            conn = await self.get_connection()
            try:
                # Get overall stats
                query_overall = """
                SELECT 
                    COUNT(DISTINCT quiz_id) as total_quizzes,
                    SUM(correct_answers) as correct_answers,
                    SUM(wrong_answers) as wrong_answers,
                    SUM(points) as total_points,
                    MAX(points) as highest_score,
                    AVG(points) as average_score,
                    COUNT(DISTINCT category) as categories_played
                FROM user_quiz_sessions
                WHERE user_id = $1
                """
                overall_stats_raw = await conn.fetchrow(query_overall, user_id)
                overall_stats = {} if overall_stats_raw is None else dict(overall_stats_raw)
                logger.debug(f"Overall stats for user {user_id}: {overall_stats}")
                
                # Get stats by difficulty
                query_difficulty = """
                SELECT 
                    difficulty, 
                    COUNT(DISTINCT quiz_id) as quizzes,
                    SUM(correct_answers) as correct,
                    SUM(wrong_answers) as wrong,
                    SUM(points) as points
                FROM user_quiz_sessions
                WHERE user_id = $1
                GROUP BY difficulty
                """
                difficulty_stats_raw = await conn.fetch(query_difficulty, user_id)
                difficulty_stats = [] if difficulty_stats_raw is None else [dict(row) for row in difficulty_stats_raw]
                logger.debug(f"Difficulty stats for user {user_id}: {difficulty_stats}")
                
                # Get stats by category
                query_category = """
                SELECT 
                    category, 
                    COUNT(DISTINCT quiz_id) as quizzes,
                    SUM(correct_answers) as correct,
                    SUM(wrong_answers) as wrong,
                    SUM(points) as points
                FROM user_quiz_sessions
                WHERE user_id = $1
                GROUP BY category
                """
                category_stats_raw = await conn.fetch(query_category, user_id)
                category_stats = [] if category_stats_raw is None else [dict(row) for row in category_stats_raw]
                logger.debug(f"Category stats for user {user_id}: {category_stats}")
                
                # Get recent activity
                query_recent = """
                SELECT 
                    quiz_id,
                    topic,
                    correct_answers,
                    wrong_answers,
                    points,
                    difficulty,
                    created_at
                FROM user_quiz_sessions
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 3
                """
                recent_activity_raw = await conn.fetch(query_recent, user_id)
                recent_activity = [] if recent_activity_raw is None else [dict(row) for row in recent_activity_raw]
                logger.debug(f"Recent activity for user {user_id}: {recent_activity}")
                
                for activity in recent_activity:
                    if 'created_at' in activity and activity['created_at']:
                        activity['created_at'] = activity['created_at'].isoformat() if hasattr(activity['created_at'], 'isoformat') else str(activity['created_at'])
                
                stats = {
                    "user_id": user_id,
                    "overall": overall_stats,
                    "by_difficulty": difficulty_stats,
                    "by_category": category_stats,
                    "recent_activity": recent_activity
                }
                
                total_answers = (overall_stats.get("correct_answers") or 0) + (overall_stats.get("wrong_answers") or 0)
                stats["overall"]["accuracy"] = round(((overall_stats.get("correct_answers") or 0) / total_answers) * 100, 1) if total_answers > 0 else 0.0
                
                logger.info(f"Successfully fetched comprehensive stats for user_id: {user_id}")
                return stats
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting comprehensive user stats for {user_id}: {e}", exc_info=True)
            return {
                "user_id": user_id,
                "overall": {}, "by_difficulty": [], "by_category": [], "recent_activity": []
            }
    
    async def record_user_quiz_session(self, user_id: int, username: str, quiz_id: str, topic: str, 
                              correct: int, wrong: int, points: int, difficulty: str,
                              category: str, guild_id: int = None) -> bool:
        logger.info(f"Recording quiz session for user_id: {user_id}, quiz_id: {quiz_id}, topic: {topic}, "
                    f"correct: {correct}, wrong: {wrong}, points: {points}, difficulty: {difficulty}, category: {category}, guild_id: {guild_id}")
        
        # Validate inputs to prevent recording failed sessions
        if not user_id or not isinstance(user_id, int):
            logger.error(f"Invalid user_id provided: {user_id}")
            return False
            
        if not quiz_id or not isinstance(quiz_id, str):
            logger.error(f"Invalid quiz_id provided for user {user_id}: {quiz_id}")
            return False
            
        # Validate numeric values, converting to integer if needed
        try:
            correct = int(correct)
            wrong = int(wrong)
            points = int(points)
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting numeric values for user {user_id}: {e}")
            correct = correct if isinstance(correct, int) else 0
            wrong = wrong if isinstance(wrong, int) else 0
            points = points if isinstance(points, int) else 0
            logger.warning(f"Using fallback values for user {user_id}: correct={correct}, wrong={wrong}, points={points}")
            
        # Import content normalization utilities
        from utils.content import truncate_content
        
        # Ensure other fields are valid strings with proper length limits
        username = truncate_content(str(username) if username else "Unknown", "username")
        
        # Try to update the username if it's 'Unknown' or 'UnknownUser'
        if username in ["Unknown", "UnknownUser"] and user_id:
            try:
                from discord.ext import commands
                bot = commands.Bot.get_instance()
                if bot:
                    for guild in bot.guilds:
                        member = guild.get_member(user_id)
                        if member:
                            username = truncate_content(member.display_name, "username")
                            logger.info(f"Updated unknown username to actual Discord username: {username} for user ID {user_id}")
                            break
            except Exception as e:
                logger.warning(f"Failed to update username for user {user_id}: {e}")
        
        # Apply content size limits to all fields being stored
        topic = truncate_content(str(topic) if topic else "Unknown", "topic")
        difficulty = truncate_content(str(difficulty) if difficulty else "medium", "category")
        category = truncate_content(str(category) if category else "general", "category")
            
        try:
            conn = await self.get_connection()
            try:
                # Try to verify database connection is working
                try:
                    test_result = await conn.fetchval("SELECT 1")
                    logger.debug(f"Database connection test returned: {test_result}")
                except Exception as test_error:
                    logger.error(f"Database connection test failed: {test_error}", exc_info=True)
                
                # Check what columns exist in the users table
                try:
                    columns_result = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
                    user_columns = [dict(row)['column_name'] for row in columns_result] if columns_result else []
                    logger.debug(f"Detected columns in users table: {user_columns}")
                except Exception as cols_error:
                    logger.error(f"Error checking users table columns: {cols_error}", exc_info=True)
                    user_columns = []
                
                # Determine which column to use for the last_seen/last_active timestamp
                if not hasattr(self, 'timestamp_column') or not self.timestamp_column:
                    # Only detect if not already set
                    last_time_column = "last_active" if "last_active" in user_columns else "last_seen"
                    logger.debug(f"Using '{last_time_column}' column for timestamp")
                    self.timestamp_column = last_time_column
                else:
                    logger.debug(f"Using previously set timestamp column: '{self.timestamp_column}'")
                
                # Insert or update user record
                try:
                    user_query = f"""
                    INSERT INTO users (user_id, username, {self.timestamp_column})
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (user_id) DO UPDATE 
                    SET username = $3, {self.timestamp_column} = NOW()
                    """
                    # For ON CONFLICT with asyncpg, parameters need to be repeated if used in SET
                    await conn.execute(user_query, user_id, username, username) 
                    logger.debug(f"Upserted user record for user_id: {user_id}, username: {username}")
                except Exception as user_error:
                    logger.error(f"Error upserting user record: {user_error}", exc_info=True)
                    return False
                
                # Update user stats before recording quiz session
                try:
                    update_query = """
                    UPDATE users 
                    SET 
                        correct_answers = COALESCE(correct_answers, 0) + $1,
                        wrong_answers = COALESCE(wrong_answers, 0) + $2,
                        points = COALESCE(points, 0) + $3,
                        quizzes_taken = COALESCE(quizzes_taken, 0) + 1
                    WHERE user_id = $4
                    """
                    await conn.execute(update_query, correct, wrong, points, user_id)
                    logger.debug(f"Updated user stats for user_id: {user_id} with correct={correct}, wrong={wrong}, points={points}")
                except Exception as stats_error:
                    logger.error(f"Error updating user stats: {stats_error}", exc_info=True)
                    # Continue even if this fails, try to record session anyway
                
                # Ensure the user_quiz_sessions table exists
                try:
                    create_table_query = """
                    CREATE TABLE IF NOT EXISTS user_quiz_sessions (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        quiz_id VARCHAR(100) NOT NULL,
                        topic VARCHAR(255) NOT NULL,
                        correct_answers INTEGER DEFAULT 0,
                        wrong_answers INTEGER DEFAULT 0,
                        points INTEGER DEFAULT 0,
                        difficulty VARCHAR(50) DEFAULT 'medium',
                        category VARCHAR(100) DEFAULT 'general',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                    await conn.execute(create_table_query)
                    logger.debug("Ensured user_quiz_sessions table exists")
                except Exception as table_error:
                    logger.error(f"Error ensuring user_quiz_sessions table: {table_error}", exc_info=True)
                    return False
                
                # Record quiz session
                try:
                    session_query = """
                    INSERT INTO user_quiz_sessions (
                        user_id, quiz_id, topic, correct_answers, wrong_answers, 
                        points, difficulty, category, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    """
                    await conn.execute(
                        session_query, user_id, quiz_id, topic, correct, wrong, 
                        points, difficulty, category
                    )
                    logger.info(f"Successfully recorded quiz session for user_id: {user_id}, quiz_id: {quiz_id}")
                except Exception as session_error:
                    logger.error(f"Error inserting quiz session: {session_error}", exc_info=True)
                    return False
                
                # Track guild member if guild_id is provided
                if guild_id:
                    try:
                        guild_query = """
                        INSERT INTO guild_members (guild_id, user_id, joined_at)
                        VALUES ($1, $2, NOW())
                        ON CONFLICT (guild_id, user_id) DO NOTHING
                        """
                        await conn.execute(guild_query, guild_id, user_id)
                        logger.debug(f"Added user {user_id} to guild {guild_id} in guild_members table")
                    except Exception as guild_error:
                        logger.error(f"Error adding guild member: {guild_error}", exc_info=True)
                        # Continue since this is not critical
                
                # Update user achievements if needed
                try:
                    await self._update_achievements(conn, user_id)
                except Exception as achieve_error:
                    logger.error(f"Error updating achievements: {achieve_error}", exc_info=True)
                    # Continue since this is not critical
                
                return True
            except Exception as db_error:
                logger.error(f"Database error recording quiz session for user {user_id}, quiz {quiz_id}: {db_error}", exc_info=True)
                return False
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Outer error recording quiz session for user {user_id}, quiz {quiz_id}: {e}", exc_info=True)
            return False
    
    async def _update_achievements(self, conn, user_id: int) -> None:
        logger.info(f"Updating achievements for user_id: {user_id}")
        try:
            # Get user stats
            stats_query = """
            SELECT 
                COUNT(DISTINCT quiz_id) as total_quizzes,
                SUM(correct_answers) as total_correct,
                MAX(points) as highest_score
            FROM user_quiz_sessions
            WHERE user_id = $1
            """
            
            logger.debug(f"Executing achievement stats query for user {user_id}")
            try:
                stats_raw = await conn.fetchrow(stats_query, user_id)
                stats = dict(stats_raw) if stats_raw else {}
                logger.debug(f"Stats for achievement calculation for user {user_id}: {stats}")
            except Exception as stats_error:
                logger.error(f"Error fetching achievement stats for user {user_id}: {stats_error}", exc_info=True)
                return
            
            if not stats:
                logger.info(f"No stats found for user {user_id}, cannot update achievements.")
                return
                
            achievements_to_grant = []
            # Check for quiz count achievements
            if stats.get("total_quizzes", 0) >= 1:
                achievements_to_grant.append("first_quiz")
            if stats.get("total_quizzes", 0) >= 10:
                achievements_to_grant.append("quiz_novice")
            if stats.get("total_quizzes", 0) >= 50:
                achievements_to_grant.append("quiz_enthusiast")
            if stats.get("total_quizzes", 0) >= 100:
                achievements_to_grant.append("quiz_master")
            
            # Check for correct answer achievements
            if stats.get("total_correct", 0) >= 10:
                achievements_to_grant.append("knowledge_beginner")
            if stats.get("total_correct", 0) >= 50:
                achievements_to_grant.append("knowledge_adept")
            if stats.get("total_correct", 0) >= 100:
                achievements_to_grant.append("knowledge_expert")
            if stats.get("total_correct", 0) >= 500:
                achievements_to_grant.append("knowledge_scholar")
            
            # Check for score achievements
            if stats.get("highest_score", 0) >= 10:
                achievements_to_grant.append("score_apprentice")
            if stats.get("highest_score", 0) >= 50:
                achievements_to_grant.append("score_journeyman")
            if stats.get("highest_score", 0) >= 100:
                achievements_to_grant.append("score_virtuoso")

            if not achievements_to_grant:
                logger.info(f"No new achievements to grant for user {user_id}")
                return

            logger.info(f"Attempting to grant achievements for user {user_id}: {achievements_to_grant}")
            
            # Test if user_achievements table exists
            try:
                check_table_query = "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_achievements')"
                table_exists = await conn.fetchval(check_table_query)
                if not table_exists:
                    logger.error(f"user_achievements table does not exist when trying to grant achievements for user {user_id}")
                    try:
                        # Try to create the table
                        create_ach_table = """
                        CREATE TABLE IF NOT EXISTS user_achievements (
                            user_id BIGINT NOT NULL, 
                            achievement VARCHAR(100) NOT NULL, 
                            earned_at TIMESTAMP DEFAULT NOW(), 
                            PRIMARY KEY (user_id, achievement)
                        )
                        """
                        await conn.execute(create_ach_table)
                        logger.info("Successfully created user_achievements table on-the-fly")
                    except Exception as create_err:
                        logger.error(f"Failed to create user_achievements table: {create_err}", exc_info=True)
                        return
            except Exception as check_err:
                logger.error(f"Error checking if user_achievements table exists: {check_err}", exc_info=True)
            
            # Update user achievements
            for achievement_id in achievements_to_grant:
                try:
                    logger.debug(f"Attempting to grant achievement '{achievement_id}' to user {user_id}")
                    ach_query = """
                    INSERT INTO user_achievements (user_id, achievement, earned_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (user_id, achievement) DO NOTHING
                    """
                    await conn.execute(ach_query, user_id, achievement_id)
                    logger.debug(f"Successfully granted achievement '{achievement_id}' to user {user_id}")
                except Exception as ach_error:
                    logger.error(f"Error granting achievement '{achievement_id}' to user {user_id}: {ach_error}", exc_info=True)
            
            logger.info(f"Finished updating achievements for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error updating achievements for {user_id}: {e}", exc_info=True)
    
    async def get_user_achievements(self, user_id: int) -> List[Dict[str, Any]]:
        logger.info(f"Getting achievements for user_id: {user_id}")
        try:
            conn = await self.get_connection()
            try:
                query = """
                SELECT achievement, earned_at
                FROM user_achievements
                WHERE user_id = $1
                ORDER BY earned_at DESC
                """
                rows_raw = await conn.fetch(query, user_id)
                rows = [dict(row) for row in rows_raw] if rows_raw else []
                achievements = []
                for row in rows:
                    achievement_data = self._get_achievement_data(row["achievement"])
                    achievement_data.update({
                        "earned_at": row["earned_at"].isoformat() if row["earned_at"] else None
                    })
                    achievements.append(achievement_data)
                logger.info(f"Found {len(achievements)} achievements for user {user_id}")
                return achievements
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting achievements for {user_id}: {e}", exc_info=True)
            return []
    
    def _get_achievement_data(self, achievement_id: str) -> Dict[str, Any]:
        # This method is synchronous and doesn't do DB calls, so no changes needed here for placeholders
        # Logging could be added if desired, but it's mostly a static data lookup
        achievements = {
            "first_quiz": {"name": "First Steps", "description": "Complete your first quiz", "icon": "🎓"},
            "quiz_novice": {"name": "Quiz Novice", "description": "Complete 10 quizzes", "icon": "📚"},
            "quiz_enthusiast": {"name": "Quiz Enthusiast", "description": "Complete 50 quizzes", "icon": "🧠"},
            "quiz_master": {"name": "Quiz Master", "description": "Complete 100 quizzes", "icon": "👑"},
            "knowledge_beginner": {"name": "Knowledge Beginner", "description": "Answer 10 questions correctly", "icon": "🔍"},
            "knowledge_adept": {"name": "Knowledge Adept", "description": "Answer 50 questions correctly", "icon": "📝"},
            "knowledge_expert": {"name": "Knowledge Expert", "description": "Answer 100 questions correctly", "icon": "🏆"},
            "knowledge_scholar": {"name": "Knowledge Scholar", "description": "Answer 500 questions correctly", "icon": "🎖️"},
            "score_apprentice": {"name": "Score Apprentice", "description": "Earn 10 points in a single quiz", "icon": "⭐"},
            "score_journeyman": {"name": "Score Journeyman", "description": "Earn 50 points in a single quiz", "icon": "🌟"},
            "score_virtuoso": {"name": "Score Virtuoso", "description": "Earn 100 points in a single quiz", "icon": "💫"}
        }
        return achievements.get(achievement_id, {"name": achievement_id.replace("_", " ").title(), "description": "Achievement", "icon": "🏅"})
    
    async def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        logger.info(f"Getting preferences for user_id: {user_id}")
        try:
            conn = await self.get_connection()
            try:
                query = """
                SELECT preferences
                FROM users
                WHERE user_id = $1
                """
                row_raw = await conn.fetchrow(query, user_id)
                row = dict(row_raw) if row_raw else {}
                if row and row.get("preferences"):
                    prefs = json.loads(row["preferences"])
                    logger.info(f"Found preferences for user {user_id}: {prefs}")
                    return prefs
                default_prefs = {"difficulty": "medium", "question_count": 5, "question_type": "multiple_choice", "theme": "default"}
                logger.info(f"No preferences found for user {user_id}, returning defaults: {default_prefs}")
                return default_prefs
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting preferences for {user_id}: {e}", exc_info=True)
            return {} # Return empty dict on error or default? Default seems better.
    
    async def set_user_preferences(self, user_id: int, **preferences) -> bool:
        logger.info(f"Setting preferences for user_id: {user_id} with data: {preferences}")
        try:
            current_prefs = await self.get_user_preferences(user_id) # This already logs
            for key, value in preferences.items():
                if value is not None:
                    current_prefs[key] = value
            
            conn = await self.get_connection()
            try:
                query = """
                INSERT INTO users (user_id, preferences)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE 
                SET preferences = $3
                """
                prefs_json = json.dumps(current_prefs)
                # For ON CONFLICT with asyncpg, parameters need to be repeated if used in SET
                await conn.execute(query, user_id, prefs_json, prefs_json)
                logger.info(f"Successfully set preferences for user {user_id}")
                return True
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Error setting preferences for {user_id}: {e}", exc_info=True)
            return False
    
    async def get_leaderboard(self, guild_id: Optional[int] = None, 
                           category: Optional[str] = None,
                           timeframe: str = "all-time", 
                           limit: int = 10) -> List[Dict[str, Any]]:
        logger.info(f"Getting leaderboard for guild_id: {guild_id}, category: {category}, timeframe: {timeframe}, limit: {limit}")
        try:
            conn = await self.get_connection()
            try:
                params_list = [] # Use a list for asyncpg params
                param_counter = 1

                time_filter_sql = ""
                if timeframe == "weekly": time_filter_sql = "AND s.created_at > NOW() - INTERVAL '7 days'"
                elif timeframe == "monthly": time_filter_sql = "AND s.created_at > NOW() - INTERVAL '30 days'"
                
                category_filter_sql = ""
                if category:
                    category_filter_sql = f"AND s.category = ${param_counter}"
                    params_list.append(category)
                    param_counter += 1
                
                guild_filter_sql = ""
                guild_join_sql = ""
                if guild_id:
                    guild_join_sql = "JOIN guild_members g ON s.user_id = g.user_id"
                    guild_filter_sql = f"AND g.guild_id = ${param_counter}"
                    params_list.append(guild_id)
                    param_counter += 1
                
                limit_placeholder = f"${param_counter}"
                params_list.append(limit) # Limit is always a parameter

                query = f"""
                SELECT 
                    s.user_id, u.username, SUM(s.points) as total_points,
                    COUNT(DISTINCT s.quiz_id) as quizzes_completed,
                    SUM(s.correct_answers) as correct_answers, SUM(s.wrong_answers) as wrong_answers
                FROM user_quiz_sessions s
                JOIN users u ON s.user_id = u.user_id
                {guild_join_sql}
                WHERE 1=1
                {time_filter_sql}
                {category_filter_sql}
                {guild_filter_sql}
                GROUP BY s.user_id, u.username
                ORDER BY total_points DESC
                LIMIT {limit_placeholder}
                """
                
                logger.debug(f"Leaderboard query: {query} with params: {params_list}")
                rows = await conn.fetch(query, *params_list) # Pass params as individual arguments
                
                leaderboard = []
                for i, row_raw in enumerate(rows):
                    row = dict(row_raw)
                    total_answers = row.get("correct_answers", 0) + row.get("wrong_answers", 0)
                    accuracy = round((row.get("correct_answers", 0) / total_answers * 100), 1) if total_answers > 0 else 0
                    leaderboard.append({
                        "rank": i + 1, "user_id": row.get("user_id"), "username": row.get("username"),
                        "points": row.get("total_points", 0), "quizzes": row.get("quizzes_completed", 0),
                        "correct": row.get("correct_answers", 0), "wrong": row.get("wrong_answers", 0),
                        "accuracy": accuracy
                    })
                logger.info(f"Leaderboard generated with {len(leaderboard)} entries.")
                return leaderboard
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}", exc_info=True)
            return []
    
    async def get_user_quiz_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        logger.info(f"Getting quiz history for user_id: {user_id}, limit: {limit}")
        try:
            conn = await self.get_connection()
            try:
                query = """
                SELECT quiz_id, topic, difficulty, category, correct_answers, wrong_answers, points, created_at
                FROM user_quiz_sessions
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """
                rows = await conn.fetch(query, user_id, limit)
                history = []
                for row_raw in rows:
                    row = dict(row_raw)
                    created_at = row.get("created_at")
                    history.append({
                        "quiz_id": row.get("quiz_id", ""), "topic": row.get("topic", "Unknown"),
                        "difficulty": row.get("difficulty", "Unknown"), "category": row.get("category", "General"),
                        "correct": row.get("correct_answers", 0), "wrong": row.get("wrong_answers", 0),
                        "points": row.get("points", 0),
                        "date": created_at.isoformat() if created_at else None
                    })
                logger.info(f"Found {len(history)} quiz history entries for user {user_id}")
                return history
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting quiz history for {user_id}: {e}", exc_info=True)
            return []
    
    async def get_server_analytics(self, guild_id: int) -> Dict[str, Any]:
        logger.info(f"Getting server analytics for guild_id: {guild_id}")
        try:
            if not await self._ensure_tables_exist(): # This already logs
                return {"error": "Database tables not properly initialized"}
                
            conn = await self.get_connection()
            try:
                analytics = {"guild_id": guild_id, "general": {}, "by_difficulty": [], "by_category": [], "usage_over_time": [], "popular_topics": []}
                
                # General usage stats
                gen_query = """
                SELECT 
                    COUNT(DISTINCT s.quiz_id) as total_quizzes, COUNT(DISTINCT s.user_id) as active_users,
                    SUM(s.correct_answers) as total_correct_answers, SUM(s.wrong_answers) as total_wrong_answers,
                    SUM(s.points) as total_points, MIN(s.created_at) as first_quiz_date
                FROM user_quiz_sessions s
                JOIN guild_members g ON s.user_id = g.user_id
                WHERE g.guild_id = $1
                """
                general_stats_raw = await conn.fetchrow(gen_query, guild_id)
                if general_stats_raw: analytics["general"] = dict(general_stats_raw)
                logger.debug(f"General server analytics for guild {guild_id}: {analytics['general']}")

                # Usage by difficulty
                diff_query = """
                SELECT s.difficulty, COUNT(DISTINCT s.quiz_id) as quiz_count
                FROM user_quiz_sessions s JOIN guild_members g ON s.user_id = g.user_id
                WHERE g.guild_id = $1 GROUP BY s.difficulty
                """
                diff_usage_raw = await conn.fetch(diff_query, guild_id)
                if diff_usage_raw: analytics["by_difficulty"] = [dict(row) for row in diff_usage_raw]
                logger.debug(f"Difficulty server analytics for guild {guild_id}: {analytics['by_difficulty']}")

                # Usage by category
                cat_query = """
                SELECT s.category, COUNT(DISTINCT s.quiz_id) as quiz_count
                FROM user_quiz_sessions s JOIN guild_members g ON s.user_id = g.user_id
                WHERE g.guild_id = $1 GROUP BY s.category
                """
                cat_usage_raw = await conn.fetch(cat_query, guild_id)
                if cat_usage_raw: analytics["by_category"] = [dict(row) for row in cat_usage_raw]
                logger.debug(f"Category server analytics for guild {guild_id}: {analytics['by_category']}")

                # Usage over time
                time_query = """
                SELECT DATE_TRUNC('day', s.created_at) as date, COUNT(DISTINCT s.quiz_id) as quiz_count
                FROM user_quiz_sessions s JOIN guild_members g ON s.user_id = g.user_id
                WHERE g.guild_id = $1 AND s.created_at > NOW() - INTERVAL '30 days'
                GROUP BY DATE_TRUNC('day', s.created_at) ORDER BY date
                """
                time_usage_raw = await conn.fetch(time_query, guild_id)
                if time_usage_raw:
                    analytics["usage_over_time"] = [{"date": row.get("date").isoformat() if row.get("date") else None, "count": row.get("quiz_count",0)} for row in time_usage_raw]
                logger.debug(f"Time-based server analytics for guild {guild_id}: {analytics['usage_over_time']}")
                
                # Popular topics
                topic_query = """
                SELECT s.topic, COUNT(DISTINCT s.quiz_id) as quiz_count
                FROM user_quiz_sessions s JOIN guild_members g ON s.user_id = g.user_id
                WHERE g.guild_id = $1 GROUP BY s.topic ORDER BY quiz_count DESC LIMIT 10
                """
                topic_usage_raw = await conn.fetch(topic_query, guild_id)
                if topic_usage_raw: analytics["popular_topics"] = [dict(row) for row in topic_usage_raw]
                logger.debug(f"Popular topics for guild {guild_id}: {analytics['popular_topics']}")

                logger.info(f"Successfully fetched server analytics for guild_id: {guild_id}")
                return analytics
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Error getting server analytics for {guild_id}: {e}", exc_info=True)
            return {"error": str(e)}
            
    async def _ensure_tables_exist(self) -> bool:
        logger.info("Ensuring core stats tables exist.")
        try:
            conn = await self.get_connection()
            try:
                # Check if tables exist
                logger.debug("Checking if core tables exist...")
                check_queries = [
                    ("guild_members", "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'guild_members')"),
                    ("user_quiz_sessions", "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_quiz_sessions')"),
                    ("users", "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')"),
                    ("user_achievements", "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_achievements')")
                ]
                
                tables_missing = False
                for table_name, query in check_queries:
                    try:
                        result_raw = await conn.fetchrow(query)
                        result = dict(result_raw) if result_raw else {}
                        if not result or not result.get('exists', False):
                            logger.warning(f"Table '{table_name}' does not exist and needs to be created")
                            tables_missing = True
                        else:
                            logger.debug(f"Table '{table_name}' already exists")
                    except Exception as check_error:
                        logger.error(f"Error checking if table '{table_name}' exists: {check_error}", exc_info=True)
                        tables_missing = True
                
                if tables_missing:
                    logger.info("Creating missing tables...")
                    
                    # Create guild_members table
                    try:
                        logger.debug("Creating 'guild_members' table...")
                        create_guild_members = """
                        CREATE TABLE IF NOT EXISTS guild_members (
                            user_id BIGINT NOT NULL, 
                            guild_id BIGINT NOT NULL, 
                            joined_at TIMESTAMP DEFAULT NOW(), 
                            PRIMARY KEY (user_id, guild_id)
                        )
                        """
                        await conn.execute(create_guild_members)
                        logger.info("Successfully created 'guild_members' table")
                    except Exception as e_guild:
                        logger.error(f"Error creating 'guild_members' table: {e_guild}", exc_info=True)
                        return False
                    
                    # Create user_quiz_sessions table
                    try:
                        logger.debug("Creating 'user_quiz_sessions' table...")
                        create_quiz_sessions = """
                        CREATE TABLE IF NOT EXISTS user_quiz_sessions (
                            id SERIAL PRIMARY KEY, 
                            user_id BIGINT NOT NULL, 
                            quiz_id VARCHAR(36) NOT NULL,
                            topic VARCHAR(255) NOT NULL, 
                            correct_answers INT DEFAULT 0, 
                            wrong_answers INT DEFAULT 0,
                            points INT DEFAULT 0, 
                            difficulty VARCHAR(50) DEFAULT 'medium', 
                            category VARCHAR(100) DEFAULT 'general',
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                        """
                        await conn.execute(create_quiz_sessions)
                        logger.info("Successfully created 'user_quiz_sessions' table")
                    except Exception as e_sessions:
                        logger.error(f"Error creating 'user_quiz_sessions' table: {e_sessions}", exc_info=True)
                        return False
                    
                    # Create users table
                    try:
                        logger.debug("Creating 'users' table...")
                        create_users = """
                        CREATE TABLE IF NOT EXISTS users (
                            user_id BIGINT PRIMARY KEY, 
                            username VARCHAR(100) NOT NULL,
                            last_seen TIMESTAMP DEFAULT NOW(), 
                            preferences JSONB DEFAULT '{}'::jsonb
                        )
                        """
                        await conn.execute(create_users)
                        logger.info("Successfully created 'users' table")
                    except Exception as e_users:
                        logger.error(f"Error creating 'users' table: {e_users}", exc_info=True)
                        return False
                    
                    # Create user_achievements table
                    try:
                        logger.debug("Creating 'user_achievements' table...")
                        create_achievements = """
                        CREATE TABLE IF NOT EXISTS user_achievements (
                            user_id BIGINT NOT NULL, 
                            achievement VARCHAR(100) NOT NULL, 
                            earned_at TIMESTAMP DEFAULT NOW(), 
                            PRIMARY KEY (user_id, achievement)
                        )
                        """
                        await conn.execute(create_achievements)
                        logger.info("Successfully created 'user_achievements' table")
                    except Exception as e_achievements:
                        logger.error(f"Error creating 'user_achievements' table: {e_achievements}", exc_info=True)
                        return False
                    
                    logger.info("All required tables have been created successfully")
                else:
                    logger.info("All required tables already exist, no need to create them")
                    
                return True
            finally:
                await self.release_connection(conn)
        except Exception as e:
            logger.error(f"Error ensuring tables exist: {e}", exc_info=True)
            return False
    
    async def get_connection(self):
        # ... (no changes to method signature, but internal logging can be added) ...
        # logger.debug("Acquiring database connection via db_service")
        if not self.db_service:
            logger.error("Database service is not initialized in UserStatsService") # More specific log
            raise ValueError("Database service is not initialized")
        try:
            if not hasattr(self.db_service, 'get_connection'):
                logger.error("Database service does not have a get_connection method")
                raise ValueError("Database service missing required method: get_connection")
            return await self.db_service.get_connection()
        except Exception as e:
            logger.error(f"Error getting database connection from db_service: {e}", exc_info=True)
            raise
    
    async def release_connection(self, conn):
        # logger.debug("Releasing database connection via db_service")
        if not self.db_service:
            logger.error("Database service is not initialized in UserStatsService") # More specific log
            raise ValueError("Database service is not initialized")
        try:
            if not hasattr(self.db_service, 'release_connection'):
                logger.error("Database service does not have a release_connection method")
                raise ValueError("Database service missing required method: release_connection")
            await self.db_service.release_connection(conn)
        except Exception as e:
            logger.error(f"Error releasing database connection via db_service: {e}", exc_info=True)
            # Don't re-raise from release typically 