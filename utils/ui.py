import discord
from discord import Embed, Color
from typing import Optional, Dict, List, Any, Union

# UI Constants
MEDALS = ["🥇", "🥈", "🥉"]
PROGRESS_BAR_CHARS = {"filled": "█", "empty": "░"}
DIFFICULTY_COLORS = {
    "easy": Color.green(),
    "medium": Color.gold(),
    "hard": Color.red(),
    "expert": Color.purple()
}
CATEGORY_EMOJIS = {
    "general": "🔍",
    "science": "🧪",
    "history": "📜",
    "geography": "🌎",
    "literature": "📚",
    "mathematics": "🔢",
    "computer science": "💻",
    "arts": "🎨",
    "music": "🎵",
    "sports": "⚽",
    "entertainment": "🎬",
    "food": "🍽️",
    "technology": "📱",
    "languages": "🗣️"
}
REACTION_EMOJIS = {
    "correct": "✅",
    "incorrect": "❌",
    "thinking": "🤔",
    "warning": "⚠️",
    "time": "⏰",
    "complete": "🏁",
    "info": "ℹ️"
}

def get_medal(position: int) -> str:
    """Get medal emoji for leaderboard position."""
    if 0 <= position < len(MEDALS):
        return f"{MEDALS[position]} "
    return ""

def create_embed(
    title: str,
    description: Optional[str] = None,
    color: Optional[Union[Color, int]] = None,
    fields: Optional[List[Dict[str, Any]]] = None,
    footer_text: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    image_url: Optional[str] = None,
    author_name: Optional[str] = None,
    author_icon_url: Optional[str] = None
) -> Embed:
    """
    Create a consistently styled embed.
    
    Args:
        title: The embed title
        description: The embed description
        color: Discord.Color or int for the embed color
        fields: List of field dictionaries with name, value, and inline keys
        footer_text: Text to display in the footer
        thumbnail_url: URL for the thumbnail image
        image_url: URL for the main image
        author_name: Name to display in the author field
        author_icon_url: URL for the author icon
        
    Returns:
        A Discord Embed object
    """
    # Set default color if not provided
    if color is None:
        color = Color.blue()
    
    embed = Embed(
        title=title,
        description=description,
        color=color
    )
    
    # Add fields if provided
    if fields:
        for field in fields:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", False)
            )
    
    # Set footer if provided
    if footer_text:
        embed.set_footer(text=footer_text)
    
    # Set thumbnail if provided
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    
    # Set main image if provided
    if image_url:
        embed.set_image(url=image_url)
    
    # Set author if provided
    if author_name:
        embed.set_author(
            name=author_name,
            icon_url=author_icon_url if author_icon_url else discord.Embed.Empty
        )
    
    return embed

def create_progress_bar(
    percent: float,
    length: int = 10,
    filled_char: Optional[str] = None,
    empty_char: Optional[str] = None,
    include_percent: bool = True,
    use_emoji: bool = True
) -> str:
    """
    Create a text-based progress bar.
    
    Args:
        percent: The percentage of completion (0-100)
        length: The length of the progress bar in characters
        filled_char: The character to use for filled portion (default from constants)
        empty_char: The character to use for empty portion (default from constants)
        include_percent: Whether to include the percentage at the end
        use_emoji: Whether to use custom Discord emojis instead of text
        
    Returns:
        A string representing the progress bar
    """
    # Import here to avoid circular imports
    from utils.progress_bars import create_progress_bar as create_bar
    
    # Convert percent to current/total format
    current = int(length * percent / 100)
    maximum = length
    
    # Call the implementation in progress_bars.py
    return create_bar(
        current=current,
        maximum=maximum, 
        length=length,
        filled_char=filled_char or PROGRESS_BAR_CHARS["filled"],
        empty_char=empty_char or PROGRESS_BAR_CHARS["empty"],
        show_percentage=include_percent,
        use_emoji=use_emoji
    )

def get_color_for_difficulty(difficulty: str) -> Color:
    """
    Get a consistent color based on difficulty.
    
    Args:
        difficulty: The difficulty level (easy, medium, hard, etc.)
        
    Returns:
        A Discord Color object
    """
    difficulty = difficulty.lower()
    return DIFFICULTY_COLORS.get(difficulty, Color.blue())

def get_emoji_for_category(category: str) -> str:
    """
    Get a consistent emoji based on category.
    
    Args:
        category: The question category
        
    Returns:
        An emoji string
    """
    category = category.lower()
    return CATEGORY_EMOJIS.get(category, "❓")

def format_duration(seconds: int) -> str:
    """
    Format seconds into a human-readable duration string.
    
    Args:
        seconds: The duration in seconds
        
    Returns:
        A formatted string (e.g., "2m 30s")
    """
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def format_leaderboard_entry(
    position: int, 
    username: str, 
    score: int, 
    correct: Optional[int] = None, 
    total: Optional[int] = None
) -> str:
    """
    Format a leaderboard entry consistently.
    
    Args:
        position: Position in the leaderboard (0-based)
        username: Username to display
        score: User's score
        correct: Number of correct answers (optional)
        total: Total number of questions (optional)
        
    Returns:
        Formatted leaderboard entry string
    """
    medal = get_medal(position)
    entry = f"{medal}**{position+1}.** {username}: {score} points"
    
    if correct is not None and total is not None:
        entry += f" ({correct}/{total} correct)"
        
    return entry 