"""
Unified Persistent UI System for Discord.py 2.5.2

This module consolidates all persistent button and view functionality into a single,
clean, maintainable system. It combines the best features from the existing systems
while maintaining readability and leveraging existing utilities.

Architecture:
- Primary: DynamicItem-based buttons with state encoding (performance)
- Fallback: Database persistence for complex state (compatibility)
- Utilities: Leverages existing progress bars, embeds, and error handling
"""

import json
import base64
import logging
import re
import traceback
from typing import Dict, Any, Optional, Type, Union, List, Callable, Awaitable
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass

import discord
from discord.ext import commands

from utils.context import BotContext
from utils.ui import create_embed, get_color_for_difficulty
from utils.errors import BotError, log_exception
from utils.ui_config import get_ui_config, get_timeout, get_toggle_timeout, get_custom_id
from utils.ui_constants import (
    ui_emojis, ui_colors, ui_messages, button_styles,
    get_emoji, get_color, get_button_config, get_message
)

# Global registry for database-mode buttons
_global_database_buttons: Dict[str, Dict[str, Any]] = {}


# Core Enums and Types
class ButtonAction(Enum):
    """Standardized button action types."""
    NAVIGATE = "nav"      # Pagination, navigation
    TOGGLE = "toggle"     # Binary state switches  
    ACTION = "action"     # Static actions (help, welcome)
    MODAL = "modal"       # Modal dialog triggers
    CONFIRM = "confirm"   # Confirmation dialogs


class PersistenceMode(Enum):
    """How button state should be persisted."""
    STATE_ENCODED = "encoded"    # Encode in custom_id (fast, limited size)
    DATABASE = "database"        # Store in database (complex state)
    MEMORY = "memory"           # Memory only (non-persistent)


@dataclass
class ButtonState:
    """Compact state representation for buttons."""
    user_id: int
    action: ButtonAction
    data: Dict[str, Any]
    guild_id: Optional[int] = None
    expires: Optional[int] = None  # Unix timestamp
    
    def encode(self) -> str:
        """Encode state to base64 string for custom_id."""
        # Use minimal keys and omit None/empty values to reduce size
        state_dict = {
            'u': self.user_id,
            'a': self.action.value,
            'd': self.data
        }
        if self.guild_id:
            state_dict['g'] = self.guild_id
        if self.expires:
            state_dict['e'] = self.expires
            
        # Try optimized encoding for simple states first
        if len(self.data) == 1 and all(isinstance(v, str) and len(v) < 10 for v in self.data.values()):
            # Use compact encoding for simple single-value states
            key, value = next(iter(self.data.items()))
            compact = f"{self.user_id}|{self.action.value}|{key}:{value}"
            if self.guild_id:
                compact += f"|g:{self.guild_id}"
            if self.expires:
                compact += f"|e:{self.expires}"
            encoded = base64.b64encode(compact.encode('utf-8')).decode('ascii')
        else:
            # Use JSON encoding for complex states
            json_str = json.dumps(state_dict, separators=(',', ':'))
            encoded = base64.b64encode(json_str.encode('utf-8')).decode('ascii')
        
        # Use configured limits instead of hardcoded values
        config = get_ui_config()
        if len(encoded) > config.limits.ENCODED_STATE_MAX_LENGTH:
            raise ValueError("State too complex for encoding, use database persistence")
            
        return encoded
    
    @classmethod
    def decode(cls, encoded: str) -> 'ButtonState':
        """Decode state from base64 string (supports both compact and JSON formats)."""
        try:
            decoded_str = base64.b64decode(encoded.encode('ascii')).decode('utf-8')
            
            # Check if it's compact format (contains | separators)
            if '|' in decoded_str and not decoded_str.startswith('{'):
                # Parse compact format: user_id|action|key:value|g:guild_id|e:expires
                parts = decoded_str.split('|')
                user_id = int(parts[0])
                action = ButtonAction(parts[1])
                
                # Parse key:value data
                key_value = parts[2].split(':', 1)
                data = {key_value[0]: key_value[1]}
                
                guild_id = None
                expires = None
                
                # Parse optional guild_id and expires
                for part in parts[3:]:
                    if part.startswith('g:'):
                        guild_id = int(part[2:])
                    elif part.startswith('e:'):
                        expires = int(part[2:])
                
                return cls(
                    user_id=user_id,
                    action=action,
                    data=data,
                    guild_id=guild_id,
                    expires=expires
                )
            else:
                # Parse JSON format
                data = json.loads(decoded_str)
                return cls(
                    user_id=data['u'],
                    action=ButtonAction(data['a']),
                    data=data['d'],
                    guild_id=data.get('g'),
                    expires=data.get('e')
                )
        except Exception as e:
            raise ValueError(f"Failed to decode button state: {e}")
    
    def is_expired(self) -> bool:
        """Check if button state has expired."""
        if not self.expires:
            return False
        return datetime.utcnow().timestamp() > self.expires


