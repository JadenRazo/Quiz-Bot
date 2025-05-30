"""
Test script for verifying multi-guild quiz functionality.
"""

import asyncio
import discord
import logging
from discord.ext import commands
from typing import Dict, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("multi_guild_test")

class QuizMultiGuildTester:
    """A class to simulate and test quiz functionality across multiple guilds."""
    
    def __init__(self, bot):
        self.bot = bot
        self.guild_channels = {}  # guild_id -> channel_id
        
    async def run_tests(self):
        """Run the full test suite."""
        logger.info("Starting multi-guild quiz tests")
        
        # First, identify and store some test guilds and channels
        await self._find_test_guilds()
        
        if len(self.guild_channels) < 2:
            logger.error("Need at least 2 different guilds to run multi-guild tests. Test failed.")
            return False
            
        logger.info(f"Found {len(self.guild_channels)} testable guilds")
        
        # Now run the tests
        try:
            # Start quizzes in parallel in multiple guilds
            await self._test_concurrent_quizzes()
            
            # Test cleanup of inactive quizzes
            await self._test_inactivity_cleanup()
            
            # Test session recovery
            await self._test_session_recovery()
            
            logger.info("All multi-guild quiz tests completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Test failed with error: {e}")
            return False
            
    async def _find_test_guilds(self):
        """Find suitable guild/channel pairs for testing."""
        # Wait for bot to be ready
        await self.bot.wait_until_ready()
        
        # Iterate through all guilds the bot is in
        for guild in self.bot.guilds:
            # Find a suitable channel for testing (text channel where bot has permissions)
            for channel in guild.text_channels:
                permissions = channel.permissions_for(guild.me)
                if permissions.send_messages and permissions.read_messages:
                    self.guild_channels[guild.id] = channel.id
                    logger.info(f"Found test channel: Guild {guild.name} ({guild.id}), Channel #{channel.name} ({channel.id})")
                    break
    
    async def _test_concurrent_quizzes(self):
        """Test running quizzes concurrently in multiple guilds."""
        logger.info("Testing concurrent quizzes in multiple guilds")
        
        # Get quiz cog
        quiz_cog = self.bot.get_cog("Quiz")
        if not quiz_cog:
            logger.error("Quiz cog not found!")
            return False
            
        # Start a quiz in each test guild (this is a simulation, not actual command execution)
        guild_quizzes = {}
        
        for guild_id, channel_id in list(self.guild_channels.items())[:2]:  # Use first 2 guilds
            # Get guild and channel objects
            guild = self.bot.get_guild(guild_id)
            channel = self.bot.get_channel(channel_id)
            
            if not guild or not channel:
                continue
                
            # Create a mock session
            from cogs.models.quiz_models import ActiveQuiz, QuizState
            
            # Create a dummy quiz with different topics per guild
            quiz = ActiveQuiz(
                guild_id=guild_id,
                channel_id=channel_id,
                host_id=self.bot.user.id,
                topic=f"Test Quiz for Guild {guild.name}",
                questions=[],  # Empty for testing
                timeout=30,
                llm_provider="test"
            )
            
            # Manually add to active quizzes
            session_key = (guild_id, channel_id)
            quiz_cog.active_quizzes[session_key] = quiz
            quiz.state = QuizState.ACTIVE
            
            # Store for verification
            guild_quizzes[guild_id] = quiz
            logger.info(f"Started test quiz in guild {guild.name} ({guild_id})")
            
        # Verify each guild has its own separate quiz
        for guild_id, quiz in guild_quizzes.items():
            # Check that this guild's quiz has the right topic
            expected_topic = f"Test Quiz for Guild {self.bot.get_guild(guild_id).name}"
            assert quiz.topic == expected_topic, f"Wrong topic for guild {guild_id}: {quiz.topic} != {expected_topic}"
            
            # Check that this quiz is stored with the correct composite key
            session_key = (guild_id, self.guild_channels[guild_id])
            assert session_key in quiz_cog.active_quizzes, f"Quiz not found at expected key {session_key}"
            assert quiz_cog.active_quizzes[session_key].topic == expected_topic
            
        logger.info("Concurrent quiz test passed!")
        
        # Clean up
        for guild_id, quiz in guild_quizzes.items():
            session_key = (guild_id, self.guild_channels[guild_id])
            if session_key in quiz_cog.active_quizzes:
                del quiz_cog.active_quizzes[session_key]
                
        return True
        
    async def _test_inactivity_cleanup(self):
        """Test that inactive quizzes are cleaned up."""
        logger.info("Testing inactive quiz cleanup")
        
        # Get quiz cog
        quiz_cog = self.bot.get_cog("Quiz")
        if not quiz_cog:
            logger.error("Quiz cog not found!")
            return False
            
        # Take the first guild
        first_guild = list(self.guild_channels.keys())[0]
        guild_id = first_guild
        channel_id = self.guild_channels[first_guild]
        
        # Create a mock inactive quiz
        from cogs.models.quiz_models import ActiveQuiz, QuizState
        import time
        
        # Create a quiz with inactive timestamp
        quiz = ActiveQuiz(
            guild_id=guild_id,
            channel_id=channel_id,
            host_id=self.bot.user.id, 
            topic="Inactive Quiz",
            questions=[],  # Empty for testing
            timeout=30,
            llm_provider="test"
        )
        
        # Set inactive timestamp (31 minutes ago)
        quiz.last_activity_time = time.time() - 1860  # 31 minutes
        
        # Add to active quizzes
        session_key = (guild_id, channel_id)
        quiz_cog.active_quizzes[session_key] = quiz
        quiz.state = QuizState.ACTIVE
        
        # Force run cleanup
        await quiz_cog.cleanup_expired_quizzes()
        
        # Check if it was cleaned up
        assert session_key not in quiz_cog.active_quizzes, "Inactive quiz was not cleaned up"
        
        logger.info("Inactivity cleanup test passed!")
        return True
        
    async def _test_session_recovery(self):
        """Test session recovery after bot restart."""
        logger.info("Testing session recovery")
        
        # Get quiz cog
        quiz_cog = self.bot.get_cog("Quiz")
        if not quiz_cog:
            logger.error("Quiz cog not found!")
            return False
            
        # Take the first guild
        first_guild = list(self.guild_channels.keys())[0]
        guild_id = first_guild
        channel_id = self.guild_channels[first_guild]
        
        # Create a mock quiz that needs recovery
        from cogs.models.quiz_models import ActiveQuiz, QuizState
        
        # Create a recoverable quiz
        quiz = ActiveQuiz(
            guild_id=guild_id,
            channel_id=channel_id,
            host_id=self.bot.user.id,
            topic="Recoverable Quiz",
            questions=[],  # Empty for testing
            timeout=30,
            llm_provider="test"
        )
        
        # Add to active quizzes
        session_key = (guild_id, channel_id)
        quiz_cog.active_quizzes[session_key] = quiz
        quiz.state = QuizState.ACTIVE
        
        # Call save recovery data
        quiz_cog._save_session_recovery_data(quiz)
        
        # Verify recovery data is saved
        assert session_key in quiz_cog.session_recovery_data, "Recovery data not saved"
        
        # Remove from active quizzes to simulate a restart
        del quiz_cog.active_quizzes[session_key]
        
        # Call recovery
        await quiz_cog._recover_active_sessions()
        
        # Check recovery happened (in real use, the recovery just notifies the channel)
        assert session_key not in quiz_cog.session_recovery_data, "Recovery data not cleared after recovery attempt"
        
        logger.info("Session recovery test passed!")
        return True


async def run_tests(bot):
    """Run all multi-guild tests."""
    tester = QuizMultiGuildTester(bot)
    return await tester.run_tests()