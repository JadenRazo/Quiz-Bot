"""XP calculation engine for the Discord quiz bot leveling system."""

from typing import Dict, Tuple, Optional, List
import math
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class XPCalculator:
    """Handles all XP calculations, level progression, and bonus systems."""
    
    # Base XP configuration
    BASE_XP_PER_CORRECT = 10  # Base XP awarded per correct answer
    
    # Difficulty multipliers
    DIFFICULTY_MULTIPLIERS = {
        "easy": 1.0,
        "medium": 1.5,
        "hard": 2.0
    }
    
    # Accuracy bonus thresholds and multipliers
    ACCURACY_BONUSES = {
        100.0: 0.50,  # 50% bonus for perfect accuracy
        90.0: 0.20,   # 20% bonus for 90%+ accuracy
        80.0: 0.10,   # 10% bonus for 80%+ accuracy
    }
    
    # Quiz completion bonuses
    PERFECT_QUIZ_BONUS = 0.25  # 25% bonus for getting all questions correct
    FIRST_QUIZ_OF_DAY_BONUS = 0.15  # 15% bonus for first quiz of the day
    
    # Streak multipliers
    STREAK_MULTIPLIERS = {
        3: 1.1,   # 10% bonus at 3-day streak
        7: 1.2,   # 20% bonus at 7-day streak
        14: 1.3,  # 30% bonus at 14-day streak
        30: 1.5,  # 50% bonus at 30-day streak
    }
    
    @classmethod
    def calculate_base_xp(cls, correct_answers: int, difficulty: str = "medium") -> int:
        """Calculate base XP from correct answers and difficulty."""
        if correct_answers < 0:
            return 0
            
        difficulty = difficulty.lower()
        multiplier = cls.DIFFICULTY_MULTIPLIERS.get(difficulty, 1.5)
        
        base_xp = correct_answers * cls.BASE_XP_PER_CORRECT * multiplier
        return int(base_xp)
    
    @classmethod
    def calculate_accuracy_bonus(cls, correct: int, total: int) -> Tuple[int, float]:
        """Calculate XP bonus based on accuracy percentage.
        
        Returns:
            Tuple of (bonus_xp_percentage_as_int, accuracy_percentage)
        """
        if total <= 0:
            return 0, 0.0
            
        accuracy = (correct / total) * 100
        
        # Find the highest applicable bonus
        for threshold, bonus in sorted(cls.ACCURACY_BONUSES.items(), reverse=True):
            if accuracy >= threshold:
                return int(bonus * 100), accuracy
                
        return 0, accuracy
    
    @classmethod
    def calculate_perfect_quiz_bonus(cls, correct: int, total: int) -> int:
        """Calculate bonus for perfect quiz completion.
        
        Returns:
            Bonus percentage as integer (e.g., 25 for 25%)
        """
        if total > 0 and correct == total:
            return int(cls.PERFECT_QUIZ_BONUS * 100)
        return 0
    
    @classmethod
    def calculate_streak_multiplier(cls, current_streak: int) -> float:
        """Calculate streak multiplier based on consecutive quiz days.
        
        Args:
            current_streak: Number of consecutive days with quizzes completed
            
        Returns:
            Multiplier to apply to total XP (e.g., 1.2 for 20% bonus)
        """
        multiplier = 1.0
        
        # Apply the highest applicable streak bonus
        for streak_threshold in sorted(cls.STREAK_MULTIPLIERS.keys(), reverse=True):
            if current_streak >= streak_threshold:
                multiplier = cls.STREAK_MULTIPLIERS[streak_threshold]
                break
                
        return multiplier
    
    @classmethod
    def detect_streak_milestone(cls, old_streak: int, new_streak: int) -> Optional[int]:
        """Detect if a streak milestone was reached.
        
        Args:
            old_streak: Previous streak count
            new_streak: New streak count after quiz
            
        Returns:
            Milestone streak level if milestone reached, None otherwise
        """
        # Define milestone thresholds for celebrations
        milestones = [3, 5, 7, 10, 14, 21, 30, 50, 75, 100]
        
        for milestone in milestones:
            if old_streak < milestone <= new_streak:
                return milestone
        return None
    
    @classmethod
    def get_streak_celebration_level(cls, streak: int) -> str:
        """Get celebration intensity level based on streak length.
        
        Args:
            streak: Current streak count
            
        Returns:
            Celebration level: 'basic', 'impressive', 'amazing', 'legendary'
        """
        if streak >= 50:
            return 'legendary'
        elif streak >= 21:
            return 'amazing'
        elif streak >= 10:
            return 'impressive'
        else:
            return 'basic'
    
    @classmethod
    def calculate_total_xp(cls, 
                          correct_answers: int, 
                          total_questions: int,
                          difficulty: str = "medium",
                          current_streak: int = 0,
                          is_first_today: bool = False,
                          time_bonus_percentage: int = 0) -> Dict[str, int]:
        """Calculate total XP with all bonuses applied.
        
        Args:
            correct_answers: Number of correct answers
            total_questions: Total number of questions
            difficulty: Quiz difficulty level
            current_streak: Current daily streak count
            is_first_today: Whether this is the first quiz today
            time_bonus_percentage: Additional time-based bonus percentage
            
        Returns:
            Dictionary with XP breakdown:
            {
                'base_xp': int,
                'accuracy_bonus': int,
                'perfect_bonus': int,
                'streak_bonus': int,
                'time_bonus': int,
                'first_today_bonus': int,
                'total_xp': int,
                'accuracy_percentage': float
            }
        """
        # Calculate base XP
        base_xp = cls.calculate_base_xp(correct_answers, difficulty)
        
        # Calculate accuracy bonus
        accuracy_bonus_pct, accuracy = cls.calculate_accuracy_bonus(correct_answers, total_questions)
        accuracy_bonus = int(base_xp * (accuracy_bonus_pct / 100))
        
        # Calculate perfect quiz bonus
        perfect_bonus_pct = cls.calculate_perfect_quiz_bonus(correct_answers, total_questions)
        perfect_bonus = int(base_xp * (perfect_bonus_pct / 100))
        
        # Calculate time bonus
        time_bonus = int(base_xp * (time_bonus_percentage / 100))
        
        # Calculate first quiz of day bonus
        first_today_bonus = 0
        if is_first_today:
            first_today_bonus = int(base_xp * cls.FIRST_QUIZ_OF_DAY_BONUS)
        
        # Calculate subtotal before streak multiplier
        subtotal = base_xp + accuracy_bonus + perfect_bonus + time_bonus + first_today_bonus
        
        # Apply streak multiplier to everything
        streak_multiplier = cls.calculate_streak_multiplier(current_streak)
        streak_bonus = int(subtotal * (streak_multiplier - 1.0))  # Only the bonus portion
        
        total_xp = subtotal + streak_bonus
        
        return {
            'base_xp': base_xp,
            'accuracy_bonus': accuracy_bonus,
            'perfect_bonus': perfect_bonus,
            'streak_bonus': streak_bonus,
            'time_bonus': time_bonus,
            'first_today_bonus': first_today_bonus,
            'total_xp': total_xp,
            'accuracy_percentage': round(accuracy, 1)
        }

