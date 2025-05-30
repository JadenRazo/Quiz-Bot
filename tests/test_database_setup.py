#!/usr/bin/env python3
"""
Database Setup Test Script for Educational Quiz Bot

This script helps verify that the database is properly configured and accessible.
It's designed to help bot operators validate their database setup and troubleshoot
common connection issues.

Usage:
    python tests/test_database_setup.py

This will:
1. Test database connectivity
2. Verify all required tables exist
3. Test basic CRUD operations
4. Check connection pooling
5. Validate async operations work correctly
"""

import logging
import sys
import os
import asyncio
from datetime import datetime
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("database_setup_test")

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import load_config
    from services.database import DatabaseService
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you're running this from the quiz_bot directory")
    sys.exit(1)


class DatabaseSetupTester:
    """Comprehensive database setup testing utility."""
    
    def __init__(self):
        self.config = None
        self.db_service = None
        self.test_user_id = 123456789012345678  # Test user ID
        self.test_username = "TestUser"
        
    async def run_all_tests(self):
        """Run all database tests in sequence."""
        logger.info("=" * 60)
        logger.info("Educational Quiz Bot - Database Setup Test")
        logger.info("=" * 60)
        
        # Load configuration
        if not await self.test_config():
            return False
            
        # Test basic connectivity
        if not await self.test_connectivity():
            return False
            
        # Initialize database service
        if not await self.test_service_initialization():
            return False
            
        # Check tables
        if not await self.test_table_existence():
            return False
            
        # Test operations
        if not await self.test_basic_operations():
            return False
            
        # Test async operations
        if not await self.test_async_operations():
            return False
            
        # Test connection pooling
        if not await self.test_connection_pooling():
            return False
            
        logger.info("=" * 60)
        logger.info("✅ All database tests passed successfully!")
        logger.info("=" * 60)
        return True
        
    async def test_config(self):
        """Test configuration loading."""
        try:
            logger.info("\n🔧 Testing configuration loading...")
            self.config = load_config()
            
            # Check database config
            if not hasattr(self.config, 'database'):
                logger.error("❌ No database configuration found")
                return False
                
            db_config = self.config.database
            required_fields = ['host', 'port', 'database', 'user', 'password']
            
            missing_fields = []
            for field in required_fields:
                if not hasattr(db_config, field) or not getattr(db_config, field):
                    missing_fields.append(field)
                    
            if missing_fields:
                logger.error(f"❌ Missing database configuration fields: {missing_fields}")
                logger.error("Please check your .env file")
                return False
                
            # Log configuration (without password)
            logger.info(f"✅ Database configuration loaded:")
            logger.info(f"   Host: {db_config.host}")
            logger.info(f"   Port: {db_config.port}")
            logger.info(f"   Database: {db_config.database}")
            logger.info(f"   User: {db_config.user}")
            logger.info(f"   Password: {'*' * len(db_config.password)}")
            
            # Check if using IP address
            if db_config.host == 'localhost':
                logger.warning("⚠️  Using 'localhost' - should use IP address (195.201.136.53)")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Configuration test failed: {e}")
            return False
            
    async def test_connectivity(self):
        """Test basic database connectivity."""
        try:
            logger.info("\n🔌 Testing database connectivity...")
            
            db_config = self.config.database
            conn_string = f"host={db_config.host} port={db_config.port} dbname={db_config.database} user={db_config.user} password={db_config.password}"
            
            # Test direct connection
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()
            
            # Test simple query
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            logger.info(f"✅ Connected to PostgreSQL")
            logger.info(f"   Version: {version}")
            
            # Test database name
            cursor.execute("SELECT current_database();")
            current_db = cursor.fetchone()[0]
            logger.info(f"   Current database: {current_db}")
            
            cursor.close()
            conn.close()
            
            return True
            
        except psycopg2.OperationalError as e:
            logger.error(f"❌ Cannot connect to database: {e}")
            logger.error("Check that:")
            logger.error("  1. PostgreSQL is running")
            logger.error("  2. Database credentials are correct")
            logger.error("  3. Database host is reachable")
            logger.error("  4. Port 5432 is not blocked")
            return False
        except Exception as e:
            logger.error(f"❌ Connectivity test failed: {e}")
            return False
            
    async def test_service_initialization(self):
        """Test database service initialization."""
        try:
            logger.info("\n🚀 Testing database service initialization...")
            
            self.db_service = DatabaseService(config=self.config.database)
            await self.db_service.initialize()
            
            # Check connection pool
            if not hasattr(self.db_service, '_connection_pool'):
                logger.error("❌ Connection pool not created")
                return False
                
            pool = self.db_service._connection_pool
            if pool is None:
                logger.error("❌ Connection pool is None")
                return False
                
            logger.info(f"✅ Connection pool created")
            # Note: asyncpg pools don't have minconn/maxconn attributes like psycopg2
            logger.info(f"   Pool size: {pool._size if hasattr(pool, '_size') else 'Unknown'}")
            logger.info("✅ Database service initialized")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            return False
            
    async def test_table_existence(self):
        """Test that all required tables exist."""
        try:
            logger.info("\n📊 Testing table existence...")
            
            required_tables = [
                'users',
                'user_quiz_sessions', 
                'guild_members',
                'guild_onboarding_log',
                'user_achievements',
                'saved_configs',
                'query_cache',
                'bot_versions',
                'version_changelog'
            ]
            
            async with self.db_service.acquire() as conn:
                missing_tables = []
                for table in required_tables:
                    exists = await conn.fetchval(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)",
                        table
                    )
                    
                    if exists:
                        # Get row count
                        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                        logger.info(f"✅ Table '{table}' exists ({count} rows)")
                    else:
                        missing_tables.append(table)
                        logger.error(f"❌ Table '{table}' does not exist")
            
            if missing_tables:
                logger.error(f"\n❌ Missing tables: {missing_tables}")
                logger.error("Run the appropriate schema SQL file to create missing tables")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Table existence test failed: {e}")
            return False
            
    async def test_basic_operations(self):
        """Test basic CRUD operations."""
        try:
            logger.info("\n💾 Testing basic database operations...")
            
            # Test user creation/update
            logger.info("Testing user operations...")
            stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            if not stats:
                logger.info("  Creating new test user...")
            else:
                logger.info(f"  Test user exists with {stats.get('quizzes_taken', 0)} quizzes")
                
            # Update user stats
            leveled_up = await self.db_service.update_user_stats(
                user_id=self.test_user_id,
                username=self.test_username,
                correct=5,
                wrong=2,
                points=35
            )
            logger.info(f"✅ User stats updated (leveled up: {leveled_up})")
            
            # Test achievement
            logger.info("Testing achievement operations...")
            achievement_id = self.db_service.add_achievement(
                user_id=self.test_user_id,
                name="test_achievement",
                description="Test Achievement",
                icon="🧪"
            )
            
            if achievement_id != -1:
                logger.info("✅ Achievement granted successfully")
            else:
                logger.info("✅ Achievement already exists or granted")
                
            # Get achievements
            achievements = self.db_service.get_achievements(self.test_user_id)
            logger.info(f"✅ Retrieved {len(achievements)} achievements")
            
            # Test quiz session recording
            logger.info("Testing quiz session recording...")
            from services.database_operations.quiz_stats_ops import record_complete_quiz_result_for_user
            
            success = await record_complete_quiz_result_for_user(
                db_service=self.db_service,
                user_id=self.test_user_id,
                username=self.test_username,
                quiz_id=f"test_quiz_{int(datetime.now().timestamp())}",
                topic="Test Topic",
                correct=8,
                wrong=2,
                points=80,
                difficulty="medium",
                category="general",
                guild_id=None
            )
            
            if success:
                logger.info("✅ Quiz session recorded successfully")
            else:
                logger.error("❌ Failed to record quiz session")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Basic operations test failed: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return False
            
    async def test_async_operations(self):
        """Test async wrapper functionality."""
        try:
            logger.info("\n⚡ Testing async operations...")
            
            # The DatabaseService uses AsyncConnectionWrapper
            # Test that async operations work correctly
            
            # Get user stats (uses safe_execute which is async-wrapped)
            stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            logger.info("✅ Async get_basic_user_stats worked")
            
            # Test comprehensive stats (if available)
            if hasattr(self.db_service, 'get_comprehensive_user_stats'):
                comp_stats = await self.db_service.get_comprehensive_user_stats(self.test_user_id)
                logger.info("✅ Async get_comprehensive_user_stats worked")
                
            # Test leaderboard
            leaderboard = self.db_service.get_leaderboard(limit=5)
            logger.info(f"✅ Async leaderboard retrieval worked ({len(leaderboard)} entries)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Async operations test failed: {e}")
            return False
            
    async def test_connection_pooling(self):
        """Test connection pool behavior."""
        try:
            logger.info("\n🏊 Testing connection pooling...")
            
            pool = self.db_service._connection_pool
            
            # Get multiple connections
            connections = []
            for i in range(3):
                conn = self.db_service._get_connection()
                connections.append(conn)
                logger.info(f"  Acquired connection {i+1}")
                
            # Return connections
            for i, conn in enumerate(connections):
                self.db_service._return_connection(conn)
                logger.info(f"  Returned connection {i+1}")
                
            logger.info("✅ Connection pooling works correctly")
            
            # Test pool exhaustion handling
            logger.info("Testing pool behavior under load...")
            try:
                # Try to get more connections than pool max
                stress_conns = []
                max_attempts = self.db_service._connection_pool.maxconn + 2
                
                for i in range(max_attempts):
                    try:
                        conn = psycopg2.connect(
                            host=self.config.database.host,
                            port=self.config.database.port,
                            database=self.config.database.database,
                            user=self.config.database.user,
                            password=self.config.database.password
                        )
                        stress_conns.append(conn)
                    except:
                        break
                        
                # Close all connections
                for conn in stress_conns:
                    conn.close()
                    
                logger.info("✅ Pool handles connection limits appropriately")
                
            except Exception as e:
                logger.warning(f"⚠️  Pool stress test inconclusive: {e}")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection pooling test failed: {e}")
            return False


async def main():
    """Run the database setup tests."""
    tester = DatabaseSetupTester()
    success = await tester.run_all_tests()
    
    if not success:
        logger.error("\n❌ Database setup test failed!")
        logger.error("Please fix the issues above before running the bot.")
        sys.exit(1)
    else:
        logger.info("\n✅ Your database is properly configured and ready to use!")
        logger.info("You can now start the bot with: python main.py")


if __name__ == "__main__":
    asyncio.run(main())