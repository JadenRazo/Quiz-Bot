# Database Setup for Educational Discord Bot

This directory contains database-related scripts and documentation for setting up and maintaining the PostgreSQL database used by the Educational Discord Bot.

## Schema Overview

The bot uses a robust PostgreSQL database with the following key files:

- `schema.sql` - Base schema with minimal structure
- `schema_complete.sql` - Full schema with all tables, functions, and optimizations for multi-guild support
- `schema_multi_guild.sql` - Additional multi-guild enhancements for extending the base schema
- `migrations/` - Directory containing database migrations for schema updates

The recommended approach is to use `schema_complete.sql` for fresh installations and the migration scripts for upgrading existing databases.

## V2 Database Service

As of the latest update, the bot uses the enhanced **DatabaseServiceV2** implementation, which offers:

- Fully asynchronous operations using asyncpg
- Better connection pooling and transaction management
- Comprehensive error handling
- Guild-specific data handling
- Auto-initialization of required data
- Optimized query performance

## Tables

The database consists of the following core tables:

- `users` - Global user information and statistics
- `guild_settings` - Server-specific configuration
- `guild_members` - Maps users to Discord servers with per-guild stats
- `user_quiz_sessions` - Records individual quiz attempts
- `guild_leaderboards` - Optimized rankings for fast access
- `user_achievements` - Tracks achievements earned by users
- `custom_quizzes` - Stores custom quizzes created by users
- `feature_flags` - Manages feature flag settings per guild/user

Advanced tables for extended functionality:
- `quiz_templates` - Templates for consistent quiz formats
- `daily_challenges` - Daily challenge quizzes
- `user_daily_challenges` - User attempts at daily challenges

## Setting Up PostgreSQL

### Prerequisites

- PostgreSQL 12 or later

### Installation

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

### Setting Up Remote Connections

If you plan to connect to your PostgreSQL server from a different machine (e.g., using pgAdmin on Windows to connect to a Linux PostgreSQL server), follow these steps:

1. **Configure PostgreSQL to listen on all interfaces**:
   ```bash
   sudo nano /etc/postgresql/[version]/main/postgresql.conf
   ```
   Find the line `#listen_addresses = 'localhost'` and change it to:
   ```
   listen_addresses = '*'
   ```
   Make sure to remove the comment indicator, #, to properly activate the listen addresses. This allows PostgreSQL to accept connections from any network interface.

2. **Configure PostgreSQL to allow remote connections**:
   ```bash
   sudo nano /etc/postgresql/[version]/main/pg_hba.conf
   ```
   Add this line to allow connections from any address:
   ```
   host    all    all    0.0.0.0/0    md5
   ```
   This enables password authentication for connections from any IP address.

3. **Restart PostgreSQL to apply changes**:
   ```bash
   sudo systemctl restart postgresql
   ```

4. **Configure firewall to allow PostgreSQL connections (default port 5432)**:
   ```bash
   sudo ufw allow 5432/tcp
   ```

5. **Verify configuration**:
   Ensure PostgreSQL is listening on all interfaces:
   ```bash
   sudo netstat -tuln | grep 5432
   ```
   You should see an entry with `0.0.0.0:5432` (listening on all IPv4 interfaces).

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

### Initializing the Schema

The recommended approach is to let the bot's DatabaseInitializer automatically initialize the schema on first run. However, you can also manually initialize it:

#### Using pgAdmin (Windows/GUI approach)

1. Open pgAdmin
2. Connect to your PostgreSQL server
3. Select your "quizbot" database
4. Click on the "Query Tool" button
5. Open the `schema_complete.sql` file
6. Click "Execute" to run the SQL script

#### Using Command Line (Windows/Linux)

```bash
# On Linux
sudo -u postgres psql quizbot < db/schema_complete.sql

# On Windows (from Command Prompt)
psql -U postgres -d quizbot -f db/schema_complete.sql
```

## Upgrading from V1 to V2

If you're upgrading from the original DatabaseService to DatabaseServiceV2, use the migration script:

```bash
# On Linux
sudo -u postgres psql quizbot < db/migrations/001_database_v2_migration.sql

# On Windows (from Command Prompt)
psql -U postgres -d quizbot -f db/migrations/001_database_v2_migration.sql
```

The migration script handles the following:
1. Schema updates to match V2 requirements
2. Data conversion for existing records
3. Creation of new tables and indexes
4. Setting up helper functions and triggers

## Environment Configuration