class LevelCalculator:
    """Handles level progression calculations."""
    
    # Level progression configuration
    BASE_XP_REQUIREMENT = 50     # XP needed for level 1 to 2
    XP_SCALING_FACTOR = 50       # Additional XP per level
    MAX_LEVEL = 100             # Maximum achievable level
    
    @classmethod
    def calculate_xp_for_level(cls, target_level: int) -> int:
        """Calculate total XP required to reach a specific level.
        
        Args:
            target_level: The level to calculate XP for
            
        Returns:
            Total XP required to reach that level
        """
        if target_level <= 1:
            return 0
            
        # Progressive XP requirement: 50 + (level-1) * 50
        # Level 2: 50 XP, Level 3: 100 XP, Level 4: 150 XP, etc.
        total_xp = 0
        for level in range(2, min(target_level + 1, cls.MAX_LEVEL + 1)):
            level_requirement = cls.BASE_XP_REQUIREMENT + ((level - 2) * cls.XP_SCALING_FACTOR)
            total_xp += level_requirement
            
        return total_xp
    
    @classmethod
    def calculate_level_from_xp(cls, total_xp: int) -> int:
        """Calculate current level based on total XP.
        
        Args:
            total_xp: Total XP accumulated
            
        Returns:
            Current level (1-based)
        """
        if total_xp < 0:
            return 1
            
        current_level = 1
        accumulated_xp = 0
        
        for level in range(2, cls.MAX_LEVEL + 1):
            level_requirement = cls.BASE_XP_REQUIREMENT + ((level - 2) * cls.XP_SCALING_FACTOR)
            
            if accumulated_xp + level_requirement <= total_xp:
                accumulated_xp += level_requirement
                current_level = level
            else:
                break
                
        return min(current_level, cls.MAX_LEVEL)
    
    @classmethod
    def calculate_progress_in_level(cls, total_xp: int) -> Tuple[int, int, int]:
        """Calculate progress within current level.
        
        Args:
            total_xp: Total XP accumulated
            
        Returns:
            Tuple of (current_level, current_xp_in_level, xp_needed_for_next_level)
        """
        current_level = cls.calculate_level_from_xp(total_xp)
        
        if current_level >= cls.MAX_LEVEL:
            return current_level, 0, 0
            
        # Calculate XP used to reach current level
        xp_for_current_level = cls.calculate_xp_for_level(current_level)
        
        # Calculate XP within current level
        current_xp_in_level = total_xp - xp_for_current_level
        
        # Calculate XP needed for next level
        xp_needed_for_next_level = cls.BASE_XP_REQUIREMENT + ((current_level - 1) * cls.XP_SCALING_FACTOR)
        
        return current_level, current_xp_in_level, xp_needed_for_next_level
    
    @classmethod
    def detect_level_up(cls, old_total_xp: int, new_total_xp: int) -> Optional[int]:
        """Detect if a level up occurred.
        
        Args:
            old_total_xp: Previous total XP
            new_total_xp: New total XP after quiz
            
        Returns:
            New level if level up occurred, None otherwise
        """
        old_level = cls.calculate_level_from_xp(old_total_xp)
        new_level = cls.calculate_level_from_xp(new_total_xp)
        
        if new_level > old_level:
            return new_level
        return None

