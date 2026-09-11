-- 010_driver_training_checklists.sql
--
-- Adds per-driver training/onboarding checklist tracking.
--
-- WHAT EXISTED BEFORE
-- training_programs (8 rows) and training_checklist_items (6 rows) formed a
-- catalogue of WHAT training exists, but there was no table anywhere in the
-- 429-table schema recording WHICH DRIVER has done WHICH training. Compliance
-- progress was therefore untrackable.
--
-- WHAT THIS ADDS
--   1. training_programs.category      - groups programs into municipal /
--                                        provincial / federal / company so the
--                                        bylaw, provincial and company
--                                        checklists can be shown separately.
--   2. training_programs.sort_order    - populated 1..8 to give the step-by-step
--                                        ordering (step 1, step 2, ...).
--   3. employee_training_records       - current status of each program for each
--                                        driver, with started/completed/expiry
--                                        dates and admin verification.
--   4. employee_checklist_progress     - per-item tick-off within a program.
--   5. employee_training_history       - append-only log of every completion and
--                                        renewal, so recurring yearly training
--                                        keeps a full history rather than being
--                                        overwritten.
--   6. v_employee_training_status      - computes live status including expiry.
--
-- RECURRENCE
-- employee_training_records holds ONE current row per (employee, program).
-- Renewing a yearly program updates that row and appends to
-- employee_training_history, so "completed 2025, renewed 2026" is preserved
-- without duplicating the current-status row.
--
-- CATEGORY DEFAULTS
-- Categories below are seeded from the existing red_deer_required flag and the
-- obvious subject matter. They are ordinary editable data, NOT a legal
-- determination - an admin should review them against current Red Deer and
-- Alberta requirements and adjust.

BEGIN;

-- ---------------------------------------------------------------- catalogue
ALTER TABLE training_programs
    ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'company';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'training_programs'::regclass
           AND conname  = 'training_programs_category_check'
    ) THEN
        ALTER TABLE training_programs
            ADD CONSTRAINT training_programs_category_check
            CHECK (category IN ('municipal', 'provincial', 'federal', 'company'));
    END IF;
END $$;

UPDATE training_programs SET category = 'municipal'
 WHERE program_name IN ('Red Deer Municipal Bylaws', 'Basic Chauffeur Training',
                        'Emergency Response');
UPDATE training_programs SET category = 'provincial'
 WHERE program_name IN ('Vehicle Inspection & Maintenance');
UPDATE training_programs SET category = 'federal'
 WHERE program_name IN ('Hours of Service Compliance');
UPDATE training_programs SET category = 'company'
 WHERE program_name IN ('Defensive Driving', 'Customer Service Excellence',
                        'Accessibility & Special Needs');

-- Give every program a distinct step number (all were 0).
WITH ordered AS (
    SELECT program_id,
           ROW_NUMBER() OVER (
               ORDER BY CASE category
                            WHEN 'municipal'  THEN 1
                            WHEN 'provincial' THEN 2
                            WHEN 'federal'    THEN 3
                            ELSE 4
                        END,
                        is_mandatory DESC,
                        program_name
           ) AS rn
      FROM training_programs
)
UPDATE training_programs t
   SET sort_order = o.rn
  FROM ordered o
 WHERE t.program_id = o.program_id;

