# Educational Quiz Discord Bot

An advanced Discord bot that leverages Large Language Models (LLMs) to create educational quizzes on various topics. The bot generates questions on demand, manages quiz sessions, and tracks user scores.

## Project Structure

```
quiz_bot/
├── main.py              # Bot entry point with AutoShardedBot
├── config.py            # Configuration management (Pydantic)
├── bot_config.json      # Bot configuration file
├── setup.py             # Package setup
├── cogs/                # Discord command modules (OOP-based)
├── services/            # Business logic and services
├── utils/               # Utility functions and helpers
├── tests/               # Test suite
│   ├── test_database_setup.py
│   ├── test_multi_guild_quizzes.py
│   ├── run_multi_guild_tests.py
│   └── run_tests.py
├── scripts/             # Utility scripts
│   ├── sync_commands.py
│   ├── update_version.py
│   ├── migrate_version_system.py
│   ├── update_cog_setup.py
│   └── archive_deprecated_files.py
├── db/                  # Database schemas and migrations
├── docs/                # Technical documentation
├── data/                # Configuration files
└── prompts/             # LLM prompt templates
```

## Features

- 🧠 **Multi-LLM Support**: Choose between OpenAI, Anthropic, and Google's Gemini language models for quiz generation
- 📝 **Multiple Question Types**: Supports multiple-choice, true/false, and short-answer questions
- 🌟 **Difficulty Levels**: Choose from easy, medium, or hard questions
- 🎯 **Quiz Templates**: Use specialized templates for different quiz styles (educational, challenge, trivia)
- 📊 **Categories**: Organize questions into various subject categories
- ⏱️ **Interactive Quizzes**: Real-time quiz sessions with timers and point tracking
- 🏆 **Leaderboards**: See who scored the highest in each quiz
- 📱 **Private Quizzes**: Option to receive quiz questions in DMs for personal study sessions
- 👥 **Group Trivia**: Interactive multiplayer trivia games with real-time leaderboards
- 🎮 **Visual Feedback**: Progress bars, color-coded difficulty levels, and response time tracking
- 📈 **Statistics Tracking**: Track and save quiz performance in PostgreSQL with multi-guild support
- 🧩 **Modular Design**: Built with OOP cog-based architecture using BaseCog pattern
- 🏗️ **Clean Architecture**: Follows best practices with dependency injection and separated concerns
- 🎯 **Achievement System**: Progressive achievements with visual feedback
- 📊 **Analytics Dashboard**: Server-wide analytics and insights
- 🔄 **Version Management**: Semantic versioning with changelog (owner-only)
- ⚡ **Async Architecture**: Fully asynchronous using asyncpg for database operations

## Setup

### Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Discord bot token
- At least one LLM API key (OpenAI, Anthropic, or Google AI)
- Git for version control
- tmux (optional, for background process management)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/JadenRazo/Discord-Bot-Python
   cd educational-quiz-bot
   ```

2. **Virtual Environment Setup**:
   
   The project uses a Python virtual environment.
   
   To activate the virtual environment:
   ```bash
   source /path/to/your/venv/bin/activate
   ```
   
   To install or update packages (after activating the virtual environment):
   ```bash
   source /path/to/your/venv/bin/activate && pip install -r requirements.txt
   ```

3. Set up PostgreSQL:
   - Install PostgreSQL 12+ from the [official website](https://www.postgresql.org/download/)
   - Create a database for the bot:
     ```bash
     createdb quizbot
     ```
   - The bot will automatically initialize the database schema on first run

4. Create a `.env` file based on the example:
   ```
   cp env.example .env
   ```

5. Edit the `.env` file with your Discord token, API keys, and database configuration:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   GOOGLE_AI_API_KEY=your_google_api_key_here
   POSTGRES_HOST=your_database_host
   POSTGRES_PORT=5432
   POSTGRES_DB=quizbot
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   ```

### Testing Your Setup

Before running the bot, verify your setup:

```bash
# Activate virtual environment first
source /path/to/your/venv/bin/activate

# Test database connection and setup
python tests/test_database_setup.py

# Test multi-guild functionality
python tests/run_multi_guild_tests.py

# Run all tests
python tests/run_tests.py
```

