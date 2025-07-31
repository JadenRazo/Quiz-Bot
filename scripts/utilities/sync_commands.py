"""
Command Sync Utility

This script forces a sync of all Discord application commands.
Run this script when you need to ensure commands are registered with Discord.

Usage:
    python sync_commands.py [--guild GUILD_ID]
"""

import os
import sys
import logging
import asyncio
import argparse
from dotenv import load_dotenv

import discord
from discord.ext import commands

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("sync_commands")

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

async def sync_commands(guild_id=None):
    """Sync application commands with Discord."""
    # Create a temporary bot to sync commands
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
    
    @bot.event
    async def on_ready():
        logger.info(f"Bot connected as {bot.user} (ID: {bot.user.id})")
        
        try:
            logger.info(f"Starting command sync{' for guild '+str(guild_id) if guild_id else ' globally'}...")
            
            # Load all cogs to register their commands
            cogs_to_load = [
                "cogs.help",
                "cogs.quiz",
                "cogs.group_quiz",
                "cogs.admin",
                "cogs.faq",
                "cogs.onboarding",
                "cogs.stats",
                "cogs.preferences",
                "cogs.custom_quiz",
                "cogs.guild_preferences",
                "cogs.version"
            ]
            
            # Load all cogs
            for cog in cogs_to_load:
                try:
                    await bot.load_extension(cog)
                    logger.info(f"Loaded extension: {cog}")
                except Exception as e:
                    logger.error(f"Failed to load {cog}: {e}")
            
            # Perform the sync
            if guild_id:
                # Get the guild object
                guild = bot.get_guild(guild_id)
                if not guild:
                    guild = discord.Object(id=guild_id)
                    logger.warning(f"Guild with ID {guild_id} not found in the bot's cache, using Object instead")
                
                # Sync commands for this guild only
                synced = await bot.tree.sync(guild=guild)
                logger.info(f"Successfully synced {len(synced)} command(s) for guild ID {guild_id}")
                
                # List synced commands
                for cmd in synced:
                    logger.info(f"Command synced for guild {guild_id}: {cmd.name}")
            else:
                # Sync commands globally
                synced = await bot.tree.sync()
                logger.info(f"Successfully synced {len(synced)} global command(s)")
                
                # List synced commands
                for cmd in synced:
                    logger.info(f"Command synced globally: {cmd.name}")
            
            logger.info("Command sync completed successfully")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")
        
        # Close bot connection
        await bot.close()
    
    # Start the bot
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        # Ensure bot is properly closed
        if not bot.is_closed():
            await bot.close()

def main():
    """Run the command sync utility."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Discord application command sync utility")
    parser.add_argument("--guild", type=int, help="Guild ID to sync commands for (omit for global sync)")
    args = parser.parse_args()
    
    # Check if token is available
    if not TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables")
        logger.error("Make sure you have a .env file with DISCORD_TOKEN or set it in your environment")
        sys.exit(1)
    
    # Run the command sync
    asyncio.run(sync_commands(args.guild))
    logger.info("Sync process complete")

if __name__ == "__main__":
    main() 