def create_xp_breakdown_message(xp_breakdown: Dict[str, int], difficulty: str) -> str:
    """Create a formatted message showing XP breakdown.
    
    Args:
        xp_breakdown: XP breakdown from calculate_total_xp()
        difficulty: Quiz difficulty level
        
    Returns:
        Formatted string showing XP sources
    """
    lines = []
    
    # Base XP
    lines.append(f"📚 Base XP ({difficulty}): **{xp_breakdown['base_xp']}**")
    
    # Accuracy bonus
    if xp_breakdown['accuracy_bonus'] > 0:
        lines.append(f"🎯 Accuracy Bonus ({xp_breakdown['accuracy_percentage']}%): **+{xp_breakdown['accuracy_bonus']}**")
    
    # Perfect quiz bonus
    if xp_breakdown['perfect_bonus'] > 0:
        lines.append(f"💯 Perfect Quiz Bonus: **+{xp_breakdown['perfect_bonus']}**")
    
    # Time bonus
    if xp_breakdown['time_bonus'] > 0:
        lines.append(f"⚡ Speed Bonus: **+{xp_breakdown['time_bonus']}**")
    
    # First quiz today bonus
    if xp_breakdown['first_today_bonus'] > 0:
        lines.append(f"🌅 First Quiz Today: **+{xp_breakdown['first_today_bonus']}**")
    
    # Streak bonus
    if xp_breakdown['streak_bonus'] > 0:
        lines.append(f"🔥 Streak Bonus: **+{xp_breakdown['streak_bonus']}**")
    
    # Total
    lines.append(f"\n**Total XP Earned: {xp_breakdown['total_xp']}**")
    
    return "\n".join(lines)

# Convenience functions for backward compatibility
def calculate_xp_from_points(points: int) -> int:
    """Legacy function for backward compatibility. 
    
    Note: This is a simplified calculation. Use XPCalculator for full features.
    """
    # Simple 1:1 mapping for backward compatibility
    return points

def calculate_level_from_total_points(total_points: int) -> int:
    """Legacy function using old points system.
    
    Note: Use LevelCalculator.calculate_level_from_xp() for new XP system.
    """
    return LevelCalculator.calculate_level_from_xp(total_points)

def calculate_current_xp_in_level(total_points: int) -> int:
    """Legacy function for backward compatibility."""
    _, current_xp, _ = LevelCalculator.calculate_progress_in_level(total_points)
    return current_xp