# Base Handler Classes
class ButtonHandler(ABC):
    """
    Abstract base class for persistent button handlers.
    
    Provides type-safe interface and common functionality following OOP principles.
    """
    
    def __init__(self, context: BotContext):
        self.context = context
        self.bot = context.bot
        self.logger = logging.getLogger(f"ButtonHandler.{self.__class__.__name__}")
    
    @abstractmethod
    async def handle_interaction(self, interaction: discord.Interaction, state: ButtonState) -> None:
        """Handle button interaction with decoded state."""
        pass
    
    @abstractmethod
    def get_button_config(self, state: ButtonState) -> Dict[str, Any]:
        """Get button configuration (style, label, emoji, etc.)."""
        pass
    
    async def validate_interaction(self, interaction: discord.Interaction, state: ButtonState) -> bool:
        """Validate interaction authorization and state."""
        # Check expiration
        if state.is_expired():
            if not interaction.response.is_done():
                await interaction.response.send_message(get_message('BUTTON_EXPIRED'), ephemeral=True)
            else:
                await interaction.followup.send(get_message('BUTTON_EXPIRED'), ephemeral=True)
            return False
        
        # Check user authorization (0 = public access)
        if state.user_id != 0 and state.user_id != interaction.user.id:
            if not interaction.response.is_done():
                await interaction.response.send_message(get_message('BUTTON_UNAUTHORIZED'), ephemeral=True)
            else:
                await interaction.followup.send(get_message('BUTTON_UNAUTHORIZED'), ephemeral=True)
            return False
            
        return True
    
    async def handle_error(self, interaction: discord.Interaction, error: Exception, state: ButtonState) -> None:
        """Handle errors gracefully with user-friendly messages."""
        self.logger.error(f"Button handler error in {self.__class__.__name__}: {error}", exc_info=True)
        log_exception(error, context={"handler": self.__class__.__name__, "state": state.data})
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    get_message('BUTTON_ERROR'),
                    ephemeral=True
                )
            else:
                # If already acknowledged, use followup instead
                await interaction.followup.send(
                    get_message('BUTTON_ERROR'),
                    ephemeral=True
                )
        except Exception as e:
            # If even the error message fails, just log it
            self.logger.error(f"Failed to send error message: {e}")


