import logging
import traceback
from enum import Enum
from typing import Optional, Dict, Any, Union, Type, Callable

# Configure the logger
logger = logging.getLogger("bot.errors")

class ErrorSeverity(Enum):
    """Error severity levels for better categorization of issues."""
    DEBUG = 0       # Minor issues that don't affect functionality
    INFO = 1        # Informational events that might be relevant for debugging
    WARNING = 2     # Issues that don't prevent operation but should be addressed
    ERROR = 3       # Serious issues that prevent a specific operation from completing
    CRITICAL = 4    # Catastrophic failures that could affect the whole system


class BotError(Exception):
    """Base exception class for all bot-related errors."""
    
    def __init__(
        self, 
        message: str, 
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        """
        Initialize a bot error with enhanced context.
        
        Args:
            message: Human-readable error message
            severity: Error severity level
            details: Additional context about the error
            original_exception: Original exception if this is wrapping another error
        """
        self.message = message
        self.severity = severity
        self.details = details or {}
        self.original_exception = original_exception
        super().__init__(message)
        
    def __str__(self) -> str:
        """Create a detailed string representation of the error."""
        result = f"{self.severity.name}: {self.message}"
        
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            result += f" [{details_str}]"
            
        if self.original_exception:
            result += f" | Original error: {str(self.original_exception)}"
            
        return result


class ConfigurationError(BotError):
    """Error raised when there's an issue with the bot configuration."""
    pass


class DatabaseError(BotError):
    """Error raised when there's an issue with database operations."""
    pass


class APIError(BotError):
    """Error raised when there's an issue with external API calls (like LLM services)."""
    pass


class QuizGenerationError(BotError):
    """Error raised when there's an issue generating quiz questions."""
    pass


class UserInputError(BotError):
    """Error raised when user input is invalid or cannot be processed."""
    
    def __init__(
        self, 
        message: str,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        command: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize user input error with context about the user and command.
        
        Args:
            message: Error message
            user_id: ID of the user who caused the error
            guild_id: ID of the guild where the error occurred
            channel_id: ID of the channel where the error occurred
            command: The command that was attempted
            **kwargs: Additional details to store
        """
        details = kwargs.get("details", {})
        details.update({
            "user_id": user_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "command": command
        })
        
        # Filter out None values
        details = {k: v for k, v in details.items() if v is not None}
        
        super().__init__(
            message=message,
            severity=ErrorSeverity.WARNING,
            details=details,
            original_exception=kwargs.get("original_exception")
        )


def log_exception(
    exc: Exception,
    logger_instance: Optional[logging.Logger] = None,
    level: int = logging.ERROR,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an exception with enhanced context and traceback.
    
    Args:
        exc: The exception to log
        logger_instance: Logger instance to use (defaults to bot.errors)
        level: Logging level to use
        context: Additional contextual information
    """
    log = logger_instance or logger
    
    # Format the error message
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    
    # If it's our custom BotError, use its severity to determine log level
    if isinstance(exc, BotError):
        if exc.severity == ErrorSeverity.CRITICAL:
            level = logging.CRITICAL
        elif exc.severity == ErrorSeverity.ERROR:
            level = logging.ERROR
        elif exc.severity == ErrorSeverity.WARNING:
            level = logging.WARNING
        elif exc.severity == ErrorSeverity.INFO:
            level = logging.INFO
        elif exc.severity == ErrorSeverity.DEBUG:
            level = logging.DEBUG
    
    # Create the log message with context
    context_str = ""
    if context:
        context_str = " | Context: " + ", ".join(f"{k}={v}" for k, v in context.items())
    
    # Log the error with the traceback included
    log.log(level, f"Exception: {exc}{context_str}\n{tb_str}")


def handle_command_error(
    error: Exception,
    error_handlers: Dict[Type[Exception], Callable] = None
) -> Optional[str]:
    """
    Handle command errors consistently, with specific handling for known error types.
    
    Args:
        error: The exception that occurred
        error_handlers: Dictionary mapping exception types to handler functions
        
    Returns:
        Optional error message to display to the user, or None if already handled
    """
    # Default handlers if none provided
    if error_handlers is None:
        error_handlers = {}
    
    # Log the error
    log_exception(error)
    
    # Find the most specific handler for this error type
    for error_type, handler in error_handlers.items():
        if isinstance(error, error_type):
            return handler(error)
    
    # Default handling if no specific handler found
    if isinstance(error, BotError):
        return str(error)
    
    # For unexpected errors, provide a generic message
    return f"An unexpected error occurred: {str(error)}"


def safe_execute(
    func: Callable,
    error_msg: str = "Operation failed",
    fallback_value: Any = None,
    log_error: bool = True,
    reraise: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Execute a function safely, handling any exceptions.
    
    Args:
        func: Function to execute
        error_msg: Error message if the function fails
        fallback_value: Value to return if the function fails
        log_error: Whether to log the error
        reraise: Whether to reraise the exception after handling
        context: Additional context for error logging
        
    Returns:
        Result of the function or fallback value
        
    Raises:
        Exception: The original exception if reraise is True
    """
    try:
        return func()
    except Exception as e:
        if log_error:
            log_exception(e, context=context)
        
        if reraise:
            raise
            
        return fallback_value 