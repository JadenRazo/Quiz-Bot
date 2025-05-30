#!/usr/bin/env python3
"""
Setup Script for Quiz Bot

This script provides utilities for loading cogs and ensuring commands
are properly registered with Discord.
"""

import os
import sys
import asyncio
import logging
import discord
from discord.ext import commands
from typing import List, Optional, Dict, Any, Set, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("setup.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("setup")

async def load_all_cogs(bot) -> List[str]:
    """
    Load all cogs from the cogs directory.
    
    Args:
        bot: The Discord bot instance
    
    Returns:
        List of loaded cog names
    """
    cogs_dir = "cogs"
    loaded_cogs = []
    
    logger.info(f"Scanning for cogs in the {cogs_dir} directory")
    
    try:
        # List all Python files in the cogs directory
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                cog_name = f"cogs.{filename[:-3]}"  # Remove .py extension
                
                try:
                    logger.info(f"Loading extension: {cog_name}")
                    await bot.load_extension(cog_name)
                    loaded_cogs.append(cog_name)
                    logger.info(f"Successfully loaded extension: {cog_name}")
                except commands.ExtensionAlreadyLoaded:
                    logger.warning(f"Cog already loaded: {cog_name}")
                    loaded_cogs.append(cog_name)  # Still count as loaded
                except Exception as e:
                    logger.error(f"Failed to load extension {cog_name}: {e}")
        
        if not loaded_cogs:
            logger.critical("No cogs were loaded.")
        else:
            logger.info(f"Loaded {len(loaded_cogs)} cogs: {', '.join(loaded_cogs)}")
            
    except Exception as e:
        logger.error(f"Error scanning cogs directory: {e}", exc_info=True)
    
    return loaded_cogs

async def sync_commands(bot) -> int:
    """
    Sync slash commands with Discord without clearing commands first.
    
    Args:
        bot: The Discord bot instance
    
    Returns:
        Number of commands synced
    """
    try:
        # Log existing commands before syncing
        commands_before = list(bot.tree.get_commands())
        logger.info(f"Commands in tree before sync: {len(commands_before)}")
        for cmd in commands_before:
            logger.info(f"Command before sync: {cmd.name}")
            # Check for subcommands
            if hasattr(cmd, "children") and cmd.children:
                for name, child in cmd.children.items():
                    logger.info(f"  - Subcommand: {cmd.name} {name}")
        
        # IMPORTANT: Don't clear commands before syncing
        # Sync globally directly
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} global command(s)")
        
        # Log what commands were synced
        for cmd in synced:
            logger.info(f"Global command synced: {cmd.name}")
            # Check for subcommands
            if hasattr(cmd, "children") and cmd.children:
                for name, child in cmd.children.items():
                    logger.info(f"  - Synced subcommand: {cmd.name} {name}")
        
        # Log final command tree state
        all_commands = list(bot.tree.get_commands())
        logger.info(f"Final command tree after sync: {len(all_commands)} commands")
        
        return len(synced)
            
    except discord.HTTPException as e:
        logger.error(f"Failed to sync commands: {e}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error syncing commands: {e}", exc_info=True)
        return 0

if __name__ == "__main__":
    logger.info("Setup script should not be run directly. Import the functions as needed.") 