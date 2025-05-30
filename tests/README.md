# Test Suite for Educational Quiz Bot

This directory contains tests to help verify your bot setup and ensure everything is working correctly.

## Available Tests

### Database Setup Test (`test_database_setup.py`)
Comprehensive test that verifies your database configuration:
- Tests database connectivity
- Verifies all required tables exist
- Tests basic CRUD operations
- Validates async operations work correctly
- Checks connection pooling behavior

Run it with:
```bash
python tests/test_database_setup.py
```

### Multi-Guild Test (`test_multi_guild_quizzes.py`)
Tests the bot's ability to handle multiple Discord servers:
- Verifies guild isolation for quiz sessions
- Tests concurrent quizzes across guilds
- Validates data separation between servers

Run it with:
```bash
python tests/run_multi_guild_tests.py
```

## Test Runner (`run_tests.py`)

A convenience script to run all tests or specific test suites:

```bash
# Run all tests
python tests/run_tests.py

# Run only database tests
python tests/run_tests.py database

# Run only multi-guild tests
python tests/run_tests.py multi-guild
```

## When to Run Tests

1. **After Initial Setup**: Run all tests to verify your environment is configured correctly
2. **After Database Changes**: Run database tests to ensure schema is intact
3. **Before Deployment**: Run all tests to catch any configuration issues
4. **After Major Updates**: Verify everything still works after code changes

## Troubleshooting

### Database Test Failures
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check your `.env` file has correct database credentials
- Ensure the database exists: `psql -U postgres -c "\l"`
- Check firewall isn't blocking port 5432

### Multi-Guild Test Failures
- Ensure your bot token is valid
- Check the bot has proper permissions in test guilds
- Verify your internet connection is stable

## Adding New Tests

When adding new tests:
1. Create test files with descriptive names (e.g., `test_feature_name.py`)
2. Include clear documentation in the test file
3. Update this README with test description
4. Add the test to `run_tests.py` if it should be part of the standard test suite

## Note on Test Data

Tests may create temporary data in your database. The test suite attempts to clean up after itself, but you may see test users or sessions in your database. These can be safely ignored or manually removed if desired.