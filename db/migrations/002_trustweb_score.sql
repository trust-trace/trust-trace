-- Migration: 002_trustweb_score.sql
-- Description: TrustWeb score table for Module C graph-based risk scoring

CREATE TABLE trustweb_score (
    id              BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    firm_id         BIGINT          NOT NULL,
    score           DECIMAL(4,3)    NOT NULL CHECK (score BETWEEN 0 AND 1),
    explanation     TEXT,
    node_count      INT,
    edge_count      INT,
    max_depth_used  INT,
    computed_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_trustweb_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_trustweb_score_firm_id     ON trustweb_score(firm_id);
CREATE INDEX idx_trustweb_score_computed_at ON trustweb_score(computed_at);
