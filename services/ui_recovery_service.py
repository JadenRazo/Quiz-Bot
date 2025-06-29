"""
UI Recovery Service for Bot Startup Button Recovery

This service handles the recovery of persistent UI buttons when the bot starts up,
ensuring that buttons in existing messages remain functional after restarts.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

import discord
from discord.ext import tasks

from utils.context import BotContext
from utils.unified_persistent_ui import ButtonState, ButtonAction, PersistenceMode
from services.persistent_ui_service import PersistentUIService


class UIRecoveryService:
    """
    Service for recovering persistent UI elements after bot restarts.
    
    Scans existing messages with persistent buttons and re-establishes
    their functionality using the database persistence layer.
    """
    
    def __init__(self, context: BotContext):
        self.context = context
        self.bot = context.bot
        self.ui_service = PersistentUIService(context)
        self.logger = logging.getLogger("UIRecoveryService")
        
        # Track recovery progress
        self.recovery_stats = {
            'buttons_recovered': 0,
            'messages_scanned': 0,
            'errors_encountered': 0,
            'last_recovery': None
        }
        
        # Start periodic cleanup task
        self.cleanup_task.start()
    
    async def perform_startup_recovery(self) -> Dict[str, Any]:
        """
        Perform complete UI recovery on bot startup.
        
        Returns:
            Recovery statistics and results
        """
        self.logger.info("Starting persistent UI recovery process...")
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Initialize database tables if needed
            await self.ui_service.initialize_tables()
            
            # Step 2: Get all persistent buttons from database
            stored_buttons = await self.ui_service.recover_persistent_buttons()
            
            # Step 3: Organize buttons by message for efficient processing
            buttons_by_message = self._group_buttons_by_message(stored_buttons)
            
            # Step 4: Process each message and recover its buttons
            recovery_results = []
            for message_id, buttons in buttons_by_message.items():
                result = await self._recover_message_buttons(message_id, buttons)
                recovery_results.append(result)
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.1)
            
            # Step 5: Update global button registry for immediate use
            await self._update_global_registry(stored_buttons)
            
            # Step 6: Clean up expired buttons
            cleaned_count = await self.ui_service.cleanup_expired_buttons()
            
            # Calculate final statistics
            total_buttons = sum(len(buttons) for buttons in buttons_by_message.values())
            successful_messages = sum(1 for r in recovery_results if r['success'])
            
            recovery_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.recovery_stats.update({
                'buttons_recovered': total_buttons,
                'messages_scanned': len(buttons_by_message),
                'successful_recoveries': successful_messages,
                'cleanup_count': cleaned_count,
                'recovery_time_seconds': recovery_time,
                'last_recovery': datetime.utcnow().isoformat()
            })
            
            self.logger.info(
                f"UI recovery completed: {total_buttons} buttons across "
                f"{len(buttons_by_message)} messages in {recovery_time:.2f}s"
            )
            
            return {
                'success': True,
                'statistics': self.recovery_stats,
                'details': recovery_results
            }
            
        except Exception as e:
            self.logger.error(f"UI recovery failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'statistics': self.recovery_stats
            }
    
    def _group_buttons_by_message(self, buttons: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        """Group buttons by their message ID for efficient processing."""
        buttons_by_message = {}
        for button in buttons:
            message_id = button['message_id']
            if message_id not in buttons_by_message:
                buttons_by_message[message_id] = []
            buttons_by_message[message_id].append(button)
        return buttons_by_message
    
    async def _recover_message_buttons(self, message_id: int, buttons: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Recover buttons for a specific message.
        
        Args:
            message_id: Discord message ID
            buttons: List of button data from database
            
        Returns:
            Recovery result dictionary
        """
        try:
            # Try to fetch the message from Discord
            message = await self._fetch_message(message_id, buttons[0])
            if not message:
                return {
                    'message_id': message_id,
                    'success': False,
                    'error': 'Message not found',
                    'buttons_count': len(buttons)
                }
            
            # Verify the message still has buttons
            if not message.components:
                self.logger.warning(f"Message {message_id} has no components, deactivating buttons")
                await self.ui_service.deactivate_message(message_id)
                return {
                    'message_id': message_id,
                    'success': False,
                    'error': 'Message has no components',
                    'buttons_count': len(buttons)
                }
            
            # Update global registry with button states
            recovered_count = 0
            for button in buttons:
                try:
                    # Recreate button state from database data
                    button_state = ButtonState(
                        user_id=button['user_id'],
                        action=ButtonAction(button['button_type']),
                        data=button['data'],
                        guild_id=button['guild_id'],
                        expires=int(button['expires_at'].timestamp()) if button['expires_at'] else None
                    )
                    
                    # Add to global registry for immediate functionality
                    from utils.unified_persistent_ui import _global_database_buttons
                    _global_database_buttons[button['custom_id']] = {
                        'state': button_state,
                        'handler_name': button['handler_class']
                    }
                    
                    recovered_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to recover button {button['custom_id']}: {e}")
            
            self.logger.debug(f"Recovered {recovered_count} buttons for message {message_id}")
            
            return {
                'message_id': message_id,
                'success': True,
                'buttons_recovered': recovered_count,
                'buttons_count': len(buttons),
                'channel_id': message.channel.id,
                'guild_id': message.guild.id if message.guild else None
            }
            
        except Exception as e:
            self.logger.error(f"Error recovering message {message_id}: {e}")
            return {
                'message_id': message_id,
                'success': False,
                'error': str(e),
                'buttons_count': len(buttons)
            }
    
    async def _fetch_message(self, message_id: int, button_data: Dict[str, Any]) -> Optional[discord.Message]:
        """
        Fetch a Discord message by ID using button data for context.
        
        Args:
            message_id: Discord message ID
            button_data: Button data containing channel/guild info
            
        Returns:
            Discord message object or None if not found
        """
        try:
            # Get channel from button data
            channel_id = button_data['channel_id']
            channel = self.bot.get_channel(channel_id)
            
            if not channel:
                # Try to fetch channel if not in cache
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except discord.NotFound:
                    self.logger.warning(f"Channel {channel_id} not found for message {message_id}")
                    return None
            
            # Fetch the message
            try:
                message = await channel.fetch_message(message_id)
                return message
            except discord.NotFound:
                self.logger.warning(f"Message {message_id} not found in channel {channel_id}")
                # Deactivate buttons for missing message
                await self.ui_service.deactivate_message(message_id)
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching message {message_id}: {e}")
            return None
    
    async def _update_global_registry(self, buttons: List[Dict[str, Any]]) -> None:
        """Update the global button registry with recovered buttons."""
        try:
            from utils.unified_persistent_ui import _global_database_buttons
            
            for button in buttons:
                try:
                    button_state = ButtonState(
                        user_id=button['user_id'],
                        action=ButtonAction(button['button_type']),
                        data=button['data'],
                        guild_id=button['guild_id'],
                        expires=int(button['expires_at'].timestamp()) if button['expires_at'] else None
                    )
                    
                    _global_database_buttons[button['custom_id']] = {
                        'state': button_state,
                        'handler_name': button['handler_class']
                    }
                    
                except Exception as e:
                    self.logger.error(f"Failed to update registry for button {button['custom_id']}: {e}")
            
            self.logger.info(f"Updated global registry with {len(buttons)} buttons")
            
        except Exception as e:
            self.logger.error(f"Failed to update global registry: {e}")
    
    async def verify_button_functionality(self, custom_id: str, message_id: int) -> bool:
        """
        Verify that a recovered button is functional.
        
        Args:
            custom_id: Button's custom ID
            message_id: Message ID containing the button
            
        Returns:
            True if button is functional
        """
        try:
            # Check if button exists in global registry
            from utils.unified_persistent_ui import _global_database_buttons
            if custom_id not in _global_database_buttons:
                return False
            
            # Check if button data is in database
            button_data = await self.ui_service.get_button_state(custom_id, message_id)
            if not button_data:
                return False
            
            # Verify button hasn't expired
            if button_data.get('expires_at'):
                if datetime.utcnow() > button_data['expires_at']:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying button {custom_id}: {e}")
            return False
    
    @tasks.loop(hours=6)
    async def cleanup_task(self):
        """Periodic cleanup task for expired buttons."""
        try:
            cleaned_count = await self.ui_service.cleanup_expired_buttons()
            if cleaned_count > 0:
                self.logger.info(f"Periodic cleanup removed {cleaned_count} expired buttons")
        except Exception as e:
            self.logger.error(f"Periodic cleanup failed: {e}")
    
    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """Wait for bot to be ready before starting cleanup task."""
        await self.bot.wait_until_ready()
    
    async def get_recovery_status(self) -> Dict[str, Any]:
        """
        Get current recovery status and statistics.
        
        Returns:
            Recovery status dictionary
        """
        try:
            # Get current button counts from database
            current_buttons = await self.ui_service.recover_persistent_buttons()
            active_count = len(current_buttons)
            
            # Get analytics
            analytics = await self.ui_service.get_button_analytics(hours=24)
            
            return {
                'recovery_stats': self.recovery_stats,
                'current_active_buttons': active_count,
                'analytics': analytics,
                'cleanup_task_running': self.cleanup_task.is_running()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting recovery status: {e}")
            return {'error': str(e)}
    
    def stop_cleanup_task(self):
        """Stop the periodic cleanup task."""
        if self.cleanup_task.is_running():
            self.cleanup_task.cancel()
            self.logger.info("Stopped UI cleanup task")