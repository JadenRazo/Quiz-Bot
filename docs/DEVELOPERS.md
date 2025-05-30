# Developer Guide for Educational Discord Bot

This guide provides an overview of the bot's architecture, key components, and design patterns to help developers understand and contribute to the codebase.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Dependency Management](#dependency-management)
3. [Configuration System](#configuration-system)
4. [Database Setup](#database-setup)
5. [Error Handling](#error-handling)
6. [Feature Flags](#feature-flags)
7. [User Interface Components](#user-interface-components)
8. [User Experience Features](#user-experience-features)
9. [Performance Optimizations](#performance-optimizations)
10. [Best Practices](#best-practices)

## Architecture Overview

The bot follows a modular, object-oriented architecture with clear separation of concerns:

- **Main Module**: Entry point and bot initialization
- **Cogs**: Command groups and Discord event handlers (all inherit from `BaseCog`)
- **Services**: Business logic and external integrations
- **Models**: Data models for better encapsulation
- **Utilities**: Helper functions and common tools

The architecture is designed to minimize circular dependencies through the use of a centralized context object and proper dependency injection.

```
educational-discord-bot/
├── main.py               # Bot entry point
├── config.py             # Configuration management
├── cogs/                 # Command handlers
│   ├── base_cog.py       # Base class for all cogs
│   ├── quiz.py           # Quiz commands
│   ├── group_quiz.py     # Group quiz commands
│   ├── admin.py          # Admin commands
│   ├── help.py           # Help commands
│   ├── faq.py            # FAQ system with interactive UI
│   ├── onboarding.py     # Server onboarding
│   ├── stats.py          # User statistics
│   ├── preferences.py    # User preferences
│   ├── custom_quiz.py    # Custom quiz creation
│   ├── cog_loader.py     # Dynamic cog loading utility
│   ├── models/           # Data models
│   │   ├── __init__.py
│   │   └── quiz_models.py # Quiz-related data models
│   └── utils/            # Cog-specific utilities
│       └── __init__.py
├── services/             # Business logic
│   ├── database.py       # PostgreSQL database operations
│   ├── database_extensions/  # Database service extensions
│   │   └── user_stats.py     # User statistics service
│   ├── llm_service.py    # LLM integration
│   ├── quiz_generator.py # Quiz generation
│   ├── group_quiz.py     # Group quiz management
│   └── message_service.py # Message utilities
├── utils/                # Utilities and helpers
│   ├── context.py        # Dependency injection
│   ├── decorators.py     # Function decorators
│   ├── errors.py         # Error handling
│   ├── feature_flags.py  # Feature management
│   └── ui.py             # UI components
└── data/                 # Data storage
    └── feature_flags.json # Feature configuration
```

## Dependency Management

The bot uses a dependency injection pattern through the `BotContext` class to avoid circular imports and facilitate testing.

### BotContext

The `BotContext` class centralizes access to shared resources:

```python
# Initialize context in main.py
self.context = BotContext(
    bot=self,
    config=config,
    db_service=self.db_service,
    message_router=self.message_router,
    group_quiz_manager=self.group_quiz_manager
)

# Use context in cogs
def set_context(self, context):
    self.context = context
    self.config = context.config
    self.db_service = context.db_service
    self.message_router = context.message_router
```

### Cog Loading

All cogs inherit from `BaseCog` and follow a standardized loading pattern:

```python
from cogs.base_cog import BaseCog

class MyCog(BaseCog, name="MyCog"):
    def __init__(self, bot):
        super().__init__(bot, "MyCog")
        # Cog-specific initialization

# Standard setup function for Discord.py
async def setup(bot):
    cog = MyCog(bot)
    await bot.add_cog(cog)
    return cog

# Context-aware setup function
async def setup_with_context(bot, context):
    from cogs.base_cog import setup_with_context as base_setup
    return await base_setup(bot, context, MyCog)
```

The `CogLoader` utility handles dynamic loading and context management:

```python
# In main.py
from cogs.cog_loader import CogLoader

# Load cog with context
success = await CogLoader.load_cog_with_context(
    bot=self,
    module_name=cog_name,
    context=self.context
)
```

## Configuration System

The bot uses a hierarchical configuration system based on Pydantic models with environment variable support:

```python
class DatabaseConfig(BaseModel):
    """Configuration for PostgreSQL database functionality."""
    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    database: str = Field(default="quizbot", description="PostgreSQL database name")
    user: str = Field(default="postgres", description="PostgreSQL username")
    password: str = Field(default="", description="PostgreSQL password")
    min_connections: int = Field(default=1, description="Minimum number of connections in pool")
    max_connections: int = Field(default=10, description="Maximum number of connections in pool")
    
    @validator('host', pre=True, always=True)
    def validate_host(cls, v):
        return os.getenv("POSTGRES_HOST", v)

class BotConfig(BaseModel):
    bot_token: str = Field(default="", description="Discord bot token")
    default_prefix: str = Field(default="!", description="Default command prefix")
    admin_roles: List[str] = Field(default=["Admin", "Moderator"], description="Admin role names")
    admin_users: List[int] = Field(default=[], description="Admin user IDs")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    quiz: QuizConfig = Field(default_factory=QuizConfig, description="Quiz configuration")
    trivia: TriviaConfig = Field(default_factory=TriviaConfig, description="Trivia configuration")
    database: DatabaseConfig = Field(default_factory=DatabaseConfig, description="Database configuration")
```

## Database Setup

The bot uses PostgreSQL for database storage. Here's how to set up PostgreSQL for development:

### PostgreSQL Installation

#### Windows

1. Download PostgreSQL installer from the [official website](https://www.postgresql.org/download/windows/)
2. Run the installer and follow the installation steps
3. Remember the password you set for the postgres user
4. Make sure to check the option to install pgAdmin (GUI tool for PostgreSQL)
5. After installation, you can launch pgAdmin to manage your databases

#### Linux (Ubuntu/Debian)

1. Update your package index:
   ```bash
   sudo apt update
   ```

2. Install PostgreSQL and related packages:
   ```bash
   sudo apt install postgresql postgresql-contrib
   ```

3. Start and enable PostgreSQL service:
   ```bash
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
   ```

4. Set a password for the postgres user:
   ```bash
   sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'your_password';"
   ```

### Creating the Database

#### Using pgAdmin (Windows/GUI approach)

1. Open pgAdmin
2. Connect to your PostgreSQL server
3. Right-click on "Databases" and select "Create" → "Database"
4. Name your database "quizbot" (or your preferred name)
5. Click "Save"

#### Using Command Line (Windows/Linux)

1. Login to PostgreSQL:
   ```bash
   # On Linux
   sudo -u postgres psql
   
   # On Windows (from Command Prompt)
   psql -U postgres
   ```

2. Create the database:
   ```sql
   CREATE DATABASE quizbot;
   ```

3. Exit PostgreSQL:
   ```
   \q
   ```

### Configuration for the Bot

Configure the bot to use your PostgreSQL database by setting the following environment variables in your `.env` file:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=quizbot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

Or manually configure it in your code:

```python
bot_config = BotConfig(
    database=DatabaseConfig(
        host="localhost",
        port=5432,
        database="quizbot",
        user="postgres",
        password="your_password"
    )
)
```

### Required Python Packages

Make sure to install the required PostgreSQL Python packages:

```bash
pip install psycopg2-binary
```

### Database Schema

The bot uses several tables to store user data and quiz information:

- **users**: Stores user information and preferences
- **user_quiz_sessions**: Records quiz attempts by users
- **user_achievements**: Tracks achievements earned by users
- **guild_members**: Maps users to guilds they belong to
- **guild_settings**: Stores server-specific settings
- **custom_quizzes**: Stores custom quizzes created by users

## Error Handling

The bot uses a comprehensive error handling system with custom exceptions, logging, and context tracking:

### Custom Exceptions

```python
class BotError(Exception):
    def __init__(
        self, 
        message: str, 
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.message = message
        self.severity = severity
        self.details = details or {}
        self.original_exception = original_exception
        super().__init__(message)
```

### Centralized Logging

```python
def log_exception(
    exc: Exception,
    logger_instance: Optional[logging.Logger] = None,
    level: int = logging.ERROR,
    context: Optional[Dict[str, Any]] = None
) -> None:
    # Log exception with context and traceback
```

### Safe Execution

```python
def safe_execute(
    func: Callable,
    error_msg: str = "Operation failed",
    fallback_value: Any = None,
    log_error: bool = True,
    reraise: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> Any:
    # Safely execute a function with error handling
```

## Feature Flags

The bot includes a feature flag system for enabling/disabling features globally or per guild:

### Feature Definition

```python
class FeatureFlag(Enum):
    """Enumeration of available feature flags."""
    GROUP_QUIZ = "group_quiz"
    PRIVATE_QUIZZES = "private_quizzes"
    LLM_ANTHROPIC = "llm_anthropic"
    # ...other features
```

### Feature Usage

```python
# Check if a feature is enabled
if feature_manager.is_enabled(FeatureFlag.GROUP_QUIZ, guild_id=ctx.guild.id):
    # Feature-specific code
```

### Admin Commands

Administrators can manage features through commands:

```
!admin features enable group_quiz            # Enable globally
!admin features disable private_quizzes      # Disable globally
!admin features enable group_quiz 123456789  # Enable for specific guild
!admin features guild 123456789              # View guild settings
```

## User Interface Components

The bot leverages Discord's UI components for interactive interfaces:

### Interactive Views

Views are used to create interactive interfaces with buttons, select menus, and more:

```python
class FAQView(discord.ui.View):
    """View for handling FAQ pagination with interactivity controls."""
    
    def __init__(self, embeds: List[discord.Embed], author_id: int, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0
        self.total_pages = len(embeds)
        self.author_id = author_id
        
        # Update button states for initial view
        self._update_buttons()
        
        # Update page indicators in all embeds
        self._update_embed_footers()
```

### Button Components

Buttons provide interactive controls for users:

```python
@discord.ui.button(emoji="◀️", style=discord.ButtonStyle.gray, custom_id="prev_page")
async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
    """Go to previous page button handler."""
    self.current_page = max(0, self.current_page - 1)
    self._update_buttons()
    await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
```

### Modal Dialogs

Modal dialogs enable complex data input from users:

```python
class QuizCreationModal(discord.ui.Modal, title='Create Custom Quiz'):
    """Modal dialog for creating custom quizzes."""
    
    quiz_name = discord.ui.TextInput(
        label='Quiz Name',
        placeholder='Enter a name for your quiz',
        required=True,
        max_length=100
    )
    
    topic = discord.ui.TextInput(
        label='Topic',
        placeholder='What is this quiz about?',
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Process the submitted data
        await interaction.response.defer(ephemeral=True)
        # Create and save the custom quiz
        await interaction.followup.send("Your quiz has been created!", ephemeral=True)
```

### Security Considerations

Views should include validation to ensure only authorized users can interact:

```python
async def interaction_check(self, interaction: discord.Interaction) -> bool:
    """
    Ensure only the command author can use the buttons.
    
    Args:
        interaction: The interaction that triggered this check
        
    Returns:
        bool: Whether the interaction should proceed
    """
    if interaction.user.id != self.author_id:
        await interaction.response.send_message(
            "You cannot use these controls as you didn't run the command.",
            ephemeral=True
        )
        return False
    return True
```

### Timeout Handling

Proper timeout handling prevents stale components:

```python
async def on_timeout(self) -> None:
    """Handle view timeout by disabling all buttons."""
    for item in self.children:
        if isinstance(item, discord.ui.Button):
            item.disabled = True
    
    # Try to update the message if possible
    try:
        message = self.message
        if message:
            await message.edit(view=self)
    except Exception as e:
        logger.warning(f"Failed to update message on timeout: {e}")
```

### Hybrid Commands

The bot uses hybrid commands to support both prefix and slash commands:

```python
@commands.hybrid_command(name="faq", description="Show frequently asked questions and bot information.")
async def faq(self, ctx: commands.Context):
    """Show frequently asked questions and bot information with paginated navigation."""
    # Command implementation
```

## User Experience Features

The bot includes several features to enhance user experience:

### Server Onboarding

When the bot joins a new server, it automatically sends a welcome message with quick-start instructions:

```python
@commands.Cog.listener()
async def on_guild_join(self, guild: discord.Guild) -> None:
    """Send a welcome message when the bot joins a new server."""
    # Find a suitable channel and send welcome message
    welcome_embed = self._create_welcome_embed(guild)
    await channel.send(embed=welcome_embed, view=WelcomeView(self.bot))
```

### User Statistics

Users can view their quiz performance statistics with detailed breakdowns:

```python
@commands.hybrid_command(name="stats", description="View your quiz statistics and learning progress.")
@app_commands.describe(user="The user to view stats for (defaults to yourself)")
async def stats(self, ctx: commands.Context, user: Optional[discord.Member] = None):
    """Show comprehensive statistics about a user's quiz performance."""
    stats = await self.db_service.get_user_stats(user.id)
    # Create and send stats visualization
```

### Server Leaderboards

Servers can have competitive leaderboards with various filters:

```python
@commands.hybrid_command(name="leaderboard", description="View the server quiz leaderboard.")
@app_commands.describe(
    category="Quiz category to filter by",
    timeframe="Time period for the leaderboard"
)
async def leaderboard(self, ctx: commands.Context, 
                     category: Optional[str] = None,
                     timeframe: Literal["weekly", "monthly", "all-time"] = "all-time"):
    """Display server leaderboard with customizable filters."""
    # Get and display leaderboard data
```

### User Preferences

Users can set and save their quiz preferences:

```python
@commands.hybrid_command(name="preferences", description="Manage your personal quiz preferences.")
async def preferences_group(self, ctx: commands.Context):
    """Commands for managing personal preferences."""
    # Show current preferences
```

### Custom Quiz Creation

Users can create and share their own custom quizzes:

```python
@commands.hybrid_command(name="create_quiz", description="Create a custom quiz.")
async def create_quiz(self, ctx: commands.Context):
    """Create a custom quiz using a modal dialog."""
    # Open modal dialog for quiz creation
    modal = QuizCreationModal(self)
    await ctx.interaction.response.send_modal(modal)
```

### Quiz History

Users can view their quiz history with detailed information:

```python
@commands.hybrid_command(name="history", description="View your quiz history.")
async def history(self, ctx: commands.Context):
    """Show a user's quiz history with detailed statistics."""
    # Get and display quiz history
```

### Server Analytics

Server administrators can view usage analytics:

```python
@commands.hybrid_command(name="analytics", description="View bot usage analytics for your server.")
@app_commands.checks.has_permissions(administrator=True)
async def analytics(self, ctx: commands.Context):
    """Display usage analytics for server administrators."""
    # Get and display server analytics data
```

## Performance Optimizations

The bot includes several optimizations for performance:

### Caching

```python
@cache_result(expire_seconds=3600, key_prefix="llm_question")
async def generate_questions(
    self,
    topic: str,
    question_count: int = 5,
    # ...
) -> List[Question]:
    # Generate questions with caching
```

### Token Optimization

```python
class TokenOptimizer:
    @staticmethod
    def optimize_prompt(prompt: str, max_tokens: int = 4000) -> str:
        # Optimize a prompt to fit within token limits
    
    @staticmethod
    def batch_requests(items: List[Any], batch_size: int = 5) -> List[List[Any]]:
        # Split a list of items into batches for more efficient API calls
```

### Database Query Caching

```python
def get_cached_query_result(self, key: str) -> Optional[str]:
    # Get a cached query result
    
def cache_query_result(self, key: str, data: str, expires_in_seconds: int = 300) -> bool:
    # Cache a query result
```

### Connection Pooling

```python
# The database service uses a connection pool to efficiently manage database connections
self.connection_pool = pool.ThreadedConnectionPool(
    minconn=self.config.min_connections,
    maxconn=self.config.max_connections,
    host=self.config.host,
    port=self.config.port,
    dbname=self.config.database,
    user=self.config.user,
    password=self.config.password
)
```

## Best Practices

When contributing to the codebase, follow these best practices:

### Code Style
- Use type hints for all function parameters and return values
- Document all public classes and functions with docstrings
- Follow PEP 8 style guidelines
- Use meaningful variable and function names

### Error Handling
- Use custom exceptions for domain-specific errors
- Always log exceptions with appropriate context
- Provide user-friendly error messages
- Use ephemeral messages for error responses when appropriate

### Feature Development
- Check if related features are enabled before executing code
- Add new features behind feature flags for controlled rollout
- Create appropriate configuration entries for customizable features

### Performance
- Cache expensive operations (API calls, database queries)
- Use asynchronous code for I/O operations
- Batch requests when possible
- Use parameter binding for SQL queries to prevent SQL injection

### UI Components
- Always implement proper timeout handling for views
- Include user validation in interaction_check methods
- Update button states based on current context
- Provide clear visual feedback for user actions
- Make all interactive components accessible

### Testing
- Write unit tests for new functionality
- Test with different configurations and feature flag combinations
- Use dependency injection to facilitate testing with mocks
- Ensure interactive components have proper validation and error handling 