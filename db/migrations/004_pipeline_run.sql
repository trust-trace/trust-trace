-- Migration 004: Pipeline orchestration tables
-- Requires: 003_timeline_scoring.sql

-- Tracks a full E2E pipeline run (scraping → scoring → merge)
CREATE TABLE IF NOT EXISTS pipeline_run (
    id              UUID PRIMARY KEY,
    query           TEXT NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'created',
    phase           VARCHAR(30) NOT NULL DEFAULT 'created',
    article_target  INT NOT NULL DEFAULT 30,
    articles_scraped  INT NOT NULL DEFAULT 0,
    articles_processed INT NOT NULL DEFAULT 0,
    firm_ids        TEXT NOT NULL DEFAULT '[]',
    final_scores    TEXT NOT NULL DEFAULT '{}',
    error           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_status ON pipeline_run(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_created ON pipeline_run(created_at);

-- Merged final timeline scores per bucket per firm per run
CREATE TABLE IF NOT EXISTS final_score_timeline (
    id              SERIAL PRIMARY KEY,
    firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    bucket_index    SMALLINT NOT NULL,
    bucket_start    TIMESTAMP NOT NULL,
    bucket_end      TIMESTAMP NOT NULL,
    eem_score       DECIMAL(5,2),
    trustweb_score  DECIMAL(4,3),
    nsa_score       DECIMAL(4,3),
    final_score     DECIMAL(4,3) NOT NULL,
    risk_level      VARCHAR(10) NOT NULL,
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, firm_id, bucket_index)
);

CREATE INDEX IF NOT EXISTS idx_fstl_firm_id ON final_score_timeline(firm_id);
CREATE INDEX IF NOT EXISTS idx_fstl_run_id ON final_score_timeline(run_id);
