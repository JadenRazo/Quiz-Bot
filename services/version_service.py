"""Version management service for tracking bot versions."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("bot.version_service")


class VersionService:
    """Service for managing bot versions and changelogs."""
    
    def __init__(self, db_service):
        """Initialize the version service.
        
        Args:
            db_service: Database service instance
        """
        self.db_service = db_service
        self._initialized = False
    
    async def initialize(self):
        """Initialize the version tables if they don't exist."""
        if self._initialized:
            return
            
        try:
            # Execute the schema in separate manageable chunks
            conn = await self.db_service.get_connection()
            try:
                # 1. Create tables (these use IF NOT EXISTS so they're safe)
                await conn.execute("""
                -- Main versions table
                CREATE TABLE IF NOT EXISTS bot_versions (
                    id SERIAL PRIMARY KEY,
                    version VARCHAR(20) NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    release_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    is_current BOOLEAN DEFAULT FALSE,
                    author_id BIGINT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );

                -- Version changelog entries (detailed changes for each version)
                CREATE TABLE IF NOT EXISTS version_changelog (
                    id SERIAL PRIMARY KEY,
                    version_id INTEGER REFERENCES bot_versions(id),
                    change_type VARCHAR(50) NOT NULL, -- 'feature', 'fix', 'improvement', 'breaking'
                    description TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """)
                
                # 2. Create indexes (also use IF NOT EXISTS)
                await conn.execute("""
                -- Index for faster queries
                CREATE INDEX IF NOT EXISTS idx_bot_versions_current ON bot_versions(is_current);
                CREATE INDEX IF NOT EXISTS idx_bot_versions_version ON bot_versions(version);
                CREATE INDEX IF NOT EXISTS idx_version_changelog_version_id ON version_changelog(version_id);
                """)
                
                # 3. Create function (safe with OR REPLACE)
                await conn.execute("""
                -- Trigger to ensure only one current version
                CREATE OR REPLACE FUNCTION ensure_single_current_version()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF NEW.is_current = TRUE THEN
                        UPDATE bot_versions SET is_current = FALSE WHERE id != NEW.id;
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """)
                
                # 4. Create trigger (need to check if exists)
                try:
                    # Check if trigger already exists using a different approach
                    check_query = """
                    SELECT 1 FROM pg_trigger 
                    JOIN pg_class ON pg_trigger.tgrelid = pg_class.oid
                    WHERE pg_trigger.tgname = 'ensure_single_current_trigger'
                    AND pg_class.relname = 'bot_versions'
                    """
                    trigger_exists = await conn.fetchval(check_query)
                    
                    if not trigger_exists:
                        await conn.execute("""
                        CREATE TRIGGER ensure_single_current_trigger
                        BEFORE INSERT OR UPDATE ON bot_versions
                        FOR EACH ROW
                        EXECUTE FUNCTION ensure_single_current_version();
                        """)
                        logger.info("Created ensure_single_current_trigger")
                    else:
                        logger.info("Trigger ensure_single_current_trigger already exists, skipping creation")
                except Exception as trigger_error:
                    logger.warning(f"Error with trigger: {trigger_error}")
                    # Continue anyway as the trigger might already exist
                
                # 5. Insert initial version if needed
                try:
                    await conn.execute("""
                    -- Add initial version if none exists
                    INSERT INTO bot_versions (version, description, is_current)
                    VALUES ('1.0.0', 'Initial release of Educational Quiz Bot', TRUE)
                    ON CONFLICT (version) DO NOTHING;
                    """)
                except Exception as insert_error:
                    logger.warning(f"Error inserting initial version: {insert_error}")
                
                logger.info("Version tables initialized successfully")
                self._initialized = True
            finally:
                await self.db_service.release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error initializing version tables: {e}")
            raise
    
    async def get_current_version(self) -> Optional[Dict[str, Any]]:
        """Get the current bot version.
        
        Returns:
            Dictionary with version info or None if no version is set
        """
        try:
            conn = await self.db_service.get_connection()
            try:
                query = """
                SELECT id, version, description, release_date, author_id
                FROM bot_versions
                WHERE is_current = TRUE
                LIMIT 1
                """
                result = await conn.fetchrow(query)
                
                if result:
                    return dict(result)
                return None
                
            finally:
                await self.db_service.release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error getting current version: {e}")
            return None
    
    async def get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific version.
        
        Args:
            version: Version string (e.g., "1.0.0")
            
        Returns:
            Dictionary with version info or None if version not found
        """
        try:
            conn = await self.db_service.get_connection()
            try:
                # Get version details
                version_query = """
                SELECT id, version, description, release_date, author_id, is_current
                FROM bot_versions
                WHERE version = $1
                """
                version_result = await conn.fetchrow(version_query, version)
                
                if not version_result:
                    return None
                
                version_data = dict(version_result)
                
                # Get changelog entries
                changelog_query = """
                SELECT change_type, description
                FROM version_changelog
                WHERE version_id = $1
                ORDER BY created_at ASC
                """
                changelog_results = await conn.fetch(changelog_query, version_data['id'])
                
                version_data['changelog'] = [dict(row) for row in changelog_results]
                
                return version_data
                
            finally:
                await self.db_service.release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error getting version info for {version}: {e}")
            return None
    
    async def list_versions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List all versions in descending order.
        
        Args:
            limit: Maximum number of versions to return
            
        Returns:
            List of version dictionaries
        """
        try:
            conn = await self.db_service.get_connection()
            try:
                query = """
                SELECT id, version, description, release_date, is_current, author_id
                FROM bot_versions
                ORDER BY created_at DESC
                LIMIT $1
                """
                results = await conn.fetch(query, limit)
                
                return [dict(row) for row in results]
                
            finally:
                await self.db_service.release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error listing versions: {e}")
            return []
    
    async def create_version(
        self, 
        version: str, 
        description: str, 
        author_id: int,
        changelog: Optional[List[Dict[str, str]]] = None,
        set_current: bool = True
    ) -> bool:
        """Create a new version entry.
        
        Args:
            version: Version string (e.g., "1.1.0")
            description: Version description
            author_id: Discord ID of the author
            changelog: List of changelog entries with 'type' and 'description'
            set_current: Whether to set this as the current version
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = await self.db_service.get_connection()
            try:
                # Insert the version
                version_query = """
                INSERT INTO bot_versions (version, description, author_id, is_current)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """
                result = await conn.fetchrow(
                    version_query, 
                    version, description, author_id, set_current
                )
                
                version_id = result['id']
                
                # Insert changelog entries if provided
                if changelog:
                    for entry in changelog:
                        changelog_query = """
                        INSERT INTO version_changelog (version_id, change_type, description)
                        VALUES ($1, $2, $3)
                        """
                        await conn.execute(
                            changelog_query,
                            version_id, entry.get('type', 'feature'), entry.get('description', '')
                        )
                
                logger.info(f"Created version {version} (ID: {version_id})")
                return True
                
            finally:
                await self.db_service.release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error creating version {version}: {e}")
            return False
    
    async def update_version(
        self,
        version: str,
        description: Optional[str] = None,
        set_current: Optional[bool] = None
    ) -> bool:
        """Update an existing version.
        
        Args:
            version: Version string to update
            description: New description (optional)
            set_current: Whether to make this the current version (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = await self.db_service.get_connection()
            try:
                # Build the query dynamically with asyncpg $1, $2, etc. placeholders
                
                # Initialize parameters and updates
                params = []
                updates = []
                param_num = 1
                
                if description is not None:
                    updates.append(f"description = ${param_num}")
                    params.append(description)
                    param_num += 1
                
                if set_current is not None:
                    updates.append(f"is_current = ${param_num}")
                    params.append(set_current)
                    param_num += 1
                
                updates.append("updated_at = NOW()")
                
                if not params:
                    return True  # Nothing to update
                
                # Add version parameter
                params.append(version)
                
                query = f"""
                UPDATE bot_versions
                SET {', '.join(updates)}
                WHERE version = ${param_num}
                """
                
                result = await conn.execute(query, *params)
                
                # Check if any rows were updated
                if result == "UPDATE 0":
                    logger.warning(f"No version found to update: {version}")
                    return False
                
                logger.info(f"Updated version {version}")
                return True
                
            finally:
                await self.db_service.release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error updating version {version}: {e}")
            return False
    
    async def add_changelog_entry(
        self,
        version: str,
        change_type: str,
        description: str
    ) -> bool:
        """Add a changelog entry to an existing version.
        
        Args:
            version: Version string
            change_type: Type of change ('feature', 'fix', 'improvement', 'breaking')
            description: Description of the change
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = await self.db_service.get_connection()
            try:
                # Get version ID
                version_query = "SELECT id FROM bot_versions WHERE version = $1"
                version_result = await conn.fetchrow(version_query, version)
                
                if not version_result:
                    logger.warning(f"Version {version} not found")
                    return False
                
                version_id = version_result['id']
                
                # Insert changelog entry
                changelog_query = """
                INSERT INTO version_changelog (version_id, change_type, description)
                VALUES ($1, $2, $3)
                """
                await conn.execute(changelog_query, version_id, change_type, description)
                
                logger.info(f"Added changelog entry to version {version}")
                return True
                
            finally:
                await self.db_service.release_connection(conn)
                
        except Exception as e:
            logger.error(f"Error adding changelog entry: {e}")
            return False
    
    def format_version_info(self, version_data: Dict[str, Any]) -> str:
        """Format version information for display.
        
        Args:
            version_data: Version data dictionary
            
        Returns:
            Formatted string for display
        """
        if not version_data:
            return "No version information available."
        
        # Format release date
        release_date = version_data.get('release_date')
        if isinstance(release_date, datetime):
            date_str = release_date.strftime("%Y-%m-%d %H:%M UTC")
        else:
            date_str = str(release_date)
        
        # Build the formatted string
        lines = [
            f"**Version {version_data['version']}**",
            version_data['description'],
            f"Released: {date_str}"
        ]
        
        if version_data.get('is_current'):
            lines.append("*(Current Version)*")
        
        # Add changelog if available
        changelog = version_data.get('changelog', [])
        if changelog:
            lines.append("\n**Changelog:**")
            
            # Group by change type
            grouped = {}
            for entry in changelog:
                change_type = entry['change_type']
                if change_type not in grouped:
                    grouped[change_type] = []
                grouped[change_type].append(entry['description'])
            
            # Format each group
            type_emojis = {
                'feature': '✨',
                'fix': '🐛',
                'improvement': '🔧',
                'breaking': '⚠️'
            }
            
            for change_type, changes in grouped.items():
                emoji = type_emojis.get(change_type, '•')
                type_name = change_type.capitalize()
                lines.append(f"\n{emoji} **{type_name}:**")
                for change in changes:
                    lines.append(f"  • {change}")
        
        return '\n'.join(lines)


# Create a singleton instance
version_service = VersionService(None)  # DB service will be set later


def initialize_version_service(db_service):
    """Initialize the version service with a database service.
    
    Args:
        db_service: Database service instance
    """
    global version_service
    version_service = VersionService(db_service)
    return version_service