Configure the bot to use your PostgreSQL database by setting either of these approaches in your `.env` file:

### Option 1: Connection URL (Recommended)
```
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/quizbot
```

### Option 2: Individual connection parameters
```
POSTGRES_HOST=localhost  # Or your actual database host IP
POSTGRES_PORT=5432
POSTGRES_DB=quizbot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

## Maintenance

### Backing Up the Database

#### Using pg_dump (Command Line)

```bash
# On Linux
sudo -u postgres pg_dump quizbot > backup.sql

# On Windows (from Command Prompt)
pg_dump -U postgres quizbot > backup.sql
```

### Restoring from Backup

#### Using psql (Command Line)

```bash
# On Linux
sudo -u postgres psql quizbot < backup.sql

# On Windows (from Command Prompt)
psql -U postgres -d quizbot -f backup.sql
```

## Troubleshooting

### Connection Issues

If the bot has trouble connecting to the database, check:

1. PostgreSQL is running
   ```bash
   # On Linux
   sudo systemctl status postgresql
   
   # On Windows
   Check Services console for PostgreSQL service status
   ```

2. Your connection info is correct in the .env file
3. PostgreSQL is accepting connections:
   ```bash
   # Try connecting manually
   psql -U postgres -h localhost
   ```

4. Your firewall isn't blocking PostgreSQL (usually port 5432)

### Performance Issues

If you encounter performance issues:

1. Check that indexes are properly created (included in schema_complete.sql)
2. Monitor connection pool usage in the bot logs
3. Consider adjusting the connection pool size in configuration (min_size and max_size)
4. If you have a large dataset, consider running VACUUM ANALYZE periodically:
   ```sql
   VACUUM ANALYZE;
   ```

## Advanced Usage

### Running Database Diagnostics

The bot includes a database diagnostics command that provides insights into the database status:

```
!admin dbstats
```

This command shows:
- Connection pool status
- Table row counts
- Index statistics
- Recent query performance

### Database Migrations

For database migrations, we use the built-in migration system in DatabaseInitializer:

1. Create a new SQL file in the `migrations/` directory with a numeric prefix (e.g., `002_add_new_feature.sql`)
2. The bot will automatically detect and apply new migrations on startup
3. Each migration runs in a transaction and is marked as applied to prevent duplicate runs

To manually run migrations:

```bash
# On Linux
sudo -u postgres psql -d quizbot -f db/migrations/002_add_new_feature.sql

# On Windows
psql -U postgres -d quizbot -f db/migrations/002_add_new_feature.sql
```

### Connection Pooling Configuration

The DatabaseServiceV2 uses asyncpg's built-in connection pooling with these default settings:

```python
# Default pool configuration
self.pool = await asyncpg.create_pool(
    self.config.database_url,
    min_size=5,                        # Minimum connections to keep ready
    max_size=20,                       # Maximum connections allowed
    max_inactive_connection_lifetime=300, # Recycle inactive connections after 5 minutes
    command_timeout=60                 # Command timeout in seconds
)
```

Adjust these values in your configuration based on expected load:
- For low-traffic servers: min_size=2, max_size=10
- For high-traffic servers: min_size=10, max_size=30

## Database Schema Diagrams

### Core Tables Relationships

```
users
  ↑
  | 1:N
  ↓
guild_members ← → guild_settings
  ↑               (1:1)
  | 1:N
  ↓
user_quiz_sessions
```

### Performance Optimization

The V2 schema includes:
- Materialized leaderboard tables for fast lookups
- JSONB columns with GIN indexes for flexible data storage
- Computed columns for frequently needed values
- Prepared functions for common operations
- Transaction management for all multi-step operations

## Example Queries

The `schema_complete.sql` file includes views and example queries for common operations. Here are some of the most useful:

### Get Top Performers in a Guild

```sql
SELECT *
FROM guild_top_users
WHERE guild_id = 123456789
LIMIT 10;
```

### Get User's Performance Across All Guilds

```sql
SELECT * FROM user_global_stats
WHERE user_id = 987654321;
```

### Get Recent Quiz Activity for a Guild

```sql
SELECT 
    u.username,
    s.topic,
    s.difficulty,
    s.correct_answers,
    s.wrong_answers,
    s.points_earned,
    s.accuracy_percentage,
    s.completed_at
FROM user_quiz_sessions s
JOIN users u ON s.user_id = u.user_id
WHERE s.guild_id = 123456789
ORDER BY s.completed_at DESC
LIMIT 20;
```