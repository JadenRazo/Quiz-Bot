# Version Management System

The Educational Quiz Bot now includes a comprehensive version management system that allows you to track and manage bot versions directly through Discord commands.

## Features

- Track bot versions with detailed descriptions
- Maintain a changelog for each version
- Mark a specific version as the current version
- View version history and information
- Bot owner-only version management commands

## Commands

### `/version` or `/version current`
Shows the current bot version.

**Example:**
```
/version
```
**Output:**
```
📦 Bot Version 1.0.0
Initial release of Educational Quiz Bot
Released: 2025-05-18 15:30 UTC
```

### `/version info <version>`
Get detailed information about a specific version including its changelog.

**Example:**
```
/version info 1.1.0
```
**Output:**
```
📦 Version 1.1.0 Details
Added trivia game mode and performance improvements
Released: 2025-05-19 10:00 UTC
✅ Current Version

✨ Features:
• Added trivia game mode with multiplayer support
• Implemented one-winner mode for competitive play
• Added private quiz options

🐛 Fixes:
• Fixed leaderboard display issues
• Resolved guild member tracking problems

🔧 Improvements:
• Optimized database queries for better performance
• Enhanced error handling for quiz sessions
```

### `/version list [limit]`
List all available versions (default: 10 most recent).

**Example:**
```
/version list 5
```
**Output:**
```
📦 Bot Versions
Showing the latest 5 versions

1.1.0 (Current)
Added trivia game mode and performance improvements
Released: 2025-05-19

1.0.2
Bug fixes and stability improvements
Released: 2025-05-17

1.0.1
Fixed critical database connection issue
Released: 2025-05-16

1.0.0
Initial release of Educational Quiz Bot
Released: 2025-05-15
```

### `/version change <version> <description> [set_current]` (Jaden Razo Only)
Create a new version or update an existing one. This command is restricted to the bot owner (User ID: 1351309423015886899).

**Parameters:**
- `version`: Version string (e.g., "1.2.0")
- `description`: Description of the version (use \n for new lines)
- `set_current`: Whether to set this as the current version (default: true)

**Example:**
```
/version change 1.2.0 "Major update with new features\n\nAdded custom quiz creation\nImproved UI/UX\nEnhanced statistics tracking" true
```

### `/version changelog <version> <change_type> <description>` (Jaden Razo Only)
Add a changelog entry to an existing version. This command is restricted to the bot owner (User ID: 1351309423015886899).

**Parameters:**
- `version`: The version to add the changelog to
- `change_type`: Type of change (feature, fix, improvement, breaking)
- `description`: Description of the change

**Example:**
```
/version changelog 1.2.0 feature "Added support for image-based questions"
```

### `/version set <version>` (Jaden Razo Only)
Set a specific version as the current version. This command is restricted to the bot owner (User ID: 1351309423015886899).

**Example:**
```
/version set 1.1.0
```

## Database Schema

The version system uses two tables:

### `bot_versions` table
- `id`: Primary key
- `version`: Version string (unique)
- `description`: Detailed description
- `release_date`: When the version was released
- `is_current`: Boolean flag for current version
- `author_id`: Discord ID of who created the version
- `created_at`: When the entry was created
- `updated_at`: When the entry was last updated

### `version_changelog` table
- `id`: Primary key
- `version_id`: Reference to bot_versions
- `change_type`: Type of change (feature, fix, improvement, breaking)
- `description`: Description of the change
- `created_at`: When the entry was created

## Usage Examples

### Creating a new version with changelog

```python
# Bot owner uses these commands:
/version change 1.3.0 "Quiz performance update\n\nOptimized quiz generation\nAdded caching system" true
/version changelog 1.3.0 feature "Implemented Redis caching for quiz questions"
/version changelog 1.3.0 improvement "Reduced quiz generation time by 50%"
/version changelog 1.3.0 fix "Fixed memory leak in question generator"
```

### Rolling back to a previous version

```python
# If something goes wrong with the new version:
/version set 1.2.9
```

### Viewing version history

```python
# Any user can check version info:
/version info 1.0.0  # See the initial release details
/version list 20     # See last 20 versions
/version            # Check current version
```

## Best Practices

1. **Semantic Versioning**: Use semantic versioning (MAJOR.MINOR.PATCH)
   - MAJOR: Breaking changes
   - MINOR: New features (backwards compatible)
   - PATCH: Bug fixes

2. **Descriptive Changelogs**: Write clear, user-friendly changelog entries
   - Start with a verb (Added, Fixed, Improved, Removed)
   - Be specific about what changed
   - Mention affected components

3. **Regular Updates**: Keep the version system updated with each release
   - Update version immediately after deployment
   - Add all significant changes to the changelog

4. **Testing**: Always test version commands after major updates
   - Verify current version displays correctly
   - Check that changelog entries are formatted properly

## Integration with Bot

The version system is fully integrated into the bot:

1. The version service initializes with the database on bot startup
2. Version information is accessible through the bot context
3. Version commands are available as slash commands
4. All version operations are logged for debugging

## Error Handling

The system includes comprehensive error handling:

- Invalid version formats are rejected
- Database errors are logged but don't crash the bot
- Missing version entries return user-friendly messages
- Permission checks prevent unauthorized changes

## Future Enhancements

Potential improvements to the version system:

1. Automatic version bumping based on git tags
2. Version comparison and upgrade notes
3. Rollback functionality with database migrations
4. Version-specific feature flags
5. Automated changelog generation from commit messages
6. Version notification system for server admins
7. API endpoint for version information
8. Integration with CI/CD pipeline