#!/usr/bin/env python3
"""
Script to safely archive deprecated files after the database V2 migration.
This script:
1. Adds deprecation warnings to files
2. Creates archive copies in deprecated_files/
3. Creates shim files for backward compatibility (where needed)

Usage:
    python3 scripts/archive_deprecated_files.py

To revert (recover original files):
    python3 scripts/archive_deprecated_files.py --revert
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Root directory
ROOT_DIR = Path(__file__).parent.parent

# Archive directory
ARCHIVE_DIR = ROOT_DIR / "deprecated_files"

# Files to archive with their warning messages and shim status
FILES_TO_ARCHIVE = [
    {
        "path": "services/database.py",
        "warning": """
\"\"\"
DEPRECATED: This file is deprecated and will be removed in a future version.
Use services.database_v2.DatabaseServiceV2 instead.
This file remains only for backward compatibility.
\"\"\"
""",
        "needs_shim": True
    },
    {
        "path": "services/database_extensions/user_stats.py",
        "warning": """
\"\"\"
DEPRECATED: This file is deprecated and will be removed in a future version.
User stats functionality is now integrated into services.database_v2.
This file remains only for backward compatibility.
\"\"\"
""",
        "needs_shim": True
    },
    {
        "path": "services/group_quiz.py",
        "warning": """
\"\"\"
DEPRECATED: This file is deprecated and will be removed in a future version.
Use services.group_quiz_multi_guild instead, which supports multiple guilds.
This file remains only for backward compatibility.
\"\"\"
""",
        "needs_shim": True
    },
    {
        "path": "services/database_operations/user_stats_ops.py",
        "warning": """
\"\"\"
DEPRECATED: This file is deprecated and will be removed in a future version.
User stats operations are now integrated into services.database_v2.
This file remains only for backward compatibility.
\"\"\"
""",
        "needs_shim": True
    },
    {
        "path": "services/database_operations/guild_ops.py",
        "warning": """
\"\"\"
DEPRECATED: This file is deprecated and will be removed in a future version.
Guild operations are now integrated into services.database_v2.
This file remains only for backward compatibility.
\"\"\"
""",
        "needs_shim": True
    },
    {
        "path": "services/database_operations/config_ops.py",
        "warning": """
\"\"\"
DEPRECATED: This file is deprecated and will be removed in a future version.
Configuration operations are now integrated into services.database_v2.
This file remains only for backward compatibility.
\"\"\"
""",
        "needs_shim": True
    },
    {
        "path": "db/schema.sql",
        "warning": """
-- DEPRECATED: This schema file is deprecated and will be removed in a future version.
-- Use schema_complete.sql instead, which includes all necessary tables and functions.
-- This file remains only for backward compatibility.

""",
        "needs_shim": False
    },
    {
        "path": "db/schema_multi_guild.sql",
        "warning": """
-- DEPRECATED: This schema file is deprecated and will be removed in a future version.
-- Use schema_complete.sql instead, which includes multi-guild support.
-- This file remains only for backward compatibility.

""",
        "needs_shim": False
    },
    {
        "path": "db/version_schema.sql",
        "warning": """
-- DEPRECATED: This schema file is deprecated and will be removed in a future version.
-- Versioning is now integrated into schema_complete.sql.
-- This file remains only for backward compatibility.

""",
        "needs_shim": False
    },
    {
        "path": "db_test.py",
        "warning": """
\"\"\"
DEPRECATED: This test file is deprecated and will be removed in a future version.
It tests the old database service. A new test file for DatabaseServiceV2 should be created.
This file remains only for backward compatibility.
\"\"\"
""",
        "needs_shim": False
    }
]

# Shim content template (Python)
PYTHON_SHIM_TEMPLATE = """
\"\"\"
Shim for backward compatibility with {module_name} imports.
This file loads the archived module and provides the same interface.
\"\"\"
import warnings
import os
import sys
from pathlib import Path

