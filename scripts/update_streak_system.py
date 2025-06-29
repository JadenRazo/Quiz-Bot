#!/usr/bin/env python3
"""
Migration script to initialize and backfill the streak tracking system.
This script ensures streak columns exist and populates them with historical data.
"""

import asyncio
import asyncpg
import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv
from datetime import datetime, date

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database configuration - CRITICAL: Use IP address, not localhost
DB_CONFIG: Dict[str, Any] = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'quizbot'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}


async def ensure_streak_columns(conn: asyncpg.Connection) -> None:
    """Ensure guild_members table has streak tracking columns."""
    logger.info("Ensuring streak columns exist in guild_members table...")
    
    # Add streak columns if they don't exist
    await conn.execute("""
        ALTER TABLE guild_members 
        ADD COLUMN IF NOT EXISTS current_streak INTEGER DEFAULT 0
    """)
    
    await conn.execute("""
        ALTER TABLE guild_members 
        ADD COLUMN IF NOT EXISTS best_streak INTEGER DEFAULT 0
    """)
    
    await conn.execute("""
        ALTER TABLE guild_members 
        ADD COLUMN IF NOT EXISTS last_quiz_date DATE
    """)
    
    logger.info("Streak columns verified/created in guild_members table")


async def backfill_streak_data(conn: asyncpg.Connection) -> None:
    """Backfill streak data from historical quiz sessions."""
    logger.info("Starting streak data backfill from quiz history...")
    
    # First, ensure is_perfect column exists
    logger.info("Adding is_perfect column if it doesn't exist...")
    await conn.execute("""
        ALTER TABLE user_quiz_sessions 
        ADD COLUMN IF NOT EXISTS is_perfect BOOLEAN
    """)
    
    # Then, ensure is_perfect column is populated correctly
    logger.info("Updating is_perfect flags for existing quiz sessions...")
    await conn.execute("""
        UPDATE user_quiz_sessions
        SET is_perfect = TRUE
        WHERE wrong_answers = 0 
          AND skipped_answers = 0 
          AND correct_answers > 0
          AND (is_perfect IS NULL OR is_perfect = FALSE)
    """)
    
    await conn.execute("""
        UPDATE user_quiz_sessions
        SET is_perfect = FALSE
        WHERE (wrong_answers > 0 OR correct_answers = 0)
          AND (is_perfect IS NULL OR is_perfect = TRUE)
    """)
    
    # Get all guild-user combinations that need streak calculation
    logger.info("Fetching guild-user combinations for streak calculation...")
    guild_users = await conn.fetch("""
        SELECT DISTINCT guild_id, user_id
        FROM user_quiz_sessions
        WHERE guild_id IS NOT NULL
        ORDER BY guild_id, user_id
    """)
    
    logger.info(f"Found {len(guild_users)} guild-user combinations to process")
    
    processed = 0
    for row in guild_users:
        guild_id = row['guild_id']
        user_id = row['user_id']
        
        # Get quiz history for this user in this guild, ordered by date
        quiz_history = await conn.fetch("""
            SELECT 
                DATE(created_at) as quiz_date,
                is_perfect,
                quiz_id
            FROM user_quiz_sessions
            WHERE user_id = $1 
              AND guild_id = $2
            ORDER BY created_at ASC
        """, user_id, guild_id)
        
        if not quiz_history:
            continue
            
        # Calculate streaks
        current_streak = 0
        best_streak = 0
        last_perfect_date = None
        temp_streak = 0
        
        for quiz in quiz_history:
            quiz_date = quiz['quiz_date']
            is_perfect = quiz.get('is_perfect', False)
            
            if is_perfect:
                # Check if this continues a streak (same day or consecutive day)
                if last_perfect_date is None:
                    # First perfect quiz
                    temp_streak = 1
                elif quiz_date == last_perfect_date:
                    # Same day, don't increment streak
                    pass
                elif (quiz_date - last_perfect_date).days == 1:
                    # Consecutive day, increment streak
                    temp_streak += 1
                else:
                    # Gap in days, reset streak
                    temp_streak = 1
                
                last_perfect_date = quiz_date
                best_streak = max(best_streak, temp_streak)
                current_streak = temp_streak
            else:
                # Non-perfect quiz breaks the streak
                temp_streak = 0
                current_streak = 0
        
        # Update guild_members with calculated streaks
        await conn.execute("""
            INSERT INTO guild_members (guild_id, user_id, current_streak, best_streak, last_quiz_date)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                current_streak = EXCLUDED.current_streak,
                best_streak = GREATEST(guild_members.best_streak, EXCLUDED.best_streak),
                last_quiz_date = EXCLUDED.last_quiz_date
        """, guild_id, user_id, current_streak, best_streak, 
            quiz_history[-1]['quiz_date'] if quiz_history else None)
        
        processed += 1
        if processed % 100 == 0:
            logger.info(f"Processed {processed}/{len(guild_users)} guild-user combinations...")
    
    logger.info(f"Completed streak backfill for {processed} guild-user combinations")


