#!/usr/bin/env python3
import os
import asyncio
import logging
import sys
import traceback
from typing import List, Dict, Optional, Any, Set, ClassVar
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from discord import app_commands

from config import load_config
from utils.context import BotContext
from utils.errors import BotError, ErrorSeverity, log_exception, handle_command_error
from utils.feature_flags import FeatureFlag, feature_manager
from services.database import DatabaseService, ConfigError
from services.message_service import MessageRouter
from services.group_quiz import GroupQuizManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("discord_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bot")

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Load configuration
config = load_config()

class EducationalQuizBot(commands.AutoShardedBot):
    """
    Advanced Discord bot for educational purposes with quiz functionality
    using LLMs for flashcard-like scenarios.
    Uses AutoShardedBot for automatic sharding when scale requires it.
    """
    
    # Class constants
    VERSION: ClassVar[str] = "1.0.0"
    DEFAULT_ACTIVITY_TYPE: ClassVar[discord.ActivityType] = discord.ActivityType.playing
    
    # Status rotation messages
    ROTATING_STATUSES: ClassVar[List[Dict[str, Any]]] = [
        {"type": discord.ActivityType.playing, "name": "/help for commands!"},
        {"type": discord.ActivityType.listening, "name": "/faq to learn more!"},
        {"type": discord.ActivityType.playing, "name": "/trivia start to learning!"},
        {"type": discord.ActivityType.watching, "name": "over educational content"},
        {"type": discord.ActivityType.playing, "name": "/stats to track progress!"},
        {"type": discord.ActivityType.listening, "name": "to your quiz requests"},
        {"type": discord.ActivityType.playing, "name": "A trivia game!"},
        {"type": discord.ActivityType.watching, "name": "knowledge grow 🌱"},
        {"type": discord.ActivityType.playing, "name": "/preferences as an admin to customize!"},
        {"type": discord.ActivityType.listening, "name": "quiz feedback"},
    ]
    
    def __init__(self) -> None:
        """Initialize the Discord bot with required intents and services."""
        # Store the config
        self.config = config
        self.bot_config = config  # Add bot_config alias for backward compatibility
        
        # Track bot uptime
        self.uptime = None
        
        # Initialize status rotation index
        self._status_index = 0
        
        try:
            # Configure intents with privileged intents
            intents = discord.Intents.default()
            intents.message_content = True  # Required for prefix commands
            intents.members = True          # Required for user-related features
            
            logger.info("Using privileged intents (message_content, members)")
            logger.info("Make sure these are enabled at https://discord.com/developers/applications")
            
            super().__init__(
                command_prefix=config.default_prefix,
                intents=intents,
                help_command=None,  # We'll implement our own help command
                case_insensitive=True  # Allow case-insensitive command invocation
            )
        except discord.errors.PrivilegedIntentsRequired:
            # Fall back to non-privileged intents if privileged ones aren't available
            logger.warning("Privileged intents not enabled in Discord Developer Portal!")
            logger.warning("Please go to https://discord.com/developers/applications")
            logger.warning("Select your application, go to 'Bot' section, and enable:")
            logger.warning("- MESSAGE CONTENT INTENT")
            logger.warning("- GUILD MEMBERS INTENT")
            logger.warning("Falling back to basic functionality without privileged intents.")
            
            # Use only default intents
            basic_intents = discord.Intents.default()
            
            super().__init__(
                command_prefix=config.default_prefix,
                intents=basic_intents,
                help_command=None,
                case_insensitive=True
            )
        
        # Initialize service placeholders - actual initialization happens in setup_hook
        self.db_service = None
        self.message_router = None
        self.group_quiz_manager = None
        
        # Set up bot context for dependency injection
        self.context: Optional[BotContext] = None
        
        # Setup shutdown handlers
        self._setup_shutdown_handlers()
        
        # List of cogs to load - maintain in order of dependencies
        self._cogs_to_load: List[str] = [
            "cogs.help",       # Help command should load first
            "cogs.quiz",       # Core quiz functionality
            "cogs.group_quiz", # Group quiz feature
            "cogs.admin",      # Administrative commands
            "cogs.faq",        # FAQ system
            "cogs.onboarding", # Server onboarding
            "cogs.stats",      # User statistics
            "cogs.preferences", # User preferences
            "cogs.custom_quiz", # Custom quiz creation
            "cogs.version"      # Version management system
        ]
        
        # Track error counts to prevent infinite error loops
        self._error_counts: Dict[str, int] = {}
        self._max_errors: int = 5
    
    def _setup_shutdown_handlers(self):
        """Setup handlers for graceful shutdown."""
        import signal
        
        # Define the shutdown handler
        def shutdown_handler(signum, frame):
            logger.info(f"Received shutdown signal {signum}")
            asyncio.create_task(self.close_gracefully())
        
        # Register handlers for common shutdown signals
        for sig in [signal.SIGINT, signal.SIGTERM]:
            try:
                signal.signal(sig, shutdown_handler)
                logger.debug(f"Registered shutdown handler for signal {sig}")
            except Exception as e:
                logger.warning(f"Failed to register shutdown handler for signal {sig}: {e}")
    
    async def close_gracefully(self):
        """Perform graceful shutdown."""
        logger.info("Performing graceful shutdown...")
        
        # Close database connections
        if self.db_service:
            try:
                await self.db_service.close()
                logger.info("Database connections closed")
            except Exception as e:
                logger.error(f"Error closing database connections: {e}")
        
        # Close Discord connection
        try:
            await self.close()
            logger.info("Discord connection closed")
        except Exception as e:
            logger.error(f"Error closing Discord connection: {e}")
        
        # Stop the status rotation task
        if self.rotate_status.is_running():
            self.rotate_status.stop()
            logger.info("Stopped status rotation task")
    
    async def setup_hook(self) -> None:
        """
        Called when the bot is starting up.
        This is a Discord.py lifecycle hook for initialization.
        """
        try:
            logger.info("Starting bot initialization...")
            
            # Set initial uptime
            import datetime
            self.uptime = datetime.datetime.now()
            
            # Initialize services that need async setup
            await self._setup_services()
            
            # Load cogs after services and context are initialized
            await self._load_cogs()
            
            # Sync slash commands - this is the only place we should do the initial sync
            await self._sync_commands()
            
            logger.info("Bot initialization completed successfully")
            
        except Exception as e:
            logger.critical(f"Critical error during bot initialization: {e}")
            log_exception(e, context={"stage": "setup_hook"}, level=logging.CRITICAL)
            # Re-raise to prevent bot from starting with incomplete initialization
            raise
    
    async def _setup_services(self) -> None:
        """Initialize bot services."""
        try:
            # Initialize database service
            try:
                self.db_service = DatabaseService(config=self.config.database)
                await self.db_service.initialize()
            except ConfigError as e:
                logger.critical(f"Database configuration error: {e}")
                logger.warning("Bot will run with limited functionality (no database features available)")
                self.db_service = None
            except Exception as e:
                logger.critical(f"Failed to initialize database service: {e}")
                logger.warning("Bot will run with limited functionality (no database features available)")
                self.db_service = None
            
            # Initialize other services
            self.message_router = MessageRouter(self)
            self.group_quiz_manager = GroupQuizManager(self)
            
            # Initialize version service
            version_service = None
            if self.db_service:
                try:
                    from services.version_service import initialize_version_service
                    version_service = initialize_version_service(self.db_service)
                    await version_service.initialize()
                    logger.info("Version service initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize version service: {e}")
                    version_service = None
            
            # Create context with all services
            self.context = BotContext(
                bot=self,
                config=self.config,
                db_service=self.db_service,
                message_router=self.message_router,
                group_quiz_manager=self.group_quiz_manager,
                version_service=version_service
            )
            
            logger.info("Services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise
    
    async def _load_cogs(self) -> None:
        """Load all cogs from the cogs directory dynamically."""
        from cogs.cog_loader import CogLoader
        
        loaded_cogs_list = []
        failed_cogs_list = []

        logger.info("Starting to load cogs...")
        
        # Use predefined cog list for controlled loading order
        cogs_to_load = self._cogs_to_load
        
        for cog_name in cogs_to_load:
            try:
                # Check if already loaded
                if cog_name in self.extensions:
                    logger.info(f"Reloading extension: {cog_name}")
                    await self.reload_extension(cog_name)
                else:
                    logger.info(f"Loading extension: {cog_name}")
                    
                    # Use CogLoader for better cog management
                    success = await CogLoader.load_cog_with_context(
                        bot=self,
                        module_name=cog_name,
                        context=self.context
                    )
                    
                    if success:
                        loaded_cogs_list.append(cog_name)
                        logger.info(f"Successfully loaded: {cog_name}")
                    else:
                        failed_cogs_list.append(cog_name)

            except commands.ExtensionError as e:
                logger.error(f"Failed to load extension {cog_name}: {e}", exc_info=True)
                failed_cogs_list.append(cog_name)
            except Exception as e:
                logger.error(f"Unexpected error loading {cog_name}: {e}", exc_info=True)
                failed_cogs_list.append(cog_name)
        
        if loaded_cogs_list:
            logger.info(f"Successfully loaded {len(loaded_cogs_list)} cogs: {', '.join(loaded_cogs_list)}")
        else:
            logger.warning("No cogs were loaded.")
        
        if failed_cogs_list:
            logger.error(f"Failed to load {len(failed_cogs_list)} cogs: {', '.join(failed_cogs_list)}")
    
    async def _sync_commands(self) -> None:
        """
        Sync slash commands with Discord.
        This should only be called once during setup_hook.
        """
        try:
            # Log existing commands before syncing
            commands_before = list(self.tree.get_commands())
            logger.info(f"Commands in tree before sync: {len(commands_before)}")
            for cmd in commands_before:
                logger.info(f"Command before sync: {cmd.name}")
                # Check for subcommands
                if hasattr(cmd, "children") and cmd.children:
                    for name, child in cmd.children.items():
                        logger.info(f"  - Subcommand: {cmd.name} {name}")
            
            # Sync globally
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} global command(s)")
            
            # Log what commands were synced
            for cmd in synced:
                logger.info(f"Global command synced: {cmd.name}")
                # Check for subcommands
                if hasattr(cmd, "children") and cmd.children:
                    for name, child in cmd.children.items():
                        logger.info(f"  - Synced subcommand: {cmd.name} {name}")
            
            # Log final command tree state
            all_commands = list(self.tree.get_commands())
            logger.info(f"Final command tree after sync: {len(all_commands)} commands")
                
        except discord.HTTPException as e:
            logger.error(f"Failed to sync commands: {e}")
            # Not raising this exception as the bot can still function with prefix commands
        except Exception as e:
            logger.error(f"Unexpected error syncing commands: {e}", exc_info=True)
            log_exception(e, context={"stage": "command_sync"})

    async def get_context(self, message: discord.Message, *, cls=None) -> commands.Context:
        """
        Get the context for a message.
        
        Args:
            message: The Discord message
            cls: Optional custom context class
            
        Returns:
            The command context
        """
        # Don't use BotContext as the context class - it's not a commands.Context subclass
        if cls is None:
            # Use default commands.Context class if none provided
            return await super().get_context(message)
        return await super().get_context(message, cls=cls)
    
    async def process_commands(self, message: discord.Message) -> None:
        """
        Process commands in a message.
        
        Args:
            message: The Discord message to process
        """
        # Ignore messages from bots
        if message.author.bot:
            return
        
        try:
            # Get context and invoke command
            ctx = await self.get_context(message)
            if ctx.command is not None:
                await self.invoke(ctx)
            elif self.message_router and not message.content.startswith(self.command_prefix):
                # If not a command and message router exists, try processing as a regular message
                await self.message_router.process_message(message)
        except Exception as e:
            # Log the error
            log_exception(
                e, 
                context={
                    "event": "process_commands",
                    "message_content": message.content[:100] # Truncate for privacy
                }
            )
            # Don't re-raise to prevent the bot from crashing
    
    async def on_ready(self) -> None:
        """Called when the bot is ready and connected to Discord."""
        logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Set the uptime when bot is ready
        if self.uptime is None:
            import datetime
            self.uptime = datetime.datetime.now()
            logger.info(f"Bot started at {self.uptime}")
        
        # If context hasn't been initialized yet, ensure it exists
        if self.context is None:
            logger.warning("BotContext not initialized during setup_hook, creating now")
            self.context = BotContext(
                bot=self,
                config=self.config,
                db_service=self.db_service,
                message_router=self.message_router,
                group_quiz_manager=self.group_quiz_manager
            )
        
        for cog_name, cog in self.cogs.items():
            if hasattr(cog, 'set_context'):
                try:
                    cog.set_context(self.context)
                    logger.debug(f"Set context for cog: {cog_name}")
                except Exception as e:
                    logger.error(f"Error setting context for cog {cog_name}: {e}")
            
        # Start the status rotation task if not already running
        if not self.rotate_status.is_running():
            self.rotate_status.start()
            logger.info("Started status rotation task")
            
        # Set initial activity/presence - the rotation task will handle it after this
        await self.change_presence(
            activity=discord.Activity(
                type=self.DEFAULT_ACTIVITY_TYPE,
                name=f"{self.config.default_prefix}help"
            ),
            status=discord.Status.online
        )
            
    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        """
        Global error handler for all events.
        
        Args:
            event_method: The name of the event that raised the exception
            *args: Arguments passed to the event
            **kwargs: Keyword arguments passed to the event
        """
        # Get the exception that was raised
        error = sys.exc_info()[1]
        
        # Track error frequency to prevent error spam
        if event_method in self._error_counts:
            self._error_counts[event_method] += 1
        else:
            self._error_counts[event_method] = 1
        
        # Log the error with context information
        log_exception(
            error, 
            context={
                "event": event_method,
                "count": self._error_counts[event_method]
            },
            level=logging.ERROR
        )
        
        # If we've seen too many errors from this event, ignore future instances
        if self._error_counts[event_method] >= self._max_errors:
            logger.warning(
                f"Too many errors from event {event_method}, ignoring further errors"
            )
            return
        
        # Print traceback to console for visibility
        traceback.print_exception(type(error), error, error.__traceback__)
    
    @tasks.loop(minutes=5.0)
    async def rotate_status(self) -> None:
        """Rotate bot's status every 5 minutes."""
        try:
            # Get the current status from the rotation list
            status_info = self.ROTATING_STATUSES[self._status_index]
            
            # Create the activity
            activity = discord.Activity(
                type=status_info["type"],
                name=status_info["name"]
            )
            
            # Set the presence
            await self.change_presence(activity=activity, status=discord.Status.online)
            
            # Update the index for next rotation
            self._status_index = (self._status_index + 1) % len(self.ROTATING_STATUSES)
            
        except Exception as e:
            logger.error(f"Error rotating status: {e}")
    
    @rotate_status.before_loop
    async def before_rotate_status(self) -> None:
        """Wait until the bot is ready before starting status rotation."""
        await self.wait_until_ready()

