import logging
from typing import Dict, Any, Optional
import discord
from discord.ext import commands
import asyncio

from utils.errors import BotError, log_exception
from utils.feature_flags import feature_manager

logger = logging.getLogger("bot.context")

class BotContext:
    """
    Centralized context for bot components to avoid circular imports.
    Provides access to shared resources like the bot instance, configuration,
    and services.
    """
    
    def __init__(self, bot: commands.Bot, config: Any, 
                 db_service=None, db_service_v2=None, message_router=None, 
                 group_quiz_manager=None, version_service=None):
        """
        Initialize the bot context.
        
        Args:
            bot: The Discord bot instance
            config: The loaded configuration
            db_service: Original Database service instance (deprecated)
            db_service_v2: Enhanced Database service V2 instance
            message_router: Message router service
            group_quiz_manager: Group quiz manager service
            version_service: Version management service
        """
        self.bot = bot
        self.config = config
        self.db_service = db_service  # Legacy service for backward compatibility
        self.db_service_v2 = db_service_v2  # Enhanced V2 database service
        self.message_router = message_router
        self.group_quiz_manager = group_quiz_manager
        self.version_service = version_service
        self.feature_manager = feature_manager
        self._services = {}  # Additional service registry
        
        # Set the default log level based on debug mode
        self._configure_logging()
        
    def _configure_logging(self):
        """Configure logging based on debug mode."""
        if self.feature_manager.is_enabled("debug_mode"):
            logging.getLogger("bot").setLevel(logging.DEBUG)
            logger.debug("Debug mode enabled - setting log level to DEBUG")
    
    async def initialize_services(self):
        """Initialize all shared services asynchronously."""
        logger.info("Initializing bot services...")
        
        try:
            # Import services here to avoid circular imports
            from services.database import DatabaseService
            from services.message_service import MessageRouter
            from services.group_quiz_multi_guild import GroupQuizManager
            from services.database_initializer import DatabaseInitializer
            
            # Initialize database service
            if hasattr(self.config, "database"):
                self.db_service = DatabaseService(config=self.config.database)
                await self.db_service.initialize()
                logger.info(f"Database service initialized with host: {self.config.database.host if hasattr(self.config.database, 'host') else 'Using configured host'}")
            else:
                logger.error("No database configuration found")
                raise BotError("Missing database configuration")
            
            # Initialize database initializer for schema management
            db_initializer = DatabaseInitializer(self.db_service)
            await db_initializer.initialize_database()
            logger.info("Database schema initialized and validated")
            
            # Register the initializer as a service
            self.register_service("db_initializer", db_initializer)
            
            # Initialize message router
            self.message_router = MessageRouter(self.bot)
            logger.info("Message router service initialized")
            
            # Initialize group quiz manager - conditionally, based on feature flag
            if self.feature_manager.is_enabled("group_quiz"):
                self.group_quiz_manager = GroupQuizManager()
                self.group_quiz_manager.set_db_service(self.db_service)  # Use the main db_service
                logger.info("Group quiz manager initialized with database service")
            else:
                logger.info("Group quiz feature disabled - manager not initialized")
            
            # Set global instances for backward compatibility
            # This allows existing modules to continue working
            import sys
            import services.database
            import services.message_service
            import services.group_quiz
            
            services.database.db_service = self.db_service
            services.message_service.message_router = self.message_router
            
            # Only set the group quiz manager if it's enabled
            if self.group_quiz_manager:
                services.group_quiz.group_quiz_manager = self.group_quiz_manager
            
            logger.info("All services initialized successfully")
            
        except Exception as e:
            logger.critical("Failed to initialize services", exc_info=True)
            log_exception(e, context={"stage": "initialize_services"})
            raise
        
    def register_service(self, name: str, service: Any):
        """
        Register a custom service in the context.
        
        Args:
            name: Name to register the service under
            service: The service instance
        """
        if name in self._services:
            logger.warning(f"Overwriting existing service: {name}")
            
        self._services[name] = service
        logger.debug(f"Registered service: {name}")
        
    def get_service(self, name: str) -> Optional[Any]:
        """
        Get a registered service.
        
        Args:
            name: Name of the service to retrieve
            
        Returns:
            The service instance or None if not found
        """
        service = self._services.get(name)
        if service is None:
            logger.debug(f"Service not found: {name}")
        return service
    
    def add_to_all_cogs(self, cogs: list):
        """
        Attach this context to all cogs when loading them.
        
        Args:
            cogs: List of cog instances
        """
        for cog in cogs:
            if hasattr(cog, 'set_context'):
                try:
                    cog.set_context(self)
                    logger.debug(f"Set context for {cog.__class__.__name__}")
                except Exception as e:
                    logger.error(f"Failed to set context for {cog.__class__.__name__}: {e}")
            else:
                logger.warning(f"Cog {cog.__class__.__name__} does not implement set_context")
    
    def is_feature_enabled(self, feature: str, guild_id: Optional[int] = None) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature: The feature flag to check
            guild_id: Guild ID to check for guild-specific overrides
            
        Returns:
            True if the feature is enabled, False otherwise
        """
        return self.feature_manager.is_enabled(feature, guild_id)
    
    def update_feature_flags(self):
        """Update internal state based on current feature flags."""
        # Reconfigure logging if debug mode changed
        self._configure_logging()
        
    async def get_preferred_db_service(self):
        """
        Get the preferred database service.
        
        Returns:
            The database service instance
        """
        return self.db_service
        
    async def close_services(self):
        """Close and clean up all services properly."""
        
        # Close database service
        if self.db_service:
            try:
                await self.db_service.close()
                logger.info("Database service closed successfully")
            except Exception as e:
                logger.error(f"Error closing database service: {e}")
                
        # Close other services that need cleanup
        for name, service in self._services.items():
            if hasattr(service, 'close') and callable(service.close):
                try:
                    if asyncio.iscoroutinefunction(service.close):
                        await service.close()
                    else:
                        service.close()
                    logger.info(f"Service {name} closed successfully")
                except Exception as e:
                    logger.error(f"Error closing service {name}: {e}")