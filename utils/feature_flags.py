import json
import logging
import os
from enum import Enum
from typing import Dict, Optional, Any, List, Union, Set

logger = logging.getLogger("bot.features")

class FeatureFlag(Enum):
    """Enumeration of available feature flags."""
    GROUP_QUIZ = "group_quiz"
    PRIVATE_QUIZZES = "private_quizzes"
    LLM_ANTHROPIC = "llm_anthropic"
    LLM_OPENAI = "llm_openai"
    LLM_GOOGLE = "llm_google"
    ACHIEVEMENTS = "achievements"
    LEADERBOARD = "leaderboard"
    ADVANCED_QUIZ_OPTIONS = "advanced_quiz_options"
    FLASHCARDS = "flashcards"
    LEARNING_PATHS = "learning_paths"
    DEBUG_MODE = "debug_mode"


class FeatureManager:
    """Manages feature flags for the bot, supporting per-guild configuration."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the feature manager.
        
        Args:
            data_dir: Directory to store feature flag data
        """
        self.data_dir = data_dir
        self.flags_file = os.path.join(data_dir, "feature_flags.json")
        self.global_flags: Dict[str, bool] = {}
        self.guild_flags: Dict[int, Dict[str, bool]] = {}
        
        # Create the data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize feature flags with defaults
        self._initialize_defaults()
        
        # Load saved feature flags
        self._load_flags()
    
    def _initialize_defaults(self) -> None:
        """Initialize default values for all feature flags."""
        # Default values for features (all enabled by default)
        self.global_flags = {
            flag.value: True for flag in FeatureFlag
        }
        
        # Special debug flag disabled by default
        self.global_flags[FeatureFlag.DEBUG_MODE.value] = False
        
        # Default guild overrides
        self.guild_flags = {}
    
    def _load_flags(self) -> None:
        """Load feature flags from file."""
        try:
            if os.path.exists(self.flags_file):
                with open(self.flags_file, 'r') as f:
                    data = json.load(f)
                    
                    # Load global flags (use defaults for missing flags)
                    if "global" in data:
                        for flag, value in data["global"].items():
                            if flag in self.global_flags:
                                self.global_flags[flag] = value
                    
                    # Load guild-specific flags
                    if "guilds" in data:
                        for guild_id_str, flags in data["guilds"].items():
                            try:
                                guild_id = int(guild_id_str)
                                self.guild_flags[guild_id] = {}
                                for flag, value in flags.items():
                                    if flag in self.global_flags:
                                        self.guild_flags[guild_id][flag] = value
                            except ValueError:
                                logger.warning(f"Invalid guild ID in feature flags: {guild_id_str}")
                
                logger.info(f"Loaded feature flags from {self.flags_file}")
        except Exception as e:
            logger.error(f"Error loading feature flags: {e}")
    
    def _save_flags(self) -> None:
        """Save feature flags to file."""
        try:
            data = {
                "global": self.global_flags,
                "guilds": {str(guild_id): flags for guild_id, flags in self.guild_flags.items()}
            }
            
            with open(self.flags_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Saved feature flags to {self.flags_file}")
        except Exception as e:
            logger.error(f"Error saving feature flags: {e}")
    
    def is_enabled(self, feature: Union[str, FeatureFlag], guild_id: Optional[int] = None) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature: The feature to check (can be FeatureFlag enum or string)
            guild_id: Guild ID to check overrides for (None for global setting)
            
        Returns:
            True if the feature is enabled, False otherwise
        """
        feature_key = feature.value if isinstance(feature, FeatureFlag) else feature
        
        # Check if valid feature
        if feature_key not in self.global_flags:
            logger.warning(f"Unknown feature flag: {feature_key}")
            return False
        
        # Check guild-specific override if provided
        if guild_id is not None and guild_id in self.guild_flags:
            guild_settings = self.guild_flags[guild_id]
            if feature_key in guild_settings:
                return guild_settings[feature_key]
        
        # Fall back to global setting
        return self.global_flags.get(feature_key, False)
    
    def set_global_flag(self, feature: Union[str, FeatureFlag], enabled: bool) -> None:
        """
        Set a global feature flag.
        
        Args:
            feature: The feature to set (can be FeatureFlag enum or string)
            enabled: Whether the feature should be enabled
        """
        feature_key = feature.value if isinstance(feature, FeatureFlag) else feature
        
        # Validate feature key
        if feature_key not in self.global_flags:
            logger.warning(f"Attempt to set unknown feature flag: {feature_key}")
            return
        
        # Update the flag
        self.global_flags[feature_key] = enabled
        logger.info(f"Set global feature flag {feature_key} to {enabled}")
        
        # Save changes
        self._save_flags()
    
    def set_guild_flag(self, guild_id: int, feature: Union[str, FeatureFlag], enabled: bool) -> None:
        """
        Set a guild-specific feature flag override.
        
        Args:
            guild_id: Discord guild ID
            feature: The feature to set (can be FeatureFlag enum or string)
            enabled: Whether the feature should be enabled
        """
        feature_key = feature.value if isinstance(feature, FeatureFlag) else feature
        
        # Validate feature key
        if feature_key not in self.global_flags:
            logger.warning(f"Attempt to set unknown guild feature flag: {feature_key}")
            return
        
        # Initialize guild settings if needed
        if guild_id not in self.guild_flags:
            self.guild_flags[guild_id] = {}
        
        # Update the flag
        self.guild_flags[guild_id][feature_key] = enabled
        logger.info(f"Set guild {guild_id} feature flag {feature_key} to {enabled}")
        
        # Save changes
        self._save_flags()
    
    def reset_guild_flag(self, guild_id: int, feature: Union[str, FeatureFlag]) -> None:
        """
        Reset a guild-specific feature flag override to use the global setting.
        
        Args:
            guild_id: Discord guild ID
            feature: The feature to reset (can be FeatureFlag enum or string)
        """
        feature_key = feature.value if isinstance(feature, FeatureFlag) else feature
        
        # Check if guild has overrides
        if guild_id in self.guild_flags:
            if feature_key in self.guild_flags[guild_id]:
                del self.guild_flags[guild_id][feature_key]
                logger.info(f"Reset guild {guild_id} feature flag {feature_key} to global setting")
                
                # Remove guild entry if it's now empty
                if not self.guild_flags[guild_id]:
                    del self.guild_flags[guild_id]
                
                # Save changes
                self._save_flags()
    
    def reset_guild_flags(self, guild_id: int) -> None:
        """
        Reset all guild-specific feature flag overrides.
        
        Args:
            guild_id: Discord guild ID
        """
        if guild_id in self.guild_flags:
            del self.guild_flags[guild_id]
            logger.info(f"Reset all feature flags for guild {guild_id}")
            
            # Save changes
            self._save_flags()
    
    def get_all_features(self) -> List[Dict[str, Any]]:
        """
        Get information about all available features.
        
        Returns:
            List of dictionaries with feature information
        """
        features = []
        
        for flag in FeatureFlag:
            features.append({
                "id": flag.value,
                "name": flag.name,
                "enabled": self.global_flags.get(flag.value, False)
            })
            
        return features
    
    def get_guild_features(self, guild_id: int) -> Dict[str, Any]:
        """
        Get guild-specific feature settings.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary with global and overridden settings for the guild
        """
        # Get all features with their global value
        all_features = {
            flag.value: self.global_flags.get(flag.value, False) 
            for flag in FeatureFlag
        }
        
        # Get guild overrides
        guild_overrides = {}
        if guild_id in self.guild_flags:
            guild_overrides = self.guild_flags[guild_id]
        
        return {
            "global": all_features,
            "overrides": guild_overrides,
            "effective": {
                k: guild_overrides.get(k, v) for k, v in all_features.items()
            }
        }


# Singleton instance
feature_manager = FeatureManager() 