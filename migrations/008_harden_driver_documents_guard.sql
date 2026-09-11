-- 008_harden_driver_documents_guard.sql
--
-- Closes a gap in the dedupe guard added by 007_dedupe_driver_documents.sql.
--
-- PROBLEM
-- uq_driver_documents_no_exact_dupes indexes employee_id directly while
-- wrapping every other column in COALESCE. Postgres treats NULLs as distinct
-- in a unique index, so any row with employee_id IS NULL sidesteps the guard
-- entirely and unlimited duplicates could be inserted. This was confirmed
-- empirically: an insert with a NULL employee_id was accepted even though an
-- identical row already existed.
--
-- A driver_documents row with no employee is meaningless anyway -- the
-- document has to belong to someone -- so the correct fix is to forbid NULL
-- rather than to fold it into the index with a sentinel value.
--
-- SAFETY
-- Verified before writing this migration:
--   - rows with employee_id IS NULL ............ 0
--   - orphan rows (no matching employees row) .. 0
-- So SET NOT NULL cannot fail on existing data, and the existing
-- driver_documents_employee_id_fkey (ON DELETE CASCADE) already guarantees
-- referential integrity going forward.
--
-- training_programs needs no equivalent change: program_name is already
-- NOT NULL, so uq_training_programs_name has no NULL escape hatch.

BEGIN;

-- Re-assert the preconditions at apply time so this cannot silently corrupt
-- data if run against a database whose state has drifted.
DO $$
DECLARE
    null_rows   integer;
    orphan_rows integer;
BEGIN
    SELECT COUNT(*) INTO null_rows
      FROM driver_documents
     WHERE employee_id IS NULL;

    IF null_rows > 0 THEN
        RAISE EXCEPTION
            'Refusing to apply: % driver_documents row(s) have a NULL employee_id. Assign them to an employee or delete them first.',
            null_rows;
    END IF;

    SELECT COUNT(*) INTO orphan_rows
      FROM driver_documents d
      LEFT JOIN employees e USING (employee_id)
     WHERE e.employee_id IS NULL;

    IF orphan_rows > 0 THEN
        RAISE EXCEPTION
            'Refusing to apply: % driver_documents row(s) reference a missing employee.',
            orphan_rows;
    END IF;
END $$;

ALTER TABLE driver_documents
    ALTER COLUMN employee_id SET NOT NULL;

COMMIT;

-- VERIFICATION (expected results)
--   employee_id is_nullable ......................... NO
--   inserting a NULL employee_id .................... rejected (NotNullViolation)
--   inserting a full-row duplicate .................. rejected (UniqueViolation)
--   SELECT COUNT(*) FROM driver_documents ........... 133 (unchanged)