# DynamicItem Implementation
class PersistentButton(discord.ui.DynamicItem[discord.ui.Button], template=r'pui:(?P<encoded>[A-Za-z0-9+/=]{4,}):(?P<handler>\w+)'):
    """
    Persistent button using DynamicItem pattern for STATE_ENCODED mode.
    
    Custom ID format: pui:{encoded_state}:{handler_name}
    - pui: Persistent UI prefix
    - encoded_state: Base64 encoded ButtonState
    - handler_name: Handler class name for routing
    """
    
    def __init__(self, encoded: str, handler: str):
        self.encoded = encoded
        self.handler_name = handler
        
        try:
            self.state = ButtonState.decode(encoded)
        except ValueError as e:
            # Create a fallback button for invalid state
            self.state = ButtonState(
                user_id=0,
                action=ButtonAction.ACTION,
                data={'error': str(e)}
            )
        
        # Create the actual Discord button
        config = self._get_button_config()
        custom_id = f'pui:{encoded}:{handler}'
        super().__init__(discord.ui.Button(
            custom_id=custom_id,
            style=config.get('style', discord.ButtonStyle.secondary),
            label=config.get('label'),
            emoji=config.get('emoji'),
            disabled=config.get('disabled', self.state.is_expired())
        ))
    
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        """Create PersistentButton from custom_id match (required for DynamicItem)."""
        encoded = match.group('encoded')
        handler = match.group('handler')
        return cls(encoded, handler)
    
    def _get_handler(self) -> Optional[ButtonHandler]:
        """Get handler instance for this button."""
        logger = logging.getLogger("PersistentButton")
        
        # Try to get from global context first
        context = getattr(self.__class__, '_global_context', None)
        if not context:
            logger.warning(f"No global context available for handler {self.handler_name}")
            return None
            
        handler_registry = getattr(context, 'button_handlers', {})
        if not handler_registry:
            logger.warning(f"No button handlers registered in context for {self.handler_name}")
            return self._try_direct_handler_import(context)
        
        handler_class = handler_registry.get(self.handler_name)
        if not handler_class:
            logger.warning(f"Handler {self.handler_name} not found in registry: {list(handler_registry.keys())}")
            return self._try_direct_handler_import(context)
        
        logger.debug(f"Found handler {self.handler_name}, creating instance")
        return handler_class(context)
    
    def _try_direct_handler_import(self, context) -> Optional[ButtonHandler]:
        """Try to import handler directly as fallback."""
        logger = logging.getLogger("PersistentButton")
        try:
            if self.handler_name == 'LeaderboardToggleHandler':
                from utils.specialized_handlers import LeaderboardToggleHandler
                logger.info(f"Direct import fallback successful for {self.handler_name}")
                return LeaderboardToggleHandler(context)
            elif self.handler_name == 'StatsNavigationHandler':
                from utils.specialized_handlers import StatsNavigationHandler
                logger.info(f"Direct import fallback successful for {self.handler_name}")
                return StatsNavigationHandler(context)
            else:
                logger.error(f"No direct import fallback available for {self.handler_name}")
                return None
        except Exception as e:
            logger.error(f"Direct import fallback failed for {self.handler_name}: {e}")
            logger.error(f"Import traceback:\n{traceback.format_exc()}")
            return None
    
    def _get_button_config(self) -> Dict[str, Any]:
        """Get button configuration from handler."""
        handler = self._get_handler()
        if handler:
            try:
                return handler.get_button_config(self.state)
            except Exception as e:
                logger = logging.getLogger("PersistentButton")
                logger.warning(f"Failed to get button config from handler: {e}")
        
        # Fallback configuration
        return {
            'style': discord.ButtonStyle.secondary,
            'label': 'Action',
            'emoji': None,
            'disabled': False
        }
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        logger = logging.getLogger("PersistentButton")
        
        try:
            # Get handler
            handler = self._get_handler()
            if not handler:
                await interaction.response.send_message(
                    "Button handler not available. Please try again later.",
                    ephemeral=True
                )
                return
            
            # Handle the interaction
            await handler.handle_interaction(interaction, self.state)
            
        except Exception as e:
            # Get full traceback for debugging
            tb_str = traceback.format_exc()
            logger.error(f"Error in PersistentButton callback: {e}")
            logger.error(f"Full traceback:\n{tb_str}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"An error occurred while processing your request.\nError: {str(e)[:100]}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"An error occurred while processing your request.\nError: {str(e)[:100]}",
                        ephemeral=True
                    )
            except Exception as followup_error:
                logger.error(f"Failed to send error message: {followup_error}")
                logger.error(f"Followup error traceback:\n{traceback.format_exc()}")


