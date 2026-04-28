-- Migration 003: Timeline scoring tables + founded_at column
-- Requires: 002_trustweb_score.sql

-- Add founded_at to firm table
ALTER TABLE firm ADD COLUMN founded_at DATETIME;
UPDATE firm SET founded_at = created_at WHERE founded_at IS NULL;

-- EEM timeline scores (8 rows per scoring run)
CREATE TABLE IF NOT EXISTS firm_score_timeline (
    id              SERIAL PRIMARY KEY,
    firm_id         INT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL,
    bucket_index    SMALLINT NOT NULL,
    bucket_start    TIMESTAMP NOT NULL,
    bucket_end      TIMESTAMP NOT NULL,
    score           INT NOT NULL,
    risk            VARCHAR(10) NOT NULL,
    event_count     INT NOT NULL DEFAULT 0,
    keywords        TEXT NOT NULL DEFAULT '[]',
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, bucket_index)
);

CREATE INDEX IF NOT EXISTS idx_fst_firm_id ON firm_score_timeline(firm_id);
CREATE INDEX IF NOT EXISTS idx_fst_run_id ON firm_score_timeline(run_id);

-- TrustWeb timeline scores (8 rows per scoring run)
CREATE TABLE IF NOT EXISTS trustweb_score_timeline (
    id              SERIAL PRIMARY KEY,
    firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL,
    bucket_index    SMALLINT NOT NULL,
    bucket_start    TIMESTAMP NOT NULL,
    bucket_end      TIMESTAMP NOT NULL,
    score           DECIMAL(4,3) NOT NULL CHECK (score BETWEEN 0 AND 1),
    node_count      INT,
    edge_count      INT,
    max_depth_used  INT,
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, bucket_index)
);

CREATE INDEX IF NOT EXISTS idx_twst_firm_id ON trustweb_score_timeline(firm_id);
CREATE INDEX IF NOT EXISTS idx_twst_run_id ON trustweb_score_timeline(run_id);

-- One explanation per TrustWeb timeline run
CREATE TABLE IF NOT EXISTS trustweb_run (
    run_id          UUID PRIMARY KEY,
    firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
    explanation     TEXT,
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
