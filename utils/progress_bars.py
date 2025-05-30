"""Progress bar utilities for visual displays."""

# Custom emoji IDs for progress bars
PROGRESS_EMOJIS = {
    "left": "<:progress1:1374437729269452860>",
    "middle": "<:progress2:1374437814837579878>",
    "right": "<:progress3:1374437844575322234>",
    "left_filled": "<:progress1_filled:1374437882126925955>",
    "middle_filled": "<:progress2_filled:1374437919460163615>",
    "right_filled": "<:progress3_filled:1374437961105412136>"
}

def create_emoji_progress_bar(
    current: int,
    maximum: int,
    length: int = 10,
    show_percentage: bool = True
) -> str:
    """Create a visual progress bar using custom Discord emojis.
    
    This uses custom emojis with IDs defined in the PROGRESS_EMOJIS dictionary:
    - Left cap: progress1 (empty) / progress1_filled (filled)
    - Middle segments: progress2 (empty) / progress2_filled (filled)
    - Right cap: progress3 (empty) / progress3_filled (filled)
    """
    if maximum <= 0:
        # For zero maximum, return all empty
        bar = PROGRESS_EMOJIS["left"] 
        bar += PROGRESS_EMOJIS["middle"] * (length - 2)
        bar += PROGRESS_EMOJIS["right"]
        return bar if not show_percentage else f"{bar} 0.0%"
    
    # Calculate the percentage completion
    percentage = min(100, max(0, (current / maximum) * 100))
    
    # Calculate filled segments (excluding caps)
    # Need at least length 3 (left cap, middle section, right cap)
    middle_length = max(1, length - 2)
    filled_middle_blocks = max(0, min(middle_length, int((percentage / 100) * middle_length)))
    empty_middle_blocks = middle_length - filled_middle_blocks
    
    # Generate the progress bar with custom emojis
    bar = ""
    
    # Left cap (filled or empty based on progress)
    if percentage > 0:
        bar += PROGRESS_EMOJIS["left_filled"]
    else:
        bar += PROGRESS_EMOJIS["left"]
    
    # Middle segments (filled)
    bar += PROGRESS_EMOJIS["middle_filled"] * filled_middle_blocks
    
    # Middle segments (empty)
    bar += PROGRESS_EMOJIS["middle"] * empty_middle_blocks
    
    # Right cap (filled or empty based on completion)
    if percentage >= 100:
        bar += PROGRESS_EMOJIS["right_filled"]
    else:
        bar += PROGRESS_EMOJIS["right"]
    
    if show_percentage:
        return f"{bar} {percentage:.1f}%"
    return bar

def create_progress_bar(
    current: int,
    maximum: int,
    length: int = 10,
    filled_char: str = "█",
    empty_char: str = "░",
    show_percentage: bool = True,
    use_emoji: bool = True
) -> str:
    """Create a visual progress bar using Unicode characters or custom emojis.
    
    Args:
        current: The current value
        maximum: The maximum value
        length: The length of the progress bar
        filled_char: Character to use for filled portion (text mode)
        empty_char: Character to use for empty portion (text mode)
        show_percentage: Whether to include the percentage
        use_emoji: Whether to use custom Discord emojis instead of text characters
        
    Returns:
        A string representing the progress bar
    """
    if use_emoji:
        return create_emoji_progress_bar(current, maximum, length, show_percentage)
        
    # Traditional text-based progress bar (fallback)
    if maximum <= 0:
        return empty_char * length
    
    # Calculate the percentage
    percentage = min(100, max(0, (current / maximum) * 100))
    
    # Calculate how many blocks should be filled
    filled_blocks = int((percentage / 100) * length)
    empty_blocks = length - filled_blocks
    
    # Create the bar
    bar = filled_char * filled_blocks + empty_char * empty_blocks
    
    if show_percentage:
        return f"{bar} {percentage:.1f}%"
    return bar

def create_xp_bar(current_xp: int, next_level_xp: int, use_emoji: bool = True) -> str:
    """Create an XP progress bar for leveling."""
    xp_needed = next_level_xp - current_xp
    xp_progress = current_xp
    
    if xp_needed <= 0:
        return create_progress_bar(1, 1, length=10, use_emoji=use_emoji)
    
    return create_progress_bar(xp_progress, next_level_xp, length=10, use_emoji=use_emoji)

def create_accuracy_bar(correct: int, total: int, use_emoji: bool = True) -> str:
    """Create an accuracy bar showing quiz performance."""
    if total == 0:
        return create_progress_bar(0, 1, length=10, use_emoji=use_emoji)
    
    accuracy = (correct / total) * 100
    return f"{create_progress_bar(correct, total, length=10, use_emoji=use_emoji)} ({accuracy:.1f}% accuracy)"

def create_level_display(level: int, current_xp: int, next_level_xp: int, use_emoji: bool = True) -> str:
    """Create a formatted level display with progress."""
    xp_bar = create_xp_bar(current_xp, next_level_xp, use_emoji=use_emoji)
    return f"**Level {level}**\n{xp_bar}\n{current_xp}/{next_level_xp} XP"

def create_streak_display(streak: int, best_streak: int) -> str:
    """Create a streak display with fire emojis."""
    fire_count = min(5, (streak // 5) + 1)
    fire_emojis = "🔥" * fire_count
    
    if streak > 0:
        display = f"{fire_emojis} **{streak} Streak**"
        if streak >= best_streak:
            display += " (Personal Best!)"
        return display
    return "No current streak"

def get_rank_emoji(rank: int) -> str:
    """Get the appropriate emoji for a rank."""
    rank_emojis = {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }
    return rank_emojis.get(rank, f"#{rank}")