class PersistentButtonDB(discord.ui.DynamicItem[discord.ui.Button], template=r'pui:db:(?P<handler>\w+):(?P<unique_id>.*)'):
    """
    Persistent button using DynamicItem pattern for DATABASE mode.
    
    Custom ID format: pui:db:{handler_name}:{unique_id}
    - pui: Persistent UI prefix
    - db: Database persistence mode prefix
    - handler_name: Handler class name for routing
    - unique_id: Unique identifier for button instance
    """
    
    def __init__(self, handler: str, unique_id: str):
        self.handler_name = handler
        self.unique_id = unique_id
        self.state = None  # Will be loaded from database
        
        # Create the actual Discord button
        config = self._get_button_config()
        custom_id = f'pui:db:{handler}:{unique_id}'
        super().__init__(discord.ui.Button(
            custom_id=custom_id,
            style=config.get('style', discord.ButtonStyle.secondary),
            label=config.get('label'),
            emoji=config.get('emoji'),
            disabled=config.get('disabled', False)
        ))
    
    def _get_button_config(self) -> Dict[str, Any]:
        """Get button configuration for database mode."""
        return {
            'style': discord.ButtonStyle.secondary,
            'label': 'Switch View',
            'emoji': None,
            'disabled': False
        }
    
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        """Create PersistentButtonDB from custom_id match (required for DynamicItem)."""
        handler = match.group('handler')
        unique_id = match.group('unique_id')
        return cls(handler, unique_id)
    
    def _get_handler(self) -> Optional[ButtonHandler]:
        """Get handler instance for this button from database mode."""
        logger = logging.getLogger("PersistentButtonDB")
        
        # Try to get from global context first
        context = getattr(self.__class__, '_global_context', None)
        if not context:
            logger.warning(f"No global context available for handler {self.handler_name}")
            return None
            
        handler_registry = getattr(context, 'button_handlers', {})
        if not handler_registry:
            logger.warning(f"No button handlers registered in context for {self.handler_name}")
            return self._try_direct_handler_import(context)
        
        handler_class = handler_registry.get(self.handler_name)
        if not handler_class:
            logger.warning(f"Handler {self.handler_name} not found in registry: {list(handler_registry.keys())}")
            return self._try_direct_handler_import(context)
        
        logger.debug(f"Found handler {self.handler_name}, creating instance")
        return handler_class(context)
    
    def _try_direct_handler_import(self, context) -> Optional[ButtonHandler]:
        """Try to import handler directly as fallback."""
        logger = logging.getLogger("PersistentButtonDB")
        
        try:
            # Try importing specialized handlers
            if self.handler_name == 'LeaderboardToggleHandler':
                from utils.specialized_handlers import LeaderboardToggleHandler
                logger.info(f"Successfully imported {self.handler_name} via direct import")
                return LeaderboardToggleHandler(context)
            elif self.handler_name == 'StatsNavigationHandler':
                from utils.specialized_handlers import StatsNavigationHandler
                logger.info(f"Successfully imported {self.handler_name} via direct import")
                return StatsNavigationHandler(context)
            else:
                logger.error(f"No direct import fallback available for {self.handler_name}")
                return None
        except Exception as e:
            logger.error(f"Failed to directly import handler {self.handler_name}: {e}")
            logger.error(f"Import traceback:\n{traceback.format_exc()}")
            return None
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click for database-mode buttons."""
        logger = logging.getLogger("PersistentButtonDB")
        logger.info(f"PersistentButtonDB callback called for custom_id: {self.custom_id}")
        
        try:
            # Load state from global database_buttons registry
            global _global_database_buttons
            logger.info(f"Available database buttons: {list(_global_database_buttons.keys())}")
            
            if self.custom_id in _global_database_buttons:
                button_data = _global_database_buttons[self.custom_id]
                self.state = button_data['state']
                logger.info(f"Loaded state for button {self.custom_id}")
            else:
                logger.error(f"No database entry found for button {self.custom_id}")
                await interaction.response.send_message("Button state not found.", ephemeral=True)
                return
            
            # Get handler
            logger.info(f"Getting handler for {self.handler_name}")
            handler = self._get_handler()
            if not handler:
                logger.error(f"Handler {self.handler_name} not found")
                await interaction.response.send_message(
                    "Button handler not available. Please try again later.",
                    ephemeral=True
                )
                return
            
            logger.info(f"Handler {self.handler_name} found, calling handle_interaction")
            # Handle the interaction
            await handler.handle_interaction(interaction, self.state)
            logger.info(f"Handler {self.handler_name} completed successfully")
            
        except Exception as e:
            # Get full traceback for debugging
            tb_str = traceback.format_exc()
            logger.error(f"Error in PersistentButtonDB callback: {e}")
            logger.error(f"Full traceback:\n{tb_str}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"An error occurred while processing your request.\nError: {str(e)[:100]}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"An error occurred while processing your request.\nError: {str(e)[:100]}",
                        ephemeral=True
                    )
            except Exception as followup_error:
                logger.error(f"Failed to send error message: {followup_error}")
                logger.error(f"Followup error traceback:\n{traceback.format_exc()}")


# Unified Persistent View
class PersistentView(discord.ui.View):
    """
    Unified persistent view with enhanced functionality.
    
    Features:
    - Automatic DynamicItem registration
    - State-encoded button management
    - Database fallback for complex state
    - Integration with existing utilities
    """
    
    def __init__(self, 
                 context: BotContext,
                 timeout: Optional[float] = None,
                 persistence_mode: PersistenceMode = PersistenceMode.STATE_ENCODED):
        super().__init__(timeout=timeout)
        self.context = context
        self.persistence_mode = persistence_mode
        self.logger = logging.getLogger("PersistentView")
        
        # DynamicItems are registered globally, not added to views
        # They will be automatically created when buttons are clicked
        
        # Track buttons for database persistence if needed
        self._database_buttons: Dict[str, Dict[str, Any]] = {}
    
    def add_button(self,
                   handler_name: str,
                   user_id: int,
                   action: ButtonAction,
                   data: Dict[str, Any],
                   guild_id: Optional[int] = None,
                   expires_in: Optional[timedelta] = None,
                   row: Optional[int] = None,
                   persistence_mode: Optional[PersistenceMode] = None) -> str:
        """
        Add a persistent button to the view.
        
        Args:
            handler_name: Name of registered handler class
            user_id: User ID for authorization (0 = public)
            action: Button action type
            data: Custom data for the button
            guild_id: Optional guild ID
            expires_in: Optional expiration time
            row: Optional row for button placement
            persistence_mode: Override default persistence mode
            
        Returns:
            The custom_id of the created button
        """
        # Use provided mode or fall back to view default
        mode = persistence_mode or self.persistence_mode
        
        # Calculate expiration timestamp
        expires = None
        if expires_in:
            expires = int((datetime.utcnow() + expires_in).timestamp())
        
        # Create button state
        state = ButtonState(
            user_id=user_id,
            action=action,
            data=data,
            guild_id=guild_id,
            expires=expires
        )
        
        try:
            if mode == PersistenceMode.STATE_ENCODED:
                # Use state encoding (primary method)
                encoded = state.encode()
                custom_id = get_custom_id(handler_name=handler_name, encoded_state=encoded)
                
                # Create and add actual Discord button to the view
                button = self._create_discord_button(handler_name, state, custom_id, row)
                if button:
                    self.add_item(button)
                
                return custom_id
                
            elif mode == PersistenceMode.DATABASE:
                # Use database persistence (fallback for complex state)
                config = get_ui_config()
                import random
                timestamp = int(datetime.utcnow().timestamp() * 1000)  # Include milliseconds
                random_suffix = random.randint(1000, 9999)  # Add random component
                custom_id = f'{config.prefixes.PERSISTENT_BUTTON_PREFIX}:{config.prefixes.DATABASE_PREFIX}:{handler_name}:{user_id}_{timestamp}_{random_suffix}'
                
                # Store in both local and global registries
                button_data = {
                    'state': state,
                    'handler_name': handler_name
                }
                self._database_buttons[custom_id] = button_data
                _global_database_buttons[custom_id] = button_data
                
                # Create and add actual Discord button to the view
                button = self._create_discord_button(handler_name, state, custom_id, row)
                if button:
                    self.add_item(button)
                
                return custom_id
                
            else:  # MEMORY mode
                # Memory-only (for temporary buttons)
                config = get_ui_config()
                import random
                timestamp = int(datetime.utcnow().timestamp() * 1000)  # Include milliseconds
                random_suffix = random.randint(1000, 9999)  # Add random component
                custom_id = f'{config.prefixes.PERSISTENT_BUTTON_PREFIX}:{config.prefixes.MEMORY_PREFIX}:{handler_name}_{user_id}_{timestamp}_{random_suffix}'
                
                # Create and add actual Discord button to the view
                button = self._create_discord_button(handler_name, state, custom_id, row)
                if button:
                    self.add_item(button)
                
                return custom_id
                
        except ValueError as e:
            # State too complex for encoding, fall back to database
            # Use debug level since this is an expected fallback mechanism
            self.logger.debug(f"State encoding exceeded limit, using database persistence: {e}")
            return self.add_button(
                handler_name, user_id, action, data, guild_id, expires_in, row,
                PersistenceMode.DATABASE
            )
    
    def _create_discord_button(self, handler_name: str, state: ButtonState, custom_id: str, row: Optional[int] = None) -> Optional[discord.ui.Button]:
        """Create a Discord UI Button with proper configuration."""
        try:
            # Get handler to determine button configuration
            handler_registry = getattr(self.context, 'button_handlers', {})
            handler_class = handler_registry.get(handler_name)
            
            if handler_class:
                handler = handler_class(self.context)
                config = handler.get_button_config(state)
            else:
                # Fallback configuration
                config = {
                    'style': discord.ButtonStyle.secondary,
                    'label': 'Button',
                    'disabled': True
                }
            
            # Create the Discord button
            button = discord.ui.Button(
                custom_id=custom_id,
                style=config.get('style', discord.ButtonStyle.secondary),
                label=config.get('label'),
                emoji=config.get('emoji'),
                disabled=config.get('disabled', state.is_expired()),
                row=row
            )
            
            # Don't set a callback - the DynamicItem system will handle this
            # through the PersistentButton class and its callback method
            return button
            
        except Exception as e:
            self.logger.error(f"Failed to create Discord button: {e}")
            return None
    
    async def persist_to_database(self, message: discord.Message) -> None:
        """Persist database buttons to storage using the UI service."""
        if not self._database_buttons:
            return
            
        try:
            # Use the persistent UI service for proper database handling
            ui_service = getattr(self.context, 'ui_service', None)
            if not ui_service:
                # Import and create service if not available
                from services.persistent_ui_service import PersistentUIService
                ui_service = PersistentUIService(self.context)
            
            # Register the message first
            await ui_service.register_message(
                message,
                self.__class__.__name__,
                None,  # embed_data can be added later if needed
                None   # expires_at will be handled per button
            )
            
            # Store each button
            for custom_id, button_data in self._database_buttons.items():
                state = button_data['state']
                expires_at = datetime.fromtimestamp(state.expires) if state.expires else None
                
                await ui_service.store_button(
                    custom_id=custom_id,
                    button_type=state.action.value,
                    handler_class=button_data['handler_name'],
                    view_class=self.__class__.__name__,
                    message=message,
                    button_state=state,
                    expires_at=expires_at
                )
                
        except Exception as e:
            self.logger.error(f"Failed to persist buttons to database: {e}")
    
    async def on_timeout(self) -> None:
        """Handle view timeout gracefully."""
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True


# Unified Button Manager
class UnifiedButtonManager:
    """
    Centralized manager for the unified persistent button system.
    
    Handles registration, recovery, and lifecycle management of all persistent UI components.
    """
    
    def __init__(self, context: BotContext):
        self.context = context
        self.logger = logging.getLogger("UnifiedButtonManager")
        
        # Handler registry
        self.handlers: Dict[str, Type[ButtonHandler]] = {}
        
        # Set global context for DynamicItem access
        PersistentButton._global_context = context
        PersistentButtonDB._global_context = context
        context.button_handlers = self.handlers
        
        # Also ensure the context object itself has the handlers
        if not hasattr(context, 'button_handlers'):
            context.button_handlers = self.handlers
        
        self.logger.info(f"Set global context with {len(self.handlers)} handlers")
    
    def register_handler(self, name: str, handler_class: Type[ButtonHandler]) -> None:
        """Register a button handler class."""
        self.handlers[name] = handler_class
        self.logger.info(f"Registered handler: {name}")
    
    def register_handlers_from_module(self, module) -> None:
        """Register all handlers from a module (like specialized_handlers.py)."""
        import inspect
        
        registered_count = 0
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, ButtonHandler) and 
                obj != ButtonHandler):
                self.register_handler(name, obj)
                registered_count += 1
        
        self.logger.info(f"Registered {registered_count} handlers from module: {module.__name__}")
        self.logger.info(f"Available handlers: {list(self.handlers.keys())}")
        
        # Explicitly register the LeaderboardToggleHandler if not found
        if 'LeaderboardToggleHandler' not in self.handlers:
            try:
                from utils.specialized_handlers import LeaderboardToggleHandler
                self.register_handler('LeaderboardToggleHandler', LeaderboardToggleHandler)
                self.logger.info("Explicitly registered LeaderboardToggleHandler")
            except ImportError as e:
                self.logger.error(f"Failed to import LeaderboardToggleHandler: {e}")
    
    async def setup_persistent_views(self) -> None:
        """Set up persistent views on bot startup."""
        # Register DynamicItem with the bot for automatic handling
        # Note: add_dynamic_items() expects the DynamicItem class, not an instance
        self.context.bot.add_dynamic_items(PersistentButton, PersistentButtonDB)
        self.logger.info("Set up unified persistent views for bot startup")
    
    async def recover_database_buttons(self) -> None:
        """Recover database-persisted buttons after restart using the recovery service."""
        try:
            # Use the UI recovery service for comprehensive recovery
            recovery_service = getattr(self.context, 'recovery_service', None)
            if not recovery_service:
                # Import and create service if not available
                from services.ui_recovery_service import UIRecoveryService
                recovery_service = UIRecoveryService(self.context)
                self.context.recovery_service = recovery_service
            
            # Perform full startup recovery
            recovery_result = await recovery_service.perform_startup_recovery()
            
            if recovery_result['success']:
                stats = recovery_result['statistics']
                self.logger.info(
                    f"Successfully recovered {stats['buttons_recovered']} buttons "
                    f"across {stats['messages_scanned']} messages"
                )
            else:
                self.logger.error(f"Button recovery failed: {recovery_result.get('error', 'Unknown error')}")
                    
        except Exception as e:
            self.logger.error(f"Failed to recover database buttons: {e}")


# Factory Functions for Easy View Creation
def create_navigation_view(context: BotContext, user_id: int, current_page: int, total_pages: int,
                          guild_id: Optional[int] = None) -> PersistentView:
    """Create a view with navigation buttons using existing handlers."""
    view = PersistentView(context)
    
    # Add navigation buttons based on position
    if current_page > 0:
        view.add_button(
            'NavigationHandler', user_id, ButtonAction.NAVIGATE,
            {'direction': 'prev', 'page': current_page, 'total': total_pages},
            guild_id, get_timeout('navigation')
        )
    
    if current_page < total_pages - 1:
        view.add_button(
            'NavigationHandler', user_id, ButtonAction.NAVIGATE,
            {'direction': 'next', 'page': current_page, 'total': total_pages},
            guild_id, get_timeout('navigation')
        )
    
    return view


def create_stats_navigation_view(context: BotContext, user_id: int, target_user_id: int, 
                                current_page: int, total_pages: int, guild_id: Optional[int] = None) -> PersistentView:
    """Create a view with navigation buttons specifically for stats pages."""
    view = PersistentView(context)
    
    # Add navigation buttons based on position
    if current_page > 0:
        view.add_button(
            'StatsNavigationHandler', user_id, ButtonAction.NAVIGATE,
            {
                'direction': 'prev', 
                'page': current_page, 
                'total': total_pages,
                'target_user_id': target_user_id
            },
            guild_id, get_timeout('stats')
        )
    
    if current_page < total_pages - 1:
        view.add_button(
            'StatsNavigationHandler', user_id, ButtonAction.NAVIGATE,
            {
                'direction': 'next', 
                'page': current_page, 
                'total': total_pages,
                'target_user_id': target_user_id
            },
            guild_id, get_timeout('stats')
        )
    
    return view


def create_welcome_view(context: BotContext, guild_id: Optional[int] = None) -> PersistentView:
    """Create welcome action buttons using existing handlers."""
    view = PersistentView(context, timeout=None)  # Never timeout
    
    # Public buttons (user_id = 0) using existing WelcomeActionHandler
    config = get_ui_config()
    actions = config.actions.WELCOME_ACTIONS
    for action in actions:
        view.add_button(
            'WelcomeActionHandler', 0, ButtonAction.ACTION,
            {'action': action},
            guild_id, None  # Never expire
        )
    
    return view


# Integration Function
async def initialize_unified_ui_system(context: BotContext) -> UnifiedButtonManager:
    """Initialize the unified persistent UI system."""
    manager = UnifiedButtonManager(context)
    
    # Register existing specialized handlers
    try:
        from utils import specialized_handlers
        manager.register_handlers_from_module(specialized_handlers)
    except ImportError:
        manager.logger.warning("specialized_handlers module not found, skipping auto-registration")
    
    # Set up persistent views
    await manager.setup_persistent_views()
    
    # Recover any database-persisted buttons
    await manager.recover_database_buttons()
    
    # Make available through context
    context.ui_manager = manager
    
    manager.logger.info("Unified persistent UI system initialized successfully")
    return manager