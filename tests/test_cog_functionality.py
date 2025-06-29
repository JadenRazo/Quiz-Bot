#!/usr/bin/env python3
"""
Discord Cog Functionality Test for Educational Quiz Bot

This test validates that all Discord cogs can be loaded and their basic
functionality works correctly.

Usage:
    python tests/test_cog_functionality.py
"""

import os
import sys
import asyncio
import logging
import discord
from typing import List, Dict, Any, Optional, Set
from unittest.mock import Mock, AsyncMock, MagicMock

# Add parent directory to path  
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import shared test utilities
from test_utils import ConfigValidator, MockObjects, setup_test_logging

# Setup logging using shared utility
logger = setup_test_logging("cog_test")

class CogFunctionalityTester:
    """Test Discord cog functionality."""
    
    def __init__(self):
        self.config = None
        self.bot = None
        self.context = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.loaded_cogs: Set[str] = set()
        
    async def run_all_tests(self) -> bool:
        """Run all cog functionality tests."""
        logger.info("=" * 60)
        logger.info("Educational Quiz Bot - Cog Functionality Test")
        logger.info("=" * 60)
        
        tests = [
            self.test_config_loading,
            self.test_bot_initialization,
            self.test_context_creation,
            self.test_cog_loading,
            self.test_cog_commands,
            self.test_cog_error_handling,
            self.test_cog_permissions
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
        
    async def test_config_loading(self) -> bool:
        """Test configuration loading."""
        logger.info("\n🔧 Testing configuration loading...")
        
        validator = ConfigValidator()
        result = validator.validate_configuration_loading()
        self.config = validator.config
        
        if result:
            logger.info("✅ Configuration loaded successfully")
        else:
            self.errors.extend(validator.errors)
            for error in validator.errors:
                logger.error(error)
                
        return result
            
    async def test_bot_initialization(self) -> bool:
        """Test bot initialization without actually starting it."""
        logger.info("\n🤖 Testing bot initialization...")
        
        try:
            from discord.ext import commands
            from utils.context import BotContext
            
            # Create a mock bot for testing
            intents = discord.Intents.default()
            intents.message_content = True
            intents.guilds = True
            intents.guild_messages = True
            
            self.bot = commands.AutoShardedBot(
                command_prefix="!",
                intents=intents,
                help_command=None
            )
            
            logger.info("✅ Bot initialized successfully")
            return True
        except Exception as e:
            self.errors.append(f"❌ Failed to initialize bot: {e}")
            logger.error(f"❌ Failed to initialize bot: {e}")
            return False
            
    async def test_context_creation(self) -> bool:
        """Test BotContext creation."""
        logger.info("\n🔗 Testing context creation...")
        
        try:
            from utils.context import BotContext
            from services.database_service import DatabaseService
            from services.llm_service import LLMService
            
            # Create mock services
            db_service = Mock(spec=DatabaseService)
            llm_service = Mock(spec=LLMService)
            
            # Create context
            self.context = BotContext(
                bot=self.bot,
                config=self.config,
                db_service=db_service,
                llm_service=llm_service
            )
            
            logger.info("✅ Context created successfully")
            return True
        except Exception as e:
            self.errors.append(f"❌ Failed to create context: {e}")
            logger.error(f"❌ Failed to create context: {e}")
            return False
            
    async def test_cog_loading(self) -> bool:
        """Test loading all cogs."""
        logger.info("\n⚙️  Testing cog loading...")
        
        if not self.bot or not self.context:
            self.errors.append("❌ Bot or context not initialized")
            return False
            
        # List of expected cogs
        expected_cogs = [
            'admin',
            'quiz', 
            'group_quiz',
            'stats',
            'help',
            'faq',
            'onboarding',
            'preferences',
            'guild_preferences',
            'custom_quiz',
            'version'
        ]
        
        loaded_successfully = []
        failed_to_load = []
        
        for cog_name in expected_cogs:
            try:
                logger.info(f"   Loading {cog_name}...")
                
                # Import the cog module
                cog_module = __import__(f"cogs.{cog_name}", fromlist=[cog_name])
                
                # Check if it has setup_with_context function
                if hasattr(cog_module, 'setup_with_context'):
                    # Use setup_with_context for proper initialization
                    cog_instance = await cog_module.setup_with_context(self.bot, self.context)
                elif hasattr(cog_module, 'setup'):
                    # Fallback to regular setup
                    cog_instance = await cog_module.setup(self.bot)
                else:
                    raise Exception(f"No setup function found in {cog_name}")
                    
                self.loaded_cogs.add(cog_name)
                loaded_successfully.append(cog_name)
                logger.info(f"   ✅ {cog_name} loaded successfully")
                
            except Exception as e:
                failed_to_load.append((cog_name, str(e)))
                logger.error(f"   ❌ Failed to load {cog_name}: {e}")
                
        # Summary
        logger.info(f"\n✅ Successfully loaded {len(loaded_successfully)} cogs:")
        for cog in loaded_successfully:
            logger.info(f"   • {cog}")
            
        if failed_to_load:
            logger.error(f"\n❌ Failed to load {len(failed_to_load)} cogs:")
            for cog, error in failed_to_load:
                logger.error(f"   • {cog}: {error}")
                self.errors.append(f"Failed to load cog {cog}: {error}")
                
        return len(failed_to_load) == 0
        
    async def test_cog_commands(self) -> bool:
        """Test that cogs have expected commands."""
        logger.info("\n📋 Testing cog commands...")
        
        if not self.bot:
            self.errors.append("❌ Bot not initialized")
            return False
            
        # Expected commands per cog
        expected_commands = {
            'quiz': ['quiz', 'start_quiz'],
            'admin': ['admin', 'reload'],
            'stats': ['stats', 'leaderboard'],
            'help': ['help'],
            'faq': ['faq'],
            'preferences': ['preferences'],
            'custom_quiz': ['custom_quiz']
        }
        
        all_commands_found = True
        
        for cog_name, commands in expected_commands.items():
            if cog_name not in self.loaded_cogs:
                continue
                
            cog = self.bot.get_cog(cog_name.title() + "Cog")  # Cogs typically have "Cog" suffix
            if not cog:
                # Try alternative naming
                cog = self.bot.get_cog(cog_name.title() + "Commands")
                if not cog:
                    cog = self.bot.get_cog(cog_name.title())
                    
            if not cog:
                logger.warning(f"   ⚠️  Could not find cog instance for {cog_name}")
                self.warnings.append(f"Could not find cog instance for {cog_name}")
                continue
                
            logger.info(f"   Testing commands for {cog_name}...")
            
            for command_name in commands:
                command = self.bot.get_command(command_name)
                if command:
                    logger.info(f"     ✅ Command '{command_name}' found")
                else:
                    logger.warning(f"     ⚠️  Command '{command_name}' not found")
                    self.warnings.append(f"Command '{command_name}' not found in {cog_name}")
                    
        # Check for slash commands if available
        if hasattr(self.bot, 'tree') and self.bot.tree:
            slash_commands = self.bot.tree.get_commands()
            if slash_commands:
                logger.info(f"   ✅ Found {len(slash_commands)} slash commands")
            else:
                logger.warning("   ⚠️  No slash commands found")
                
        return all_commands_found
        
    async def test_cog_error_handling(self) -> bool:
        """Test cog error handling."""
        logger.info("\n🛡️  Testing cog error handling...")
        
        if not self.bot:
            self.errors.append("❌ Bot not initialized")
            return False
            
        # Test that cogs can handle invalid inputs gracefully
        test_passed = True
        
        for cog_name in self.loaded_cogs:
            cog = self.bot.get_cog(cog_name.title() + "Cog")
            if not cog:
                continue
                
            # Check if cog has error handling methods
            has_error_handler = (
                hasattr(cog, 'cog_command_error') or
                hasattr(cog, 'on_command_error') or
                hasattr(cog, 'handle_error')
            )
            
            if has_error_handler:
                logger.info(f"   ✅ {cog_name} has error handling")
            else:
                logger.warning(f"   ⚠️  {cog_name} may not have error handling")
                self.warnings.append(f"{cog_name} may not have error handling")
                
        return test_passed
        
    async def test_cog_permissions(self) -> bool:
        """Test cog permission checking."""
        logger.info("\n🔒 Testing cog permissions...")
        
        if not self.bot:
            self.errors.append("❌ Bot not initialized")
            return False
            
        # Test that admin cogs have proper permission checks
        admin_cogs = ['admin', 'version']
        
        for cog_name in admin_cogs:
            if cog_name not in self.loaded_cogs:
                continue
                
            cog = self.bot.get_cog(cog_name.title() + "Cog")
            if not cog:
                continue
                
            # Check commands for permission decorators
            commands = cog.get_commands() if hasattr(cog, 'get_commands') else []
            
            has_permissions = False
            for command in commands:
                if hasattr(command, 'checks') and command.checks:
                    has_permissions = True
                    break
                    
            if has_permissions:
                logger.info(f"   ✅ {cog_name} has permission checks")
            else:
                logger.warning(f"   ⚠️  {cog_name} may not have permission checks")
                self.warnings.append(f"{cog_name} may not have permission checks")
                
        return True
        
    def _show_summary(self) -> None:
        """Show test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("COG FUNCTIONALITY TEST SUMMARY")
        logger.info("=" * 60)
        
        if self.loaded_cogs:
            logger.info(f"✅ Successfully loaded {len(self.loaded_cogs)} cogs:")
            for cog in sorted(self.loaded_cogs):
                logger.info(f"   • {cog}")
                
        if self.errors:
            logger.error(f"\n❌ {len(self.errors)} ERRORS FOUND:")
            for error in self.errors:
                logger.error(f"   {error}")
                
        if self.warnings:
            logger.warning(f"\n⚠️  {len(self.warnings)} WARNINGS:")
            for warning in self.warnings:
                logger.warning(f"   {warning}")
                
        if not self.errors and not self.warnings:
            logger.info("\n✅ All cog functionality tests passed!")
        elif not self.errors:
            logger.info("\n✅ Cogs are working (with warnings)")
        else:
            logger.error("\n❌ Cogs have errors that must be fixed")
            
        logger.info("=" * 60)


# Mock classes are now provided by shared test utilities
# See MockObjects class in test_utils.py for:
# - create_mock_user()
# - create_mock_guild() 
# - create_mock_channel()
# - create_mock_context()


async def main() -> int:
    """Run cog functionality tests."""
    tester = CogFunctionalityTester()
    success = await tester.run_all_tests()
    
    if success:
        logger.info("\n🎉 All cogs are working correctly!")
        return 0
    else:
        logger.error("\n❌ Please fix the cog issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))