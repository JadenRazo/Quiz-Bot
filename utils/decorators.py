import functools
import inspect
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger("bot.decorators")

T = TypeVar('T')

def cache_result(
    expire_seconds: int = 300,
    key_prefix: str = "",
    skip_first_arg: bool = True
):
    """
    Cache results of a function using the database cache.
    
    This decorator is meant to be used with methods in classes that 
    have access to a database service with caching capabilities.
    
    Args:
        expire_seconds: How long to cache the result for
        key_prefix: Prefix to add to the cache key
        skip_first_arg: Whether to skip the first argument (self) in key generation
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """The actual decorator."""
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Get the instance with db_service
            if not args:
                logger.warning(f"Cannot cache {func.__name__}: No instance provided")
                return func(*args, **kwargs)
                
            instance = args[0]
            db_service = getattr(instance, "db_service", None)
            
            if db_service is None:
                db_service = getattr(instance, "_db_service", None)
                
            if db_service is None:
                logger.warning(f"Cannot cache {func.__name__}: No db_service found in instance")
                return func(*args, **kwargs)
            
            # Generate a cache key from the function name and arguments
            cache_args = args[1:] if skip_first_arg else args
            
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Filter out self parameter if skip_first_arg
            if skip_first_arg and len(bound_args.arguments) > 0:
                filtered_args = {k: v for k, v in bound_args.arguments.items() 
                                 if k != next(iter(bound_args.arguments.keys()))}
            else:
                filtered_args = bound_args.arguments
                
            # Create a deterministic string from the arguments
            args_str = json.dumps(filtered_args, sort_keys=True, default=str)
            
            # Create the cache key
            key = f"{key_prefix}:{func.__module__}.{func.__name__}:{hash(args_str)}"
            
            # Try to get from cache
            cached_result = db_service.get_cached_query_result(key)
            if cached_result:
                try:
                    return json.loads(cached_result)
                except:
                    logger.warning(f"Failed to deserialize cached result for {key}")
            
            # Not in cache, execute the function
            result = func(*args, **kwargs)
            
            # Cache the result
            try:
                serialized = json.dumps(result, default=str)
                db_service.cache_query_result(key, serialized, expire_seconds)
            except Exception as e:
                logger.warning(f"Failed to cache result for {key}: {e}")
                
            return result
            
        return wrapper
    return decorator

def time_execution(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that logs the execution time of a function.
    
    Args:
        func: The function to time
        
    Returns:
        Wrapped function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        
        # Get function details
        if args and hasattr(args[0], "__class__"):
            class_name = args[0].__class__.__name__
            logger.debug(f"Execution time: {class_name}.{func.__name__} - {elapsed:.3f}s")
        else:
            logger.debug(f"Execution time: {func.__name__} - {elapsed:.3f}s")
            
        return result
    return wrapper

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, 
         exceptions: tuple = (Exception,), logger_instance=None):
    """
    Retry a function if it fails with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch and retry
        logger_instance: Logger to use (defaults to bot.decorators)
        
    Returns:
        Decorator function
    """
    log = logger_instance or logger
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt == max_attempts:
                        log.error(f"All retry attempts failed for {func.__name__}: {e}")
                        raise
                        
                    log.warning(f"Retry attempt {attempt}/{max_attempts} for {func.__name__}: {e}")
                    log.info(f"Waiting {current_delay}s before retrying")
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
        return wrapper
    return decorator 