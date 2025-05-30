#!/usr/bin/env python3
"""
Migration script to add version management tables to existing bot database.
Run this script to add version tracking capability to your bot.
"""

import asyncio
import asyncpg
import logging
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'quizbot'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}


async def create_version_tables(conn):
    """Create the version management tables."""
    logger.info("Creating version management tables...")
    
    # Create bot_versions table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_versions (
            id SERIAL PRIMARY KEY,
            version VARCHAR(20) NOT NULL UNIQUE,
            description TEXT NOT NULL,
            release_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_current BOOLEAN DEFAULT FALSE,
            author_id BIGINT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    logger.info("Created bot_versions table")
    
    # Create version_changelog table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS version_changelog (
            id SERIAL PRIMARY KEY,
            version_id INTEGER REFERENCES bot_versions(id),
            change_type VARCHAR(50) NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    logger.info("Created version_changelog table")
    
    # Create indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bot_versions_current ON bot_versions(is_current)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bot_versions_version ON bot_versions(version)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_version_changelog_version_id ON version_changelog(version_id)
    """)
    logger.info("Created indexes")
    
    # Create trigger function
    await conn.execute("""
        CREATE OR REPLACE FUNCTION ensure_single_current_version()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.is_current = TRUE THEN
                UPDATE bot_versions SET is_current = FALSE WHERE id != NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    
    # Create trigger
    await conn.execute("""
        DROP TRIGGER IF EXISTS ensure_single_current_trigger ON bot_versions
    """)
    await conn.execute("""
        CREATE TRIGGER ensure_single_current_trigger
        BEFORE INSERT OR UPDATE ON bot_versions
        FOR EACH ROW
        EXECUTE FUNCTION ensure_single_current_version()
    """)
    logger.info("Created trigger for single current version enforcement")


async def insert_initial_version(conn):
    """Insert initial version if no versions exist."""
    # Check if any versions exist
    result = await conn.fetchval("SELECT COUNT(*) FROM bot_versions")
    
    if result == 0:
        logger.info("No versions found, inserting initial version...")
        await conn.execute("""
            INSERT INTO bot_versions (version, description, is_current)
            VALUES ('1.0.0', 'Initial release of Educational Quiz Bot', TRUE)
        """)
        logger.info("Inserted initial version 1.0.0")
    else:
        logger.info(f"Found {result} existing versions, skipping initial version insert")


async def migrate_version_system():
    """Main migration function."""
    try:
        # Connect to database
        logger.info("Connecting to database...")
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Create tables
            await create_version_tables(conn)
            
            # Insert initial version if needed
            await insert_initial_version(conn)
            
            # Verify migration
            table_count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_name IN ('bot_versions', 'version_changelog')
            """)
            
            if table_count == 2:
                logger.info("✅ Version system migration completed successfully!")
                
                # Show current version
                current_version = await conn.fetchrow("""
                    SELECT version, description
                    FROM bot_versions
                    WHERE is_current = TRUE
                """)
                
                if current_version:
                    logger.info(f"Current version: {current_version['version']} - {current_version['description']}")
            else:
                logger.error("❌ Migration verification failed - tables not created properly")
                
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


def main():
    """Entry point for the migration script."""
    try:
        asyncio.run(migrate_version_system())
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
    except Exception as e:
        logger.error(f"Migration error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())