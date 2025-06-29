#!/usr/bin/env python3
"""
Configuration Validation Test for Educational Quiz Bot

This test validates that all configuration is properly loaded and all required
environment variables are set correctly.

Usage:
    python tests/test_configuration.py
"""

import os
import sys
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import shared test utilities
from test_utils import ConfigValidator, setup_test_logging

# Setup logging using shared utility
logger = setup_test_logging("config_test")

class ConfigurationTester:
    """Test configuration loading and validation using shared utilities."""
    
    def __init__(self):
        self.validator = ConfigValidator()
        self.config = None
        
    def run_all_tests(self) -> bool:
        """Run all configuration tests."""
        logger.info("=" * 60)
        logger.info("Educational Quiz Bot - Configuration Test")
        logger.info("=" * 60)
        
        tests = [
            self.test_env_file_exists,
            self.test_config_loading,
            self.test_discord_config,
            self.test_database_config,
            self.test_llm_config,
            self.test_quiz_config,
            self.test_file_structure,
            self.test_python_environment
        ]
        
        all_passed = True
        for test in tests:
            try:
                if not test():
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ Test {test.__name__} failed with exception: {e}")
                all_passed = False
                
        # Show summary
        self._show_summary()
        return all_passed and len(self.validator.errors) == 0
        
    def test_env_file_exists(self) -> bool:
        """Test that .env file exists and is readable."""
        logger.info("\n📁 Testing .env file...")
        
        result = self.validator.validate_environment_file()
        
        if result:
            logger.info("✅ .env file exists and is readable")
        else:
            for error in self.validator.errors:
                logger.error(error)
                if "Copy env.example" in error:
                    logger.info("   📝 Copy env.example to .env and configure it:")
                    logger.info("   cp env.example .env")
                    
        for warning in self.validator.warnings:
            logger.warning(warning)
            
        return result
        
    def test_config_loading(self) -> bool:
        """Test that configuration can be loaded."""
        logger.info("\n🔧 Testing configuration loading...")
        
        result = self.validator.validate_configuration_loading()
        self.config = self.validator.config
        
        if result:
            logger.info("✅ Configuration loaded successfully")
        else:
            for error in self.validator.errors:
                logger.error(error)
                
        return result
            
    def test_discord_config(self) -> bool:
        """Test Discord bot configuration."""
        logger.info("\n🤖 Testing Discord configuration...")
        
        result = self.validator.validate_discord_config()
        
        if result:
            logger.info("✅ Discord token is configured")
            if hasattr(self.config, 'owner_id') and self.config.owner_id:
                logger.info(f"✅ Bot owner ID: {self.config.owner_id}")
        else:
            for error in self.validator.errors:
                if "DISCORD_TOKEN" in error:
                    logger.error(error)
                    if "required" in error:
                        logger.info("   Set DISCORD_TOKEN in your .env file")
                        
        for warning in self.validator.warnings:
            if "Discord token" in warning or "BOT_OWNER_ID" in warning:
                logger.warning(warning)
                
        return result
        
    def test_database_config(self) -> bool:
        """Test database configuration."""
        logger.info("\n💾 Testing database configuration...")
        
        result = self.validator.validate_database_config()
        
        if result and self.config and self.config.database:
            db_config = self.config.database
            # Log configuration (without password)
            logger.info("✅ Database configuration:")
            logger.info(f"   Host: {db_config.host}")
            logger.info(f"   Port: {db_config.port}")
            logger.info(f"   Database: {db_config.database}")
            logger.info(f"   User: {db_config.user}")
            logger.info(f"   Password: {'*' * len(db_config.password)}")
        else:
            for error in self.validator.errors:
                if "Missing database" in error or "Database password" in error:
                    logger.error(error)
                    
        for warning in self.validator.warnings:
            if "connections" in warning:
                logger.warning(warning)
                
        return result
        
    def test_llm_config(self) -> bool:
        """Test LLM provider configuration."""
        logger.info("\n🧠 Testing LLM configuration...")
        
        result = self.validator.validate_llm_config()
        
        if result and self.config and self.config.llm:
            llm_config = self.config.llm
            
            # Log configured providers
            for provider in ['openai', 'anthropic', 'google']:
                if hasattr(llm_config, provider):
                    provider_config = getattr(llm_config, provider)
                    if provider_config and provider_config.api_key and not provider_config.api_key.endswith("_here"):
                        logger.info(f"✅ {provider.title()} API key configured")
                    else:
                        logger.warning(f"⚠️  {provider.title()} API key not configured")
                        
            # Log default provider
            if hasattr(llm_config, 'default_provider'):
                logger.info(f"✅ Default provider: {llm_config.default_provider}")
                
        else:
            for error in self.validator.errors:
                if "LLM" in error:
                    logger.error(error)
                    if "No LLM providers" in error:
                        logger.error("   Configure at least one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_AI_API_KEY")
                        
        for warning in self.validator.warnings:
            if "provider" in warning:
                logger.warning(warning)
                
        return result
        
    def test_quiz_config(self) -> bool:
        """Test quiz configuration."""
        logger.info("\n🎯 Testing quiz configuration...")
        
        if not self.config or not self.config.quiz:
            self.errors.append("❌ Quiz configuration not loaded")
            return False
            
        quiz_config = self.config.quiz
        
        # Validate ranges
        if quiz_config.default_question_count < 1 or quiz_config.default_question_count > 50:
            self.warnings.append("⚠️  default_question_count should be 1-50")
            logger.warning("⚠️  default_question_count should be 1-50")
            
        if quiz_config.default_timeout < 10 or quiz_config.default_timeout > 300:
            self.warnings.append("⚠️  default_timeout should be 10-300 seconds")
            logger.warning("⚠️  default_timeout should be 10-300 seconds")
            
        logger.info("✅ Quiz configuration loaded:")
        logger.info(f"   Default questions: {quiz_config.default_question_count}")
        logger.info(f"   Default timeout: {quiz_config.default_timeout}s")
        logger.info(f"   Categories: {len(quiz_config.categories)}")
        logger.info(f"   Difficulty levels: {', '.join(quiz_config.difficulty_levels)}")
        
        return True
        
    def test_file_structure(self) -> bool:
        """Test that required files and directories exist."""
        logger.info("\n📂 Testing file structure...")
        
        result = self.validator.validate_file_structure()
        
        if result:
            logger.info("✅ All required files and directories present")
        else:
            for error in self.validator.errors:
                if "Missing files" in error or "Missing directories" in error:
                    logger.error(error)
                    
        return result
        
    def test_python_environment(self) -> bool:
        """Test Python environment and dependencies."""
        logger.info("\n🐍 Testing Python environment...")
        
        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 8):
            self.errors.append(f"❌ Python 3.8+ required, found {python_version.major}.{python_version.minor}")
            logger.error(f"❌ Python 3.8+ required, found {python_version.major}.{python_version.minor}")
            return False
        else:
            logger.info(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
            
        # Check critical imports
        critical_imports = [
            ("discord", "discord.py"),
            ("asyncpg", "asyncpg"),
            ("pydantic", "pydantic"),
            ("dotenv", "python-dotenv")
        ]
        
        missing_imports = []
        for module, package in critical_imports:
            try:
                __import__(module)
                logger.info(f"✅ {package} available")
            except ImportError:
                missing_imports.append(package)
                logger.error(f"❌ {package} not installed")
                
        if missing_imports:
            self.errors.append(f"❌ Missing packages: {missing_imports}")
            logger.error("   Install with: pip install -r requirements.txt")
            return False
            
        # Check virtual environment
        venv_path = "/root/bot-env/"
        if Path(venv_path).exists():
            logger.info(f"✅ Virtual environment found at {venv_path}")
        else:
            self.warnings.append("⚠️  Expected virtual environment not found at /root/bot-env/")
            logger.warning("⚠️  Expected virtual environment not found at /root/bot-env/")
            
        return True
        
    def _show_summary(self) -> None:
        """Show test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("CONFIGURATION TEST SUMMARY")
        logger.info("=" * 60)
        
        all_errors = self.validator.errors
        all_warnings = self.validator.warnings
        
        if all_errors:
            logger.error(f"❌ {len(all_errors)} ERRORS FOUND:")
            for error in all_errors:
                logger.error(f"   {error}")
                
        if all_warnings:
            logger.warning(f"⚠️  {len(all_warnings)} WARNINGS:")
            for warning in all_warnings:
                logger.warning(f"   {warning}")
                
        if not self.validator.errors and not self.validator.warnings:
            logger.info("✅ All configuration tests passed!")
        elif not self.validator.errors:
            logger.info("✅ Configuration is valid (with warnings)")
        else:
            logger.error("❌ Configuration has errors that must be fixed")
            
        logger.info("=" * 60)


def main() -> int:
    """Run configuration tests."""
    tester = ConfigurationTester()
    success = tester.run_all_tests()
    
    if success:
        logger.info("\n🎉 Configuration is ready! You can now:")
        logger.info("   1. Test database connection: python tests/test_database_setup.py")
        logger.info("   2. Run the bot: python main.py")
        return 0
    else:
        logger.error("\n❌ Please fix the configuration issues above before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())