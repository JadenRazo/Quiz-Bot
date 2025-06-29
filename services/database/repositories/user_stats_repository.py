"""User statistics repository implementation."""

from datetime import datetime
from typing import Dict, List, Optional, Union

import asyncpg

from ..base_gateway import BaseGateway
from ..exceptions import EntityNotFoundError, ValidationError
from ..models import UserStats


class UserStatsRepository(BaseGateway):
    """Repository for user statistics operations."""
    
    async def get_user_stats(self, user_id: int, guild_id: int) -> Optional[UserStats]:
        """
        Get user statistics for a specific guild.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            UserStats model or None if not found
            
        Raises:
            DatabaseError: If query execution fails
        """
        query = """
            SELECT user_id, guild_id, total_quizzes, total_correct, total_wrong,
                   total_points, level, experience, streak, best_streak,
                   favorite_topic, last_quiz_date, created_at, updated_at
            FROM user_stats 
            WHERE user_id = $1 AND guild_id = $2
        """
        
        record = await self._fetchrow(query, user_id, guild_id)
        if record is None:
            return None
            
        return UserStats.model_validate(dict(record))
    
    async def get_user_stats_required(self, user_id: int, guild_id: int) -> UserStats:
        """
        Get user statistics for a specific guild, raising exception if not found.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            UserStats model
            
        Raises:
            EntityNotFoundError: If user stats not found
            DatabaseError: If query execution fails
        """
        stats = await self.get_user_stats(user_id, guild_id)
        if stats is None:
            raise EntityNotFoundError("UserStats", f"{user_id}:{guild_id}", "user_id:guild_id")
        return stats
    
    async def create_user_stats(self, user_id: int, guild_id: int, **kwargs) -> UserStats:
        """
        Create new user statistics record.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            **kwargs: Optional initial values for stats fields
            
        Returns:
            Created UserStats model
            
        Raises:
            DuplicateEntityError: If user stats already exist
            DatabaseError: If creation fails
        """
        # Set default values
        defaults = {
            'total_quizzes': 0,
            'total_correct': 0,
            'total_wrong': 0,
            'total_points': 0,
            'level': 1,
            'experience': 0,
            'streak': 0,
            'best_streak': 0,
            'favorite_topic': None,
            'last_quiz_date': None,
            'created_at': datetime.utcnow(),
            'updated_at': None
        }
        
        # Override with provided values
        defaults.update(kwargs)
        
        query = """
            INSERT INTO user_stats (
                user_id, guild_id, total_quizzes, total_correct, total_wrong,
                total_points, level, experience, streak, best_streak,
                favorite_topic, last_quiz_date, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING user_id, guild_id, total_quizzes, total_correct, total_wrong,
                      total_points, level, experience, streak, best_streak,
                      favorite_topic, last_quiz_date, created_at, updated_at
        """
        
        record = await self._fetchrow(
            query,
            user_id, guild_id,
            defaults['total_quizzes'], defaults['total_correct'], defaults['total_wrong'],
            defaults['total_points'], defaults['level'], defaults['experience'],
            defaults['streak'], defaults['best_streak'], defaults['favorite_topic'],
            defaults['last_quiz_date'], defaults['created_at'], defaults['updated_at']
        )
        
        if record is None:
            raise ValidationError("user_stats", f"{user_id}:{guild_id}", "Failed to create record")
            
        return UserStats.model_validate(dict(record))
    
    async def get_or_create_user_stats(self, user_id: int, guild_id: int, **kwargs) -> UserStats:
        """
        Get existing user stats or create new ones if they don't exist.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            **kwargs: Optional initial values for new stats
            
        Returns:
            UserStats model (existing or newly created)
            
        Raises:
            DatabaseError: If query execution fails
        """
        stats = await self.get_user_stats(user_id, guild_id)
        if stats is not None:
            return stats
            
        return await self.create_user_stats(user_id, guild_id, **kwargs)
    
    async def update_quiz_completion(
        self,
        user_id: int,
        guild_id: int,
        correct_answers: int,
        wrong_answers: int,
        points_earned: int,
        topic: str
    ) -> UserStats:
        """
        Update user statistics after quiz completion.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            correct_answers: Number of correct answers in this quiz
            wrong_answers: Number of wrong answers in this quiz
            points_earned: Points earned in this quiz
            topic: Quiz topic (for favorite topic tracking)
            
        Returns:
            Updated UserStats model
            
        Raises:
            EntityNotFoundError: If user stats not found
            DatabaseError: If update fails
        """
        now = datetime.utcnow()
        
        # Calculate new streak
        new_streak = 0
        if wrong_answers == 0:  # Perfect quiz extends streak
            current_stats = await self.get_user_stats(user_id, guild_id)
            if current_stats:
                new_streak = current_stats.streak + correct_answers
        
        query = """
            UPDATE user_stats SET
                total_quizzes = total_quizzes + 1,
                total_correct = total_correct + $3,
                total_wrong = total_wrong + $4,
                total_points = total_points + $5,
                experience = experience + $5,
                streak = $6,
                best_streak = GREATEST(best_streak, $6),
                last_quiz_date = $7,
                updated_at = $7
            WHERE user_id = $1 AND guild_id = $2
            RETURNING user_id, guild_id, total_quizzes, total_correct, total_wrong,
                      total_points, level, experience, streak, best_streak,
                      favorite_topic, last_quiz_date, created_at, updated_at
        """
        
        record = await self._fetchrow(
            query, user_id, guild_id, correct_answers, wrong_answers,
            points_earned, new_streak, now
        )
        
        if record is None:
            raise EntityNotFoundError("UserStats", f"{user_id}:{guild_id}", "user_id:guild_id")
        
        # Update level based on experience
        updated_stats = UserStats.model_validate(dict(record))
        new_level = self._calculate_level(updated_stats.experience)
        
        if new_level != updated_stats.level:
            updated_stats = await self._update_level(user_id, guild_id, new_level)
        
        # Update favorite topic if necessary
        await self._update_favorite_topic(user_id, guild_id, topic)
        
        return updated_stats
    
    async def update_level(self, user_id: int, guild_id: int, new_level: int) -> UserStats:
        """
        Update user level.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            new_level: New level value
            
        Returns:
            Updated UserStats model
            
        Raises:
            EntityNotFoundError: If user stats not found
            ValidationError: If level is invalid
        """
        if new_level < 1:
            raise ValidationError("level", new_level, "Level must be at least 1")
        
        return await self._update_level(user_id, guild_id, new_level)
    
    async def reset_streak(self, user_id: int, guild_id: int) -> UserStats:
        """
        Reset user's current streak to 0.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            Updated UserStats model
            
        Raises:
            EntityNotFoundError: If user stats not found
        """
        query = """
            UPDATE user_stats SET
                streak = 0,
                updated_at = $3
            WHERE user_id = $1 AND guild_id = $2
            RETURNING user_id, guild_id, total_quizzes, total_correct, total_wrong,
                      total_points, level, experience, streak, best_streak,
                      favorite_topic, last_quiz_date, created_at, updated_at
        """
        
        record = await self._fetchrow(query, user_id, guild_id, datetime.utcnow())
        
        if record is None:
            raise EntityNotFoundError("UserStats", f"{user_id}:{guild_id}", "user_id:guild_id")
            
        return UserStats.model_validate(dict(record))
    
    async def get_leaderboard(
        self,
        guild_id: int,
        limit: int = 10,
        order_by: str = "total_points"
    ) -> List[UserStats]:
        """
        Get leaderboard for a guild.
        
        Args:
            guild_id: Discord guild ID
            limit: Maximum number of entries to return
            order_by: Field to order by (total_points, total_correct, level, experience)
            
        Returns:
            List of UserStats models ordered by specified field
            
        Raises:
            ValidationError: If order_by field is invalid
            DatabaseError: If query execution fails
        """
        valid_order_fields = {"total_points", "total_correct", "level", "experience", "accuracy"}
        if order_by not in valid_order_fields:
            raise ValidationError("order_by", order_by, f"Must be one of: {', '.join(valid_order_fields)}")
        
        # Special handling for accuracy since it's a calculated field
        if order_by == "accuracy":
            order_clause = """
                CASE 
                    WHEN total_correct + total_wrong > 0 
                    THEN total_correct::numeric / (total_correct + total_wrong)
                    ELSE 0
                END DESC
            """
        else:
            order_clause = f"{order_by} DESC"
        
        query = f"""
            SELECT user_id, guild_id, total_quizzes, total_correct, total_wrong,
                   total_points, level, experience, streak, best_streak,
                   favorite_topic, last_quiz_date, created_at, updated_at
            FROM user_stats 
            WHERE guild_id = $1 AND total_quizzes > 0
            ORDER BY {order_clause}
            LIMIT $2
        """
        
        records = await self._fetch(query, guild_id, limit)
        return [UserStats.model_validate(dict(record)) for record in records]
    
    async def get_user_rank(self, user_id: int, guild_id: int, order_by: str = "total_points") -> Optional[int]:
        """
        Get user's rank in guild leaderboard.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            order_by: Field to rank by
            
        Returns:
            User's rank (1-based) or None if user not found in rankings
            
        Raises:
            ValidationError: If order_by field is invalid
        """
        valid_order_fields = {"total_points", "total_correct", "level", "experience", "accuracy"}
        if order_by not in valid_order_fields:
            raise ValidationError("order_by", order_by, f"Must be one of: {', '.join(valid_order_fields)}")
        
        # Special handling for accuracy
        if order_by == "accuracy":
            comparison = """
                CASE 
                    WHEN total_correct + total_wrong > 0 
                    THEN total_correct::numeric / (total_correct + total_wrong)
                    ELSE 0
                END
            """
        else:
            comparison = order_by
        
        query = f"""
            WITH ranked_users AS (
                SELECT user_id,
                       ROW_NUMBER() OVER (ORDER BY {comparison} DESC) as rank
                FROM user_stats 
                WHERE guild_id = $1 AND total_quizzes > 0
            )
            SELECT rank FROM ranked_users WHERE user_id = $2
        """
        
        return await self._fetchval(query, guild_id, user_id)
    
    # Private helper methods
    
    def _calculate_level(self, experience: int) -> int:
        """
        Calculate level based on experience points.
        
        Level formula: level = floor(sqrt(experience / 100)) + 1
        This gives a reasonable progression curve.
        """
        import math
        if experience < 0:
            return 1
        return int(math.sqrt(experience / 100)) + 1
    
    async def _update_level(self, user_id: int, guild_id: int, new_level: int) -> UserStats:
        """Update user level in database."""
        query = """
            UPDATE user_stats SET
                level = $3,
                updated_at = $4
            WHERE user_id = $1 AND guild_id = $2
            RETURNING user_id, guild_id, total_quizzes, total_correct, total_wrong,
                      total_points, level, experience, streak, best_streak,
                      favorite_topic, last_quiz_date, created_at, updated_at
        """
        
        record = await self._fetchrow(query, user_id, guild_id, new_level, datetime.utcnow())
        
        if record is None:
            raise EntityNotFoundError("UserStats", f"{user_id}:{guild_id}", "user_id:guild_id")
            
        return UserStats.model_validate(dict(record))
    
    async def _update_favorite_topic(self, user_id: int, guild_id: int, topic: str) -> None:
        """Update favorite topic based on most played topic."""
        # Get the most played topic for this user
        query = """
            SELECT topic, COUNT(*) as play_count
            FROM quiz_history 
            WHERE user_id = $1 AND guild_id = $2
            GROUP BY topic
            ORDER BY play_count DESC, topic
            LIMIT 1
        """
        
        record = await self._fetchrow(query, user_id, guild_id)
        if record is None:
            return
        
        favorite_topic = record['topic']
        
        # Update the favorite topic
        update_query = """
            UPDATE user_stats SET
                favorite_topic = $3,
                updated_at = $4
            WHERE user_id = $1 AND guild_id = $2
        """
        
        await self._execute(query, user_id, guild_id, favorite_topic, datetime.utcnow())