"""Embed creation utilities for cogs."""

import discord
from discord import Embed, Color
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

# Color constants for different embed types
COLORS = {
    'success': Color.green(),
    'error': Color.red(),
    'warning': Color.gold(),
    'info': Color.blue(),
    'quiz': 0x00ffff,  # Cyan for quiz-related embeds
    'leaderboard': 0xffd700,  # Gold for leaderboards
    'stats': 0x9b59b6,  # Purple for statistics
}


def create_base_embed(
    title: str,
    description: Optional[str] = None,
    color: Optional[Union[Color, int, str]] = None,
    timestamp: bool = False,
    thumbnail: Optional[str] = None,
    image: Optional[str] = None,
    url: Optional[str] = None
) -> Embed:
    """
    Create a base embed with common formatting.
    
    Args:
        title: The embed title
        description: The embed description
        color: Color (can be Color instance, hex int, or color name string)
        timestamp: Whether to add current timestamp
        thumbnail: URL for thumbnail image
        image: URL for main image
        url: URL for the title link
        
    Returns:
        Embed: The created embed
    """
    # Handle color parameter
    if isinstance(color, str) and color in COLORS:
        color_value = COLORS[color]
    elif color is None:
        color_value = COLORS['info']
    else:
        color_value = color
    
    embed = Embed(
        title=title,
        description=description,
        color=color_value,
        url=url
    )
    
    if timestamp:
        embed.timestamp = datetime.utcnow()
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    if image:
        embed.set_image(url=image)
    
    return embed


def create_error_embed(
    title: str = "Error",
    description: str = "An error occurred",
    error_details: Optional[str] = None
) -> Embed:
    """
    Create an error embed.
    
    Args:
        title: Error title
        description: Error description
        error_details: Additional error details
        
    Returns:
        Embed: The error embed
    """
    embed = create_base_embed(
        title=f"❌ {title}",
        description=description,
        color='error',
        timestamp=True
    )
    
    if error_details:
        embed.add_field(
            name="Details",
            value=f"```{error_details}```",
            inline=False
        )
    
    return embed


def create_success_embed(
    title: str = "Success",
    description: str = "Operation completed successfully"
) -> Embed:
    """
    Create a success embed.
    
    Args:
        title: Success title
        description: Success description
        
    Returns:
        Embed: The success embed
    """
    return create_base_embed(
        title=f"✅ {title}",
        description=description,
        color='success',
        timestamp=True
    )


def create_quiz_embed(
    title: str,
    question: Optional[str] = None,
    options: Optional[List[str]] = None,
    footer_text: Optional[str] = None,
    progress: Optional[str] = None,
    topic: Optional[str] = None
) -> Embed:
    """
    Create a quiz-specific embed.
    
    Args:
        title: Quiz title
        question: The quiz question
        options: List of answer options
        footer_text: Footer text
        progress: Progress indicator (e.g., "Question 1/10")
        topic: Quiz topic
        
    Returns:
        Embed: The quiz embed
    """
    embed = create_base_embed(
        title=title,
        color='quiz'
    )
    
    if topic:
        embed.add_field(
            name="📚 Topic",
            value=topic,
            inline=True
        )
    
    if progress:
        embed.add_field(
            name="📊 Progress",
            value=progress,
            inline=True
        )
    
    if question:
        embed.add_field(
            name="❓ Question",
            value=question,
            inline=False
        )
    
    if options:
        options_text = "\n".join([f"**{chr(65+i)}** {option}" for i, option in enumerate(options)])
        embed.add_field(
            name="Options",
            value=options_text,
            inline=False
        )
    
    if footer_text:
        embed.set_footer(text=footer_text)
    
    return embed


def create_leaderboard_embed(
    title: str = "Leaderboard",
    entries: List[Dict[str, Any]] = None,
    description: Optional[str] = None
) -> Embed:
    """
    Create a leaderboard embed.
    
    Args:
        title: Leaderboard title
        entries: List of leaderboard entries
        description: Optional description
        
    Returns:
        Embed: The leaderboard embed
    """
    embed = create_base_embed(
        title=f"🏆 {title}",
        description=description,
        color='leaderboard',
        timestamp=True
    )
    
    if entries:
        leaderboard_text = []
        for i, entry in enumerate(entries[:10]):  # Top 10
            position = i + 1
            if position == 1:
                emoji = "🥇"
            elif position == 2:
                emoji = "🥈"
            elif position == 3:
                emoji = "🥉"
            else:
                emoji = f"**{position}.**"
            
            username = entry.get('username', 'Unknown')
            score = entry.get('score', 0)
            accuracy = entry.get('accuracy', 0)
            
            leaderboard_text.append(
                f"{emoji} {username} - {score} points ({accuracy:.1f}% accuracy)"
            )
        
        embed.add_field(
            name="Rankings",
            value="\n".join(leaderboard_text) or "No entries yet",
            inline=False
        )
    
    return embed


def create_stats_embed(
    title: str = "Statistics",
    stats: Dict[str, Any] = None,
    user: Optional[discord.User] = None,
    thumbnail_url: Optional[str] = None
) -> Embed:
    """
    Create a statistics embed.
    
    Args:
        title: Stats title
        stats: Dictionary of statistics
        user: User object for avatar
        thumbnail_url: Custom thumbnail URL
        
    Returns:
        Embed: The stats embed
    """
    embed = create_base_embed(
        title=f"📊 {title}",
        color='stats',
        timestamp=True
    )
    
    if user:
        embed.set_author(
            name=str(user),
            icon_url=user.avatar.url if user.avatar else user.default_avatar.url
        )
        thumbnail_url = thumbnail_url or (user.avatar.url if user.avatar else user.default_avatar.url)
    
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    
    if stats:
        # Group stats into categories
        general_stats = []
        quiz_stats = []
        performance_stats = []
        
        for key, value in stats.items():
            formatted_key = key.replace('_', ' ').title()
            formatted_value = f"{value:,}" if isinstance(value, int) else str(value)
            
            if key in ['total_quizzes', 'total_questions', 'questions_answered']:
                quiz_stats.append(f"**{formatted_key}:** {formatted_value}")
            elif key in ['accuracy', 'average_score', 'best_score']:
                if key == 'accuracy':
                    formatted_value = f"{value:.1f}%"
                performance_stats.append(f"**{formatted_key}:** {formatted_value}")
            else:
                general_stats.append(f"**{formatted_key}:** {formatted_value}")
        
        if general_stats:
            embed.add_field(
                name="📋 General",
                value="\n".join(general_stats),
                inline=False
            )
        
        if quiz_stats:
            embed.add_field(
                name="❓ Quiz Stats",
                value="\n".join(quiz_stats),
                inline=True
            )
        
        if performance_stats:
            embed.add_field(
                name="🎯 Performance",
                value="\n".join(performance_stats),
                inline=True
            )
    
    return embed


def add_fields_to_embed(
    embed: Embed,
    fields: Dict[str, Any],
    inline: bool = False
) -> Embed:
    """
    Add multiple fields to an embed.
    
    Args:
        embed: The embed to add fields to
        fields: Dictionary of field names and values
        inline: Whether fields should be inline
        
    Returns:
        Embed: The updated embed
    """
    for name, value in fields.items():
        embed.add_field(
            name=name,
            value=str(value),
            inline=inline
        )
    
    return embed