### Syncing Discord Commands

Sync slash commands after adding new commands or on first setup:

```bash
# Activate virtual environment
source /path/to/your/venv/bin/activate

# Sync commands globally (takes up to 1 hour to propagate)
python scripts/sync_commands.py

# Sync commands for a specific guild (instant)
python scripts/sync_commands.py --guild YOUR_GUILD_ID
```

### Running the Bot

**Important**: Always activate the virtual environment before running the bot:

```bash
source /path/to/your/venv/bin/activate && python main.py
```

Alternative method using the provided script:
```bash
./start_quiz_bot.sh
```

## Usage

The bot uses a prefix of `!` by default (can be changed in the .env file).

### Basic Commands

- `!help` - Show all available commands
- `!about` - Information about the bot

### Quiz Commands

- `!quiz start <topic> [question_count] [difficulty] [question_type] [options]` - Start a new quiz
  - Example: `!quiz start "Python Programming" 10 medium multiple_choice`
  - Advanced: `!quiz start "Solar System" 10 hard --provider anthropic --category science --template challenge`
  - Private: `!quiz start "Python Basics" 5 easy --private` (questions sent to DMs)
- `!quiz stop` - Stop the current quiz
- `!quiz topics` - Show suggested quiz topics
- `!quiz categories` - Show available question categories
- `!quiz providers` - Show available LLM providers
- `!quiz templates` - Show available quiz templates
- `!quiz scores` - View your quiz statistics

### Trivia Commands

- `!trivia start <topic> [question_count] [difficulty] [options]` - Start a group trivia game
  - Example: `!trivia start "World Geography" 15 medium`
  - Advanced: `!trivia start "Movies" 20 hard --provider anthropic --category entertainment --timeout 45`
- `!trivia stop` - Stop the current trivia game
- `!trivia leaderboard` - Show the current trivia game leaderboard

### Admin Commands

- `!admin reload <cog>` - Reload a specific cog
- `!admin load <cog>` - Load a specific cog
- `!admin unload <cog>` - Unload a specific cog
- `!admin listcogs` - List all loaded cogs
- `!admin features` - Manage feature flags
- `!admin status` - Show bot status information
- `!admin analytics` - View server analytics
- `!admin shutdown` - Shut down the bot

## LLM Providers

The bot supports multiple LLM providers:

1. **OpenAI** - Uses the GPT models (default)
2. **Anthropic** - Uses Claude models
3. **Google AI** - Uses Gemini models

To specify which provider to use for a quiz:
```
!quiz start "topic" --provider openai
```

## Quiz Templates

Several quiz templates are available for different styles of quizzes:

1. **Standard** - A balanced mix of question types
2. **Educational** - Focused on learning and retention with detailed explanations
3. **Challenge** - Difficult questions for testing expert knowledge
4. **Trivia** - Fun facts and interesting knowledge

To use a specific template:
```
!quiz start "topic" --template educational
```

## Architecture Details

