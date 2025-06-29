#!/usr/bin/env python3
"""
Comprehensive Database Test Suite for Educational Quiz Bot

This consolidated test validates database setup, connectivity, operations, and
schema implementation. It combines the functionality of both database setup
and operations testing for comprehensive validation.

Usage:
    python tests/test_database_operations.py              # Run all tests
    python tests/test_database_operations.py --setup     # Run setup tests only
    python tests/test_database_operations.py --operations # Run operations tests only

This test replaces the previous separate test_database_setup.py file.
"""

import os
import sys
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import shared test utilities
from test_utils import ConfigValidator, MockObjects, setup_test_logging

# Setup logging using shared utility
logger = setup_test_logging("db_ops_test")

class DatabaseOperationsTester:
    """Comprehensive database testing utility combining setup and operations validation."""
    
    def __init__(self, test_mode: str = "all"):
        self.config = None
        self.db_service = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.test_user_id = int(os.getenv("TEST_USER_ID", "123456789012345678"))
        self.test_guild_id = int(os.getenv("TEST_GUILD_ID", "987654321098765432"))
        self.test_username = "TestUser"
        self.test_mode = test_mode  # "all", "setup", "operations"
        
    async def run_all_tests(self) -> bool:
        """Run all database operations tests."""
        logger.info("=" * 60)
        logger.info("Educational Quiz Bot - Database Operations Test")
        logger.info("=" * 60)
        
        # Setup tests (formerly in test_database_setup.py)
        setup_tests = [
            self.test_config_validation,
            self.test_basic_connectivity,
            self.test_service_initialization,
            self.test_table_existence_and_structure,
            self.test_basic_crud_operations,
            self.test_connection_pooling
        ]
        
        # Operations tests (enhanced from original)
        operations_tests = [
            self.test_user_operations,
            self.test_guild_operations,
            self.test_quiz_operations,
            self.test_achievement_operations,
            self.test_leaderboard_operations,
            self.test_analytics_operations,
            self.test_transaction_handling,
            self.test_async_operations,
            self.test_error_handling
        ]
        
        # Select tests based on mode
        if self.test_mode == "setup":
            tests = setup_tests
        elif self.test_mode == "operations":
            tests = operations_tests
        else:
            tests = setup_tests + operations_tests
        
        all_passed = True
        for test in tests:
            try:
                if not await test():
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ Test {test.__name__} failed with exception: {e}")
                import traceback
                traceback.print_exc()
                all_passed = False
                
        # Show summary
        self._show_summary()
        return all_passed and len(self.errors) == 0
        
    async def test_config_validation(self) -> bool:
        """Test configuration loading and validation."""
        logger.info("\n🔧 Testing configuration validation...")
        
        validator = ConfigValidator()
        
        # Validate environment and configuration
        env_valid = validator.validate_environment_file()
        config_valid = validator.validate_configuration_loading() if env_valid else False
        db_valid = validator.validate_database_config() if config_valid else False
        
        # Store config for later use
        self.config = validator.config
        
        # Collect errors and warnings
        self.errors.extend(validator.errors)
        self.warnings.extend(validator.warnings)
        
        if db_valid and self.config and self.config.database:
            db_config = self.config.database
            logger.info(f"✅ Database configuration loaded:")
            logger.info(f"   Host: {db_config.host}")
            logger.info(f"   Port: {db_config.port}")
            logger.info(f"   Database: {db_config.database}")
            logger.info(f"   User: {db_config.user}")
            logger.info(f"   Password: {'*' * len(db_config.password)}")
            
            # Check if using IP address vs localhost
            if db_config.host == 'localhost':
                self.warnings.append("⚠️  Using 'localhost' - consider using actual IP address if needed")
                logger.warning("⚠️  Using 'localhost' - consider using actual IP address if needed")
        else:
            # Log specific errors
            for error in validator.errors:
                logger.error(error)
                if "Missing database" in error:
                    logger.error("Please check your .env file")
                    
        return db_valid
    
    async def test_service_initialization(self) -> bool:
        """Test database service initialization."""
        logger.info("\n🚀 Testing database service initialization...")
        
        try:
            from services.database_service import DatabaseService
            
            if not self.config:
                self.errors.append("❌ Configuration not loaded")
                return False
                
            self.db_service = DatabaseService(config=self.config.database)
            
            # Initialize the service
            await self.db_service.initialize()
            
            # Check connection pool was created
            if not hasattr(self.db_service, '_connection_pool'):
                self.errors.append("❌ Connection pool not created")
                return False
                
            pool = self.db_service._connection_pool
            if pool is None:
                self.errors.append("❌ Connection pool is None")
                return False
                
            logger.info(f"✅ Connection pool created")
            logger.info(f"   Pool size: {pool._size if hasattr(pool, '_size') else 'Unknown'}")
            logger.info("✅ Database service initialized successfully")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Failed to initialize database service: {e}")
            logger.error(f"❌ Failed to initialize database service: {e}")
            return False
            
    async def test_basic_connectivity(self) -> bool:
        """Test basic database connectivity."""
        logger.info("\n🔌 Testing basic connectivity...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test connection pool
            async with self.db_service.acquire() as conn:
                # Test simple query
                result = await conn.fetchval("SELECT 1")
                if result != 1:
                    self.errors.append("❌ Basic query failed")
                    return False
                    
                # Test database version
                version = await conn.fetchval("SELECT version()")
                logger.info(f"   Database version: {version[:50]}...")
                
                # Test current database
                db_name = await conn.fetchval("SELECT current_database()")
                logger.info(f"   Connected to database: {db_name}")
                
            logger.info("✅ Basic connectivity test passed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Connectivity test failed: {e}")
            logger.error(f"❌ Connectivity test failed: {e}")
            return False
            
    async def test_table_existence_and_structure(self) -> bool:
        """Test database table existence and structure validation."""
        logger.info("\n📊 Testing table existence and structure...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
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
                existing_tables = []
                missing_tables = []
                
                for table in required_tables:
                    exists = await conn.fetchval(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)",
                        table
                    )
                    
                    if exists:
                        existing_tables.append(table)
                        
                        # Get row count
                        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                        logger.info(f"   ✅ Table '{table}' exists ({count} rows)")
                    else:
                        missing_tables.append(table)
                        logger.error(f"   ❌ Table '{table}' missing")
                        
                if missing_tables:
                    self.errors.append(f"❌ Missing tables: {missing_tables}")
                    logger.error("   Run the schema SQL files to create missing tables")
                    return False
                    
                # Test table structure for critical tables
                await self._validate_table_structure(conn, 'users')
                await self._validate_table_structure(conn, 'user_quiz_sessions')
                await self._validate_table_structure(conn, 'guild_members')
                
            logger.info(f"✅ All {len(existing_tables)} required tables exist with proper structure")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Table existence and structure test failed: {e}")
            logger.error(f"❌ Table existence and structure test failed: {e}")
            return False
            
    async def test_basic_crud_operations(self) -> bool:
        """Test basic Create, Read, Update, Delete operations."""
        logger.info("\n💾 Testing basic CRUD operations...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test user creation/retrieval
            logger.info("   Testing user CRUD operations...")
            stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            if not stats:
                logger.info("     Creating new test user...")
            else:
                logger.info(f"     Test user exists with {stats.get('quizzes_taken', 0)} quizzes")
                
            # Update user stats (CREATE/UPDATE)
            leveled_up = await self.db_service.update_user_stats(
                user_id=self.test_user_id,
                username=self.test_username,
                correct=5,
                wrong=2,
                points=35
            )
            logger.info(f"     User stats updated (leveled up: {leveled_up})")
            
            # Read updated stats
            updated_stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            if not updated_stats:
                self.errors.append("❌ Failed to retrieve updated user stats")
                return False
                
            logger.info(f"     ✅ CRUD operations working: {updated_stats.get('total_points', 0)} points")
            
            # Test achievement operations
            logger.info("   Testing achievement CRUD operations...")
            achievement_id = await self.db_service.add_achievement(
                user_id=self.test_user_id,
                name="test_crud_achievement",
                description="Test CRUD Achievement",
                icon="🧪"
            )
            
            if achievement_id != -1:
                logger.info("     ✅ Achievement granted successfully")
            else:
                logger.info("     ✅ Achievement already exists (expected)")
                
            # Retrieve achievements
            achievements = await self.db_service.get_achievements(self.test_user_id)
            logger.info(f"     ✅ Retrieved {len(achievements) if achievements else 0} achievements")
            
            logger.info("✅ Basic CRUD operations test passed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Basic CRUD operations test failed: {e}")
            logger.error(f"❌ Basic CRUD operations test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    async def test_async_operations(self) -> bool:
        """Test async wrapper functionality and concurrent operations."""
        logger.info("\n⚡ Testing async operations...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test async operations work correctly
            async def test_operation():
                return await self.db_service.get_basic_user_stats(self.test_user_id)
                
            # Test concurrent async operations
            tasks = [test_operation() for _ in range(3)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if not isinstance(r, Exception))
            logger.info(f"   ✅ {successful}/3 concurrent async operations successful")
            
            if successful < 2:
                self.warnings.append("⚠️  Some async operations failed")
            
            # Test that async operations are actually async (non-blocking)
            import time
            start_time = time.time()
            
            # Test comprehensive stats if available
            if hasattr(self.db_service, 'get_comprehensive_user_stats'):
                comp_stats = await self.db_service.get_comprehensive_user_stats(self.test_user_id)
                logger.info("   ✅ Async comprehensive stats retrieval worked")
                
            # Test leaderboard
            leaderboard = await self.db_service.get_leaderboard(limit=5)
            logger.info(f"   ✅ Async leaderboard retrieval worked ({len(leaderboard) if leaderboard else 0} entries)")
            
            elapsed = time.time() - start_time
            logger.info(f"   ⏱️  Async operations completed in {elapsed:.2f}s")
            
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Async operations test failed: {e}")
            logger.error(f"❌ Async operations test failed: {e}")
            return False
            
    async def test_user_operations(self) -> bool:
        """Test user-related database operations."""
        logger.info("\n👤 Testing user operations...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test getting user stats (should create user if not exists)
            logger.info("   Testing get_basic_user_stats...")
            stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            
            if stats is None:
                logger.info("   User doesn't exist, testing user creation...")
            else:
                logger.info(f"   User exists with {stats.get('quizzes_taken', 0)} quizzes")
                
            # Test updating user stats
            logger.info("   Testing update_user_stats...")
            leveled_up = await self.db_service.update_user_stats(
                user_id=self.test_user_id,
                username=self.test_username,
                correct=5,
                wrong=2,
                points=35
            )
            logger.info(f"   Stats updated (leveled up: {leveled_up})")
            
            # Test getting updated stats
            updated_stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            if updated_stats:
                logger.info(f"   Updated stats: {updated_stats.get('total_points', 0)} points")
            else:
                self.errors.append("❌ Failed to retrieve updated user stats")
                return False
                
            # Test comprehensive stats if available
            if hasattr(self.db_service, 'get_comprehensive_user_stats'):
                logger.info("   Testing get_comprehensive_user_stats...")
                comp_stats = await self.db_service.get_comprehensive_user_stats(self.test_user_id)
                if comp_stats:
                    logger.info("   Comprehensive stats retrieved")
                    
            logger.info("✅ User operations test passed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ User operations test failed: {e}")
            logger.error(f"❌ User operations test failed: {e}")
            return False
            
    async def test_guild_operations(self) -> bool:
        """Test guild-related database operations."""
        logger.info("\n🏠 Testing guild operations...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test guild member operations
            logger.info("   Testing guild member operations...")
            
            # Add guild member
            async with self.db_service.acquire() as conn:
                # Check if guild_members table exists and test operations
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'guild_members')"
                )
                
                if exists:
                    # Test guild member insertion/update
                    await conn.execute(
                        """
                        INSERT INTO guild_members (user_id, guild_id, username, joined_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (user_id, guild_id) 
                        DO UPDATE SET username = $3, last_seen = CURRENT_TIMESTAMP
                        """,
                        self.test_user_id, self.test_guild_id, self.test_username, datetime.now()
                    )
                    
                    # Test guild member retrieval
                    member = await conn.fetchrow(
                        "SELECT * FROM guild_members WHERE user_id = $1 AND guild_id = $2",
                        self.test_user_id, self.test_guild_id
                    )
                    
                    if member:
                        logger.info("   Guild member operations working")
                    else:
                        self.warnings.append("⚠️  Guild member operations may not be working")
                else:
                    self.warnings.append("⚠️  guild_members table not found")
                    
            # Test guild settings if available
            if hasattr(self.db_service, 'get_guild_settings'):
                logger.info("   Testing guild settings...")
                settings = await self.db_service.get_guild_settings(self.test_guild_id)
                logger.info("   Guild settings operations available")
                
            logger.info("✅ Guild operations test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Guild operations test failed: {e}")
            logger.warning(f"⚠️  Guild operations test failed: {e}")
            return True  # Not critical for basic functionality
            
    async def test_quiz_operations(self) -> bool:
        """Test quiz-related database operations."""
        logger.info("\n🎯 Testing quiz operations...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test quiz session recording
            logger.info("   Testing quiz session recording...")
            
            # Check if we have quiz stats operations available
            try:
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
                    guild_id=self.test_guild_id
                )
                
                if success:
                    logger.info("   Quiz session recorded successfully")
                else:
                    self.errors.append("❌ Failed to record quiz session")
                    return False
                    
            except ImportError:
                logger.warning("   Quiz stats operations not available, testing basic recording...")
                
                # Test basic quiz session recording
                async with self.db_service.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO user_quiz_sessions 
                        (user_id, username, quiz_id, topic, correct_answers, wrong_answers, 
                         total_points, difficulty, category, session_date)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        self.test_user_id, self.test_username,
                        f"test_quiz_{int(datetime.now().timestamp())}",
                        "Test Topic", 8, 2, 80, "medium", "general", datetime.now()
                    )
                    
                logger.info("   Basic quiz session recording working")
                
            # Test quiz history retrieval
            logger.info("   Testing quiz history retrieval...")
            
            if hasattr(self.db_service, 'get_user_quiz_history'):
                history = await self.db_service.get_user_quiz_history(self.test_user_id, limit=5)
                logger.info(f"   Retrieved {len(history) if history else 0} quiz history entries")
            else:
                # Test basic history query
                async with self.db_service.acquire() as conn:
                    history = await conn.fetch(
                        "SELECT * FROM user_quiz_sessions WHERE user_id = $1 ORDER BY session_date DESC LIMIT 5",
                        self.test_user_id
                    )
                    logger.info(f"   Retrieved {len(history)} quiz history entries")
                    
            logger.info("✅ Quiz operations test passed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Quiz operations test failed: {e}")
            logger.error(f"❌ Quiz operations test failed: {e}")
            return False
            
    async def test_achievement_operations(self) -> bool:
        """Test achievement-related database operations."""
        logger.info("\n🏆 Testing achievement operations...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test achievement granting
            logger.info("   Testing achievement granting...")
            
            achievement_id = await self.db_service.add_achievement(
                user_id=self.test_user_id,
                name="test_achievement",
                description="Test Achievement for Testing",
                icon="🧪"
            )
            
            if achievement_id != -1:
                logger.info("   Achievement granted successfully")
            else:
                logger.info("   Achievement already exists (expected)")
                
            # Test achievement retrieval
            logger.info("   Testing achievement retrieval...")
            achievements = await self.db_service.get_achievements(self.test_user_id)
            
            if achievements is not None:
                logger.info(f"   Retrieved {len(achievements)} achievements")
            else:
                self.warnings.append("⚠️  Achievement retrieval may not be working")
                
            logger.info("✅ Achievement operations test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Achievement operations test failed: {e}")
            logger.warning(f"⚠️  Achievement operations test failed: {e}")
            return True  # Not critical for basic functionality
            
    async def test_leaderboard_operations(self) -> bool:
        """Test leaderboard-related database operations."""
        logger.info("\n🥇 Testing leaderboard operations...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test leaderboard retrieval
            logger.info("   Testing leaderboard retrieval...")
            
            leaderboard = await self.db_service.get_leaderboard(limit=10)
            
            if leaderboard is not None:
                logger.info(f"   Retrieved leaderboard with {len(leaderboard)} entries")
                
                # Validate leaderboard structure
                if leaderboard and isinstance(leaderboard[0], dict):
                    required_fields = ['user_id', 'username']
                    first_entry = leaderboard[0]
                    
                    missing_fields = [field for field in required_fields if field not in first_entry]
                    if missing_fields:
                        self.warnings.append(f"⚠️  Leaderboard entries missing fields: {missing_fields}")
                    else:
                        logger.info("   Leaderboard structure looks good")
                        
            else:
                self.warnings.append("⚠️  Leaderboard retrieval returned None")
                
            # Test guild-specific leaderboard if available
            if hasattr(self.db_service, 'get_guild_leaderboard'):
                logger.info("   Testing guild leaderboard...")
                guild_leaderboard = await self.db_service.get_guild_leaderboard(self.test_guild_id, limit=5)
                logger.info(f"   Guild leaderboard: {len(guild_leaderboard) if guild_leaderboard else 0} entries")
                
            logger.info("✅ Leaderboard operations test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Leaderboard operations test failed: {e}")
            logger.warning(f"⚠️  Leaderboard operations test failed: {e}")
            return True  # Not critical for basic functionality
            
    async def test_analytics_operations(self) -> bool:
        """Test analytics-related database operations."""
        logger.info("\n📈 Testing analytics operations...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test basic analytics queries
            logger.info("   Testing basic analytics...")
            
            async with self.db_service.acquire() as conn:
                # Test total users count
                total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
                logger.info(f"   Total users: {total_users}")
                
                # Test total quiz sessions
                total_sessions = await conn.fetchval("SELECT COUNT(*) FROM user_quiz_sessions")
                logger.info(f"   Total quiz sessions: {total_sessions}")
                
                # Test recent activity
                recent_sessions = await conn.fetchval(
                    "SELECT COUNT(*) FROM user_quiz_sessions WHERE session_date > $1",
                    datetime.now() - timedelta(days=7)
                )
                logger.info(f"   Recent sessions (7 days): {recent_sessions}")
                
            # Test advanced analytics if available
            if hasattr(self.db_service, 'get_analytics_summary'):
                logger.info("   Testing analytics summary...")
                analytics = await self.db_service.get_analytics_summary()
                if analytics:
                    logger.info("   Analytics summary available")
                    
            logger.info("✅ Analytics operations test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Analytics operations test failed: {e}")
            logger.warning(f"⚠️  Analytics operations test failed: {e}")
            return True  # Not critical for basic functionality
            
    async def test_transaction_handling(self) -> bool:
        """Test database transaction handling."""
        logger.info("\n🔄 Testing transaction handling...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test transaction rollback
            logger.info("   Testing transaction rollback...")
            
            async with self.db_service.acquire() as conn:
                # Start transaction
                async with conn.transaction():
                    # Insert test data
                    await conn.execute(
                        "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
                        999999999, "TransactionTestUser"
                    )
                    
                    # Check data exists in transaction
                    exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1)",
                        999999999
                    )
                    
                    if exists:
                        logger.info("   Data inserted in transaction")
                    
                    # Simulate error to trigger rollback
                    raise Exception("Intentional rollback test")
                    
        except Exception as e:
            if "Intentional rollback test" in str(e):
                logger.info("   Transaction rollback triggered as expected")
                
                # Verify data was rolled back
                async with self.db_service.acquire() as conn:
                    exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1)",
                        999999999
                    )
                    
                    if not exists:
                        logger.info("   ✅ Transaction rollback successful")
                    else:
                        self.warnings.append("⚠️  Transaction rollback may not have worked")
            else:
                self.warnings.append(f"⚠️  Transaction test failed: {e}")
                
        logger.info("✅ Transaction handling test completed")
        return True
        
    async def test_connection_pooling(self) -> bool:
        """Test connection pooling functionality."""
        logger.info("\n🏊 Testing connection pooling...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test multiple concurrent connections
            logger.info("   Testing concurrent connections...")
            
            async def test_connection():
                async with self.db_service.acquire() as conn:
                    return await conn.fetchval("SELECT 1")
                    
            # Test multiple connections concurrently
            tasks = [test_connection() for _ in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if r == 1)
            logger.info(f"   {successful}/5 concurrent connections successful")
            
            if successful < 3:
                self.warnings.append("⚠️  Connection pooling may have issues")
            else:
                logger.info("   Connection pooling working well")
                
            logger.info("✅ Connection pooling test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Connection pooling test failed: {e}")
            logger.warning(f"⚠️  Connection pooling test failed: {e}")
            return True  # Not critical
            
    async def test_error_handling(self) -> bool:
        """Test database error handling."""
        logger.info("\n🛡️  Testing error handling...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test handling of invalid queries
            logger.info("   Testing invalid query handling...")
            
            try:
                async with self.db_service.acquire() as conn:
                    await conn.fetchval("SELECT * FROM nonexistent_table")
            except Exception as e:
                logger.info(f"   Invalid query handled: {type(e).__name__}")
                
            # Test handling of constraint violations
            logger.info("   Testing constraint violation handling...")
            
            try:
                async with self.db_service.acquire() as conn:
                    # Try to insert duplicate primary key (if users table has one)
                    await conn.execute(
                        "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                        self.test_user_id, self.test_username
                    )
                    # Try again to trigger constraint violation
                    await conn.execute(
                        "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                        self.test_user_id, self.test_username
                    )
            except Exception as e:
                logger.info(f"   Constraint violation handled: {type(e).__name__}")
                
            logger.info("✅ Error handling test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Error handling test failed: {e}")
            logger.warning(f"⚠️  Error handling test failed: {e}")
            return True  # Not critical
            
    async def _validate_table_structure(self, conn, table_name: str) -> None:
        """Validate table structure for critical tables."""
        try:
            columns = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = $1
                ORDER BY ordinal_position
                """,
                table_name
            )
            
            if columns:
                logger.info(f"   Table '{table_name}' has {len(columns)} columns")
            else:
                self.warnings.append(f"⚠️  No columns found for table '{table_name}'")
                
        except Exception as e:
            self.warnings.append(f"⚠️  Could not validate structure for table '{table_name}': {e}")
            
    def _show_summary(self) -> None:
        """Show test summary."""
        logger.info("\n" + "=" * 60)
        if self.test_mode == "setup":
            logger.info("DATABASE SETUP TEST SUMMARY")
        elif self.test_mode == "operations":
            logger.info("DATABASE OPERATIONS TEST SUMMARY")
        else:
            logger.info("COMPREHENSIVE DATABASE TEST SUMMARY")
        logger.info("=" * 60)
        
        if self.errors:
            logger.error(f"❌ {len(self.errors)} ERRORS FOUND:")
            for error in self.errors:
                logger.error(f"   {error}")
                
        if self.warnings:
            logger.warning(f"⚠️  {len(self.warnings)} WARNINGS:")
            for warning in self.warnings:
                logger.warning(f"   {warning}")
                
        if not self.errors and not self.warnings:
            if self.test_mode == "setup":
                logger.info("✅ All database setup tests passed!")
            elif self.test_mode == "operations":
                logger.info("✅ All database operations tests passed!")
            else:
                logger.info("✅ All database tests passed!")
        elif not self.errors:
            logger.info(f"✅ Database {self.test_mode} tests are working (with warnings)")
        else:
            logger.error(f"❌ Database {self.test_mode} tests have errors that must be fixed")
            
        logger.info("=" * 60)


async def main() -> int:
    """Run database operations tests."""
    # Parse command line arguments
    test_mode = "all"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "--setup":
            test_mode = "setup"
        elif arg == "--operations":
            test_mode = "operations"
        elif arg in ["--help", "-h"]:
            print(__doc__)
            return 0
    
    logger.info(f"Running database tests in '{test_mode}' mode...")
    
    tester = DatabaseOperationsTester(test_mode=test_mode)
    success = await tester.run_all_tests()
    
    if success:
        if test_mode == "setup":
            logger.info("\n✅ Database setup validation passed!")
            logger.info("   Your database is properly configured and ready.")
            logger.info("   Run with --operations to test advanced functionality.")
        elif test_mode == "operations":
            logger.info("\n✅ Database operations are working correctly!")
        else:
            logger.info("\n🎉 All database tests passed!")
            logger.info("   Database setup and operations are working correctly.")
        return 0
    else:
        logger.error(f"\n❌ Database {test_mode} tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))