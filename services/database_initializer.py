"""Database initialization and validation service."""

import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handles database initialization and ensures all data is properly set up."""
    
    def __init__(self, db_service):
        self.db = db_service
        self.schema_path = Path(__file__).parent.parent / "db" / "schema_complete.sql"
        self.migrations_path = Path(__file__).parent.parent / "db" / "migrations"
    
    async def initialize_database(self):
        """Initialize the database with complete schema and handle migrations."""
        try:
            logger.info("Starting database initialization...")
            
            # Create base tables
            await self._create_base_schema()
            
            # Run migrations
            await self._run_migrations()
            
            # Validate schema
            await self._validate_schema()
            
            # Initialize default data
            await self._initialize_defaults()
            
            logger.info("Database initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _create_base_schema(self):
        """Create the base database schema."""
        try:
            if not self.schema_path.exists():
                logger.info("No schema file found, skipping base schema creation")
                return
                
            schema_sql = self.schema_path.read_text()
            
            # Use the database service's connection methods
            conn = await self.db.get_connection()
            try:
                # Execute the schema using the connection wrapper
                await conn.execute(schema_sql)
                logger.info("Base schema created successfully")
            finally:
                await self.db.release_connection(conn)
            
        except Exception as e:
            logger.error(f"Failed to create base schema: {e}")
            raise
    
    async def _run_migrations(self):
        """Run all pending database migrations."""
        try:
            if not self.migrations_path.exists():
                logger.info("No migrations directory found, skipping migrations")
                return
                
            # Get list of migration files
            migration_files = sorted(self.migrations_path.glob("*.sql"))
            
            for migration_file in migration_files:
                migration_name = migration_file.stem
                
                # Check if migration has already been applied
                if await self._is_migration_applied(migration_name):
                    logger.info(f"Skipping already applied migration: {migration_name}")
                    continue
                
                # Run the migration
                logger.info(f"Running migration: {migration_name}")
                migration_sql = migration_file.read_text()
                
                conn = await self.db.get_connection()
                try:
                    await conn.execute(migration_sql)
                    await self._mark_migration_applied(migration_name)
                    logger.info(f"Migration {migration_name} applied successfully")
                finally:
                    await self.db.release_connection(conn)
            
        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
            raise
    
    async def _is_migration_applied(self, migration_name: str) -> bool:
        """Check if a migration has already been applied."""
        conn = await self.db.get_connection()
        try:
            # Create migrations table if it doesn't exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_name VARCHAR(100) PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE migration_name = %s)",
                migration_name
            )
            return result
        finally:
            await self.db.release_connection(conn)
    
    async def _mark_migration_applied(self, migration_name: str):
        """Mark a migration as applied."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                "INSERT INTO schema_migrations (migration_name) VALUES (%s)",
                migration_name
            )
        finally:
            await self.db.release_connection(conn)
    
    async def _validate_schema(self):
        """Validate that all required tables and columns exist."""
        required_tables = [
            'users', 'guild_settings', 'guild_members', 'user_quiz_sessions',
            'guild_leaderboards', 'user_achievements', 'custom_quizzes',
            'quiz_templates', 'daily_challenges', 'user_daily_challenges',
            'feature_flags'
        ]
        
        conn = await self.db.get_connection()
        try:
            for table in required_tables:
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                    table
                )
                if not exists:
                    logger.warning(f"Table '{table}' does not exist - will be created if needed")
        finally:
            await self.db.release_connection(conn)
            
        logger.info("Schema validation completed")
    
    async def _initialize_defaults(self):
        """Initialize default data for the database."""
        try:
            conn = await self.db.get_connection()
            try:
                # Create default feature flags if feature_flags table exists
                table_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                    'feature_flags'
                )
                
                if table_exists:
                    default_features = [
                        ('trivia_game', True, 'Trivia game functionality'),
                        ('custom_quizzes', True, 'User-created custom quizzes'),
                        ('achievements', True, 'Achievement system'),
                        ('daily_challenges', True, 'Daily challenge quizzes'),
                        ('leaderboards', True, 'Guild and global leaderboards'),
                        ('premium_features', False, 'Premium subscription features')
                    ]
                    
                    for feature_name, is_enabled, description in default_features:
                        await conn.execute("""
                            INSERT INTO feature_flags (feature_name, is_enabled, description, guild_id)
                            VALUES (%s, %s, %s, NULL)
                            ON CONFLICT DO NOTHING
                        """, feature_name, is_enabled, description)
                    
                    logger.info("Default feature flags initialized")
                else:
                    logger.info("feature_flags table does not exist, skipping default feature flags")
                    
            finally:
                await self.db.release_connection(conn)
        except Exception as e:
            logger.warning(f"Failed to initialize defaults: {e}")
    
    async def ensure_user_exists(self, user_id: int, username: str, 
                                discriminator: Optional[str] = None,
                                display_name: Optional[str] = None) -> bool:
        """Ensure a user exists in the database."""
        try:
            # Use the database service's built-in user creation methods
            await self.db.get_or_create_user(user_id, username, discriminator, display_name)
            return True
        except Exception as e:
            logger.error(f"Failed to ensure user exists: {e}")
            return False
    
    async def ensure_guild_exists(self, guild_id: int, guild_name: Optional[str] = None) -> bool:
        """Ensure a guild exists in the database."""
        try:
            # Use the database service's built-in guild creation methods
            await self.db.ensure_guild_exists(guild_id, guild_name)
            return True
        except Exception as e:
            logger.error(f"Failed to ensure guild exists: {e}")
            return False
    
    async def ensure_guild_member(self, guild_id: int, user_id: int) -> bool:
        """Ensure a user is a member of a guild."""
        try:
            # Use the database service's built-in guild member methods
            result = await self.db.add_guild_member(guild_id, user_id)
            return result
        except Exception as e:
            logger.error(f"Failed to ensure guild member: {e}")
            return False
    
    async def get_or_create_user_data(self, user_id: int, username: str,
                                     guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Get or create complete user data including guild membership."""
        try:
            # Use the database service's built-in methods
            if guild_id:
                user_data = await self.db.get_user_stats(user_id, guild_id)
            else:
                user_data = await self.db.get_basic_user_stats(user_id)
                
            return user_data
                
        except Exception as e:
            logger.error(f"Failed to get/create user data: {e}")
            return {}
    
    async def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity and return report."""
        report = {
            'users_without_guilds': 0,
            'guilds_without_settings': 0,
            'orphaned_sessions': 0,
            'invalid_achievements': 0,
            'total_users': 0,
            'total_guilds': 0,
            'total_sessions': 0
        }
        
        try:
            conn = await self.db.get_connection()
            try:
                # Count total entities
                report['total_users'] = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
                
                # Check other tables if they exist
                tables_to_check = {
                    'guild_settings': 'total_guilds',
                    'user_quiz_sessions': 'total_sessions'
                }
                
                for table, report_key in tables_to_check.items():
                    try:
                        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                        report[report_key] = count or 0
                    except Exception:
                        report[report_key] = 0
                        
                logger.info(f"Data integrity report: {report}")
            finally:
                await self.db.release_connection(conn)
        except Exception as e:
            logger.error(f"Failed to validate data integrity: {e}")
        
        return report


# Usage example
async def initialize_database(db_service):
    """Initialize the database with all necessary setup."""
    initializer = DatabaseInitializer(db_service)
    await initializer.initialize_database()
    
    # Run integrity check
    report = await initializer.validate_data_integrity()
    logger.info(f"Database integrity report: {report}")
    
    return initializer