```
educational-quiz-bot/
├── main.py                    # Bot entry point with AutoShardedBot
├── config.py                  # Configuration management (Pydantic)
├── bot_config.json            # Bot configuration file
├── cogs/                      # Discord command handlers
│   ├── base_cog.py           # Base class for all cogs (OOP pattern)
│   ├── quiz.py               # Main quiz functionality
│   ├── group_quiz.py         # Group quiz mode
│   ├── admin.py              # Admin commands
│   ├── help.py               # Help system
│   ├── faq.py                # FAQ with interactive UI
│   ├── onboarding.py         # Server onboarding
│   ├── stats.py              # User statistics
│   ├── preferences.py        # User preferences
│   ├── guild_preferences.py  # Guild-specific preferences
│   ├── custom_quiz.py        # Custom quiz creation
│   ├── version.py            # Version management (owner-only)
│   ├── models/               # Data models
│   │   └── quiz_models.py    # Quiz-related models
│   └── utils/                # Cog-specific utilities
│       ├── permissions.py    # Permission checking
│       ├── embeds.py         # Embed creation
│       ├── validation.py     # Input validation
│       └── decorators.py     # Command decorators
├── services/                 # Business logic layer
│   ├── database.py           # PostgreSQL operations (asyncpg)
│   ├── database_initializer.py # Database setup
│   ├── database_extensions/  # Extended functionality
│   │   └── user_stats.py     # User statistics service
│   ├── database_operations/  # Modular DB operations
│   │   ├── achievement_ops.py # Achievements
│   │   ├── analytics_ops.py  # Analytics
│   │   ├── config_ops.py     # Configuration
│   │   ├── guild_ops.py      # Guild operations
│   │   ├── history_ops.py    # History tracking
│   │   ├── leaderboard_ops.py # Leaderboards
│   │   ├── quiz_stats_ops.py # Quiz statistics
│   │   └── user_stats_ops.py # User statistics
│   ├── llm_service.py        # LLM integrations
│   ├── quiz_generator.py     # Quiz generation
│   ├── group_quiz.py         # Group quiz management
│   ├── group_quiz_multi_guild.py # Multi-guild support
│   ├── learning_path.py      # Learning paths
│   ├── message_service.py    # Message formatting
│   └── version_service.py    # Version management
├── utils/                    # Global utilities
│   ├── context.py            # Dependency injection
│   ├── errors.py             # Error handling
│   ├── feature_flags.py      # Feature flags
│   ├── messages.py           # Message constants
│   ├── progress_bars.py      # Visual progress bars
│   └── ui.py                 # UI components
├── db/                       # Database schemas
│   ├── schema.sql            # Main schema
│   └── migrations/           # Migration scripts
└── data/                     # Configuration files
    └── feature_flags.json    # Feature configuration
```

## Extending the Bot

The bot follows clean OOP principles and is designed to be easily extensible:

### Adding a New Cog

1. Create a new file in the `cogs` directory
2. Inherit from `BaseCog` for standardized functionality:
   ```python
   from cogs.base_cog import BaseCog
   
   class MyCog(BaseCog, name="MyCog"):
       def __init__(self, bot):
           super().__init__(bot, "MyCog")
   ```
3. Implement your commands and functionality
4. Add both `setup()` and `setup_with_context()` functions:
   ```python
   async def setup(bot):
       cog = MyCog(bot)
       await bot.add_cog(cog)
       return cog
   
   async def setup_with_context(bot, context):
       from cogs.base_cog import setup_with_context as base_setup
       return await base_setup(bot, context, MyCog)
   ```
5. Add the cog to `_cogs_to_load` list in `main.py`
6. Update `cogs/cog_loader.py` with the cog name mapping
7. Run `python scripts/sync_commands.py` to register new commands

### Adding a New LLM Provider

1. Create a new provider class in `services/llm_service.py`
2. Add the provider configuration to `config.py`
3. Add the provider initialization in `LLMService._initialize_providers()`

### Adding a New Quiz Template

1. Add a new template to the templates dictionary in `services/quiz_generator.py`
2. The template will automatically be available for use

### Adding New Models

1. Create data models in `cogs/models/` for better separation of concerns
2. Use dataclasses or Pydantic models for type safety
3. Import and use them in your cogs as needed

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Ensure PostgreSQL is running
   - Verify the database host address is correct in `.env`
   - Check database credentials and permissions

2. **Commands Not Showing in Discord**
   - Run `python scripts/sync_commands.py`
   - Wait up to 1 hour for global sync
   - Use guild-specific sync for instant updates

3. **Module Import Errors**
   - Activate virtual environment: `source /path/to/your/venv/bin/activate`
   - Install requirements: `pip install -r requirements.txt`

4. **LLM API Errors**
   - Verify API keys in `.env`
   - Check API rate limits and quotas
   - Ensure network connectivity

5. **Cog Loading Failures**
   - Check cog inherits from `BaseCog`
   - Verify both `setup()` and `setup_with_context()` are implemented
   - Review error logs for specific issues

## License

MIT

## Acknowledgements

- [discord.py](https://github.com/Rapptz/discord.py)
- [OpenAI API](https://platform.openai.com/docs/)
- [Anthropic API](https://docs.anthropic.com/)
- [Google Generative AI](https://ai.google.dev/)
- [PostgreSQL](https://www.postgresql.org/)
- [asyncpg](https://github.com/MagicStack/asyncpg)
- [Pydantic](https://docs.pydantic.dev/) 