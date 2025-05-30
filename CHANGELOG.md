# Changelog

All notable changes to the Educational Quiz Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added

### Fixed

### Changed


## [1.1.0] - 2025-05-25
### Added
- Comprehensive CLAUDE.md documentation for services directory
- Enhanced error handling in database operations
- Content validation utilities to prevent field overflow
- Batch operations for efficient database updates

### Fixed
- Database connection issues with proper IP address usage
- psycopg2 parameter repetition in ON CONFLICT clauses
- Option validation in message service to detect placeholders

### Changed
- Updated services documentation with implementation details
- Improved error logging throughout the codebase
## [1.2.0] - 2025-05-25
### Added
- Version management system with changelog tracking
- Owner-only version commands (/version change, /version changelog)
- Database-backed version persistence
- Semantic versioning support

### Fixed
- Group quiz session cleanup
- Memory leaks in quiz session management

### Improved
- Performance optimizations for database queries
- Enhanced error messages for better debugging

## [1.1.0] - 2025-05-20
### Added
- Multi-guild support with proper data isolation
- Group quiz mode with real-time scoring
- Single answer mode for competitive play
- Achievement system with visual icons
- XP and leveling system
- Visual progress bars using Discord emojis

### Fixed
- Leaderboard display issues
- Guild member tracking problems
- Answer validation in quiz sessions

### Improved
- Database schema with composite keys
- Query performance with proper indexing
- User experience with autocomplete

## [1.0.0] - 2025-05-15
### Added
- Initial release of Educational Quiz Bot
- AI-powered quiz generation (OpenAI, Anthropic, Google Gemini)
- Multiple question types (multiple choice, true/false, short answer)
- User statistics tracking
- Basic leaderboard functionality
- Discord slash command support
- PostgreSQL database integration

### Security
- Environment-based configuration
- Parameterized database queries
- Input validation and sanitization

---

## Version Guidelines

When updating this changelog:

1. **Unreleased Section**: Add all changes here during development
2. **Version Release**: Move unreleased items to a new version section
3. **Categories**: Use Added, Changed, Deprecated, Removed, Fixed, Security
4. **Clear Descriptions**: Write user-friendly, clear change descriptions
5. **Link References**: Link to issues, PRs, or commits when relevant

## Version Command Integration

This changelog works with the bot's version system:
- Use `/version change` to create a new version in the database
- Use `/version changelog` to add specific entries
- The bot reads from the database, not this file
- This file serves as a backup and reference

## Example Version Update Process

```bash
# 1. Update this CHANGELOG.md file
# 2. Create version in bot (as bot owner)
/version change 1.3.0 "Performance improvements and bug fixes"

# 3. Add changelog entries
/version changelog 1.3.0 feature "Added caching system for quiz questions"
/version changelog 1.3.0 fix "Fixed memory leak in question generator"
/version changelog 1.3.0 improvement "Reduced quiz generation time by 50%"

# 4. Set as current version
/version set 1.3.0
```