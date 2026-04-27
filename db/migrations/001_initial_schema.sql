-- Migration: 001_initial_schema.sql
-- Description: Full initial schema (squashed from 001 + 002_tarkov_schema)
-- Requires: MySQL 8.0.16+

-- ─────────────────────────────────────────
-- Core entities
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
    confidence  DECIMAL(3,2)    CHECK (confidence BETWEEN 0 AND 1),
    is_primary  BOOLEAN         DEFAULT FALSE,
    CONSTRAINT fk_firm_alias_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Events & Sources
-- ─────────────────────────────────────────

-- event_category is a tagged union discriminator:
--   classical → sentiment/risk events (links to sentiment table)
--   people    → person extraction events (links to person_event table)
--   connection → relationship events (links to connection_entity table)
CREATE TABLE event (
    unique_id               CHAR(36)        NOT NULL DEFAULT (UUID()) PRIMARY KEY,
    firm_id                 BIGINT          NOT NULL,
    title                   TEXT            NOT NULL,
    event_type              VARCHAR(100)    NOT NULL,
    event_category          VARCHAR(20)     NOT NULL DEFAULT 'classical'
                                            CHECK (event_category IN ('people', 'connection', 'classical')),
    risk_level              TINYINT         NOT NULL CHECK (risk_level BETWEEN 1 AND 10),
    occurred_at             DATETIME        NOT NULL,
    extraction_confidence   DECIMAL(3,2)    CHECK (extraction_confidence BETWEEN 0 AND 1),
    source_text_quote       TEXT,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_event_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE source (
    id              BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    event_id        CHAR(36)        NOT NULL,
    url             TEXT            NOT NULL,
    title           TEXT,
    content         TEXT,
    language        VARCHAR(10),
    source_type     VARCHAR(50)     NOT NULL,
    source_category VARCHAR(20)     DEFAULT 'article'
                                    CHECK (source_category IN ('article', 'extraction', 'summary')),
    published_at    DATETIME,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    credibility     DECIMAL(3,2)    CHECK (credibility BETWEEN 0 AND 1),
    CONSTRAINT fk_source_event FOREIGN KEY (event_id) REFERENCES event(unique_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- People
-- ─────────────────────────────────────────

CREATE TABLE person (
    id          BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name        TEXT            NOT NULL,
    role        VARCHAR(100),
    description TEXT,
    firm_id     BIGINT,
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_person_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Links people to events where event_category = 'people'
CREATE TABLE person_event (
    id              BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    person_id       BIGINT          NOT NULL,
    event_id        CHAR(36)        NOT NULL,
    role_in_event   VARCHAR(100),
    confidence      DECIMAL(3,2)    CHECK (confidence BETWEEN 0 AND 1),
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_person_event (person_id, event_id),
    CONSTRAINT fk_pe_person FOREIGN KEY (person_id) REFERENCES person(id)       ON DELETE CASCADE,
    CONSTRAINT fk_pe_event  FOREIGN KEY (event_id)  REFERENCES event(unique_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Connection entities
-- ─────────────────────────────────────────

-- Data payload for events where event_category = 'connection'
CREATE TABLE connection_entity (
    id                       BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    connection_event_id      CHAR(36)        NOT NULL,
    connection_type          VARCHAR(50)     NOT NULL
                                             CHECK (connection_type IN (
                                                 'shared_director',
                                                 'business_relationship',
                                                 'activity_link',
                                                 'shared_beneficial_owner'
                                             )),
    entity_1_type            VARCHAR(20)     NOT NULL CHECK (entity_1_type IN ('company', 'person')),
    entity_1_id              VARCHAR(50)     NOT NULL,
    entity_1_name            TEXT,
    entity_2_type            VARCHAR(20)     NOT NULL CHECK (entity_2_type IN ('company', 'person')),
    entity_2_id              VARCHAR(50)     NOT NULL,
    entity_2_name            TEXT,
    relationship_description TEXT,
    confidence               DECIMAL(3,2)    CHECK (confidence BETWEEN 0 AND 1),
    created_at               DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_connection_event FOREIGN KEY (connection_event_id) REFERENCES event(unique_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Article processing metadata
-- ─────────────────────────────────────────

CREATE TABLE article_metadata (
    id              BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    article_id      VARCHAR(50)     NOT NULL UNIQUE,
    correlation_id  VARCHAR(50)     NOT NULL,
    source_url      TEXT            NOT NULL,
    title           TEXT,
    published_at    DATETIME,
    scraped_at      DATETIME,
    processed_at    DATETIME,
    language        VARCHAR(10),
    region          VARCHAR(50),
    companies_found INT             DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Reputation
-- ─────────────────────────────────────────

CREATE TABLE reputation_score (
    id               BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    firm_id          BIGINT          NOT NULL,
    score            DECIMAL(6,2)    NOT NULL,
    delta            DECIMAL(6,2),
    trigger_event_id CHAR(36),
    calculated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reputation_firm  FOREIGN KEY (firm_id)          REFERENCES firm(id)         ON DELETE CASCADE,
    CONSTRAINT fk_reputation_event FOREIGN KEY (trigger_event_id) REFERENCES event(unique_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Sentiment & Keywords
-- ─────────────────────────────────────────

-- Used for events where event_category = 'classical'
CREATE TABLE sentiment (
    id             BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    event_id       CHAR(36)        NOT NULL,
    firm_id        BIGINT          NOT NULL,
    score          DECIMAL(4,3)    NOT NULL CHECK (score BETWEEN -1 AND 1),
    sentiment_type VARCHAR(50)     NOT NULL,
    impact_weight  DECIMAL(4,3)    CHECK (impact_weight BETWEEN 0 AND 1),
    analyzed_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sentiment_event FOREIGN KEY (event_id) REFERENCES event(unique_id) ON DELETE CASCADE,
    CONSTRAINT fk_sentiment_firm  FOREIGN KEY (firm_id)  REFERENCES firm(id)         ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE risk_keywords (
    id          BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    keyword     VARCHAR(255)    NOT NULL UNIQUE,
    category    VARCHAR(100)    NOT NULL,
    base_weight DECIMAL(4,3)    NOT NULL CHECK (base_weight BETWEEN 0 AND 1)
) ENGINE=InnoDB;

CREATE TABLE sentiment_keywords (
    id           BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sentiment_id BIGINT          NOT NULL,
    keywords_id  BIGINT          NOT NULL,
    score        DECIMAL(4,3)    CHECK (score BETWEEN -1 AND 1),
    occurrences  INT             NOT NULL DEFAULT 1 CHECK (occurrences > 0),
    UNIQUE KEY uq_sentiment_keyword (sentiment_id, keywords_id),
    CONSTRAINT fk_sk_sentiment FOREIGN KEY (sentiment_id) REFERENCES sentiment(id)     ON DELETE CASCADE,
    CONSTRAINT fk_sk_keyword   FOREIGN KEY (keywords_id)  REFERENCES risk_keywords(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Market data
-- ─────────────────────────────────────────

CREATE TABLE firm_market (
    id          BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    firm_id     BIGINT          NOT NULL,
    tv_symbol   VARCHAR(50)     NOT NULL,
    tv_exchange VARCHAR(30)     NOT NULL,
    currency    VARCHAR(3)      NOT NULL,
    is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
    added_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_firm_market_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE CASCADE,
    UNIQUE KEY uq_tv_symbol_exchange (tv_symbol, tv_exchange)
) ENGINE=InnoDB;

CREATE TABLE market_data (
    id          BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    firm_id     BIGINT          NOT NULL,
    tv_symbol   VARCHAR(50)     NOT NULL,
    tv_exchange VARCHAR(30)     NOT NULL,
    date        DATE            NOT NULL,
    open        DECIMAL(18,4)   NOT NULL,
    high        DECIMAL(18,4)   NOT NULL,
    low         DECIMAL(18,4)   NOT NULL,
    close       DECIMAL(18,4)   NOT NULL,
    volume      BIGINT          NOT NULL,
    fetched_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_market_data_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE CASCADE,
    UNIQUE KEY uq_firm_date (firm_id, date)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────

CREATE INDEX idx_firm_alias_firm_id               ON firm_alias(firm_id);
CREATE INDEX idx_firm_alias_confidence            ON firm_alias(confidence);
CREATE INDEX idx_firm_alias_type                  ON firm_alias(alias_type);

CREATE INDEX idx_event_firm_id                    ON event(firm_id);
CREATE INDEX idx_event_occurred_at                ON event(occurred_at);
CREATE INDEX idx_event_type                       ON event(event_type);
CREATE INDEX idx_event_category                   ON event(event_category);
CREATE INDEX idx_event_extraction_confidence      ON event(extraction_confidence);

CREATE INDEX idx_source_event_id                  ON source(event_id);
CREATE INDEX idx_source_category                  ON source(source_category);
CREATE INDEX idx_source_event_id_category         ON source(event_id, source_category);

CREATE INDEX idx_person_name                      ON person(name(100));
CREATE INDEX idx_person_role                      ON person(role);
CREATE INDEX idx_person_firm_id                   ON person(firm_id);

CREATE INDEX idx_person_event_person_id           ON person_event(person_id);
CREATE INDEX idx_person_event_event_id            ON person_event(event_id);
CREATE INDEX idx_person_event_confidence          ON person_event(confidence);

CREATE INDEX idx_connection_event_id              ON connection_entity(connection_event_id);
CREATE INDEX idx_connection_type                  ON connection_entity(connection_type);
CREATE INDEX idx_connection_entity_1              ON connection_entity(entity_1_type, entity_1_id);
CREATE INDEX idx_connection_entity_2              ON connection_entity(entity_2_type, entity_2_id);
CREATE INDEX idx_connection_confidence            ON connection_entity(confidence);

CREATE INDEX idx_article_metadata_correlation     ON article_metadata(correlation_id);
CREATE INDEX idx_article_metadata_processed_at    ON article_metadata(processed_at);
CREATE INDEX idx_article_language                 ON article_metadata(language);
CREATE INDEX idx_article_region                   ON article_metadata(region);

CREATE INDEX idx_reputation_score_firm_id         ON reputation_score(firm_id);
CREATE INDEX idx_reputation_score_calculated_at   ON reputation_score(calculated_at);
CREATE INDEX idx_reputation_score_trigger_event   ON reputation_score(trigger_event_id);

CREATE INDEX idx_sentiment_event_id               ON sentiment(event_id);
CREATE INDEX idx_sentiment_firm_id                ON sentiment(firm_id);

CREATE INDEX idx_sentiment_keywords_sentiment_id  ON sentiment_keywords(sentiment_id);
CREATE INDEX idx_sentiment_keywords_keywords_id   ON sentiment_keywords(keywords_id);

CREATE INDEX idx_risk_keywords_category           ON risk_keywords(category);

CREATE INDEX idx_firm_market_firm_id              ON firm_market(firm_id);
CREATE INDEX idx_market_data_firm_id              ON market_data(firm_id);
CREATE INDEX idx_market_data_date                 ON market_data(date);

-- ─────────────────────────────────────────
-- Triggers
-- ─────────────────────────────────────────

DELIMITER $$

CREATE TRIGGER trg_source_tagged_union_validation
BEFORE INSERT ON source FOR EACH ROW
BEGIN
    DECLARE event_category_val VARCHAR(20);

    SELECT event_category INTO event_category_val
    FROM event
    WHERE unique_id = NEW.event_id;

    IF event_category_val IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Foreign Key Violation: source.event_id references non-existent event';
    END IF;

    IF NEW.source_category = 'extraction' AND event_category_val NOT IN ('people', 'connection') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Tagged Union Violation: extraction sources require event_category IN (people, connection)';
    END IF;
END $$

DELIMITER ;
