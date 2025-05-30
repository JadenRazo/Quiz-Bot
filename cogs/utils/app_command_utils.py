"""Utilities for handling application commands."""

from typing import Dict, List, Optional, Callable, Any, Union
import inspect
import logging
import discord
from discord import app_commands
from discord.ext import commands

# Setup logger
logger = logging.getLogger("bot.app_commands")


def command_to_app_command(command: commands.Command) -> app_commands.Command:
    """
    Convert a Discord.py command to an application command.
    
    Args:
        command: The hybrid or regular command to convert
        
    Returns:
        An application command equivalent
    """
    # Get command signature
    callback = command.callback
    params = inspect.signature(callback).parameters
    
    # Skip first parameter (usually 'self' or 'ctx')
    param_list = list(params.values())[1:]
    
    # Create app command
    app_cmd = app_commands.Command(
        name=command.name,
        description=command.description or command.help or "No description provided",
        callback=callback,
        parent=None,
        nsfw=getattr(command, 'nsfw', False),
        extras=command.extras
    )
    
    # Discord.py's app_commands.Parameter constructor is different than expected
    # Instead of manually creating parameters, we'll let discord.py handle it via the transform method
    
    return app_cmd


def find_command_conflicts(bot: commands.Bot, cog: commands.Cog) -> Dict[str, List[str]]:
    """
    Find command naming conflicts between a cog and existing bot commands.
    
    Args:
        bot: The Discord bot
        cog: The cog to check for conflicts
        
    Returns:
        Dict mapping command names to a list of conflicting locations
    """
    conflicts = {}
    
    # Get existing command names and their sources
    existing_commands = {}
    for command in bot.commands:
        existing_commands[command.name] = getattr(command.cog, '__cog_name__', 'Unknown') if command.cog else 'Bot'
    
    # Check for conflicts
    for command in cog.get_commands():
        if command.name in existing_commands:
            conflicts[command.name] = [
                f"{cog.__class__.__name__}",
                f"{existing_commands[command.name]}"
            ]
    
    return conflicts

def register_app_commands(bot: commands.Bot, cog: commands.Cog) -> List[app_commands.Command]:
    """
    Register all commands in a cog as application commands.
    
    Args:
        bot: The Discord bot
        cog: The cog containing commands
        
    Returns:
        List of registered app commands
    """
    registered_commands = []
    
    try:
        logger.info(f"Registering app commands for {cog.__class__.__name__}")
        
        # Get existing command names
        existing_command_names = [cmd.name for cmd in bot.tree.get_commands()]
        logger.debug(f"Existing app command names: {existing_command_names}")
        
        # Get all commands from the cog
        for command in cog.get_commands():
            try:
                # Skip commands that are already hybrid commands or already registered
                if isinstance(command, commands.HybridCommand):
                    logger.debug(f"Skipping hybrid command: {command.name}")
                    continue
                
                if command.name in existing_command_names:
                    logger.warning(f"Command '{command.name}' already exists as an app command, skipping")
                    continue
                    
                # Handle command groups
                if isinstance(command, commands.Group):
                    # Skip if a group with this name already exists
                    if command.name in existing_command_names:
                        logger.warning(f"Command group '{command.name}' already exists, skipping")
                        continue
                        
                    logger.info(f"Registering command group: {command.name}")
                    
                    try:
                        # Create command group
                        group = app_commands.Group(
                            name=command.name,
                            description=command.description or command.help or "No description provided",
                            parent=None
                        )
                        
                        # Register group
                        bot.tree.add_command(group)
                        registered_commands.append(group)
                        
                        # Track subcommand names for this group
                        registered_subcommand_names = []
                        
                        # Register subcommands
                        for subcommand in command.commands:
                            try:
                                # Skip duplicate subcommands
                                if subcommand.name in registered_subcommand_names:
                                    logger.warning(f"Subcommand '{subcommand.name}' already exists in group '{command.name}', skipping")
                                    continue
                                    
                                logger.debug(f"Registering subcommand: {command.name} {subcommand.name}")
                                app_cmd = command_to_app_command(subcommand)
                                app_cmd.parent = group
                                group.add_command(app_cmd)
                                registered_commands.append(app_cmd)
                                registered_subcommand_names.append(subcommand.name)
                            except Exception as subcmd_error:
                                logger.error(f"Error registering subcommand {subcommand.name}: {subcmd_error}")
                    except Exception as group_error:
                        logger.error(f"Error registering command group {command.name}: {group_error}")
                else:
                    # Regular command
                    logger.info(f"Registering command: {command.name}")
                    try:
                        app_cmd = command_to_app_command(command)
                        bot.tree.add_command(app_cmd)
                        registered_commands.append(app_cmd)
                    except Exception as cmd_add_error:
                        logger.error(f"Error adding command {command.name}: {cmd_add_error}")
            except Exception as cmd_error:
                logger.error(f"Error registering command {command.name}: {cmd_error}", exc_info=True)
                
        logger.info(f"Registered {len(registered_commands)} app commands for {cog.__class__.__name__}")
    except Exception as e:
        logger.error(f"Error registering app commands for {cog.__class__.__name__}: {e}", exc_info=True)
    
    return registered_commands