# Issue deprecation warning
warnings.warn(
    "The '{module_name}' module is deprecated and will be removed in a future version. "
    "Please update your code to use the recommended replacement.",
    DeprecationWarning,
    stacklevel=2
)

# Add deprecated_files directory to sys.path
deprecated_dir = Path(__file__).parent.parent / "deprecated_files"
sys.path.insert(0, str(deprecated_dir))

# Import from the archived location
from deprecated_files.{relative_import_path} import *

# Remove deprecated_files from path to prevent unwanted imports elsewhere
if str(deprecated_dir) in sys.path:
    sys.path.remove(str(deprecated_dir))
"""

def create_backup(file_path):
    """Create a backup of a file with timestamp."""
    backup_path = f"{file_path}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if os.path.exists(file_path):
        shutil.copy2(file_path, backup_path)
        print(f"Created backup: {backup_path}")
    return backup_path

def archive_file(file_info):
    """Archive a file by adding a warning and moving to archive directory."""
    source_path = os.path.join(ROOT_DIR, file_info["path"])
    if not os.path.exists(source_path):
        print(f"WARNING: Source file not found: {source_path}")
        return
        
    # Create backup
    backup_path = create_backup(source_path)
    
    # Read file content
    with open(source_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Add warning to content
    new_content = file_info["warning"] + content
    
    # Create archive directory if needed
    archive_path = os.path.join(ARCHIVE_DIR, file_info["path"])
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    
    # Write content to archive location
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print(f"Archived file with warning: {archive_path}")
    
    # Create shim file if needed
    if file_info["needs_shim"]:
        module_name = file_info["path"].replace("/", ".")
        relative_import_path = file_info["path"]
        
        # Create shim content
        shim_content = PYTHON_SHIM_TEMPLATE.format(
            module_name=module_name,
            relative_import_path=relative_import_path
        )
        
        # Write shim to original location
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(shim_content)
            
        print(f"Created shim file: {source_path}")
    else:
        # For non-shim files, just add a note that the file is deprecated
        # and the original is in the archive
        note_content = file_info["warning"] + "\n# Original file archived to: {}\n".format(
            os.path.relpath(archive_path, ROOT_DIR)
        )
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(note_content)
            
        print(f"Added deprecation note to: {source_path}")

def restore_backup(file_path):
    """Restore the most recent backup of a file."""
    # Find the most recent backup
    backups = sorted([f for f in os.listdir(os.path.dirname(file_path)) 
                     if f.startswith(os.path.basename(file_path) + ".bak")])
    
    if not backups:
        print(f"No backup found for {file_path}")
        return False
        
    most_recent = backups[-1]
    backup_path = os.path.join(os.path.dirname(file_path), most_recent)
    
    # Restore the backup
    shutil.copy2(backup_path, file_path)
    print(f"Restored {file_path} from {backup_path}")
    return True

def revert_changes():
    """Revert changes by restoring backups."""
    for file_info in FILES_TO_ARCHIVE:
        source_path = os.path.join(ROOT_DIR, file_info["path"])
        if restore_backup(source_path):
            print(f"Reverted changes to {source_path}")
        else:
            print(f"Could not revert {source_path}")

def main():
    parser = argparse.ArgumentParser(description="Archive deprecated files after database V2 migration")
    parser.add_argument("--revert", action="store_true", help="Revert changes by restoring backups")
    args = parser.parse_args()
    
    if args.revert:
        revert_changes()
        return
    
    print(f"Archiving {len(FILES_TO_ARCHIVE)} deprecated files...")
    
    # Ensure archive directory exists
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    
    # Process each file
    for file_info in FILES_TO_ARCHIVE:
        try:
            archive_file(file_info)
        except Exception as e:
            print(f"ERROR processing {file_info['path']}: {e}")
    
    print("\nArchiving complete!")
    print(f"Files have been archived to: {ARCHIVE_DIR}")
    print("Backups of original files were created with .bak extension")
    print("To revert these changes, run: python scripts/archive_deprecated_files.py --revert")

if __name__ == "__main__":
    main()