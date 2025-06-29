# Educational Quiz Discord Bot

An advanced Discord bot that leverages Large Language Models (LLMs) to create educational quizzes on various topics. The bot generates questions on demand, manages quiz sessions, and tracks user scores.

## Project Structure

```
quiz_bot/
├── main.py                    # Bot entry point with AutoShardedBot
├── config.py                  # Configuration management (Pydantic)
├── bot_config.json            # Bot configuration file
├── setup.py                   # Package setup configuration
├── start_quiz_bot.sh          # Tmux-based bot launcher
├── env.example                # Environment variables template
├── requirements.txt           # Python dependencies
├── CHANGELOG.md               # Version history and changes
├── cogs/                      # Discord command modules (OOP-based)
│   ├── __init__.py
│   ├── base_cog.py           # Base class for all cogs
│   ├── admin.py              # Administrative commands
│   ├── quiz.py               # Core quiz functionality
│   ├── group_quiz.py         # Group quiz sessions
│   ├── stats.py              # Statistics and leaderboards
│   ├── help.py               # Help system
│   ├── faq.py                # FAQ with interactive UI
│   ├── onboarding.py         # Server onboarding
│   ├── preferences.py        # User preferences
│   ├── guild_preferences.py  # Guild-specific settings
│   ├── custom_quiz.py        # Custom quiz creation
│   ├── version.py            # Version management (owner-only)
│   ├── persistent_ui_admin.py # Persistent UI administration
│   ├── cog_loader.py         # Dynamic cog loading
│   ├── models/               # Data models
│   │   ├── __init__.py
│   │   └── quiz_models.py    # Quiz-related models
│   └── utils/                # Cog-specific utilities
│       ├── __init__.py
│       ├── app_command_utils.py  # Application command helpers
│       ├── decorators.py         # Command decorators
│       ├── embeds.py             # Embed creation utilities
│       ├── interaction_handler.py # Interaction handling
│       ├── permissions.py        # Permission checking
│       └── validation.py         # Input validation
├── services/                 # Business logic layer
│   ├── __init__.py
│   ├── database.py           # Core PostgreSQL operations
│   ├── database_service.py   # Database service wrapper
│   ├── database_initializer.py # Database setup
│   ├── database/             # Advanced database architecture
│   │   ├── __init__.py
│   │   ├── base_gateway.py   # Database gateway base class
│   │   ├── exceptions.py     # Database-specific exceptions
│   │   ├── models.py         # Database models
│   │   ├── unit_of_work.py   # Unit of work pattern
│   │   ├── adapters/         # Data adapters
│   │   │   ├── __init__.py
│   │   │   └── user_stats_adapter.py
│   │   └── repositories/     # Repository pattern
│   │       ├── __init__.py
│   │       └── user_stats_repository.py
│   ├── database_extensions/  # Extended database functionality
│   │   └── user_stats.py     # User statistics service
│   ├── database_operations/  # Modular database operations
│   │   ├── achievement_ops.py # Achievement operations
│   │   ├── admin_user_ops.py # Admin user operations
│   │   ├── analytics_ops.py  # Analytics operations
│   │   ├── config_ops.py     # Configuration operations
│   │   ├── guild_ops.py      # Guild operations
│   │   ├── history_ops.py    # History tracking
│   │   ├── leaderboard_ops.py # Leaderboard operations
│   │   ├── quiz_stats_ops.py # Quiz statistics
│   │   └── user_stats_ops.py # User statistics
│   ├── llm_service.py        # LLM integrations (OpenAI, Anthropic, Google)
│   ├── quiz_generator.py     # Quiz generation logic
│   ├── group_quiz.py         # Group quiz management
│   ├── group_quiz_multi_guild.py # Multi-guild group quiz
│   ├── learning_path.py      # Learning path functionality
│   ├── message_service.py    # Message routing and formatting
│   ├── persistent_ui_service.py # Persistent UI management
│   ├── ui_recovery_service.py # UI recovery and restoration
│   └── version_service.py    # Version management service
├── utils/                    # Global utilities
│   ├── __init__.py
│   ├── context.py            # Dependency injection (BotContext)
│   ├── content.py            # Content generation utilities
│   ├── db_helpers.py         # Database helper functions
│   ├── decorators.py         # Global decorators
│   ├── errors.py             # Error handling
│   ├── feature_flags.py      # Feature flag management
│   ├── messages.py           # Message constants
│   ├── progress_bars.py      # Custom emoji progress bars  
│   ├── ui.py                 # UI components and views
│   ├── button_handlers.py    # Button interaction handlers
│   ├── data_validation.py    # Data validation utilities
│   ├── specialized_handlers.py # Specialized UI handlers
│   ├── standardized_modals.py # Modal dialog components
│   ├── ui_config.py          # UI configuration management
│   ├── ui_constants.py       # UI constants
│   ├── unified_persistent_ui.py # Unified persistent UI system
│   ├── xp_calculator.py      # XP and leveling calculations
│   ├── permissions.py        # Permission utilities
│   ├── persistent_ui_example.py # UI persistence examples
│   └── migration_guide.md    # Migration documentation
├── tests/                    # Comprehensive test infrastructure
│   ├── __init__.py
│   ├── README.md
│   ├── run_tests.py          # Main test runner
│   ├── run_multi_guild_tests.py # Multi-guild test runner
│   ├── run_comprehensive_tests.py # Comprehensive test runner
│   ├── test_database_setup.py      # Database connection tests
│   ├── test_multi_guild_quizzes.py # Multi-guild functionality tests
│   ├── test_cog_functionality.py   # Cog functionality tests
│   ├── test_configuration.py       # Configuration tests
│   ├── test_database_operations.py # Database operations tests
│   ├── test_integration_workflow.py # Integration workflow tests
│   ├── test_llm_service.py         # LLM service tests
│   ├── test_quiz_validation.py     # Quiz validation tests
│   ├── test_utils.py               # Utility function tests
│   └── performance/          # Performance testing suite
│       ├── run_performance_tests.py # Performance test runner
│       ├── test_database_performance.py # Database performance tests
│       ├── test_llm_performance.py     # LLM performance tests
│       └── test_memory_performance.py  # Memory performance tests
├── scripts/                  # Utility scripts and maintenance tools
│   ├── README.md
│   ├── sync_commands.py      # Discord command synchronization
│   ├── update_version.py     # Version update utility
│   ├── migrate_version_system.py # Version system migration
│   ├── update_cog_setup.py   # Cog setup update utility
│   ├── archive_deprecated_files.py # Archive old files
│   ├── check_bot_health.py   # Bot health monitoring
│   ├── check_data_consistency.py # Data consistency checker
│   └── update_streak_system.py # Streak system updater
├── db/                       # Database schemas and migrations
│   ├── README.md
│   ├── schema.sql            # Main database schema
│   └── migrations/           # SQL migration scripts
├── docs/                     # Technical documentation (may be deprecated)
├── data/                     # Configuration files (user-created, gitignored)
└── prompts/                  # LLM prompt templates (user-created, gitignored)
    └── README.md             # Prompt creation guide
```