async def create_streak_update_function(conn: asyncpg.Connection) -> None:
    """Create a PL/pgSQL function to update streaks when a quiz is completed."""
    logger.info("Creating streak update function...")
    
    await conn.execute("""
        CREATE OR REPLACE FUNCTION update_user_streak(
            p_user_id BIGINT,
            p_guild_id BIGINT,
            p_is_perfect BOOLEAN,
            p_quiz_date DATE
        ) RETURNS VOID AS $$
        DECLARE
            v_last_quiz_date DATE;
            v_current_streak INTEGER;
            v_best_streak INTEGER;
        BEGIN
            -- Get current streak info
            SELECT last_quiz_date, current_streak, best_streak
            INTO v_last_quiz_date, v_current_streak, v_best_streak
            FROM guild_members
            WHERE user_id = p_user_id AND guild_id = p_guild_id;
            
            -- If no record exists, initialize
            IF NOT FOUND THEN
                v_current_streak := 0;
                v_best_streak := 0;
                v_last_quiz_date := NULL;
            END IF;
            
            -- Update streak based on quiz result
            IF p_is_perfect THEN
                -- Perfect quiz
                IF v_last_quiz_date IS NULL OR p_quiz_date > v_last_quiz_date THEN
                    -- First quiz or new day
                    IF v_last_quiz_date IS NULL OR (p_quiz_date - v_last_quiz_date) > 1 THEN
                        -- First quiz or gap in days, reset to 1
                        v_current_streak := 1;
                    ELSIF (p_quiz_date - v_last_quiz_date) = 1 THEN
                        -- Consecutive day, increment
                        v_current_streak := v_current_streak + 1;
                    END IF;
                    -- Same day quizzes don't change streak
                END IF;
                
                -- Update best streak if needed
                v_best_streak := GREATEST(v_best_streak, v_current_streak);
            ELSE
                -- Non-perfect quiz breaks the streak
                v_current_streak := 0;
            END IF;
            
            -- Update or insert guild_members record
            INSERT INTO guild_members (guild_id, user_id, current_streak, best_streak, last_quiz_date)
            VALUES (p_guild_id, p_user_id, v_current_streak, v_best_streak, p_quiz_date)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                current_streak = EXCLUDED.current_streak,
                best_streak = EXCLUDED.best_streak,
                last_quiz_date = EXCLUDED.last_quiz_date;
                
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    logger.info("Streak update function created successfully")


async def add_streak_indexes(conn: asyncpg.Connection) -> None:
    """Add indexes for efficient streak queries."""
    logger.info("Adding indexes for streak queries...")
    
    # Index for leaderboard queries with streaks
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_guild_members_streak 
        ON guild_members(guild_id, current_streak DESC, total_points DESC)
    """)
    
    # Index for finding users with active streaks
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_guild_members_active_streak 
        ON guild_members(current_streak) 
        WHERE current_streak > 0
    """)
    
    logger.info("Streak indexes created successfully")


async def main():
    """Main migration function."""
    logger.info("Starting streak system migration...")
    logger.info(f"Connecting to database at {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(**DB_CONFIG)
        logger.info("Successfully connected to database")
        
        try:
            # Run migration steps
            await ensure_streak_columns(conn)
            await backfill_streak_data(conn)
            await create_streak_update_function(conn)
            await add_streak_indexes(conn)
            
            # Verify the migration
            streak_count = await conn.fetchval("""
                SELECT COUNT(*) FROM guild_members WHERE current_streak > 0
            """)
            
            best_streak = await conn.fetchrow("""
                SELECT user_id, guild_id, best_streak 
                FROM guild_members 
                ORDER BY best_streak DESC 
                LIMIT 1
            """)
            
            logger.info(f"Migration completed successfully!")
            logger.info(f"Users with active streaks: {streak_count}")
            if best_streak:
                logger.info(f"Highest streak: {best_streak['best_streak']} "
                          f"(User: {best_streak['user_id']}, Guild: {best_streak['guild_id']})")
            
        finally:
            await conn.close()
            logger.info("Database connection closed")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())