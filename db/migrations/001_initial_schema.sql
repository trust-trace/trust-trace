-- Migration: 001_initial_schema.sql
-- Description: Create initial schema and tables
-- Requires: MySQL 8.0.16+

-- ─────────────────────────────────────────
-- Core entity
-- ─────────────────────────────────────────

CREATE TABLE firm (
    id          BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    full_name   TEXT            NOT NULL,
    nip         VARCHAR(13)     UNIQUE,
    regon       VARCHAR(14)     UNIQUE,
    krs         VARCHAR(10)     UNIQUE,
    country     VARCHAR(3)      NOT NULL DEFAULT 'PL',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE firm_alias (
    id          BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    firm_id     BIGINT          NOT NULL,
    alias       TEXT            NOT NULL,
    alias_type  VARCHAR(50)     NOT NULL,
    CONSTRAINT fk_firm_alias_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Events & Sources
-- ─────────────────────────────────────────

CREATE TABLE event (
    unique_id    CHAR(36)       NOT NULL DEFAULT (UUID()) PRIMARY KEY,
    firm_id      BIGINT         NOT NULL,
    title        TEXT           NOT NULL,
    event_type   VARCHAR(100)   NOT NULL,
    risk_level   TINYINT        NOT NULL CHECK (risk_level BETWEEN 1 AND 10),
    occurred_at  DATETIME       NOT NULL,
    created_at   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_event_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE source (
    id           BIGINT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    event_id     CHAR(36)       NOT NULL,
    url          TEXT           NOT NULL,
    title        TEXT,
    content      TEXT,
    language     VARCHAR(10),
    source_type  VARCHAR(50)    NOT NULL,
    published_at DATETIME,
    created_at   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    credibility  DECIMAL(3,2)   CHECK (credibility BETWEEN 0 AND 1),
    CONSTRAINT fk_source_event FOREIGN KEY (event_id) REFERENCES event(unique_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Reputation
-- ─────────────────────────────────────────

CREATE TABLE reputation_score (
    id               BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    firm_id          BIGINT       NOT NULL,
    score            DECIMAL(6,2) NOT NULL,
    delta            DECIMAL(6,2),
    trigger_event_id CHAR(36),
    calculated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reputation_firm  FOREIGN KEY (firm_id)          REFERENCES firm(id)          ON DELETE CASCADE,
    CONSTRAINT fk_reputation_event FOREIGN KEY (trigger_event_id) REFERENCES event(unique_id)  ON DELETE SET NULL
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Sentiment & Keywords
-- ─────────────────────────────────────────

CREATE TABLE sentiment (
    id             BIGINT        NOT NULL AUTO_INCREMENT PRIMARY KEY,
    event_id       CHAR(36)      NOT NULL,
    firm_id        BIGINT        NOT NULL,
    score          DECIMAL(4,3)  NOT NULL CHECK (score BETWEEN -1 AND 1),
    sentiment_type VARCHAR(50)   NOT NULL,
    impact_weight  DECIMAL(4,3)  CHECK (impact_weight BETWEEN 0 AND 1),
    analyzed_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sentiment_event FOREIGN KEY (event_id) REFERENCES event(unique_id) ON DELETE CASCADE,
    CONSTRAINT fk_sentiment_firm  FOREIGN KEY (firm_id)  REFERENCES firm(id)         ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE risk_keywords (
    id          BIGINT        NOT NULL AUTO_INCREMENT PRIMARY KEY,
    keyword     VARCHAR(255)  NOT NULL UNIQUE,
    category    VARCHAR(100)  NOT NULL,
    base_weight DECIMAL(4,3)  NOT NULL CHECK (base_weight BETWEEN 0 AND 1)
) ENGINE=InnoDB;

CREATE TABLE sentiment_keywords (
    id           BIGINT        NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sentiment_id BIGINT        NOT NULL,
    keywords_id  BIGINT        NOT NULL,
    score        DECIMAL(4,3)  CHECK (score BETWEEN -1 AND 1),
    occurrences  INT           NOT NULL DEFAULT 1 CHECK (occurrences > 0),
    UNIQUE KEY uq_sentiment_keyword (sentiment_id, keywords_id),
    CONSTRAINT fk_sk_sentiment FOREIGN KEY (sentiment_id) REFERENCES sentiment(id)     ON DELETE CASCADE,
    CONSTRAINT fk_sk_keyword   FOREIGN KEY (keywords_id)  REFERENCES risk_keywords(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────

CREATE INDEX idx_firm_alias_firm_id              ON firm_alias(firm_id);

CREATE INDEX idx_event_firm_id                   ON event(firm_id);
CREATE INDEX idx_event_occurred_at               ON event(occurred_at);
CREATE INDEX idx_event_type                      ON event(event_type);

CREATE INDEX idx_source_event_id                 ON source(event_id);

CREATE INDEX idx_reputation_score_firm_id        ON reputation_score(firm_id);
CREATE INDEX idx_reputation_score_calculated_at  ON reputation_score(calculated_at);
CREATE INDEX idx_reputation_score_trigger_event  ON reputation_score(trigger_event_id);

CREATE INDEX idx_sentiment_event_id              ON sentiment(event_id);
CREATE INDEX idx_sentiment_firm_id               ON sentiment(firm_id);

CREATE INDEX idx_sentiment_keywords_sentiment_id ON sentiment_keywords(sentiment_id);
CREATE INDEX idx_sentiment_keywords_keywords_id  ON sentiment_keywords(keywords_id);

CREATE INDEX idx_risk_keywords_category          ON risk_keywords(category);
