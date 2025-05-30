"""Input validation utilities for cogs."""

import re
from typing import Optional, List, Tuple, Any
import logging

logger = logging.getLogger("bot.cogs.utils.validation")

# Constants for validation
MIN_QUIZ_QUESTIONS = 1
MAX_QUIZ_QUESTIONS = 50
MIN_TOPIC_LENGTH = 2
MAX_TOPIC_LENGTH = 100
MIN_USERNAME_LENGTH = 1
MAX_USERNAME_LENGTH = 32
VALID_DIFFICULTIES = ['easy', 'medium', 'hard']
VALID_PROVIDERS = ['openai', 'anthropic', 'google']


def validate_quiz_count(count: Any) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Validate quiz question count.
    
    Args:
        count: The count to validate
        
    Returns:
        Tuple[bool, Optional[int], Optional[str]]: (is_valid, parsed_value, error_message)
    """
    try:
        count_int = int(count)
        
        if count_int < MIN_QUIZ_QUESTIONS:
            return False, None, f"Question count must be at least {MIN_QUIZ_QUESTIONS}"
        
        if count_int > MAX_QUIZ_QUESTIONS:
            return False, None, f"Question count cannot exceed {MAX_QUIZ_QUESTIONS}"
        
        return True, count_int, None
        
    except (ValueError, TypeError):
        return False, None, "Question count must be a valid number"


def validate_topic(topic: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate quiz topic.
    
    Args:
        topic: The topic to validate
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, cleaned_topic, error_message)
    """
    if not topic or not isinstance(topic, str):
        return False, None, "Topic must be provided"
    
    # Clean the topic
    cleaned_topic = topic.strip()
    
    if len(cleaned_topic) < MIN_TOPIC_LENGTH:
        return False, None, f"Topic must be at least {MIN_TOPIC_LENGTH} characters long"
    
    if len(cleaned_topic) > MAX_TOPIC_LENGTH:
        return False, None, f"Topic cannot exceed {MAX_TOPIC_LENGTH} characters"
    
    # Check for invalid characters
    if not re.match(r'^[\w\s\-.,!?\'"()]+$', cleaned_topic):
        return False, None, "Topic contains invalid characters"
    
    return True, cleaned_topic, None


def validate_difficulty(difficulty: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate quiz difficulty.
    
    Args:
        difficulty: The difficulty to validate
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, normalized_difficulty, error_message)
    """
    if not difficulty:
        return True, 'medium', None  # Default to medium
    
    normalized = difficulty.lower().strip()
    
    if normalized not in VALID_DIFFICULTIES:
        return False, None, f"Difficulty must be one of: {', '.join(VALID_DIFFICULTIES)}"
    
    return True, normalized, None


def validate_provider(provider: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate LLM provider.
    
    Args:
        provider: The provider to validate
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, normalized_provider, error_message)
    """
    if not provider:
        return True, 'openai', None  # Default to openai
    
    normalized = provider.lower().strip()
    
    if normalized not in VALID_PROVIDERS:
        return False, None, f"Provider must be one of: {', '.join(VALID_PROVIDERS)}"
    
    return True, normalized, None


def validate_username(username: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate username.
    
    Args:
        username: The username to validate
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, cleaned_username, error_message)
    """
    if not username or not isinstance(username, str):
        return False, None, "Username must be provided"
    
    cleaned = username.strip()
    
    if len(cleaned) < MIN_USERNAME_LENGTH:
        return False, None, f"Username must be at least {MIN_USERNAME_LENGTH} character long"
    
    if len(cleaned) > MAX_USERNAME_LENGTH:
        return False, None, f"Username cannot exceed {MAX_USERNAME_LENGTH} characters"
    
    # Check for Discord username restrictions
    if cleaned in ['everyone', 'here']:
        return False, None, "Username cannot be 'everyone' or 'here'"
    
    if cleaned.startswith('@'):
        cleaned = cleaned[1:]  # Remove @ prefix
    
    return True, cleaned, None


def validate_quiz_parameters(
    topic: str,
    count: Any = None,
    difficulty: str = None
) -> Tuple[bool, dict, Optional[str]]:
    """
    Validate all quiz parameters at once.
    
    Args:
        topic: Quiz topic
        count: Number of questions
        difficulty: Quiz difficulty
        
    Returns:
        Tuple[bool, dict, Optional[str]]: (is_valid, validated_params, error_message)
    """
    validated = {}
    
    # Validate topic
    valid, cleaned_topic, error = validate_topic(topic)
    if not valid:
        return False, {}, error
    validated['topic'] = cleaned_topic
    
    # Validate count if provided
    if count is not None:
        valid, parsed_count, error = validate_quiz_count(count)
        if not valid:
            return False, {}, error
        validated['count'] = parsed_count
    else:
        validated['count'] = 10  # Default
    
    # Validate difficulty if provided
    if difficulty is not None:
        valid, normalized_difficulty, error = validate_difficulty(difficulty)
        if not valid:
            return False, {}, error
        validated['difficulty'] = normalized_difficulty
    else:
        validated['difficulty'] = 'medium'  # Default
    
    return True, validated, None


def validate_answer(answer: str, max_length: int = 200) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate quiz answer.
    
    Args:
        answer: The answer to validate
        max_length: Maximum allowed length
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, cleaned_answer, error_message)
    """
    if not answer or not isinstance(answer, str):
        return False, None, "Answer must be provided"
    
    cleaned = answer.strip()
    
    if not cleaned:
        return False, None, "Answer cannot be empty"
    
    if len(cleaned) > max_length:
        return False, None, f"Answer cannot exceed {max_length} characters"
    
    return True, cleaned, None


def validate_timeframe(timeframe: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate timeframe parameter.
    
    Args:
        timeframe: The timeframe to validate
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, normalized_timeframe, error_message)
    """
    valid_timeframes = ['daily', 'weekly', 'monthly', 'all-time']
    
    if not timeframe:
        return True, 'all-time', None  # Default
    
    normalized = timeframe.lower().strip()
    
    if normalized not in valid_timeframes:
        return False, None, f"Timeframe must be one of: {', '.join(valid_timeframes)}"
    
    return True, normalized, None


def validate_category(category: str, allowed_categories: List[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate category against allowed list.
    
    Args:
        category: The category to validate
        allowed_categories: List of allowed categories
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, normalized_category, error_message)
    """
    if not category:
        return True, None, None  # No category is often valid
    
    normalized = category.lower().strip()
    normalized_allowed = [cat.lower() for cat in allowed_categories]
    
    if normalized not in normalized_allowed:
        return False, None, f"Category must be one of: {', '.join(allowed_categories)}"
    
    # Return the original casing from allowed_categories
    for cat in allowed_categories:
        if cat.lower() == normalized:
            return True, cat, None
    
    return True, normalized, None


def validate_integer_range(
    value: Any,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    field_name: str = "Value"
) -> Optional[str]:
    """
    Validate that a value is an integer within a specified range.
    
    Args:
        value: The value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        return f"{field_name} must be a valid integer"
    
    if min_value is not None and int_value < min_value:
        return f"{field_name} must be at least {min_value}"
    
    if max_value is not None and int_value > max_value:
        return f"{field_name} cannot exceed {max_value}"
    
    return None