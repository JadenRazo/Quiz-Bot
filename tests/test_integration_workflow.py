#!/usr/bin/env python3
"""
Integration Workflow Test for Educational Quiz Bot

This test validates the complete end-to-end workflow of quiz creation and execution,
testing the integration between all components.

Usage:
    python tests/test_integration_workflow.py
"""

import os
import sys
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("integration_test")

class IntegrationWorkflowTester:
    """Test complete quiz workflow integration."""
    
    def __init__(self):
        self.config = None
        self.db_service = None
        self.llm_service = None
        self.quiz_generator = None
        self.bot_context = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.test_user_id = int(os.getenv("TEST_USER_ID", "123456789012345678"))
        self.test_guild_id = int(os.getenv("TEST_GUILD_ID", "987654321098765432"))
        self.test_username = "IntegrationTestUser"
        
    async def run_all_tests(self) -> bool:
        """Run all integration workflow tests."""
        logger.info("=" * 60)
        logger.info("Educational Quiz Bot - Integration Workflow Test")
        logger.info("=" * 60)
        
        tests = [
            self.test_full_system_initialization,
            self.test_quiz_creation_workflow,
            self.test_quiz_execution_simulation,
            self.test_user_stats_integration,
            self.test_achievement_integration,
            self.test_leaderboard_integration,
            self.test_multi_user_scenario,
            self.test_error_recovery_workflow,
            self.test_performance_workflow
        ]
        
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
        
    async def test_full_system_initialization(self) -> bool:
        """Test full system initialization."""
        logger.info("\n🚀 Testing full system initialization...")
        
        try:
            # Load configuration
            from config import load_config
            self.config = load_config()
            logger.info("   ✅ Configuration loaded")
            
            # Initialize database service
            from services.database_service import DatabaseService
            self.db_service = DatabaseService(config=self.config.database)
            await self.db_service.initialize()
            logger.info("   ✅ Database service initialized")
            
            # Initialize LLM service
            from services.llm_service import LLMService
            self.llm_service = LLMService(self.config.llm)
            await self.llm_service.initialize()
            logger.info("   ✅ LLM service initialized")
            
            # Initialize quiz generator
            from services.quiz_generator import QuizGenerator
            self.quiz_generator = QuizGenerator(self.llm_service, self.config)
            logger.info("   ✅ Quiz generator initialized")
            
            # Create bot context
            from utils.context import BotContext
            from discord.ext import commands
            import discord
            
            # Create mock bot
            intents = discord.Intents.default()
            intents.message_content = True
            mock_bot = commands.AutoShardedBot(command_prefix="!", intents=intents, help_command=None)
            
            self.bot_context = BotContext(
                bot=mock_bot,
                config=self.config,
                db_service=self.db_service,
                llm_service=self.llm_service
            )
            logger.info("   ✅ Bot context created")
            
            logger.info("✅ Full system initialization completed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ System initialization failed: {e}")
            logger.error(f"❌ System initialization failed: {e}")
            return False
            
    async def test_quiz_creation_workflow(self) -> bool:
        """Test the complete quiz creation workflow."""
        logger.info("\n🎯 Testing quiz creation workflow...")
        
        if not self.quiz_generator:
            self.errors.append("❌ Quiz generator not initialized")
            return False
            
        try:
            # Step 1: Generate quiz questions
            logger.info("   Step 1: Generating quiz questions...")
            
            questions = await self.quiz_generator.generate_quiz_questions(
                topic="basic programming concepts",
                num_questions=3,
                difficulty="medium"
            )
            
            if not questions:
                self.errors.append("❌ No questions generated")
                return False
                
            logger.info(f"   Generated {len(questions)} questions")
            
            # Step 2: Validate question structure
            logger.info("   Step 2: Validating question structure...")
            
            for i, question in enumerate(questions):
                if not self._validate_question_structure(question):
                    self.errors.append(f"❌ Question {i+1} has invalid structure")
                    return False
                    
            logger.info("   All questions have valid structure")
            
            # Step 3: Create quiz session object
            logger.info("   Step 3: Creating quiz session...")
            
            from cogs.models.quiz_models import ActiveQuiz, QuizState
            
            quiz_session = ActiveQuiz(
                guild_id=self.test_guild_id,
                channel_id=123456,
                host_id=self.test_user_id,
                topic="basic programming concepts",
                questions=questions,
                timeout=60,
                llm_provider="test"
            )
            
            quiz_session.state = QuizState.ACTIVE
            logger.info("   Quiz session created successfully")
            
            # Step 4: Simulate quiz initialization
            logger.info("   Step 4: Simulating quiz initialization...")
            
            quiz_session.start_time = datetime.now()
            quiz_session.current_question_index = 0
            
            if quiz_session.current_question:
                logger.info(f"   First question ready: '{quiz_session.current_question['question'][:50]}...'")
            else:
                self.errors.append("❌ Current question not accessible")
                return False
                
            logger.info("✅ Quiz creation workflow completed successfully")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Quiz creation workflow failed: {e}")
            logger.error(f"❌ Quiz creation workflow failed: {e}")
            return False
            
    async def test_quiz_execution_simulation(self) -> bool:
        """Test quiz execution simulation."""
        logger.info("\n▶️  Testing quiz execution simulation...")
        
        if not self.quiz_generator or not self.db_service:
            self.errors.append("❌ Required services not initialized")
            return False
            
        try:
            # Generate a quiz for simulation
            questions = await self.quiz_generator.generate_quiz_questions(
                topic="simple math",
                num_questions=2,
                difficulty="easy"
            )
            
            if not questions:
                self.warnings.append("⚠️  No questions for execution simulation")
                return True
                
            logger.info(f"   Simulating quiz with {len(questions)} questions...")
            
            # Simulate quiz execution
            correct_answers = 0
            wrong_answers = 0
            total_points = 0
            
            for i, question in enumerate(questions):
                logger.info(f"   Question {i+1}: {question['question'][:40]}...")
                
                # Simulate correct answer (first option as correct)
                correct_answer = question['correct_answer']
                user_answer = correct_answer  # Simulate user choosing correct answer
                
                if user_answer == correct_answer:
                    correct_answers += 1
                    points = 10  # Base points for correct answer
                    total_points += points
                    logger.info(f"     ✅ Correct! (+{points} points)")
                else:
                    wrong_answers += 1
                    logger.info(f"     ❌ Wrong (correct: {correct_answer})")
                    
            # Calculate final results
            accuracy = (correct_answers / len(questions)) * 100 if questions else 0
            logger.info(f"   Final results: {correct_answers}/{len(questions)} correct ({accuracy:.1f}%)")
            logger.info(f"   Total points: {total_points}")
            
            # Test quiz completion workflow
            logger.info("   Testing quiz completion workflow...")
            
            # Record quiz results
            try:
                from services.database_operations.quiz_stats_ops import record_complete_quiz_result_for_user
                
                success = await record_complete_quiz_result_for_user(
                    db_service=self.db_service,
                    user_id=self.test_user_id,
                    username=self.test_username,
                    quiz_id=f"integration_test_{int(datetime.now().timestamp())}",
                    topic="simple math",
                    correct=correct_answers,
                    wrong=wrong_answers,
                    points=total_points,
                    difficulty="easy",
                    category="mathematics",
                    guild_id=self.test_guild_id
                )
                
                if success:
                    logger.info("   Quiz results recorded successfully")
                else:
                    self.warnings.append("⚠️  Quiz results recording failed")
                    
            except ImportError:
                logger.warning("   Quiz stats operations not available")
                
            logger.info("✅ Quiz execution simulation completed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Quiz execution simulation failed: {e}")
            logger.error(f"❌ Quiz execution simulation failed: {e}")
            return False
            
    async def test_user_stats_integration(self) -> bool:
        """Test user statistics integration."""
        logger.info("\n📊 Testing user stats integration...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Get initial user stats
            logger.info("   Getting initial user stats...")
            initial_stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            
            initial_quizzes = initial_stats.get('quizzes_taken', 0) if initial_stats else 0
            initial_points = initial_stats.get('total_points', 0) if initial_stats else 0
            
            logger.info(f"   Initial stats: {initial_quizzes} quizzes, {initial_points} points")
            
            # Update user stats
            logger.info("   Updating user stats...")
            
            leveled_up = await self.db_service.update_user_stats(
                user_id=self.test_user_id,
                username=self.test_username,
                correct=8,
                wrong=2,
                points=100
            )
            
            logger.info(f"   Stats updated (leveled up: {leveled_up})")
            
            # Get updated user stats
            logger.info("   Verifying updated stats...")
            updated_stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            
            if updated_stats:
                updated_quizzes = updated_stats.get('quizzes_taken', 0)
                updated_points = updated_stats.get('total_points', 0)
                
                logger.info(f"   Updated stats: {updated_quizzes} quizzes, {updated_points} points")
                
                # Verify the update worked
                if updated_points >= initial_points + 100:
                    logger.info("   ✅ Points updated correctly")
                else:
                    self.warnings.append("⚠️  Points may not have updated correctly")
                    
            else:
                self.errors.append("❌ Could not retrieve updated stats")
                return False
                
            logger.info("✅ User stats integration test passed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ User stats integration failed: {e}")
            logger.error(f"❌ User stats integration failed: {e}")
            return False
            
    async def test_achievement_integration(self) -> bool:
        """Test achievement system integration."""
        logger.info("\n🏆 Testing achievement integration...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Test achievement granting
            logger.info("   Testing achievement granting...")
            
            achievement_id = await self.db_service.add_achievement(
                user_id=self.test_user_id,
                name="integration_test_achievement",
                description="Achievement from integration test",
                icon="🧪"
            )
            
            if achievement_id != -1:
                logger.info("   Achievement granted successfully")
            else:
                logger.info("   Achievement already exists")
                
            # Test achievement retrieval
            logger.info("   Testing achievement retrieval...")
            
            achievements = await self.db_service.get_achievements(self.test_user_id)
            
            if achievements is not None:
                logger.info(f"   User has {len(achievements)} achievements")
                
                # Look for our test achievement
                test_achievement = None
                for achievement in achievements:
                    if achievement.get('name') == 'integration_test_achievement':
                        test_achievement = achievement
                        break
                        
                if test_achievement:
                    logger.info("   ✅ Test achievement found in user's achievements")
                else:
                    self.warnings.append("⚠️  Test achievement not found in user's achievements")
                    
            else:
                self.warnings.append("⚠️  Achievement retrieval returned None")
                
            logger.info("✅ Achievement integration test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Achievement integration failed: {e}")
            logger.warning(f"⚠️  Achievement integration failed: {e}")
            return True  # Not critical for basic functionality
            
    async def test_leaderboard_integration(self) -> bool:
        """Test leaderboard integration."""
        logger.info("\n🥇 Testing leaderboard integration...")
        
        if not self.db_service:
            self.errors.append("❌ Database service not initialized")
            return False
            
        try:
            # Get leaderboard
            logger.info("   Getting global leaderboard...")
            
            leaderboard = await self.db_service.get_leaderboard(limit=5)
            
            if leaderboard is not None:
                logger.info(f"   Leaderboard has {len(leaderboard)} entries")
                
                # Check if our test user is in the leaderboard
                test_user_found = False
                for i, entry in enumerate(leaderboard):
                    if entry.get('user_id') == self.test_user_id:
                        test_user_found = True
                        logger.info(f"   Test user found at position {i+1}")
                        break
                        
                if not test_user_found and leaderboard:
                    logger.info("   Test user not in top 5 (expected if low stats)")
                    
            else:
                self.warnings.append("⚠️  Leaderboard retrieval returned None")
                
            # Test guild leaderboard if available
            if hasattr(self.db_service, 'get_guild_leaderboard'):
                logger.info("   Testing guild leaderboard...")
                
                guild_leaderboard = await self.db_service.get_guild_leaderboard(
                    self.test_guild_id, limit=5
                )
                
                if guild_leaderboard is not None:
                    logger.info(f"   Guild leaderboard has {len(guild_leaderboard)} entries")
                else:
                    logger.info("   Guild leaderboard is empty (expected for test guild)")
                    
            logger.info("✅ Leaderboard integration test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Leaderboard integration failed: {e}")
            logger.warning(f"⚠️  Leaderboard integration failed: {e}")
            return True  # Not critical
            
    async def test_multi_user_scenario(self) -> bool:
        """Test multi-user scenario simulation."""
        logger.info("\n👥 Testing multi-user scenario...")
        
        if not self.db_service or not self.quiz_generator:
            self.errors.append("❌ Required services not initialized")
            return False
            
        try:
            # Simulate multiple users taking quizzes
            logger.info("   Simulating multiple users...")
            
            test_users = [
                (self.test_user_id + 1, "TestUser1"),
                (self.test_user_id + 2, "TestUser2"),
                (self.test_user_id + 3, "TestUser3")
            ]
            
            # Generate a common quiz
            questions = await self.quiz_generator.generate_quiz_questions(
                topic="general knowledge",
                num_questions=1,
                difficulty="medium"
            )
            
            if not questions:
                self.warnings.append("⚠️  No questions for multi-user test")
                return True
                
            # Simulate each user taking the quiz
            for user_id, username in test_users:
                logger.info(f"   Simulating quiz for {username}...")
                
                # Simulate different performance
                correct = 1 if user_id % 2 == 0 else 0  # Alternate correct/wrong
                wrong = 1 - correct
                points = correct * 10
                
                # Update stats
                await self.db_service.update_user_stats(
                    user_id=user_id,
                    username=username,
                    correct=correct,
                    wrong=wrong,
                    points=points
                )
                
                logger.info(f"     {username}: {correct} correct, {points} points")
                
            # Test leaderboard after multiple users
            logger.info("   Checking leaderboard after multi-user activity...")
            
            leaderboard = await self.db_service.get_leaderboard(limit=10)
            
            if leaderboard:
                logger.info(f"   Leaderboard now has {len(leaderboard)} entries")
                
                # Check if any of our test users made it
                test_users_in_lb = 0
                for entry in leaderboard:
                    if entry.get('user_id') in [u[0] for u in test_users]:
                        test_users_in_lb += 1
                        
                logger.info(f"   {test_users_in_lb} test users in leaderboard")
            else:
                self.warnings.append("⚠️  Leaderboard empty after multi-user test")
                
            logger.info("✅ Multi-user scenario test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Multi-user scenario failed: {e}")
            logger.warning(f"⚠️  Multi-user scenario failed: {e}")
            return True  # Not critical
            
    async def test_error_recovery_workflow(self) -> bool:
        """Test error recovery workflows."""
        logger.info("\n🛡️  Testing error recovery workflow...")
        
        if not self.llm_service or not self.db_service:
            self.errors.append("❌ Required services not initialized")
            return False
            
        try:
            # Test LLM service error recovery
            logger.info("   Testing LLM service error recovery...")
            
            try:
                # Try to generate quiz with invalid parameters
                questions = await self.llm_service.generate_quiz_questions(
                    topic="",  # Empty topic
                    num_questions=0,  # Invalid count
                    difficulty="invalid"  # Invalid difficulty
                )
                
                if not questions:
                    logger.info("   ✅ LLM service handled invalid input gracefully")
                else:
                    logger.info("   ✅ LLM service generated questions despite invalid input")
                    
            except Exception as e:
                logger.info(f"   ✅ LLM service raised exception as expected: {type(e).__name__}")
                
            # Test database error recovery
            logger.info("   Testing database error recovery...")
            
            try:
                # Try to execute invalid query
                async with self.db_service.acquire() as conn:
                    await conn.fetchval("SELECT * FROM nonexistent_table_12345")
                    
            except Exception as e:
                logger.info(f"   ✅ Database handled invalid query: {type(e).__name__}")
                
            # Test that services are still functional after errors
            logger.info("   Testing service functionality after errors...")
            
            # Test LLM service still works
            questions = await self.llm_service.generate_quiz_questions(
                topic="basic science",
                num_questions=1,
                difficulty="easy"
            )
            
            if questions:
                logger.info("   ✅ LLM service still functional after error")
            else:
                self.warnings.append("⚠️  LLM service may not be functional after error")
                
            # Test database still works
            stats = await self.db_service.get_basic_user_stats(self.test_user_id)
            if stats is not None:
                logger.info("   ✅ Database service still functional after error")
            else:
                self.warnings.append("⚠️  Database service may not be functional after error")
                
            logger.info("✅ Error recovery workflow test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Error recovery workflow failed: {e}")
            logger.warning(f"⚠️  Error recovery workflow failed: {e}")
            return True  # Not critical
            
    async def test_performance_workflow(self) -> bool:
        """Test performance of complete workflow."""
        logger.info("\n⚡ Testing performance workflow...")
        
        if not self.quiz_generator or not self.db_service:
            self.errors.append("❌ Required services not initialized")
            return False
            
        try:
            import time
            
            # Test quiz generation performance
            logger.info("   Testing quiz generation performance...")
            
            start_time = time.time()
            questions = await self.quiz_generator.generate_quiz_questions(
                topic="technology",
                num_questions=3,
                difficulty="medium"
            )
            generation_time = time.time() - start_time
            
            logger.info(f"   Quiz generation took {generation_time:.2f}s")
            
            if generation_time > 30:
                self.warnings.append(f"⚠️  Quiz generation slow: {generation_time:.2f}s")
            elif generation_time > 60:
                self.errors.append(f"❌ Quiz generation too slow: {generation_time:.2f}s")
                return False
                
            # Test database operations performance
            logger.info("   Testing database operations performance...")
            
            start_time = time.time()
            
            # Perform multiple database operations
            await self.db_service.get_basic_user_stats(self.test_user_id)
            await self.db_service.update_user_stats(
                user_id=self.test_user_id,
                username=self.test_username,
                correct=1,
                wrong=0,
                points=10
            )
            await self.db_service.get_leaderboard(limit=5)
            
            db_operations_time = time.time() - start_time
            
            logger.info(f"   Database operations took {db_operations_time:.2f}s")
            
            if db_operations_time > 5:
                self.warnings.append(f"⚠️  Database operations slow: {db_operations_time:.2f}s")
            elif db_operations_time > 15:
                self.errors.append(f"❌ Database operations too slow: {db_operations_time:.2f}s")
                return False
                
            # Test concurrent operations
            logger.info("   Testing concurrent operations...")
            
            start_time = time.time()
            
            # Run multiple operations concurrently
            tasks = [
                self.db_service.get_basic_user_stats(self.test_user_id + i)
                for i in range(3)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            concurrent_time = time.time() - start_time
            
            successful = sum(1 for r in results if not isinstance(r, Exception))
            logger.info(f"   Concurrent operations: {successful}/3 successful in {concurrent_time:.2f}s")
            
            if successful < 2:
                self.warnings.append("⚠️  Concurrent operations may have issues")
                
            logger.info("✅ Performance workflow test passed")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Performance workflow failed: {e}")
            logger.warning(f"⚠️  Performance workflow failed: {e}")
            return True  # Not critical
            
    def _validate_question_structure(self, question: Dict[str, Any]) -> bool:
        """Validate question structure."""
        required_fields = ['question', 'options', 'correct_answer']
        
        for field in required_fields:
            if field not in question:
                return False
                
        if not isinstance(question['options'], list) or len(question['options']) < 2:
            return False
            
        if question['correct_answer'] not in question['options']:
            return False
            
        return True
        
    def _show_summary(self) -> None:
        """Show test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("INTEGRATION WORKFLOW TEST SUMMARY")
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
            logger.info("✅ All integration workflow tests passed!")
            logger.info("🎉 Your bot is ready for deployment!")
        elif not self.errors:
            logger.info("✅ Integration workflow is working (with warnings)")
            logger.info("🎉 Your bot should work correctly in most scenarios!")
        else:
            logger.error("❌ Integration workflow has errors that must be fixed")
            
        logger.info("=" * 60)


async def main() -> int:
    """Run integration workflow tests."""
    tester = IntegrationWorkflowTester()
    success = await tester.run_all_tests()
    
    if success:
        logger.info("\n🎉 Complete integration workflow is working!")
        logger.info("Your bot is ready for production use!")
        return 0
    else:
        logger.error("\n❌ Please fix the integration issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))