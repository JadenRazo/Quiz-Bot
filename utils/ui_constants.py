"""
UI Constants Module for Discord Quiz Bot

This module provides centralized constants for UI elements, emojis, colors,
and string literals used throughout the persistent UI system to avoid hardcoding.
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum

import discord


class UIEmojis:
    """Centralized emoji constants for UI elements."""
    
    # Navigation emojis
    PREV_ARROW = '⬅️'
    NEXT_ARROW = '➡️'
    FIRST_PAGE = '⏮️'
    LAST_PAGE = '⏭️'
    UP_ARROW = '⬆️'
    DOWN_ARROW = '⬇️'
    
    # State indicators
    ENABLED = '✅'
    DISABLED = '❌'
    TOGGLE_ON = '🟢'
    TOGGLE_OFF = '🔴'
    LOADING = '⏳'
    SUCCESS = '✅'
    ERROR = '❌'
    WARNING = '⚠️'
    INFO = 'ℹ️'
    
    # Scope indicators
    GLOBAL_SCOPE = '🌐'
    SERVER_SCOPE = '🏠'
    USER_SCOPE = '👤'
    CHANNEL_SCOPE = '💬'
    
    # Action emojis
    QUIZ = '🎯'
    TRIVIA = '🧠'
    GUIDE = '📖'
    COMMANDS = '📋'
    HELP = '❓'
    SUPPORT = '🆘'
    CLOSE = '❌'
    SETTINGS = '⚙️'
    STATS = '📊'
    LEADERBOARD = '🏆'
    HISTORY = '📜'
    PREFERENCES = '🎛️'
    
    # Quiz-related emojis
    CORRECT = '✅'
    INCORRECT = '❌'
    PARTIAL = '🟡'
    SKIPPED = '⏭️'
    TIME_UP = '⏰'
    STREAK = '🔥'
    LEVEL_UP = '⭐'
    ACHIEVEMENT = '🏅'
    
    # Progress indicators
    PROGRESS_FULL = '█'
    PROGRESS_EMPTY = '░'
    PROGRESS_PARTIAL = '▓'
    
    # Special characters
    BULLET = '•'
    ARROW_RIGHT = '→'
    ARROW_LEFT = '←'
    CHECKMARK = '✓'
    CROSS = '✗'
    
    @classmethod
    def get_emoji(cls, name: str, default: str = '❓') -> str:
        """Get emoji by name with fallback."""
        return getattr(cls, name.upper(), default)
    
    @classmethod
    def from_env(cls, name: str, fallback: str) -> str:
        """Get emoji from environment variable with fallback."""
        env_key = f'UI_EMOJI_{name.upper()}'
        return os.getenv(env_key, fallback)


class UIColors:
    """Centralized color constants for Discord embeds."""
    
    # Status colors
    SUCCESS = discord.Color.green()
    ERROR = discord.Color.red()
    WARNING = discord.Color.orange()
    INFO = discord.Color.blue()
    DEFAULT = discord.Color.blurple()
    
    # Quiz colors
    QUIZ_PRIMARY = discord.Color.blue()
    QUIZ_SUCCESS = discord.Color.green()
    QUIZ_FAILURE = discord.Color.red()
    QUIZ_NEUTRAL = discord.Color.light_grey()
    
    # Difficulty colors
    EASY = discord.Color.green()
    MEDIUM = discord.Color.orange()
    HARD = discord.Color.red()
    EXPERT = discord.Color.dark_red()
    
    # Feature colors
    STATS = discord.Color.purple()
    LEADERBOARD = discord.Color.gold()
    HELP = discord.Color.teal()
    ADMIN = discord.Color.dark_grey()
    
    # Progress colors
    LOW_PROGRESS = discord.Color.red()
    MEDIUM_PROGRESS = discord.Color.orange()
    HIGH_PROGRESS = discord.Color.green()
    
    @classmethod
    def get_difficulty_color(cls, difficulty: str) -> discord.Color:
        """Get color for difficulty level."""
        difficulty_map = {
            'easy': cls.EASY,
            'medium': cls.MEDIUM,
            'hard': cls.HARD,
            'expert': cls.EXPERT
        }
        return difficulty_map.get(difficulty.lower(), cls.DEFAULT)
    
    @classmethod
    def get_progress_color(cls, percentage: float) -> discord.Color:
        """Get color based on progress percentage."""
        if percentage >= 75:
            return cls.HIGH_PROGRESS
        elif percentage >= 50:
            return cls.MEDIUM_PROGRESS
        else:
            return cls.LOW_PROGRESS
    
    @classmethod
    def get_status_color(cls, status: str) -> discord.Color:
        """Get color for status type."""
        status_map = {
            'success': cls.SUCCESS,
            'error': cls.ERROR,
            'warning': cls.WARNING,
            'info': cls.INFO
        }
        return status_map.get(status.lower(), cls.DEFAULT)


@dataclass
class UIMessages:
    """Centralized message templates and text constants."""
    
    # Error messages
    BUTTON_EXPIRED: str = "⏰ This button has expired."
    BUTTON_UNAUTHORIZED: str = "🚫 You're not authorized to use this button."
    BUTTON_ERROR: str = "❌ Something went wrong. Please try again or contact support."
    HANDLER_NOT_FOUND: str = "❌ Button handler not available."
    
    # Success messages
    ACTION_SUCCESS: str = "✅ Action completed successfully."
    SETTINGS_SAVED: str = "✅ Settings saved successfully."
    PREFERENCES_UPDATED: str = "✅ Preferences updated successfully."
    
    # Info messages
    LOADING: str = "⏳ Loading..."
    PROCESSING: str = "⚙️ Processing your request..."
    NO_DATA: str = "📭 No data available."
    COMING_SOON: str = "🚧 This feature is coming soon!"
    
    # Navigation messages
    FIRST_PAGE: str = "📄 You're already on the first page."
    LAST_PAGE: str = "📄 You're already on the last page."
    PAGE_INFO: str = "Page {current} of {total}"
    
    # Quiz messages
    QUIZ_STARTING: str = "🎯 Starting quiz..."
    QUIZ_COMPLETE: str = "🎉 Quiz completed!"
    QUIZ_STOPPED: str = "⏹️ Quiz stopped."
    NO_ACTIVE_QUIZ: str = "❌ No active quiz found."
    
    # Help messages
    COMMAND_HELP: str = "Use `/help` for detailed command information."
    CONTACT_ADMIN: str = "Contact a server administrator for assistance."
    
    @classmethod
    def from_env(cls) -> 'UIMessages':
        """Create UIMessages from environment variables with fallbacks."""
        return cls(
            BUTTON_EXPIRED=os.getenv('UI_MSG_BUTTON_EXPIRED', cls.BUTTON_EXPIRED),
            BUTTON_UNAUTHORIZED=os.getenv('UI_MSG_BUTTON_UNAUTHORIZED', cls.BUTTON_UNAUTHORIZED),
            BUTTON_ERROR=os.getenv('UI_MSG_BUTTON_ERROR', cls.BUTTON_ERROR),
            HANDLER_NOT_FOUND=os.getenv('UI_MSG_HANDLER_NOT_FOUND', cls.HANDLER_NOT_FOUND)
        )


class ButtonStyles:
    """Standardized button style configurations."""
    
    # Navigation buttons
    NAVIGATION = {
        'prev': {'style': discord.ButtonStyle.primary, 'emoji': UIEmojis.PREV_ARROW},
        'next': {'style': discord.ButtonStyle.primary, 'emoji': UIEmojis.NEXT_ARROW},
        'first': {'style': discord.ButtonStyle.secondary, 'emoji': UIEmojis.FIRST_PAGE},
        'last': {'style': discord.ButtonStyle.secondary, 'emoji': UIEmojis.LAST_PAGE}
    }
    
    # Toggle buttons
    TOGGLE = {
        'enabled': {'style': discord.ButtonStyle.success, 'emoji': UIEmojis.ENABLED},
        'disabled': {'style': discord.ButtonStyle.danger, 'emoji': UIEmojis.DISABLED}
    }
    
    # Action buttons
    ACTIONS = {
        'quiz': {'style': discord.ButtonStyle.success, 'emoji': UIEmojis.QUIZ, 'label': 'Start Quiz'},
        'guide': {'style': discord.ButtonStyle.primary, 'emoji': UIEmojis.GUIDE, 'label': 'Setup Guide'},
        'commands': {'style': discord.ButtonStyle.secondary, 'emoji': UIEmojis.COMMANDS, 'label': 'Commands'},
        'help': {'style': discord.ButtonStyle.secondary, 'emoji': UIEmojis.HELP, 'label': 'Help'},
        'support': {'style': discord.ButtonStyle.secondary, 'emoji': UIEmojis.SUPPORT, 'label': 'Support'},
        'close': {'style': discord.ButtonStyle.danger, 'emoji': UIEmojis.CLOSE, 'label': 'Close'},
        'settings': {'style': discord.ButtonStyle.secondary, 'emoji': UIEmojis.SETTINGS, 'label': 'Settings'}
    }
    
    # Leaderboard buttons
    LEADERBOARD = {
        'global': {'style': discord.ButtonStyle.success, 'emoji': UIEmojis.GLOBAL_SCOPE, 'label': 'Global'},
        'server': {'style': discord.ButtonStyle.secondary, 'emoji': UIEmojis.SERVER_SCOPE, 'label': 'Server'}
    }
    
    @classmethod
    def get_navigation_config(cls, direction: str) -> Dict[str, Any]:
        """Get navigation button configuration."""
        return cls.NAVIGATION.get(direction, {
            'style': discord.ButtonStyle.secondary,
            'emoji': '❓'
        })
    
    @classmethod
    def get_action_config(cls, action: str) -> Dict[str, Any]:
        """Get action button configuration."""
        return cls.ACTIONS.get(action, {
            'style': discord.ButtonStyle.secondary,
            'label': action.title()
        })
    
    @classmethod
    def get_toggle_config(cls, state: bool) -> Dict[str, Any]:
        """Get toggle button configuration based on state."""
        return cls.TOGGLE['enabled' if state else 'disabled']


class UIPatterns:
    """Common UI patterns and templates."""
    
    # Embed templates
    EMBED_TEMPLATES = {
        'error': {
            'color': UIColors.ERROR,
            'footer': {'text': 'Error occurred'}
        },
        'success': {
            'color': UIColors.SUCCESS,
            'footer': {'text': 'Operation successful'}
        },
        'info': {
            'color': UIColors.INFO,
            'footer': {'text': 'Information'}
        },
        'quiz': {
            'color': UIColors.QUIZ_PRIMARY,
            'footer': {'text': 'Quiz Bot'}
        }
    }
    
    # Progress bar patterns
    PROGRESS_PATTERNS = {
        'default': {
            'full_char': UIEmojis.PROGRESS_FULL,
            'empty_char': UIEmojis.PROGRESS_EMPTY,
            'width': 10
        },
        'detailed': {
            'full_char': '█',
            'partial_char': '▓',
            'empty_char': '░',
            'width': 15
        }
    }
    
    @classmethod
    def get_embed_template(cls, template_type: str) -> Dict[str, Any]:
        """Get embed template configuration."""
        return cls.EMBED_TEMPLATES.get(template_type, cls.EMBED_TEMPLATES['info'])
    
    @classmethod
    def get_progress_pattern(cls, pattern_type: str) -> Dict[str, Any]:
        """Get progress bar pattern configuration."""
        return cls.PROGRESS_PATTERNS.get(pattern_type, cls.PROGRESS_PATTERNS['default'])


# Global constants instances
ui_emojis = UIEmojis()
ui_colors = UIColors()
ui_messages = UIMessages.from_env()
button_styles = ButtonStyles()
ui_patterns = UIPatterns()


# Convenience functions
def get_emoji(name: str, default: str = '❓') -> str:
    """Get emoji by name with fallback."""
    return ui_emojis.get_emoji(name, default)


def get_color(color_type: str, value: Any = None) -> discord.Color:
    """Get color by type with optional value context."""
    if color_type == 'difficulty' and value:
        return ui_colors.get_difficulty_color(value)
    elif color_type == 'progress' and value is not None:
        return ui_colors.get_progress_color(value)
    elif color_type == 'status' and value:
        return ui_colors.get_status_color(value)
    else:
        return getattr(ui_colors, color_type.upper(), ui_colors.DEFAULT)


def get_button_config(button_type: str, action_or_state: Any) -> Dict[str, Any]:
    """Get button configuration by type and action/state."""
    if button_type == 'navigation':
        return button_styles.get_navigation_config(action_or_state)
    elif button_type == 'action':
        return button_styles.get_action_config(action_or_state)
    elif button_type == 'toggle':
        return button_styles.get_toggle_config(action_or_state)
    else:
        return {'style': discord.ButtonStyle.secondary}


def get_message(message_type: str) -> str:
    """Get message template by type."""
    return getattr(ui_messages, message_type.upper(), "Message not found")