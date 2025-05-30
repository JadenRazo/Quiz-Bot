#!/usr/bin/env python3
"""
Script to update all cog setup functions to register app commands properly.
"""

import os
import re
import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("update_cog_setup")

# Cogs directory
COGS_DIR = Path(__file__).parent.parent / "cogs"

# Regex to find setup function
SETUP_REGEX = r'async\s+def\s+setup\(.*?\):\s*(?:["\'].*?["\'])?\s*.*?(?=async\s+def|$)'
SETUP_WITH_CONTEXT_REGEX = r'async\s+def\s+setup_with_context\(.*?\):\s*(?:["\'].*?["\'])?\s*.*?(?=async\s+def|$)'

# Template for new setup function
SETUP_TEMPLATE = '''async def setup(bot):
    """Setup function for the cog."""
    try:
        # Create cog instance
        cog = {cog_class}(bot)
        
        # Add the cog to the bot
        await bot.add_cog(cog)
        
        # Register app commands for non-hybrid commands
        from cogs.utils.app_command_utils import register_app_commands
        register_app_commands(bot, cog)
        
        logger.debug("{cog_class} loaded via setup function")
        return cog
    except Exception as e:
        logger.error(f"Error loading {cog_class}: {{e}}")
        raise
'''

def extract_cog_class(file_content):
    """Extract the cog class name from file content."""
    # Look for class definition that inherits from BaseCog
    class_match = re.search(r'class\s+(\w+)\(BaseCog', file_content)
    if class_match:
        return class_match.group(1)
    
    # Alternative pattern for cogs that might not use BaseCog
    alt_match = re.search(r'class\s+(\w+)\(commands\.Cog', file_content)
    if alt_match:
        return alt_match.group(1)
    
    return None

def update_cog_setup(file_path):
    """Update the setup function in a cog file."""
    try:
        # Read the file content
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Skip if file is not a cog
        if "commands.Cog" not in content and "BaseCog" not in content:
            logger.debug(f"Skipping {file_path} - not a cog")
            return False
        
        # Extract the cog class name
        cog_class = extract_cog_class(content)
        if not cog_class:
            logger.warning(f"Could not find cog class in {file_path}")
            return False
        
        # Check if file already has app_command_utils import
        if "from cogs.utils.app_command_utils import register_app_commands" in content:
            logger.info(f"Cog {file_path} already updated")
            return False
        
        # Find the setup function
        setup_match = re.search(SETUP_REGEX, content, re.DOTALL)
        if not setup_match:
            # If no setup function exists, check if we need to add one
            if "async def setup_with_context" in content:
                # Add a new setup function
                setup_with_context_match = re.search(SETUP_WITH_CONTEXT_REGEX, content, re.DOTALL)
                if setup_with_context_match:
                    # Insert before setup_with_context
                    new_content = content.replace(
                        setup_with_context_match.group(0),
                        SETUP_TEMPLATE.format(cog_class=cog_class) + "\n" + setup_with_context_match.group(0)
                    )
                    with open(file_path, 'w') as f:
                        f.write(new_content)
                    logger.info(f"Added setup function to {file_path}")
                    return True
            return False
        
        # Create a new setup function with the app command registration
        existing_setup = setup_match.group(0)
        
        # Check if the setup function already returns the cog
        if "return cog" not in existing_setup:
            # Add register_app_commands before the end of the function
            if "await bot.add_cog" in existing_setup:
                # Add after add_cog
                insert_point = existing_setup.find("await bot.add_cog")
                insert_point = existing_setup.find("\n", insert_point) + 1
                
                new_setup = (
                    existing_setup[:insert_point] + 
                    "\n        # Register app commands for non-hybrid commands\n" +
                    "        from cogs.utils.app_command_utils import register_app_commands\n" +
                    "        register_app_commands(bot, cog)\n" +
                    existing_setup[insert_point:]
                )
                
                # Add return cog if it doesn't exist
                if "return cog" not in new_setup:
                    # Find where to add the return statement
                    if "logger.debug" in new_setup:
                        insert_point = new_setup.find("logger.debug")
                        insert_point = new_setup.find("\n", insert_point) + 1
                        new_setup = new_setup[:insert_point] + "        return cog\n" + new_setup[insert_point:]
                    else:
                        # Add at the end of the function
                        new_setup += "        return cog\n"
                
                # Update content
                new_content = content.replace(existing_setup, new_setup)
                with open(file_path, 'w') as f:
                    f.write(new_content)
                logger.info(f"Updated setup function in {file_path}")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Error updating {file_path}: {e}")
        return False

def main():
    """Main function to update all cogs."""
    # Ensure app_command_utils.py exists
    utils_dir = COGS_DIR / "utils"
    if not (utils_dir / "app_command_utils.py").exists():
        logger.error("app_command_utils.py not found in cogs/utils/ directory")
        return
    
    # Get all Python files in the cogs directory
    cog_files = []
    for root, dirs, files in os.walk(COGS_DIR):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                cog_files.append(os.path.join(root, file))
    
    # Update each cog
    updated_count = 0
    for file in cog_files:
        if update_cog_setup(file):
            updated_count += 1
    
    logger.info(f"Updated {updated_count} cogs")

if __name__ == "__main__":
    main()