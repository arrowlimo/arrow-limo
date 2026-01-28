-- Granular accounting lock/unlock: per-year, per-type, per-action

-- 1) Lock controls table
CREATE TABLE IF NOT EXISTS accounting_lock_controls (
  id SERIAL PRIMARY KEY,
  fiscal_year INTEGER NOT NULL,
  entity_type VARCHAR(50) NOT NULL, -- 'receipts', 'payments', 'banking_transactions', 'charters', etc.
  lock_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  allowed_actions TEXT[] NOT NULL DEFAULT ARRAY['view', 'add'], -- view, add, suggest, edit, delete
  locked_at TIMESTAMP,
  locked_by TEXT,
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(fiscal_year, entity_type)
);

-- 2) Seed default unlocked state for all years and entity types
INSERT INTO accounting_lock_controls (fiscal_year, entity_type, lock_enabled, allowed_actions)
SELECT y, t, FALSE, ARRAY['view', 'add', 'suggest', 'edit', 'delete']
FROM (
  -- Years 2012-2026 (adjust as needed)
  SELECT generate_series(2012, 2026) AS y
) years
CROSS JOIN (
  SELECT unnest(ARRAY['receipts', 'payments', 'banking_transactions', 'charters', 'invoices']) AS t
) types
WHERE NOT EXISTS (
  SELECT 1 FROM accounting_lock_controls alc
  WHERE alc.fiscal_year = y AND alc.entity_type = t
)
ORDER BY y, t;

-- 3) Check if action is allowed for a given year and entity type
CREATE OR REPLACE FUNCTION is_action_allowed(
  p_fiscal_year INTEGER,
  p_entity_type VARCHAR,
  p_action VARCHAR
)
RETURNS BOOLEAN AS $$
DECLARE
  v_allowed_actions TEXT[];
  v_lock_enabled BOOLEAN;
BEGIN
  SELECT lock_enabled, allowed_actions INTO v_lock_enabled, v_allowed_actions
  FROM accounting_lock_controls
  WHERE fiscal_year = p_fiscal_year AND entity_type = p_entity_type;

  IF v_lock_enabled = FALSE THEN
    -- Unlocked: all actions allowed
    RETURN TRUE;
  ELSE
    -- Locked: check if action is in allowed list
    RETURN p_action = ANY(v_allowed_actions);
  END IF;
END;
$$ LANGUAGE plpgsql;

-- 4) Get current controls for a year and entity
CREATE OR REPLACE FUNCTION get_lock_status(
  p_fiscal_year INTEGER,
  p_entity_type VARCHAR
)
RETURNS TABLE (
  fiscal_year INTEGER,
  entity_type VARCHAR,
  lock_enabled BOOLEAN,
  allowed_actions TEXT[],
  locked_at TIMESTAMP,
  locked_by TEXT,
  notes TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT alc.fiscal_year, alc.entity_type, alc.lock_enabled, alc.allowed_actions,
         alc.locked_at, alc.locked_by, alc.notes
  FROM accounting_lock_controls alc
  WHERE alc.fiscal_year = p_fiscal_year AND alc.entity_type = p_entity_type;
END;
$$ LANGUAGE plpgsql;

-- 5) Enable lock for a year/type with optional allowed actions
CREATE OR REPLACE FUNCTION enable_lock_for_year_type(
  p_fiscal_year INTEGER,
  p_entity_type VARCHAR,
  p_locked_by TEXT,
  p_allowed_actions TEXT[] DEFAULT ARRAY['view'],
  p_notes TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
  INSERT INTO accounting_lock_controls (fiscal_year, entity_type, lock_enabled, allowed_actions, locked_at, locked_by, notes)
  VALUES (p_fiscal_year, p_entity_type, TRUE, p_allowed_actions, NOW(), p_locked_by, p_notes)
  ON CONFLICT (fiscal_year, entity_type)
  DO UPDATE SET
    lock_enabled = TRUE,
    allowed_actions = p_allowed_actions,
    locked_at = NOW(),
    locked_by = p_locked_by,
    notes = p_notes,
    updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- 6) Disable lock for a year/type
CREATE OR REPLACE FUNCTION disable_lock_for_year_type(
  p_fiscal_year INTEGER,
  p_entity_type VARCHAR
)
RETURNS VOID AS $$
BEGIN
  UPDATE accounting_lock_controls
  SET lock_enabled = FALSE,
      allowed_actions = ARRAY['view', 'add', 'suggest', 'edit', 'delete'],
      locked_at = NULL,
      locked_by = NULL,
      updated_at = NOW()
  WHERE fiscal_year = p_fiscal_year AND entity_type = p_entity_type;
END;
$$ LANGUAGE plpgsql;