async def main() -> None:
    """Main entry point for the bot."""
    bot = EducationalQuizBot()
    try:
        await bot.start(TOKEN)
    except discord.errors.PrivilegedIntentsRequired:
        logger.critical("============================================================")
        logger.critical("ERROR: Privileged intents not enabled in Discord Developer Portal!")
        logger.critical("To fix this issue, follow these steps:")
        logger.critical("1. Go to https://discord.com/developers/applications")
        logger.critical("2. Select your application")
        logger.critical("3. Navigate to the 'Bot' section")
        logger.critical("4. Scroll down to 'Privileged Gateway Intents'")
        logger.critical("5. Enable BOTH 'Message Content Intent' AND 'Server Members Intent'")
        logger.critical("6. Save changes and restart the bot")
        logger.critical("============================================================")
        sys.exit(1)
    finally:
        # Clean up resources
        if bot.db_service:
            await bot.db_service.close()
            logger.info("Database resources cleaned up")

if __name__ == "__main__":
    if not TOKEN:
        logger.critical("DISCORD_TOKEN not found in environment variables")
        sys.exit(1)
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated via keyboard interrupt")
    except Exception as e:
        logger.critical("Unhandled exception in main loop")
        log_exception(e, level=logging.CRITICAL)
        traceback.print_exc()
        sys.exit(1) 