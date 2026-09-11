-- Remove exact duplicate driver document rows and neutralise placeholder data.
--
-- Two separate problems were found in driver_documents:
--
-- 1. A bulk import on 2025-07-26 ran three times, so all 399 rows were really
--    only 133 distinct documents, each stored three times over.
--
-- 2. Every one of those rows carries the SAME fabricated dates (issued
--    2023-07-26, expiry 2028-07-26) for all 133 employees, and not one row
--    has a file attached. These are placeholder records, not real licences.
--    Left as 'active' they make every driver look licensed until 2028, which
--    could mask a genuinely expired licence, so they are moved to 'pending'
--    (unverified) instead. The real licence dates live on the employees row.
--
-- The employees table is deliberately NOT modified here: its per-driver
-- licence dates are hand-entered real values and must not be overwritten
-- with the fabricated import date.

BEGIN;

-- Keep a copy of the pre-cleanup table so the change is reversible.
CREATE TABLE IF NOT EXISTS driver_documents_dedupe_backup AS
SELECT *, NOW() AS backed_up_at FROM driver_documents;

-- Delete exact duplicates, keeping the lowest id of each identical group.
-- GROUP BY treats NULLs as equal, which is what is wanted here.
DELETE FROM driver_documents
WHERE id NOT IN (
    SELECT MIN(id)
    FROM driver_documents
    GROUP BY employee_id, document_type, document_name, document_number,
             issued_date, expiry_date, status, issuing_authority,
             file_path, notes
);

-- Flag the fabricated import rows so their expiry date is not trusted.
UPDATE driver_documents
SET status = 'pending',
    notes = COALESCE(notes || ' | ', '')
            || 'Placeholder from the 2025-07-26 bulk import: no file attached '
            || 'and the same date was applied to every employee. '
            || 'Verify against the real document before treating as valid.'
WHERE document_type = 'license'
  AND issued_date = DATE '2023-07-26'
  AND expiry_date = DATE '2028-07-26'
  AND file_path IS NULL
  AND status = 'active';

-- Stop an import from inserting the same document three times again.
CREATE UNIQUE INDEX IF NOT EXISTS uq_driver_documents_no_exact_dupes
    ON driver_documents (
        employee_id,
        document_type,
        COALESCE(document_name, ''),
        COALESCE(document_number, ''),
        COALESCE(issued_date, DATE '1900-01-01'),
        COALESCE(expiry_date, DATE '1900-01-01'),
        COALESCE(file_path, '')
    );

COMMIT;
