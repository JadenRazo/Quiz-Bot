#!/usr/bin/env python3
"""
Shared Test Utilities for Educational Quiz Bot

This module provides common testing utilities to reduce code duplication
across test files, including configuration validation, mock object creation,
and common test patterns.

Usage:
    from tests.test_utils import ConfigValidator, MockObjects, TestMetrics
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ConfigValidator:
    """Shared configuration validation utilities."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config = None
        
    def validate_environment_file(self) -> bool:
        """Validate that .env file exists and is readable."""
        env_path = Path(".env")
        env_example_path = Path("env.example")
        
        if not env_path.exists():
            if env_example_path.exists():
                self.errors.append("❌ .env file not found. Copy env.example to .env and configure it.")
                return False
            else:
                self.errors.append("❌ Neither .env nor env.example found")
                return False
                
        # Check if .env is readable
        try:
            with open(env_path, 'r') as f:
                content = f.read()
                if len(content.strip()) == 0:
                    self.warnings.append("⚠️  .env file is empty")
        except Exception as e:
            self.errors.append(f"❌ Cannot read .env file: {e}")
            return False
            
        return True
    
    def validate_configuration_loading(self) -> bool:
        """Validate that configuration can be loaded successfully."""
        try:
            from config import load_config
            self.config = load_config()
            return True
        except Exception as e:
            self.errors.append(f"❌ Failed to load configuration: {e}")
            return False
    
    def validate_database_config(self) -> bool:
        """Validate database configuration completeness."""
        if not self.config or not hasattr(self.config, 'database'):
            self.errors.append("❌ No database configuration found")
            return False
            
        db_config = self.config.database
        required_fields = ['host', 'port', 'database', 'user', 'password']
        
        missing_fields = []
        for field in required_fields:
            if not hasattr(db_config, field) or not getattr(db_config, field):
                missing_fields.append(field)
                
        if missing_fields:
            self.errors.append(f"❌ Missing database configuration fields: {missing_fields}")
            return False
            
        # Check for placeholder values
        if db_config.password == "your_password":
            self.errors.append("❌ Database password is still placeholder")
            return False
            
        # Check connection pool settings
        if hasattr(db_config, 'min_connections') and hasattr(db_config, 'max_connections'):
            if db_config.min_connections > db_config.max_connections:
                self.warnings.append("⚠️  min_connections > max_connections")
                
        return True
    
    def validate_discord_config(self) -> bool:
        """Validate Discord bot configuration."""
        if not self.config:
            self.errors.append("❌ Configuration not loaded")
            return False
            
        # Check bot token
        if not self.config.bot_token:
            self.errors.append("❌ DISCORD_TOKEN is required")
            return False
        elif self.config.bot_token == "your_discord_bot_token_here":
            self.errors.append("❌ DISCORD_TOKEN is still the default placeholder")
            return False
        else:
            # Validate token format (should be base64-ish)
            if len(self.config.bot_token) < 50:
                self.warnings.append("⚠️  Discord token seems too short")
                
        # Check owner ID
        if not hasattr(self.config, 'owner_id') or not self.config.owner_id:
            self.warnings.append("⚠️  BOT_OWNER_ID not set - some commands won't work")
            
        return True
    
    def validate_llm_config(self) -> bool:
        """Validate LLM provider configuration."""
        if not self.config or not hasattr(self.config, 'llm'):
            self.errors.append("❌ LLM configuration not loaded")
            return False
            
        llm_config = self.config.llm
        
        # Check that at least one API key is configured
        providers = {}
        if hasattr(llm_config, 'openai') and llm_config.openai:
            providers['OpenAI'] = llm_config.openai.api_key
        if hasattr(llm_config, 'anthropic') and llm_config.anthropic:
            providers['Anthropic'] = llm_config.anthropic.api_key
        if hasattr(llm_config, 'google') and llm_config.google:
            providers['Google'] = llm_config.google.api_key
        
        configured_providers = []
        for provider, api_key in providers.items():
            if api_key and not api_key.endswith("_here"):
                configured_providers.append(provider)
                
        if not configured_providers:
            self.errors.append("❌ No LLM providers configured")
            return False
            
        # Check default provider
        if hasattr(llm_config, 'default_provider'):
            default_provider = llm_config.default_provider
            provider_names = ['openai', 'anthropic', 'google']
            
            if default_provider not in provider_names:
                self.warnings.append(f"⚠️  Unknown default provider: {default_provider}")
            else:
                # Check if default provider is actually configured
                provider_config = getattr(llm_config, default_provider, None)
                if not provider_config or not provider_config.api_key or provider_config.api_key.endswith("_here"):
                    self.warnings.append(f"⚠️  Default provider {default_provider} is not configured")
                    
        return True
    
    def validate_file_structure(self) -> bool:
        """Validate that required files and directories exist."""
        required_files = [
            "main.py",
            "config.py", 
            "requirements.txt",
            "db/schema.sql"
        ]
        
        required_dirs = [
            "cogs",
            "services",
            "utils", 
            "db",
            "tests"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
                
        missing_dirs = []
        for dir_path in required_dirs:
            if not Path(dir_path).is_dir():
                missing_dirs.append(dir_path)
                
        if missing_files:
            self.errors.append(f"❌ Missing files: {missing_files}")
            
        if missing_dirs:
            self.errors.append(f"❌ Missing directories: {missing_dirs}")
            
        return len(missing_files) == 0 and len(missing_dirs) == 0
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of configuration status."""
        if not self.config:
            return {"status": "error", "message": "Configuration not loaded"}
            
        summary = {"status": "success", "details": {}}
        
        # Database summary
        if hasattr(self.config, 'database'):
            db = self.config.database
            summary["details"]["database"] = {
                "host": db.host,
                "port": db.port,
                "database": db.database,
                "user": db.user,
                "password_set": bool(db.password and db.password != "your_password")
            }
            
        # LLM summary
        if hasattr(self.config, 'llm'):
            llm = self.config.llm
            summary["details"]["llm"] = {
                "providers_configured": [],
                "default_provider": getattr(llm, 'default_provider', None)
            }
            
            for provider in ['openai', 'anthropic', 'google']:
                if hasattr(llm, provider):
                    provider_config = getattr(llm, provider)
                    if provider_config and provider_config.api_key and not provider_config.api_key.endswith("_here"):
                        summary["details"]["llm"]["providers_configured"].append(provider)
                        
        # Bot summary
        summary["details"]["bot"] = {
            "token_set": bool(self.config.bot_token and self.config.bot_token != "your_discord_bot_token_here"),
            "owner_id_set": bool(getattr(self.config, 'owner_id', None))
        }
        
        return summary


class MockObjects:
    """Factory for creating mock Discord objects for testing."""
    
    @staticmethod
    def create_mock_user(user_id: int = 123456789, username: str = "TestUser"):
        """Create a mock Discord user."""
        from unittest.mock import Mock
        
        user = Mock()
        user.id = user_id
        user.name = username
        user.display_name = username
        user.mention = f"<@{user_id}>"
        return user
    
    @staticmethod
    def create_mock_guild(guild_id: int = 987654321, name: str = "TestGuild"):
        """Create a mock Discord guild."""
        from unittest.mock import Mock
        
        guild = Mock()
        guild.id = guild_id
        guild.name = name
        guild.me = MockObjects.create_mock_user(111111111, "QuizBot")
        return guild
    
    @staticmethod
    def create_mock_channel(channel_id: int = 555666777, name: str = "test-channel"):
        """Create a mock Discord channel."""
        from unittest.mock import Mock, AsyncMock
        
        channel = Mock()
        channel.id = channel_id
        channel.name = name
        channel.send = AsyncMock()
        return channel
    
    @staticmethod
    def create_mock_context(user_id: int = 123456789, guild_id: int = 987654321, channel_id: int = 555666777):
        """Create a mock Discord context."""
        from unittest.mock import Mock, AsyncMock
        
        ctx = Mock()
        ctx.author = MockObjects.create_mock_user(user_id)
        ctx.guild = MockObjects.create_mock_guild(guild_id)
        ctx.channel = MockObjects.create_mock_channel(channel_id)
        ctx.send = AsyncMock()
        ctx.bot = Mock()
        return ctx


class TestMetrics:
    """Utilities for collecting and analyzing test metrics."""
    
    def __init__(self):
        self.test_times: Dict[str, List[float]] = {}
        self.test_results: Dict[str, bool] = {}
        
    def record_test_time(self, test_name: str, duration: float):
        """Record the execution time of a test."""
        if test_name not in self.test_times:
            self.test_times[test_name] = []
        self.test_times[test_name].append(duration)
        
    def record_test_result(self, test_name: str, passed: bool):
        """Record whether a test passed or failed."""
        self.test_results[test_name] = passed
        
    def get_slowest_tests(self, limit: int = 5) -> List[Tuple[str, float]]:
        """Get the slowest tests by average execution time."""
        import statistics
        
        avg_times = []
        for test_name, times in self.test_times.items():
            if times:
                avg_time = statistics.mean(times)
                avg_times.append((test_name, avg_time))
                
        avg_times.sort(key=lambda x: x[1], reverse=True)
        return avg_times[:limit]
    
    def get_failure_rate(self) -> float:
        """Get the overall test failure rate."""
        if not self.test_results:
            return 0.0
            
        failed_count = sum(1 for passed in self.test_results.values() if not passed)
        return failed_count / len(self.test_results)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of test metrics."""
        import statistics
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for passed in self.test_results.values() if passed)
        
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "pass_rate": passed_tests / total_tests if total_tests > 0 else 0.0,
            "execution_times": {}
        }
        
        if self.test_times:
            all_times = []
            for times in self.test_times.values():
                all_times.extend(times)
                
            if all_times:
                summary["execution_times"] = {
                    "total_time": sum(all_times),
                    "average_time": statistics.mean(all_times),
                    "median_time": statistics.median(all_times),
                    "slowest_tests": self.get_slowest_tests()
                }
                
        return summary


def setup_test_logging(test_name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up standardized logging for tests."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(test_name)


def validate_test_environment() -> Tuple[bool, List[str], List[str]]:
    """Perform a quick validation of the test environment."""
    validator = ConfigValidator()
    
    # Run all validations
    env_valid = validator.validate_environment_file()
    config_valid = validator.validate_configuration_loading() if env_valid else False
    db_valid = validator.validate_database_config() if config_valid else False
    discord_valid = validator.validate_discord_config() if config_valid else False
    llm_valid = validator.validate_llm_config() if config_valid else False
    files_valid = validator.validate_file_structure()
    
    overall_valid = all([env_valid, config_valid, db_valid, discord_valid, llm_valid, files_valid])
    
    return overall_valid, validator.errors, validator.warnings