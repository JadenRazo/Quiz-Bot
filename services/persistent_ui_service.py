"""
Persistent UI Service for Database Button Storage and Recovery

This service handles the database persistence layer for the unified persistent UI system,
providing full button persistence across bot restarts and proper recovery mechanisms.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

import discord

from utils.context import BotContext
from utils.unified_persistent_ui import ButtonState, ButtonAction, PersistenceMode


class PersistentUIService:
    """
    Service for managing database persistence of UI buttons and views.
    
    Provides comprehensive button storage, recovery, and lifecycle management
    to ensure buttons remain functional across bot restarts.
    """
    
    def __init__(self, context: BotContext):
        self.context = context
        self.database = context.database
        self.logger = logging.getLogger("PersistentUIService")
    
    async def store_button(
        self,
        custom_id: str,
        button_type: str,
        handler_class: str,
        view_class: str,
        message: discord.Message,
        button_state: ButtonState,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Store a persistent button in the database.
        
        Args:
            custom_id: Unique button identifier
            button_type: Type of button (action, navigation, toggle, etc.)
            handler_class: Name of the handler class
            view_class: Name of the view class
            message: Discord message containing the button
            button_state: Button state data
            expires_at: Optional expiration time
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO persistent_buttons 
                    (custom_id, button_type, handler_class, view_class, guild_id, 
                     channel_id, message_id, user_id, data, created_at, expires_at, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (custom_id, message_id) DO UPDATE SET
                    data = EXCLUDED.data,
                    expires_at = EXCLUDED.expires_at,
                    is_active = EXCLUDED.is_active
                """, (
                    custom_id, button_type, handler_class, view_class,
                    message.guild.id if message.guild else None,
                    message.channel.id, message.id, button_state.user_id,
                    json.dumps(button_state.data), datetime.utcnow(),
                    expires_at, True
                ))
                
                self.logger.debug(f"Stored button {custom_id} for message {message.id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to store button {custom_id}: {e}")
            return False
    
    async def get_button_state(self, custom_id: str, message_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve button state from database.
        
        Args:
            custom_id: Button's custom ID
            message_id: Message ID containing the button
            
        Returns:
            Button data dictionary or None if not found
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                row = await conn.fetchone("""
                    SELECT * FROM persistent_buttons 
                    WHERE custom_id = %s AND message_id = %s AND is_active = TRUE
                    AND (expires_at IS NULL OR expires_at > NOW())
                """, (custom_id, message_id))
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get button state {custom_id}: {e}")
            return None
    
    async def register_message(
        self,
        message: discord.Message,
        view_class: str,
        embed_data: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Register a message in the UI message registry.
        
        Args:
            message: Discord message with persistent UI
            view_class: Name of the view class
            embed_data: Optional embed data for recovery
            expires_at: Optional expiration time
            
        Returns:
            True if registered successfully
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ui_message_registry 
                    (message_id, channel_id, guild_id, view_class, embed_data, 
                     content_text, created_at, expires_at, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO UPDATE SET
                    embed_data = EXCLUDED.embed_data,
                    last_updated = NOW(),
                    expires_at = EXCLUDED.expires_at,
                    is_active = EXCLUDED.is_active
                """, (
                    message.id, message.channel.id,
                    message.guild.id if message.guild else None,
                    view_class, json.dumps(embed_data) if embed_data else None,
                    message.content, datetime.utcnow(), expires_at, True
                ))
                
                self.logger.debug(f"Registered message {message.id} with view {view_class}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to register message {message.id}: {e}")
            return False
    
    async def recover_persistent_buttons(self) -> List[Dict[str, Any]]:
        """
        Recover all active persistent buttons from database.
        
        Returns:
            List of button data dictionaries ready for recovery
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                rows = await conn.fetchall("""
                    SELECT pb.*, mr.view_class as message_view_class
                    FROM persistent_buttons pb
                    LEFT JOIN ui_message_registry mr ON pb.message_id = mr.message_id
                    WHERE pb.is_active = TRUE 
                    AND (pb.expires_at IS NULL OR pb.expires_at > NOW())
                    ORDER BY pb.message_id, pb.created_at
                """)
                
                buttons = [dict(row) for row in rows]
                self.logger.info(f"Found {len(buttons)} persistent buttons for recovery")
                return buttons
                
        except Exception as e:
            self.logger.error(f"Failed to recover persistent buttons: {e}")
            return []
    
    async def get_message_buttons(self, message_id: int) -> List[Dict[str, Any]]:
        """
        Get all buttons for a specific message.
        
        Args:
            message_id: Discord message ID
            
        Returns:
            List of button data for the message
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                rows = await conn.fetchall("""
                    SELECT * FROM persistent_buttons 
                    WHERE message_id = %s AND is_active = TRUE
                    AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY created_at
                """, (message_id,))
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Failed to get buttons for message {message_id}: {e}")
            return []
    
    async def deactivate_button(self, custom_id: str, message_id: int) -> bool:
        """
        Deactivate a persistent button.
        
        Args:
            custom_id: Button's custom ID
            message_id: Message ID containing the button
            
        Returns:
            True if deactivated successfully
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                result = await conn.execute("""
                    UPDATE persistent_buttons 
                    SET is_active = FALSE
                    WHERE custom_id = %s AND message_id = %s
                """, (custom_id, message_id))
                
                if result.rowcount > 0:
                    self.logger.debug(f"Deactivated button {custom_id}")
                    return True
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to deactivate button {custom_id}: {e}")
            return False
    
    async def deactivate_message(self, message_id: int) -> bool:
        """
        Deactivate all buttons for a message.
        
        Args:
            message_id: Discord message ID
            
        Returns:
            True if deactivated successfully
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                # Deactivate all buttons for this message
                await conn.execute("""
                    UPDATE persistent_buttons 
                    SET is_active = FALSE
                    WHERE message_id = %s
                """, (message_id,))
                
                # Deactivate message registry entry
                await conn.execute("""
                    UPDATE ui_message_registry 
                    SET is_active = FALSE
                    WHERE message_id = %s
                """, (message_id,))
                
                self.logger.debug(f"Deactivated all buttons for message {message_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to deactivate message {message_id}: {e}")
            return False
    
    async def log_button_interaction(
        self,
        custom_id: str,
        user_id: int,
        guild_id: Optional[int],
        interaction_type: str,
        handler_class: str,
        data: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        response_time_ms: Optional[int] = None
    ) -> None:
        """
        Log a button interaction for analytics and debugging.
        
        Args:
            custom_id: Button's custom ID
            user_id: User who interacted
            guild_id: Guild ID (if applicable)
            interaction_type: Type of interaction (click, timeout, error)
            handler_class: Handler class name
            data: Optional interaction data
            success: Whether interaction was successful
            error_message: Error message if failed
            response_time_ms: Response time in milliseconds
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO button_interaction_logs 
                    (custom_id, user_id, guild_id, interaction_type, handler_class,
                     data, success, error_message, response_time_ms, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    custom_id, user_id, guild_id, interaction_type, handler_class,
                    json.dumps(data) if data else None, success, error_message,
                    response_time_ms, datetime.utcnow()
                ))
                
        except Exception as e:
            # Don't let logging failures affect the main interaction
            self.logger.warning(f"Failed to log button interaction: {e}")
    
    async def cleanup_expired_buttons(self) -> int:
        """
        Clean up expired and inactive buttons.
        
        Returns:
            Number of buttons cleaned up
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                result = await conn.execute("SELECT cleanup_expired_buttons()")
                cleaned_count = await result.fetchone()
                count = cleaned_count[0] if cleaned_count else 0
                
                self.logger.info(f"Cleaned up {count} expired buttons")
                return count
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired buttons: {e}")
            return 0
    
    async def get_button_analytics(
        self, 
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get button interaction analytics.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Analytics data dictionary
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                # Get interaction counts by handler
                handler_stats = await conn.fetchall("""
                    SELECT handler_class, interaction_type, 
                           COUNT(*) as count,
                           AVG(response_time_ms) as avg_response_time
                    FROM button_interaction_logs 
                    WHERE created_at > NOW() - INTERVAL '%s hours'
                    GROUP BY handler_class, interaction_type
                    ORDER BY count DESC
                """, (hours,))
                
                # Get error rates
                error_stats = await conn.fetchall("""
                    SELECT handler_class,
                           COUNT(*) as total_interactions,
                           SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errors
                    FROM button_interaction_logs 
                    WHERE created_at > NOW() - INTERVAL '%s hours'
                    GROUP BY handler_class
                    HAVING COUNT(*) > 0
                """, (hours,))
                
                return {
                    'period_hours': hours,
                    'handler_stats': [dict(row) for row in handler_stats],
                    'error_stats': [dict(row) for row in error_stats],
                    'generated_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get button analytics: {e}")
            return {'error': str(e)}
    
    async def initialize_tables(self) -> bool:
        """
        Initialize the persistent UI database tables.
        
        The persistent UI tables are included in the main schema.sql file,
        so this method just verifies they exist.
        
        Returns:
            True if tables exist or were created successfully
        """
        try:
            async with self.database._connection_pool.acquire() as conn:
                # Check if persistent_buttons table exists
                result = await conn.fetchone("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'persistent_buttons'
                    )
                """)
                
                if result and result[0]:
                    self.logger.debug("Persistent UI tables already exist")
                    return True
                else:
                    self.logger.warning("Persistent UI tables not found - they should be created by schema.sql")
                    return False
                
        except Exception as e:
            self.logger.error(f"Failed to verify persistent UI tables: {e}")
            return False