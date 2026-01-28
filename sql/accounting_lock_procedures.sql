-- Accounting lock/unlock state and procedures

-- 1) State table (single-row)
CREATE TABLE IF NOT EXISTS accounting_lock_state (
  id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  lock_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  locked_at TIMESTAMP,
  locked_by TEXT,
  cra_notes TEXT
);

-- Ensure single-row exists
INSERT INTO accounting_lock_state (id, lock_enabled)
SELECT 1, FALSE
WHERE NOT EXISTS (SELECT 1 FROM accounting_lock_state WHERE id = 1);

-- 2) Getter
CREATE OR REPLACE FUNCTION get_accounting_lock_state()
RETURNS BOOLEAN AS $$
DECLARE
  v_locked BOOLEAN;
BEGIN
  SELECT lock_enabled INTO v_locked FROM accounting_lock_state WHERE id = 1;
  RETURN COALESCE(v_locked, FALSE);
END;
$$ LANGUAGE plpgsql;

-- 3) Enable lock with optional CRA notes
CREATE OR REPLACE FUNCTION enable_accounting_lock(p_locked_by TEXT, p_cra_notes TEXT DEFAULT NULL)
RETURNS VOID AS $$
BEGIN
  UPDATE accounting_lock_state
  SET lock_enabled = TRUE,
      locked_at = NOW(),
      locked_by = p_locked_by,
      cra_notes = p_cra_notes
  WHERE id = 1;
END;
$$ LANGUAGE plpgsql;

-- 4) Disable lock
CREATE OR REPLACE FUNCTION disable_accounting_lock()
RETURNS VOID AS $$
BEGIN
  UPDATE accounting_lock_state
  SET lock_enabled = FALSE,
      locked_at = NULL,
      locked_by = NULL
  WHERE id = 1;
END;
$$ LANGUAGE plpgsql;
