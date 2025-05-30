import logging
from typing import Dict, Any, Optional, Union, List, Tuple

logger = logging.getLogger("bot.content")

# Define size limits for different content types (in characters)
CONTENT_SIZE_LIMITS = {
    "default": 2000,  # Default size limit if not specified
    "question": 1000,  # Quiz questions
    "answer": 500,    # Quiz answers
    "explanation": 1500, # Explanations
    "title": 100,     # Titles
    "choice": 200,    # Multiple choice options
    "feedback": 500,  # User feedback
    "description": 1000, # Descriptions
    "message": 1800,  # Discord messages (leaving room for formatting)
    "username": 32,   # Discord usernames
    "command": 100,   # Command names
    "category": 50,   # Category names
    "topic": 100,     # Quiz topics
}

def truncate_content(
    content: str, 
    content_type: str = "default", 
    max_length: Optional[int] = None,
    add_ellipsis: bool = True
) -> str:
    """
    Truncates content to a specified length based on content type.
    
    Args:
        content: The string content to truncate
        content_type: Type of content (question, answer, explanation, etc.)
        max_length: Optional custom max length to override defaults
        add_ellipsis: Whether to add "..." to truncated content
        
    Returns:
        The truncated string
    """
    if content is None:
        return ""
    
    # Convert to string if not already
    if not isinstance(content, str):
        content = str(content)
    
    # Determine the max length to use
    limit = max_length if max_length is not None else CONTENT_SIZE_LIMITS.get(
        content_type, CONTENT_SIZE_LIMITS["default"]
    )
    
    # If already within limits, return unchanged
    if len(content) <= limit:
        return content
    
    # Log that truncation is occurring
    logger.warning(
        f"Content of type '{content_type}' exceeds size limit of {limit} characters. "
        f"Truncating from {len(content)} characters."
    )
    
    # Truncate and add ellipsis if needed
    if add_ellipsis and limit > 3:
        return content[:limit-3] + "..."
    else:
        return content[:limit]

def truncate_dict_content(
    data: Dict[str, Any],
    field_types: Dict[str, str] = None,
    custom_limits: Dict[str, int] = None
) -> Dict[str, Any]:
    """
    Truncates string values in a dictionary based on content types.
    
    Args:
        data: Dictionary with content to truncate
        field_types: Mapping of field names to content types
        custom_limits: Optional custom limits for specific fields
        
    Returns:
        Dictionary with truncated values
    """
    if data is None:
        return {}
    
    field_types = field_types or {}
    custom_limits = custom_limits or {}
    result = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            content_type = field_types.get(key, "default")
            max_length = custom_limits.get(key)
            result[key] = truncate_content(value, content_type, max_length)
        elif isinstance(value, dict):
            # Recursively process nested dictionaries
            result[key] = truncate_dict_content(
                value, 
                {k.replace(f"{key}.", ""): v for k, v in field_types.items() if k.startswith(f"{key}.")},
                {k.replace(f"{key}.", ""): v for k, v in custom_limits.items() if k.startswith(f"{key}.")}
            )
        elif isinstance(value, list):
            # Process lists
            if all(isinstance(item, str) for item in value):
                # List of strings
                content_type = field_types.get(key, "default")
                max_length = custom_limits.get(key)
                result[key] = [truncate_content(item, content_type, max_length) for item in value]
            elif all(isinstance(item, dict) for item in value):
                # List of dictionaries
                result[key] = [truncate_dict_content(item, field_types, custom_limits) for item in value]
            else:
                # Mixed or other types, keep as is
                result[key] = value
        else:
            # Non-string types are kept as is
            result[key] = value
    
    return result

def normalize_quiz_content(quiz_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and truncate quiz content before saving to database.
    
    Args:
        quiz_data: Quiz data dictionary containing questions, answers, etc.
        
    Returns:
        Normalized quiz data with appropriate size limits applied
    """
    field_types = {
        "topic": "topic",
        "title": "title", 
        "description": "description",
        "difficulty": "category",
        "category": "category",
        "questions": "default",
        "questions.text": "question",
        "questions.explanation": "explanation",
        "questions.choices": "default",
        "questions.choices.text": "choice",
        "questions.answer": "answer",
        "questions.correct_answer": "answer",
    }
    
    return truncate_dict_content(quiz_data, field_types)