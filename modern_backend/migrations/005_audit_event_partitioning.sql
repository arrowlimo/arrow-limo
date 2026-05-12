-- CRA record-keeping grounding:
-- - Keep records organized and support reported amounts.
-- - Generally retain records/supporting documents for 6 years.
-- - Preserve audit trail sequence of business transactions.
--
-- This migration introduces a partitioned audit event storage pattern for scale.
-- It does not assert CRA-mandated schema details.

BEGIN;

CREATE TABLE IF NOT EXISTS audit_events_partitioned (
    audit_event_pk BIGINT GENERATED ALWAYS AS IDENTITY,
    event_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    module TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    source TEXT NOT NULL,
    correlation_id TEXT,
    actor_json JSONB NOT NULL,
    before_json JSONB,
    after_json JSONB,
    evidence_links JSONB NOT NULL DEFAULT '[]'::jsonb,
    retention_until DATE NOT NULL,
    note TEXT,
    prev_hash TEXT,
    event_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (audit_event_pk, occurred_at)
) PARTITION BY RANGE (occurred_at);

-- Default partition as safety net.
CREATE TABLE IF NOT EXISTS audit_events_partitioned_default
PARTITION OF audit_events_partitioned DEFAULT;

DO $$
DECLARE
    y1 INT := EXTRACT(YEAR FROM NOW())::INT - 1;
    y2 INT := EXTRACT(YEAR FROM NOW())::INT;
    y3 INT := EXTRACT(YEAR FROM NOW())::INT + 1;
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS audit_events_%s PARTITION OF audit_events_partitioned FOR VALUES FROM (%L) TO (%L)',
        y1,
        y1 || ''-01-01'',
        y2 || ''-01-01''
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS audit_events_%s PARTITION OF audit_events_partitioned FOR VALUES FROM (%L) TO (%L)',
        y2,
        y2 || ''-01-01'',
        y3 || ''-01-01''
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS audit_events_%s PARTITION OF audit_events_partitioned FOR VALUES FROM (%L) TO (%L)',
        y3,
        y3 || ''-01-01'',
        (y3 + 1) || ''-01-01''
    );
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_events_partitioned_event_id_occurred
ON audit_events_partitioned (event_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_partitioned_module_action_time
ON audit_events_partitioned (module, action, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_partitioned_entity
ON audit_events_partitioned (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_partitioned_username
ON audit_events_partitioned ((actor_json->>'username'));

CREATE INDEX IF NOT EXISTS idx_audit_events_partitioned_correlation
ON audit_events_partitioned (correlation_id)
WHERE correlation_id IS NOT NULL;

-- Optional cut-over path (requires confirmation and a planned maintenance window):
-- 1. Backfill from audit_events into audit_events_partitioned.
-- 2. Swap names, or create a compatibility view.
-- 3. Update writes to target the partitioned table.

-- Retention helper: generally keep at least 6 years (confirm legal hold policy).
CREATE OR REPLACE FUNCTION rotate_audit_event_partitions(retain_years INT DEFAULT 7)
RETURNS VOID AS $$
DECLARE
    next_year INT := EXTRACT(YEAR FROM NOW())::INT + 1;
    future_year INT := next_year + 1;
    cutoff_year INT := EXTRACT(YEAR FROM NOW())::INT - retain_years;
    part_name TEXT;
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS audit_events_%s PARTITION OF audit_events_partitioned FOR VALUES FROM (%L) TO (%L)',
        future_year,
        future_year || ''-01-01'',
        (future_year + 1) || ''-01-01''
    );

    FOR part_name IN
        SELECT c.relname
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname = 'audit_events_partitioned'
          AND c.relname ~ '^audit_events_[0-9]{4}$'
    LOOP
        IF substring(part_name from '([0-9]{4})$')::INT < cutoff_year THEN
            EXECUTE format('DROP TABLE IF EXISTS %I', part_name);
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

COMMIT;
