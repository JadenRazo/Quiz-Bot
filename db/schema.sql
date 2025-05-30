-- Educational Discord Quiz Bot Database Schema
-- PostgreSQL Version - Clean and Consolidated
-- This is the PRIMARY schema file for the bot

-- Drop tables in reverse dependency order (for clean reinstalls)
-- Uncomment these lines if you need to completely recreate the database
/*
DROP TABLE IF EXISTS version_changelog CASCADE;
DROP TABLE IF EXISTS bot_versions CASCADE;
DROP TABLE IF EXISTS guild_quiz_sessions CASCADE;
DROP TABLE IF EXISTS guild_user_preferences CASCADE;
DROP TABLE IF EXISTS guild_leaderboards CASCADE;
DROP TABLE IF EXISTS feature_flags CASCADE;
DROP TABLE IF EXISTS custom_quizzes CASCADE;
DROP TABLE IF EXISTS user_achievements CASCADE;
DROP TABLE IF EXISTS saved_configs CASCADE;
DROP TABLE IF EXISTS achievements CASCADE;
DROP TABLE IF EXISTS user_quiz_sessions CASCADE;
DROP TABLE IF EXISTS quizzes CASCADE;
DROP TABLE IF EXISTS query_cache CASCADE;
DROP TABLE IF EXISTS guild_onboarding_log CASCADE;
DROP TABLE IF EXISTS guild_settings CASCADE;
DROP TABLE IF EXISTS guild_members CASCADE;
DROP TABLE IF EXISTS users CASCADE;
*/

-- Core user table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT NOT NULL,
    discriminator VARCHAR(4),
    display_name VARCHAR(100),
    avatar_url TEXT,
    preferences JSONB DEFAULT '{}',
    quizzes_taken INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    wrong_answers INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_banned BOOLEAN DEFAULT FALSE,
    ban_reason TEXT
);

-- Guild settings for server-specific configuration
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    guild_name VARCHAR(100),
    settings JSONB DEFAULT '{}',
    
    -- Channel configuration
    quiz_channel_id BIGINT,
    trivia_channel_id BIGINT,
    announcement_channel_id BIGINT,
    
    -- Role configuration
    admin_role_id BIGINT,
    moderator_role_id BIGINT,
    quiz_role_id BIGINT,
    
    -- Default quiz settings
    default_quiz_difficulty VARCHAR(20) DEFAULT 'medium',
    default_question_count INTEGER DEFAULT 5,
    default_quiz_timeout INTEGER DEFAULT 30,
    
    -- Feature toggles
    enable_trivia BOOLEAN DEFAULT TRUE,
    enable_custom_quizzes BOOLEAN DEFAULT TRUE,
    enable_leaderboards BOOLEAN DEFAULT TRUE,
    enable_achievements BOOLEAN DEFAULT TRUE,
    require_role_for_quiz BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Guild membership tracking with per-guild stats
