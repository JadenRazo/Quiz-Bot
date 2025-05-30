import logging
import json
import os
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from services.database import DatabaseService

logger = logging.getLogger("bot.learning_path")

class LearningPathNode:
    """Represents a single node in a learning path."""
    
    def __init__(
        self,
        node_id: str,
        title: str,
        description: str,
        topic: str,
        prerequisites: List[str] = None,
        quiz_config: Dict[str, Any] = None,
        resources: List[Dict[str, str]] = None,
        order: int = 0
    ):
        self.node_id = node_id
        self.title = title
        self.description = description
        self.topic = topic
        self.prerequisites = prerequisites or []
        self.quiz_config = quiz_config or {}
        self.resources = resources or []
        self.order = order
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the node to a dictionary."""
        return {
            "node_id": self.node_id,
            "title": self.title,
            "description": self.description,
            "topic": self.topic,
            "prerequisites": self.prerequisites,
            "quiz_config": self.quiz_config,
            "resources": self.resources,
            "order": self.order
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningPathNode":
        """Create a node from a dictionary."""
        return cls(
            node_id=data["node_id"],
            title=data["title"],
            description=data["description"],
            topic=data["topic"],
            prerequisites=data.get("prerequisites", []),
            quiz_config=data.get("quiz_config", {}),
            resources=data.get("resources", []),
            order=data.get("order", 0)
        )


class LearningPath:
    """Represents a structured learning path with multiple nodes."""
    
    def __init__(
        self,
        path_id: str,
        title: str,
        description: str,
        category: str,
        difficulty: str,
        nodes: List[LearningPathNode] = None,
        created_by: Optional[int] = None,
        is_official: bool = False
    ):
        self.path_id = path_id
        self.title = title
        self.description = description
        self.category = category
        self.difficulty = difficulty
        self.nodes = sorted(nodes or [], key=lambda n: n.order)
        self.created_by = created_by
        self.is_official = is_official
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the learning path to a dictionary."""
        return {
            "path_id": self.path_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "difficulty": self.difficulty,
            "nodes": [node.to_dict() for node in self.nodes],
            "created_by": self.created_by,
            "is_official": self.is_official
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningPath":
        """Create a learning path from a dictionary."""
        return cls(
            path_id=data["path_id"],
            title=data["title"],
            description=data["description"],
            category=data["category"],
            difficulty=data["difficulty"],
            nodes=[LearningPathNode.from_dict(node) for node in data.get("nodes", [])],
            created_by=data.get("created_by"),
            is_official=data.get("is_official", False)
        )
    
    def get_next_node(self, completed_nodes: List[str]) -> Optional[LearningPathNode]:
        """Get the next node that the user can complete based on prerequisites."""
        for node in self.nodes:
            # Skip if already completed
            if node.node_id in completed_nodes:
                continue
                
            # Check if all prerequisites are met
            if all(prereq in completed_nodes for prereq in node.prerequisites):
                return node
                
        return None  # No available nodes


class LearningPathService:
    """Service for managing learning paths."""
    
    def __init__(self, db_service: DatabaseService, paths_dir: str = "data/learning_paths"):
        """Initialize the learning path service."""
        self.db_service = db_service
        self.paths_dir = paths_dir
        self.learning_paths: Dict[str, LearningPath] = {}
        
        # Create paths directory if it doesn't exist
        os.makedirs(self.paths_dir, exist_ok=True)
        
        # Load all learning paths
        self._load_learning_paths()
    
    def _load_learning_paths(self):
        """Load all learning paths from the data directory."""
        try:
            # Load path files from the directory
            path_files = [f for f in os.listdir(self.paths_dir) if f.endswith('.json')]
            
            for file_name in path_files:
                try:
                    with open(os.path.join(self.paths_dir, file_name), 'r') as f:
                        path_data = json.load(f)
                        learning_path = LearningPath.from_dict(path_data)
                        self.learning_paths[learning_path.path_id] = learning_path
                        logger.info(f"Loaded learning path: {learning_path.title}")
                except Exception as e:
                    logger.error(f"Error loading learning path {file_name}: {e}")
            
            logger.info(f"Loaded {len(self.learning_paths)} learning paths")
        except Exception as e:
            logger.error(f"Error loading learning paths: {e}")
    
    def get_learning_path(self, path_id: str) -> Optional[LearningPath]:
        """Get a learning path by ID."""
        return self.learning_paths.get(path_id)
    
    def get_all_learning_paths(self) -> List[LearningPath]:
        """Get all available learning paths."""
        return list(self.learning_paths.values())
    
    def get_paths_by_category(self, category: str) -> List[LearningPath]:
        """Get learning paths by category."""
        return [path for path in self.learning_paths.values() if path.category.lower() == category.lower()]
    
    def get_paths_by_difficulty(self, difficulty: str) -> List[LearningPath]:
        """Get learning paths by difficulty level."""
        return [path for path in self.learning_paths.values() if path.difficulty.lower() == difficulty.lower()]
    
    def save_learning_path(self, learning_path: LearningPath) -> bool:
        """Save a learning path to the data directory."""
        try:
            # Add or update the path in memory
            self.learning_paths[learning_path.path_id] = learning_path
            
            # Save to file
            file_path = os.path.join(self.paths_dir, f"{learning_path.path_id}.json")
            with open(file_path, 'w') as f:
                json.dump(learning_path.to_dict(), f, indent=2)
            
            logger.info(f"Saved learning path: {learning_path.title}")
            return True
        except Exception as e:
            logger.error(f"Error saving learning path: {e}")
            return False
    
    def delete_learning_path(self, path_id: str) -> bool:
        """Delete a learning path."""
        try:
            if path_id in self.learning_paths:
                # Remove from memory
                del self.learning_paths[path_id]
                
                # Remove file
                file_path = os.path.join(self.paths_dir, f"{path_id}.json")
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                logger.info(f"Deleted learning path: {path_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting learning path: {e}")
            return False
    
    def get_user_progress(self, user_id: int, path_id: str) -> Dict[str, Any]:
        """Get a user's progress on a specific learning path."""
        return self.db_service.get_learning_path_progress(user_id, path_id)
    
    def update_user_progress(self, user_id: int, path_id: str, node_id: str, completed: bool = True) -> bool:
        """Update a user's progress on a learning path."""
        return self.db_service.update_learning_path_progress(user_id, path_id, node_id, completed)
    
    async def get_recommended_paths(self, user_id: int) -> List[LearningPath]:
        """Get recommended learning paths based on user's activity and interests."""
        try:
            # Check if the database service is available
            if not self.db_service:
                logger.warning("Database service not available for learning path recommendations.")
                return [] # Cannot generate recommendations without DB
            
            # Fetch user's current stats and preferences
            logger.info(f"Fetching stats for user {user_id} for learning path")
            user_stats = None
            if hasattr(self.db_service, 'get_comprehensive_user_stats'):
                user_stats = await self.db_service.get_comprehensive_user_stats(user_id)
            elif hasattr(self.db_service, 'get_user_stats'): # Old name fallback
                 user_stats = await self.db_service.get_user_stats(user_id)
            else:
                logger.warning(f"No comprehensive stats method found, trying basic for user {user_id}")
                if hasattr(self.db_service, 'get_basic_user_stats'):
                    basic_stats = self.db_service.get_basic_user_stats(user_id)
                    # Adapt basic_stats to a structure that might be useful, or indicate limited data
                    if basic_stats:
                        user_stats = {"overall": basic_stats, "by_category": [], "by_difficulty": []}
            
            if not user_stats:
                logger.info(f"No stats found for user {user_id}. Cannot personalize learning path effectively.")
                # Proceed with generic recommendations or a default path
                user_stats = {"overall": {}, "by_category": [], "by_difficulty": []} # Empty structure

            user_preferences = await self.db_service.get_user_preferences(user_id)
            
            # TODO: Implement a recommendation algorithm based on user stats
            # For now, just return paths sorted by popularity
            return sorted(
                self.learning_paths.values(),
                key=lambda p: self.db_service.get_path_popularity(p.path_id),
                reverse=True
            )[:5]  # Top 5 most popular 
        except Exception as e:
            logger.error(f"Error getting recommended paths: {e}")
            return [] 