-- ------------------------------------------------- per-driver program status
CREATE TABLE IF NOT EXISTS employee_training_records (
    record_id       SERIAL PRIMARY KEY,
    employee_id     INTEGER NOT NULL REFERENCES employees(employee_id)        ON DELETE CASCADE,
    program_id      INTEGER NOT NULL REFERENCES training_programs(program_id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'not_started'
                    CHECK (status IN ('not_started', 'in_progress', 'completed',
                                      'expired', 'waived')),
    started_date    DATE,
    completed_date  DATE,
    expiry_date     DATE,
    trainer_name    TEXT,
    score           NUMERIC(5,2),
    verified_by     INTEGER REFERENCES employees(employee_id),
    verified_at     TIMESTAMP,
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_employee_training UNIQUE (employee_id, program_id),
    CONSTRAINT chk_training_dates CHECK (
        completed_date IS NULL OR started_date IS NULL
        OR completed_date >= started_date
    )
);

CREATE INDEX IF NOT EXISTS ix_employee_training_employee ON employee_training_records (employee_id);
CREATE INDEX IF NOT EXISTS ix_employee_training_expiry   ON employee_training_records (expiry_date);

-- ---------------------------------------------------- per-driver item tick-off
CREATE TABLE IF NOT EXISTS employee_checklist_progress (
    progress_id    SERIAL PRIMARY KEY,
    employee_id    INTEGER NOT NULL REFERENCES employees(employee_id)              ON DELETE CASCADE,
    item_id        INTEGER NOT NULL REFERENCES training_checklist_items(item_id)   ON DELETE CASCADE,
    completed      BOOLEAN NOT NULL DEFAULT FALSE,
    completed_date DATE,
    verified_by    INTEGER REFERENCES employees(employee_id),
    verified_at    TIMESTAMP,
    notes          TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_employee_checklist_item UNIQUE (employee_id, item_id)
);

CREATE INDEX IF NOT EXISTS ix_employee_checklist_employee ON employee_checklist_progress (employee_id);

-- --------------------------------------------------------- append-only history
CREATE TABLE IF NOT EXISTS employee_training_history (
    history_id     SERIAL PRIMARY KEY,
    employee_id    INTEGER NOT NULL REFERENCES employees(employee_id)        ON DELETE CASCADE,
    program_id     INTEGER NOT NULL REFERENCES training_programs(program_id) ON DELETE CASCADE,
    completed_date DATE,
    expiry_date    DATE,
    trainer_name   TEXT,
    score          NUMERIC(5,2),
    recorded_by    INTEGER REFERENCES employees(employee_id),
    recorded_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    notes          TEXT
);

CREATE INDEX IF NOT EXISTS ix_employee_training_history_emp
    ON employee_training_history (employee_id, program_id);

-- ------------------------------------- auto-derive expiry from expiry_months
CREATE OR REPLACE FUNCTION trg_training_set_expiry() RETURNS TRIGGER AS $$
DECLARE
    months integer;
BEGIN
    NEW.updated_at := NOW();

    IF NEW.status = 'completed' AND NEW.completed_date IS NOT NULL THEN
        SELECT expiry_months INTO months
          FROM training_programs
         WHERE program_id = NEW.program_id;

        -- Recompute whenever the completion date moves (a renewal) so the
        -- expiry cannot silently retain the previous cycle's value.
        IF months IS NOT NULL AND months > 0
           AND (NEW.expiry_date IS NULL
                OR TG_OP = 'INSERT'
                OR NEW.completed_date IS DISTINCT FROM OLD.completed_date) THEN
            NEW.expiry_date := NEW.completed_date + (months || ' months')::interval;
        END IF;
    END IF;

    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS training_set_expiry ON employee_training_records;
CREATE TRIGGER training_set_expiry
    BEFORE INSERT OR UPDATE ON employee_training_records
    FOR EACH ROW EXECUTE FUNCTION trg_training_set_expiry();

-- ------------------------------------------------------------- status view
CREATE OR REPLACE VIEW v_employee_training_status AS
SELECT e.employee_id,
       e.first_name,
       e.last_name,
       e.employment_status,
       p.program_id,
       p.program_name,
       p.category,
       p.is_mandatory,
       p.expiry_months,
       p.sort_order            AS step_number,
       COALESCE(r.status, 'not_started') AS raw_status,
       CASE
           WHEN r.status = 'waived'                              THEN 'waived'
           WHEN r.status = 'completed'
                AND r.expiry_date IS NOT NULL
                AND r.expiry_date < CURRENT_DATE                 THEN 'expired'
           WHEN r.status = 'completed'                           THEN 'completed'
           WHEN r.status = 'in_progress'                         THEN 'in_progress'
           ELSE 'not_started'
       END AS effective_status,
       r.started_date,
       r.completed_date,
       r.expiry_date,
       CASE WHEN r.expiry_date IS NOT NULL
            THEN (r.expiry_date - CURRENT_DATE) END AS days_until_expiry,
       r.verified_by,
       r.verified_at,
       r.notes
  FROM employees e
 CROSS JOIN training_programs p
  LEFT JOIN employee_training_records r
         ON r.employee_id = e.employee_id
        AND r.program_id  = p.program_id
 WHERE p.is_active IS NOT FALSE;

COMMIT;

-- VERIFICATION (expected results)
--   training_programs categories .... municipal 3, provincial 1, federal 1, company 3
--   sort_order ...................... distinct 1..8
--   new tables ...................... employee_training_records,
--                                     employee_checklist_progress,
--                                     employee_training_history
--   expiry trigger .................. completing a 12-month program sets
--                                     expiry_date = completed_date + 12 months
