-- db/migrations/002_drop_stage_history_deal_fk.sql
--
-- DuckDB has a known FK limitation: when a parent row is updated (even on a
-- non-PK column), DuckDB incorrectly triggers a constraint violation if any
-- child table references the parent's PK. This blocks UPDATE deals SET stage=...
-- when stage_history rows reference the same deal.
--
-- Fix: recreate stage_history without the FK on deal_id. Referential integrity
-- for deal_id is enforced in application code (delete_deal nullifies/deletes
-- stage_history rows before deleting the deal).

CREATE TABLE stage_history_new (
    id INTEGER DEFAULT nextval('stage_history_id_seq'),
    deal_id INTEGER NOT NULL,
    from_stage VARCHAR,
    to_stage VARCHAR NOT NULL REFERENCES pipeline_stages(name),
    changed_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

INSERT INTO stage_history_new SELECT * FROM stage_history;

DROP TABLE stage_history;

ALTER TABLE stage_history_new RENAME TO stage_history;