CREATE TABLE IF NOT EXISTS guild_members (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    
    -- Per-guild stats
    guild_xp INTEGER DEFAULT 0,
    guild_level INTEGER DEFAULT 1,
    quiz_count INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    wrong_answers INTEGER DEFAULT 0,
    total_points INTEGER DEFAULT 0,
    
    -- Streaks
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    last_quiz_date DATE,
    
    -- Guild-specific preferences
    preferences JSONB DEFAULT '{}',
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (guild_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Quiz session records
CREATE TABLE IF NOT EXISTS quizzes (
    quiz_id SERIAL PRIMARY KEY,
    host_id BIGINT REFERENCES users(user_id),
    guild_id BIGINT,
    topic TEXT,
    category TEXT,
    difficulty TEXT,
    question_count INTEGER,
    template TEXT,
    provider TEXT,
    is_private BOOLEAN DEFAULT FALSE,
    is_group BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User quiz sessions for detailed tracking
CREATE TABLE IF NOT EXISTS user_quiz_sessions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    guild_id BIGINT,
    quiz_id VARCHAR(36),
    quiz_type VARCHAR(20) DEFAULT 'standard',
    topic VARCHAR(255),
    difficulty VARCHAR(50),
    category VARCHAR(100),
    
    -- Quiz results
    total_questions INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    wrong_answers INTEGER DEFAULT 0,
    skipped_answers INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    
    -- Performance metrics
    points_earned INTEGER DEFAULT 0,
    xp_earned INTEGER DEFAULT 0,
    time_taken_seconds INTEGER,
    accuracy_percentage DECIMAL(5,2),
    
    -- Status
    is_completed BOOLEAN DEFAULT FALSE,
    is_perfect BOOLEAN DEFAULT FALSE,
    session_data JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Guild leaderboards for optimized rankings
CREATE TABLE IF NOT EXISTS guild_leaderboards (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    
    -- Aggregate stats
    total_points INTEGER DEFAULT 0,
    total_quizzes INTEGER DEFAULT 0,
    total_correct INTEGER DEFAULT 0,
    total_wrong INTEGER DEFAULT 0,
    average_accuracy DECIMAL(5,2) DEFAULT 0.00,
    best_quiz_score INTEGER DEFAULT 0,
    
    -- Time-based stats
    points_this_week INTEGER DEFAULT 0,
    points_this_month INTEGER DEFAULT 0,
    
    -- Rankings
    guild_rank INTEGER,
    previous_rank INTEGER,
    
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (guild_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- User achievements
CREATE TABLE IF NOT EXISTS user_achievements (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    guild_id BIGINT,
    achievement VARCHAR(50) NOT NULL,
    achievement_name VARCHAR(100),
    achievement_tier VARCHAR(20) DEFAULT 'bronze',
    
    -- Progress tracking
    current_progress INTEGER DEFAULT 0,
    target_progress INTEGER DEFAULT 1,
    
    -- Status
    is_completed BOOLEAN DEFAULT TRUE,
    earned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Rewards
    xp_reward INTEGER DEFAULT 50,
    points_reward INTEGER DEFAULT 25,
    
    UNIQUE(user_id, guild_id, achievement)
);

-- Legacy achievements table (for compatibility)
CREATE TABLE IF NOT EXISTS achievements (
    achievement_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    earned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Custom quizzes created by users
CREATE TABLE IF NOT EXISTS custom_quizzes (
    id SERIAL PRIMARY KEY,
    creator_id BIGINT NOT NULL REFERENCES users(user_id),
    guild_id BIGINT,
    name VARCHAR(100) NOT NULL,
    topic VARCHAR(100) NOT NULL,
    category VARCHAR(50) DEFAULT 'general',
    difficulty VARCHAR(20) DEFAULT 'medium',
    description TEXT,
    questions JSONB NOT NULL DEFAULT '[]',
    
    -- Access control
    is_public BOOLEAN DEFAULT FALSE,
    is_approved BOOLEAN DEFAULT FALSE,
    
    -- Usage stats
    play_count INTEGER DEFAULT 0,
    total_rating INTEGER DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Saved quiz configurations
CREATE TABLE IF NOT EXISTS saved_configs (
    config_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    name TEXT NOT NULL,
    topic TEXT,
    category TEXT,
    difficulty TEXT,
    question_count INTEGER,
    template TEXT,
    provider TEXT
);

-- Guild-specific user preferences
CREATE TABLE IF NOT EXISTS guild_user_preferences (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (guild_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Active guild quiz sessions
CREATE TABLE IF NOT EXISTS guild_quiz_sessions (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    host_id BIGINT NOT NULL,
    topic VARCHAR(100) NOT NULL,
    question_count INTEGER NOT NULL,
    participant_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    quiz_type VARCHAR(20) DEFAULT 'trivia',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(guild_id, channel_id)
);

-- Feature flags for controlled rollouts
CREATE TABLE IF NOT EXISTS feature_flags (
    id SERIAL PRIMARY KEY,
    feature_name VARCHAR(50) NOT NULL,
    guild_id BIGINT,
    user_id BIGINT,
    is_enabled BOOLEAN DEFAULT TRUE,
    rollout_percentage INTEGER DEFAULT 100,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (feature_name, guild_id, user_id)
);

-- Query cache for performance
CREATE TABLE IF NOT EXISTS query_cache (
    cache_key TEXT PRIMARY KEY,
    data TEXT,
    expires_at BIGINT
);

-- Guild onboarding log
CREATE TABLE IF NOT EXISTS guild_onboarding_log (
    guild_id BIGINT PRIMARY KEY,
    channel_id BIGINT,
    onboarded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Version management tables
CREATE TABLE IF NOT EXISTS bot_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    release_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_current BOOLEAN DEFAULT FALSE,
    author_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS version_changelog (
    id SERIAL PRIMARY KEY,
    version_id INTEGER REFERENCES bot_versions(id),
    change_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance optimization
-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_points ON users(points DESC);
CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active DESC);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_preferences ON users USING gin(preferences);

-- Guild settings indexes
CREATE INDEX IF NOT EXISTS idx_guild_settings_settings ON guild_settings USING gin(settings);

-- Guild members indexes
CREATE INDEX IF NOT EXISTS idx_guild_members_guild_id ON guild_members(guild_id);
CREATE INDEX IF NOT EXISTS idx_guild_members_user_id ON guild_members(user_id);
CREATE INDEX IF NOT EXISTS idx_guild_members_guild_xp ON guild_members(guild_id, guild_xp DESC);

-- Quiz indexes
CREATE INDEX IF NOT EXISTS idx_quizzes_timestamp ON quizzes(timestamp);
CREATE INDEX IF NOT EXISTS idx_quizzes_host_id ON quizzes(host_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_guild_id ON quizzes(guild_id);

-- User quiz sessions indexes
CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_user_id ON user_quiz_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_guild_id ON user_quiz_sessions(guild_id);
CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_user_guild ON user_quiz_sessions(user_id, guild_id);
CREATE INDEX IF NOT EXISTS idx_user_quiz_sessions_created_at ON user_quiz_sessions(created_at DESC);

-- Guild leaderboards indexes
CREATE INDEX IF NOT EXISTS idx_guild_leaderboards_guild_points ON guild_leaderboards(guild_id, total_points DESC);
CREATE INDEX IF NOT EXISTS idx_guild_leaderboards_guild_rank ON guild_leaderboards(guild_id, guild_rank);

-- User achievements indexes
CREATE INDEX IF NOT EXISTS idx_user_achievements_user_guild ON user_achievements(user_id, guild_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_completed ON user_achievements(is_completed) WHERE is_completed = TRUE;

-- Custom quizzes indexes
CREATE INDEX IF NOT EXISTS idx_custom_quizzes_creator_id ON custom_quizzes(creator_id);
CREATE INDEX IF NOT EXISTS idx_custom_quizzes_guild_id ON custom_quizzes(guild_id);
CREATE INDEX IF NOT EXISTS idx_custom_quizzes_is_public ON custom_quizzes(is_public) WHERE is_public = TRUE;
CREATE INDEX IF NOT EXISTS idx_custom_quizzes_questions ON custom_quizzes USING gin(questions);

-- Feature flags indexes
CREATE INDEX IF NOT EXISTS idx_feature_flags_feature_name ON feature_flags(feature_name);
CREATE INDEX IF NOT EXISTS idx_feature_flags_guild_id ON feature_flags(guild_id);

-- Version indexes
CREATE INDEX IF NOT EXISTS idx_bot_versions_current ON bot_versions(is_current);
CREATE INDEX IF NOT EXISTS idx_bot_versions_version ON bot_versions(version);
CREATE INDEX IF NOT EXISTS idx_version_changelog_version_id ON version_changelog(version_id);

-- Trigger to ensure only one current version
CREATE OR REPLACE FUNCTION ensure_single_current_version()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = TRUE THEN
        UPDATE bot_versions SET is_current = FALSE WHERE id != NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ensure_single_current_trigger ON bot_versions;
CREATE TRIGGER ensure_single_current_trigger
BEFORE INSERT OR UPDATE ON bot_versions
FOR EACH ROW
EXECUTE FUNCTION ensure_single_current_version();

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update timestamp triggers
DROP TRIGGER IF EXISTS update_guild_settings_timestamp ON guild_settings;
CREATE TRIGGER update_guild_settings_timestamp
    BEFORE UPDATE ON guild_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS update_custom_quizzes_timestamp ON custom_quizzes;
CREATE TRIGGER update_custom_quizzes_timestamp
    BEFORE UPDATE ON custom_quizzes
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS update_feature_flags_timestamp ON feature_flags;
CREATE TRIGGER update_feature_flags_timestamp
    BEFORE UPDATE ON feature_flags
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

-- Helper functions for common operations
CREATE OR REPLACE FUNCTION calculate_level(xp INTEGER) RETURNS INTEGER AS $$
BEGIN
    -- Simple level calculation: each level requires more XP
    RETURN FLOOR(SQRT(xp / 50)) + 1;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_or_create_user(
    p_user_id BIGINT,
    p_username VARCHAR(100),
    p_discriminator VARCHAR(4) DEFAULT NULL,
    p_display_name VARCHAR(100) DEFAULT NULL
) RETURNS BIGINT AS $$
BEGIN
    INSERT INTO users (user_id, username, discriminator, display_name)
    VALUES (p_user_id, p_username, p_discriminator, p_display_name)
    ON CONFLICT (user_id) DO UPDATE
    SET username = EXCLUDED.username,
        discriminator = EXCLUDED.discriminator,
        display_name = COALESCE(EXCLUDED.display_name, users.display_name),
        last_active = NOW();
    
    RETURN p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_guild_leaderboard(
    p_guild_id BIGINT,
    p_user_id BIGINT,
    p_points INTEGER,
    p_correct INTEGER,
    p_wrong INTEGER
) RETURNS VOID AS $$
BEGIN
    INSERT INTO guild_leaderboards (
        guild_id, user_id, total_points, total_quizzes, 
        total_correct, total_wrong
    ) VALUES (
        p_guild_id, p_user_id, p_points, 1, p_correct, p_wrong
    )
    ON CONFLICT (guild_id, user_id) DO UPDATE SET
        total_points = guild_leaderboards.total_points + p_points,
        total_quizzes = guild_leaderboards.total_quizzes + 1,
        total_correct = guild_leaderboards.total_correct + p_correct,
        total_wrong = guild_leaderboards.total_wrong + p_wrong,
        average_accuracy = CASE 
            WHEN (guild_leaderboards.total_correct + p_correct + guild_leaderboards.total_wrong + p_wrong) > 0 
            THEN ((guild_leaderboards.total_correct + p_correct)::DECIMAL / 
                  (guild_leaderboards.total_correct + p_correct + guild_leaderboards.total_wrong + p_wrong) * 100)
            ELSE 0 
        END,
        last_updated = NOW();
        
    -- Update weekly/monthly points
    UPDATE guild_leaderboards 
    SET points_this_week = points_this_week + p_points
    WHERE guild_id = p_guild_id 
      AND user_id = p_user_id
      AND last_updated > NOW() - INTERVAL '7 days';
      
    UPDATE guild_leaderboards 
    SET points_this_month = points_this_month + p_points
    WHERE guild_id = p_guild_id 
      AND user_id = p_user_id
      AND last_updated > NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Initial data
INSERT INTO bot_versions (version, description, is_current)
VALUES ('1.0.0', 'Initial release of Educational Quiz Bot', TRUE)
ON CONFLICT (version) DO NOTHING;