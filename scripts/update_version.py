#!/usr/bin/env python3
"""
Helper script to update bot version and track changes.
This script helps maintain version consistency between the changelog and database.
"""

import os
import sys
import re
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config
from services.database import DatabaseService
from services.version_service import VersionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VersionUpdater:
    """Handles version updates and changelog management."""
    
    def __init__(self):
        self.config = load_config()
        self.db_service = None
        self.version_service = None
        self.changelog_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'CHANGELOG.md'
        )
    
    async def initialize(self):
        """Initialize database and version services."""
        try:
            # Initialize database
            self.db_service = DatabaseService(config=self.config.database)
            await self.db_service.initialize()
            
            # Initialize version service
            self.version_service = VersionService(self.db_service)
            await self.version_service.initialize()
            
            logger.info("Services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise
    
    async def close(self):
        """Close database connections."""
        if self.db_service:
            await self.db_service.close()
    
    def parse_changelog(self) -> Dict[str, List[Dict[str, str]]]:
        """Parse the CHANGELOG.md file to extract unreleased changes."""
        if not os.path.exists(self.changelog_path):
            logger.warning("CHANGELOG.md not found")
            return {}
        
        with open(self.changelog_path, 'r') as f:
            content = f.read()
        
        # Extract unreleased section
        unreleased_match = re.search(
            r'## \[Unreleased\](.*?)(?=## \[|$)', 
            content, 
            re.DOTALL
        )
        
        if not unreleased_match:
            return {}
        
        unreleased_content = unreleased_match.group(1)
        changes = {
            'feature': [],
            'fix': [],
            'improvement': [],
            'breaking': []
        }
        
        # Parse different sections
        sections = {
            'Added': 'feature',
            'Fixed': 'fix',
            'Changed': 'improvement',
            'Improved': 'improvement',
            'Breaking': 'breaking',
            'Security': 'improvement'
        }
        
        for section, change_type in sections.items():
            section_pattern = rf'### {section}\s*\n(.*?)(?=###|$)'
            section_match = re.search(section_pattern, unreleased_content, re.DOTALL)
            
            if section_match:
                items = re.findall(r'^- (.+)$', section_match.group(1), re.MULTILINE)
                for item in items:
                    changes[change_type].append(item.strip())
        
        return changes
    
    def update_changelog(self, version: str, description: str):
        """Update CHANGELOG.md by moving unreleased to new version."""
        if not os.path.exists(self.changelog_path):
            logger.warning("CHANGELOG.md not found")
            return
        
        with open(self.changelog_path, 'r') as f:
            content = f.read()
        
        # Get current date
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        # Find the unreleased section
        unreleased_match = re.search(
            r'(## \[Unreleased\].*?)(?=## \[)', 
            content, 
            re.DOTALL
        )
        
        if unreleased_match:
            unreleased_content = unreleased_match.group(1)
            
            # Create new version section
            new_version_section = f"\n## [{version}] - {date_str}\n"
            
            # Extract content from unreleased (remove the header)
            unreleased_items = re.sub(r'## \[Unreleased\]\s*\n', '', unreleased_content).strip()
            
            if unreleased_items:
                # Replace unreleased section with empty template
                new_unreleased = """## [Unreleased]
### Added

### Fixed

### Changed

"""
                
                # Insert new version after unreleased
                new_content = content.replace(
                    unreleased_content,
                    new_unreleased + new_version_section + unreleased_items + '\n'
                )
                
                # Write updated content
                with open(self.changelog_path, 'w') as f:
                    f.write(new_content)
                
                logger.info(f"Updated CHANGELOG.md with version {version}")
    
    async def create_version(self, version: str, description: str, author_id: int = None):
        """Create a new version with changelog entries."""
        try:
            # Parse unreleased changes from CHANGELOG.md
            changes = self.parse_changelog()
            
            # Create changelog entries list
            changelog_entries = []
            for change_type, items in changes.items():
                for item in items:
                    changelog_entries.append({
                        'type': change_type,
                        'description': item
                    })
            
            # Create version in database
            success = await self.version_service.create_version(
                version=version,
                description=description,
                author_id=author_id,
                changelog=changelog_entries,
                set_current=True
            )
            
            if success:
                logger.info(f"Successfully created version {version}")
                
                # Update CHANGELOG.md
                self.update_changelog(version, description)
                
                # Show summary
                print(f"\n✅ Version {version} created successfully!")
                print(f"📝 Description: {description}")
                print(f"📋 Changelog entries: {len(changelog_entries)}")
                
                for change_type, items in changes.items():
                    if items:
                        print(f"\n{change_type.capitalize()}:")
                        for item in items:
                            print(f"  - {item}")
            else:
                logger.error(f"Failed to create version {version}")
                print(f"\n❌ Failed to create version {version}")
                
        except Exception as e:
            logger.error(f"Error creating version: {e}")
            print(f"\n❌ Error: {e}")
    
    async def get_current_version(self) -> Optional[str]:
        """Get the current version from database."""
        version_data = await self.version_service.get_current_version()
        if version_data:
            return version_data['version']
        return None
    
    def increment_version(self, current: str, bump_type: str = 'patch') -> str:
        """Increment version number based on semver."""
        parts = current.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {current}")
        
        major, minor, patch = map(int, parts)
        
        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        elif bump_type == 'patch':
            patch += 1
        else:
            raise ValueError(f"Invalid bump type: {bump_type}")
        
        return f"{major}.{minor}.{patch}"


async def main():
    """Main entry point for the version updater."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update bot version')
    parser.add_argument('action', choices=['create', 'current', 'list'], 
                        help='Action to perform')
    parser.add_argument('--version', help='Version string (e.g., 1.2.0)')
    parser.add_argument('--description', help='Version description')
    parser.add_argument('--bump', choices=['major', 'minor', 'patch'], 
                        default='patch', help='Version bump type')
    parser.add_argument('--author-id', type=int, help='Discord user ID of author')
    
    args = parser.parse_args()
    
    updater = VersionUpdater()
    
    try:
        await updater.initialize()
        
        if args.action == 'current':
            current = await updater.get_current_version()
            if current:
                print(f"Current version: {current}")
            else:
                print("No current version set")
                
        elif args.action == 'list':
            # List recent versions
            versions = await updater.version_service.list_versions(10)
            print("\nRecent versions:")
            for v in versions:
                status = " (current)" if v.get('is_current') else ""
                print(f"  {v['version']}{status} - {v['description'][:50]}...")
                
        elif args.action == 'create':
            # Determine version
            if args.version:
                version = args.version
            else:
                # Auto-increment from current
                current = await updater.get_current_version()
                if current:
                    version = updater.increment_version(current, args.bump)
                    print(f"Auto-incrementing from {current} to {version}")
                else:
                    version = '1.0.0'
                    print("No current version, starting at 1.0.0")
            
            # Get description
            if args.description:
                description = args.description
            else:
                # Parse from changelog or prompt
                changes = updater.parse_changelog()
                total_changes = sum(len(items) for items in changes.values())
                
                if total_changes > 0:
                    print(f"\nFound {total_changes} unreleased changes in CHANGELOG.md")
                    description = input("Enter version description: ").strip()
                else:
                    print("\nNo unreleased changes found in CHANGELOG.md")
                    description = input("Enter version description: ").strip()
            
            if not description:
                print("Description is required!")
                return
            
            # Create the version
            await updater.create_version(version, description, args.author_id)
            
    finally:
        await updater.close()


if __name__ == "__main__":
    asyncio.run(main())