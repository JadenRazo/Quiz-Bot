"""
Script to run multi-guild quiz tests.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_runner")

async def run_tests():
    """Main function to run tests."""
    from test_multi_guild_quizzes import run_tests
    from main import bot
    
    try:
        # Ensure bot is ready
        await bot.wait_until_ready()
        logger.info(f"Bot is ready. Connected to {len(bot.guilds)} guild(s)")
        
        # Run the tests
        result = await run_tests(bot)
        
        if result:
            logger.info("All tests passed!")
            return 0
        else:
            logger.error("Tests failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    # Import bot after setting up paths
    from main import bot
    
    # Add test task to bot's loop
    bot.loop.create_task(run_tests())
    
    # Run the bot
    bot.run(os.environ.get('DISCORD_TOKEN'), log_handler=None)