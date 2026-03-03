-- Migration 002: Add 11 new leagues to reach 33 total + Safe Bets schema
-- Date: 2026-03-03
-- Description: Expands league coverage and adds league_profiles table for DNA categorization

-- =============================================================================
-- 1. League Registry table (new) — canonical list of all 33 monitored leagues
-- =============================================================================
CREATE TABLE IF NOT EXISTS league_registry (
    id SERIAL PRIMARY KEY,
    league_id TEXT UNIQUE NOT NULL,        -- Internal ID (e.g. "j-league")
    country TEXT NOT NULL,
    name TEXT NOT NULL,
    footystats_id TEXT NOT NULL,           -- FootyStats API league identifier
    alt_names TEXT[],                      -- Alternative names for API matching
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert existing 22 leagues
INSERT INTO league_registry (league_id, country, name, footystats_id) VALUES
    ('premier-league', 'England', 'Premier League', 'premier-league'),
    ('championship', 'England', 'Championship', 'championship'),
    ('league-one', 'England', 'League One', 'league-one'),
    ('league-two', 'England', 'League Two', 'league-two'),
    ('la-liga', 'Spain', 'La Liga', 'la-liga'),
    ('segunda-division', 'Spain', 'Segunda División', 'segunda-division'),
    ('serie-a', 'Italy', 'Serie A', 'serie-a'),
    ('serie-b', 'Italy', 'Serie B', 'serie-b'),
    ('bundesliga', 'Germany', 'Bundesliga', 'bundesliga'),
    ('2-bundesliga', 'Germany', '2. Bundesliga', '2-bundesliga'),
    ('ligue-1', 'France', 'Ligue 1', 'ligue-1'),
    ('ligue-2', 'France', 'Ligue 2', 'ligue-2'),
    ('brasileirao-serie-a', 'Brazil', 'Serie A', 'brasileirao-serie-a'),
    ('brasileirao-serie-b', 'Brazil', 'Serie B', 'brasileirao-serie-b'),
    ('eredivisie', 'Netherlands', 'Eredivisie', 'eredivisie'),
    ('primeira-liga', 'Portugal', 'Primeira Liga', 'primeira-liga'),
    ('super-lig', 'Turkey', 'Süper Lig', 'super-lig'),
    ('pro-league', 'Belgium', 'Pro League', 'pro-league'),
    ('premiership', 'Scotland', 'Premiership', 'premiership'),
    ('austrian-bundesliga', 'Austria', 'Bundesliga', 'austrian-bundesliga'),
    ('superliga', 'Denmark', 'Superliga', 'superliga'),
    ('super-league', 'Switzerland', 'Super League', 'super-league'),
    ('primera-division', 'Argentina', 'Primera División', 'primera-division'),
    ('a-league', 'Australia', 'A-League', 'a-league'),
    ('professional-league', 'Saudi Arabia', 'Professional League', 'professional-league')
ON CONFLICT (league_id) DO NOTHING;

-- Insert 11 NEW leagues (expansion to 33 total)
INSERT INTO league_registry (league_id, country, name, footystats_id, alt_names) VALUES
    ('j-league', 'Japan', 'J-League', 'j1-league', ARRAY['j1-league', 'meiji yasuda j1 league']),
    ('k-league', 'South Korea', 'K-League', 'k-league-1', ARRAY['k league 1', 'hana 1 bank k league 1']),
    ('eliteserien', 'Norway', 'Eliteserien', 'eliteserien', ARRAY['toppserien', 'norwegian premier league']),
    ('allsvenskan', 'Sweden', 'Allsvenskan', 'allsvenskan', ARRAY['swedish premier league']),
    ('uae-pro-league', 'UAE', 'UAE Pro League', 'uae-pro-league', ARRAY['arabian gulf league', 'adnoc pro league']),
    ('eerste-divisie', 'Netherlands', 'Eerste Divisie', 'eerste-divisie', ARRAY['dutch second division', 'keuken kampioen divisie']),
    ('super-league-greece', 'Greece', 'Super League', 'super-league-greece', ARRAY['super league 1', 'greek super league']),
    ('mls', 'USA', 'MLS', 'mls', ARRAY['major league soccer']),
    ('czech-first-league', 'Czech Republic', 'Czech First League', 'czech-first-league', ARRAY['chance liga', 'fortuna liga', 'first league']),
    ('colombian-primera-a', 'Colombia', 'Campeonato Colombiano', 'colombian-primera-a', ARRAY['liga betplay', 'primera a', 'categoría primera a'])
ON CONFLICT (league_id) DO NOTHING;


-- =============================================================================
-- 2. League Profiles table — "DNA da Liga" (Layer 1 categorization)
-- =============================================================================
CREATE TABLE IF NOT EXISTS league_profiles (
    league_id TEXT PRIMARY KEY REFERENCES league_registry(league_id),
    -- Season averages (populated from FootyStats API)
    season_avg_goals REAL,                -- seasonAVG_overall
    season_btts_percentage REAL,          -- seasonBTTSPercentage
    season_corners_avg REAL,              -- cornersAVG_overall
    season_cards_avg REAL,                -- cardsAVG_overall
    -- DNA classification (computed from averages)
    dna_category TEXT CHECK (dna_category IN ('DEFENSIVE', 'BALANCED', 'OFFENSIVE', 'AGGRESSIVE')),
    -- Enabled markets based on DNA
    markets_enabled TEXT[],               -- e.g. {'UNDER_GOALS', 'BTTS_NO', 'OVER_CORNERS', ...}
    -- Feature flags from API
    goal_timing_disabled BOOLEAN DEFAULT FALSE,
    corners_disabled BOOLEAN DEFAULT FALSE,
    cards_disabled BOOLEAN DEFAULT FALSE,
    -- Metadata
    last_synced_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);


-- =============================================================================
-- 3. Safe Bets Results table — stores generated safe bet tags per match
-- =============================================================================
CREATE TABLE IF NOT EXISTS safe_bets (
    id SERIAL PRIMARY KEY,
    match_id TEXT NOT NULL,
    league_id TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    match_date TIMESTAMP,
    -- Safe bet tags (array of validated tags)
    tags TEXT[] NOT NULL DEFAULT '{}',     -- e.g. {'UNDER_35', 'BTTS_NO'}
    -- Risk assessment
    risk_level TEXT CHECK (risk_level IN ('SAFE', 'MODERATE', 'NO_BET')),
    risk_score REAL,                       -- 0.0 to 1.0
    -- Layer details (JSON for flexibility)
    layer1_dna JSONB,                      -- League DNA evaluation
    layer2_risk JSONB,                     -- Risk semaphore evaluation
    layer3_strategies JSONB,               -- Strategy evaluations (A/B/C/D)
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    UNIQUE(match_id, league_id)
);

-- Index for querying safe bets by date and league
CREATE INDEX IF NOT EXISTS idx_safe_bets_date ON safe_bets(match_date);
CREATE INDEX IF NOT EXISTS idx_safe_bets_league ON safe_bets(league_id);
CREATE INDEX IF NOT EXISTS idx_safe_bets_risk ON safe_bets(risk_level);