**Note**: The `data/` and `prompts/` directories are intellectual property and do not contain useable files, prompts, specifically, is a function required to start the bot. However, I have included prompt example files in order to give you an idea on what to create. Gathering a functioning and accurate response is up to you.

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

# Run comprehensive tests or performance benchmarks
python tests/run_comprehensive_tests.py
python tests/performance/run_performance_tests.py
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

## Advanced Architecture

### Database Layer
- **Repository Pattern**: Advanced database architecture with repositories and adapters
- **Connection Pooling**: Efficient asyncpg connection management
- **Unit of Work**: Transaction management and data consistency
- **Performance Testing**: Comprehensive benchmarking suite

### UI System
- **Persistent UI**: Components that survive bot restarts
- **Specialized Handlers**: Button, modal, and interaction handlers
- **UI Recovery**: Automatic restoration of interactive elements
- **XP System**: Leveling and achievement calculations

### Services Layer
- **Multi-LLM Support**: OpenAI, Anthropic, and Google AI integration
- **Message Routing**: Smart public/private message handling
- **Quiz Generation**: AI-powered content creation with security features
- **Multi-Guild**: Complete guild isolation for statistics and settings

### Monitoring & Maintenance
- **Health Checks**: Bot health monitoring and data consistency validation
- **Performance Monitoring**: Database, LLM, and memory performance tracking
- **Automated Maintenance**: Scripts for system updates and cleanup

## Extending the Bot

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

1. **Missing Directories**
   - You may have to create `data/` directory for configuration files 
   - See individual README files for directory-specific setup

2. **Database Connection Failed**
   - Ensure PostgreSQL is running
   - Verify the database host address is correct in `.env`
   - Check database credentials and permissions

3. **Commands Not Showing in Discord**
   - Run `python scripts/sync_commands.py`
   - Wait up to 1 hour for global sync
   - Use guild-specific sync for instant updates

4. **Module Import Errors**
   - Activate virtual environment: `source /path/to/your/venv/bin/activate`
   - Install requirements: `pip install -r requirements.txt`

5. **LLM API Errors**
   - Verify API keys in `.env`
   - Check API rate limits and quotas
   - Ensure network connectivity

6. **Cog Loading Failures**
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