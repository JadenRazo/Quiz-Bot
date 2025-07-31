# Scripts for Educational Quiz Bot

This directory contains various scripts for maintaining, managing, and troubleshooting the bot.

## Directory Structure

```
scripts/
├── utilities/                     # General utility scripts
│   └── sync_commands.py          # Discord command synchronization
├── check_bot_health.py           # Bot health monitoring
└── check_data_consistency.py     # Database consistency checks
```

## Available Scripts

### 📊 Diagnostics & Maintenance

#### Bot Health Check (`check_bot_health.py`)
Checks the overall health of the bot including database connection and Discord status:
```bash
python scripts/check_bot_health.py
```

#### Data Consistency Check (`check_data_consistency.py`)
Identifies and optionally repairs data inconsistencies in the database:
```bash
# Check for issues
python scripts/check_data_consistency.py

# Auto-repair issues
python scripts/check_data_consistency.py --repair

# Check specific user
python scripts/check_data_consistency.py --user USER_ID
```

### 🔧 Utilities

#### Command Sync (`utilities/sync_commands.py`)
Synchronizes Discord slash commands with Discord's servers. Use this when:
- First setting up the bot
- After adding new commands
- If commands aren't appearing in Discord

```bash
# Sync commands globally (may take up to 1 hour to propagate)
python scripts/utilities/sync_commands.py

# Sync commands for a specific guild (instant)
python scripts/utilities/sync_commands.py --guild YOUR_GUILD_ID
```

## Common Usage Scenarios

### Initial Bot Setup
1. Configure your environment variables
2. Run database consistency check: `python scripts/check_data_consistency.py`
3. Sync commands: `python scripts/utilities/sync_commands.py --guild YOUR_GUILD_ID`

### Commands Not Showing
1. First, verify bot health: `python scripts/check_bot_health.py`
2. Then sync commands: `python scripts/utilities/sync_commands.py --guild YOUR_GUILD_ID`

### Database Issues
1. Check data consistency: `python scripts/check_data_consistency.py`
2. If issues found, repair: `python scripts/check_data_consistency.py --repair`

## Notes

- Always use guild-specific sync during development for instant updates
- Global command sync can take up to 1 hour to propagate
- The bot must have the `applications.commands` scope when invited
- All scripts assume proper environment variables are set (.env file)