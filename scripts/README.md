# Utility Scripts for Educational Quiz Bot

This directory contains utility scripts for maintaining and managing the bot.

## Available Scripts

### Command Sync (`sync_commands.py`)
Synchronizes Discord slash commands with Discord's servers. Use this when:
- First setting up the bot
- After adding new commands
- If commands aren't appearing in Discord

```bash
# Sync commands globally (may take up to 1 hour to propagate)
python scripts/sync_commands.py

# Sync commands for a specific guild (instant)
python scripts/sync_commands.py --guild YOUR_GUILD_ID
```

### Version Management (`update_version.py`)
Updates the bot version and creates changelog entries:

```bash
# Create a new version
python scripts/update_version.py create --version 1.2.3 --description "Added new features"

# Set the current version
python scripts/update_version.py set --version 1.2.3
```

### Cog Setup Updater (`update_cog_setup.py`)
Updates cog files to use the standardized setup pattern with BotContext:

```bash
# Update a specific cog
python scripts/update_cog_setup.py cogs/my_cog.py

# Update all cogs
python scripts/update_cog_setup.py --all
```

### Archive Deprecated Files (`archive_deprecated_files.py`)
Archives old or deprecated files to clean up the codebase:

```bash
# Archive specific files
python scripts/archive_deprecated_files.py file1.py file2.py

# List files that would be archived (dry run)
python scripts/archive_deprecated_files.py --dry-run
```

### Version System Migration (`migrate_version_system.py`)
Migrates from file-based to database-based version tracking:

```bash
# Run the migration
python scripts/migrate_version_system.py
```

## Best Practices

1. **Always backup** your database before running migration scripts
2. **Test in development** before running scripts in production
3. **Read script documentation** (at the top of each file) before use
4. **Check logs** after running scripts to ensure they completed successfully

## Creating New Scripts

When adding new utility scripts:
1. Place them in this directory
2. Include comprehensive documentation at the top of the file
3. Add command-line argument parsing for flexibility
4. Include error handling and logging
5. Update this README with usage instructions

## Script Requirements

Most scripts require:
- Python 3.8+
- Access to the bot's `.env` configuration
- Database connection (for scripts that modify data)
- Discord bot token (for scripts that interact with Discord API)

Ensure your environment is properly configured before running scripts.