"""
UI Configuration Module for Discord Quiz Bot

This module provides centralized configuration for all UI-related settings,
timeouts, limits, and other configurable values to avoid hardcoding throughout
the persistent UI system.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import timedelta


@dataclass
class UITimeouts:
    """Timeout configurations for UI elements."""
    
    # Button timeouts (in minutes)
    DEFAULT_BUTTON_TIMEOUT: int = 30
    NAVIGATION_TIMEOUT: int = 30
    FAQ_TIMEOUT: int = 15
    STATS_TIMEOUT: int = 30
    HELP_TIMEOUT: int = 60  # Help buttons last longer
    WELCOME_TIMEOUT: Optional[int] = None  # Welcome buttons never expire
    
    # Toggle timeouts (in hours)
    TOGGLE_TIMEOUT_HOURS: int = 1
    LEADERBOARD_TOGGLE_TIMEOUT_HOURS: int = 1
    
    # View timeouts (in minutes)
    VIEW_DEFAULT_TIMEOUT: int = 30
    MODAL_TIMEOUT: int = 15
    CONFIRMATION_TIMEOUT: int = 5
    
    @classmethod
    def from_env(cls) -> 'UITimeouts':
        """Create UITimeouts from environment variables with fallbacks."""
        return cls(
            DEFAULT_BUTTON_TIMEOUT=int(os.getenv('UI_DEFAULT_TIMEOUT_MINUTES', '30')),
            NAVIGATION_TIMEOUT=int(os.getenv('UI_NAVIGATION_TIMEOUT_MINUTES', '30')),
            FAQ_TIMEOUT=int(os.getenv('UI_FAQ_TIMEOUT_MINUTES', '15')),
            STATS_TIMEOUT=int(os.getenv('UI_STATS_TIMEOUT_MINUTES', '30')),
            HELP_TIMEOUT=int(os.getenv('UI_HELP_TIMEOUT_MINUTES', '60')),
            TOGGLE_TIMEOUT_HOURS=int(os.getenv('UI_TOGGLE_TIMEOUT_HOURS', '1')),
            LEADERBOARD_TOGGLE_TIMEOUT_HOURS=int(os.getenv('UI_LEADERBOARD_TIMEOUT_HOURS', '1')),
            VIEW_DEFAULT_TIMEOUT=int(os.getenv('UI_VIEW_TIMEOUT_MINUTES', '30')),
            MODAL_TIMEOUT=int(os.getenv('UI_MODAL_TIMEOUT_MINUTES', '15')),
            CONFIRMATION_TIMEOUT=int(os.getenv('UI_CONFIRMATION_TIMEOUT_MINUTES', '5'))
        )
    
    def get_timeout_delta(self, timeout_type: str) -> Optional[timedelta]:
        """Get timedelta for a specific timeout type."""
        timeout_map = {
            'default': self.DEFAULT_BUTTON_TIMEOUT,
            'navigation': self.NAVIGATION_TIMEOUT,
            'faq': self.FAQ_TIMEOUT,
            'stats': self.STATS_TIMEOUT,
            'help': self.HELP_TIMEOUT,
            'welcome': self.WELCOME_TIMEOUT,
            'view': self.VIEW_DEFAULT_TIMEOUT,
            'modal': self.MODAL_TIMEOUT,
            'confirmation': self.CONFIRMATION_TIMEOUT
        }
        
        timeout_minutes = timeout_map.get(timeout_type)
        if timeout_minutes is None:
            return None
        return timedelta(minutes=timeout_minutes)
    
    def get_toggle_timeout_delta(self, toggle_type: str = 'default') -> timedelta:
        """Get timedelta for toggle timeout."""
        if toggle_type == 'leaderboard':
            return timedelta(hours=self.LEADERBOARD_TOGGLE_TIMEOUT_HOURS)
        return timedelta(hours=self.TOGGLE_TIMEOUT_HOURS)


@dataclass
class UILimits:
    """Discord and system limits for UI components."""
    
    # Discord API limits
    CUSTOM_ID_MAX_LENGTH: int = 100
    EMBED_TITLE_MAX_LENGTH: int = 256
    EMBED_DESCRIPTION_MAX_LENGTH: int = 4096
    EMBED_FIELD_VALUE_MAX_LENGTH: int = 1024
    EMBED_FOOTER_MAX_LENGTH: int = 2048
    EMBED_TOTAL_MAX_LENGTH: int = 6000
    
    # Button limits
    BUTTON_LABEL_MAX_LENGTH: int = 80
    BUTTONS_PER_ROW: int = 5
    MAX_BUTTON_ROWS: int = 5
    MAX_BUTTONS_PER_VIEW: int = 25
    
    # State encoding limits
    ENCODED_STATE_MAX_LENGTH: int = 85  # Slightly increased for basic toggle states
    MAX_STATE_COMPLEXITY: int = 1000  # Max JSON string length before DB fallback
    
    # Pagination limits
    MAX_ITEMS_PER_PAGE: int = 10
    MAX_PAGES_FOR_NAVIGATION: int = 100
    
    @classmethod
    def from_env(cls) -> 'UILimits':
        """Create UILimits from environment variables with fallbacks."""
        return cls(
            CUSTOM_ID_MAX_LENGTH=int(os.getenv('UI_CUSTOM_ID_MAX_LENGTH', '100')),
            ENCODED_STATE_MAX_LENGTH=int(os.getenv('UI_ENCODED_STATE_MAX_LENGTH', '80')),
            MAX_STATE_COMPLEXITY=int(os.getenv('UI_MAX_STATE_COMPLEXITY', '1000')),
            MAX_ITEMS_PER_PAGE=int(os.getenv('UI_MAX_ITEMS_PER_PAGE', '10')),
            MAX_PAGES_FOR_NAVIGATION=int(os.getenv('UI_MAX_PAGES_FOR_NAVIGATION', '100'))
        )


@dataclass
class UIPrefixes:
    """String prefixes and identifiers for UI components."""
    
    # Button prefixes
    PERSISTENT_BUTTON_PREFIX: str = "pui"
    DATABASE_PREFIX: str = "db"
    MEMORY_PREFIX: str = "mem"
    LEGACY_PREFIX: str = "pb"  # For backward compatibility
    
    # Action prefixes
    NAVIGATION_PREFIX: str = "nav"
    TOGGLE_PREFIX: str = "toggle"
    ACTION_PREFIX: str = "action"
    MODAL_PREFIX: str = "modal"
    CONFIRM_PREFIX: str = "confirm"
    
    # Database table names
    PERSISTENT_BUTTONS_TABLE: str = "persistent_buttons"
    BUTTON_STATES_TABLE: str = "button_states"
    UI_SETTINGS_TABLE: str = "ui_settings"
    
    @classmethod
    def from_env(cls) -> 'UIPrefixes':
        """Create UIPrefixes from environment variables with fallbacks."""
        return cls(
            PERSISTENT_BUTTON_PREFIX=os.getenv('UI_BUTTON_PREFIX', 'pui'),
            DATABASE_PREFIX=os.getenv('UI_DB_PREFIX', 'db'),
            MEMORY_PREFIX=os.getenv('UI_MEMORY_PREFIX', 'mem'),
            PERSISTENT_BUTTONS_TABLE=os.getenv('UI_BUTTONS_TABLE', 'persistent_buttons')
        )


@dataclass
class UIActions:
    """Predefined action types and configurations."""
    
    # Welcome actions
    WELCOME_ACTIONS: List[str] = field(default_factory=lambda: ['quiz', 'guide', 'commands'])
    
    # Help actions
    HELP_ACTIONS: List[str] = field(default_factory=lambda: ['guide', 'support', 'menu', 'close'])
    
    # Navigation actions
    NAVIGATION_ACTIONS: List[str] = field(default_factory=lambda: ['prev', 'next', 'first', 'last'])
    
    # Toggle types
    TOGGLE_TYPES: List[str] = field(default_factory=lambda: ['leaderboard', 'scope', 'visibility', 'notifications'])
    
    # Modal actions
    MODAL_ACTIONS: List[str] = field(default_factory=lambda: ['create_quiz', 'edit_preferences', 'report_issue'])
    
    @classmethod
    def from_env(cls) -> 'UIActions':
        """Create UIActions from environment variables with fallbacks."""
        welcome_actions = os.getenv('UI_WELCOME_ACTIONS', 'quiz,guide,commands').split(',')
        help_actions = os.getenv('UI_HELP_ACTIONS', 'guide,support,menu,close').split(',')
        
        return cls(
            WELCOME_ACTIONS=[action.strip() for action in welcome_actions],
            HELP_ACTIONS=[action.strip() for action in help_actions]
        )


@dataclass
class UIConfig:
    """Master UI configuration combining all UI settings."""
    
    timeouts: UITimeouts
    limits: UILimits
    prefixes: UIPrefixes
    actions: UIActions
    
    @classmethod
    def from_env(cls) -> 'UIConfig':
        """Create complete UI configuration from environment variables."""
        return cls(
            timeouts=UITimeouts.from_env(),
            limits=UILimits.from_env(),
            prefixes=UIPrefixes.from_env(),
            actions=UIActions.from_env()
        )
    
    def get_custom_id(self, handler_name: str, encoded_state: str = "", prefix: Optional[str] = None) -> str:
        """Generate a properly formatted custom_id to match DynamicItem regex pattern."""
        prefix = prefix or self.prefixes.PERSISTENT_BUTTON_PREFIX
        
        if encoded_state:
            # Format: pui:{encoded_state}:{handler_name} to match regex pattern
            custom_id = f"{prefix}:{encoded_state}:{handler_name}"
        else:
            custom_id = f"{prefix}:{handler_name}"
        
        # Ensure it fits within Discord limits
        if len(custom_id) > self.limits.CUSTOM_ID_MAX_LENGTH:
            raise ValueError(f"Custom ID too long: {len(custom_id)} > {self.limits.CUSTOM_ID_MAX_LENGTH}")
        
        return custom_id
    
    def validate_state_complexity(self, state_data: Dict[str, Any]) -> bool:
        """Check if state is simple enough for encoding."""
        import json
        state_json = json.dumps(state_data, separators=(',', ':'))
        return len(state_json) <= self.limits.MAX_STATE_COMPLEXITY


# Global configuration instance
_ui_config: Optional[UIConfig] = None


def get_ui_config() -> UIConfig:
    """Get the global UI configuration instance."""
    global _ui_config
    if _ui_config is None:
        _ui_config = UIConfig.from_env()
    return _ui_config


def reload_ui_config() -> UIConfig:
    """Reload UI configuration from environment variables."""
    global _ui_config
    _ui_config = UIConfig.from_env()
    return _ui_config


# Convenience functions for common operations
def get_timeout(timeout_type: str) -> Optional[timedelta]:
    """Get timeout delta for a specific timeout type."""
    return get_ui_config().timeouts.get_timeout_delta(timeout_type)


def get_toggle_timeout(toggle_type: str = 'default') -> timedelta:
    """Get timeout delta for toggle buttons."""
    return get_ui_config().timeouts.get_toggle_timeout_delta(toggle_type)


def get_custom_id(handler_name: str, encoded_state: str = "", prefix: Optional[str] = None) -> str:
    """Generate a properly formatted custom_id."""
    return get_ui_config().get_custom_id(handler_name, encoded_state, prefix)


def validate_state_complexity(state_data: Dict[str, Any]) -> bool:
    """Check if state is simple enough for encoding."""
    return get_ui_config().validate_state_complexity(state_data)