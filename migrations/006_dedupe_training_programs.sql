-- Remove exact duplicate training program rows and prevent them recurring.
--
-- A historical setup script was run six times, so every training program
-- existed six times over. Each group was verified byte-identical across
-- description, is_mandatory, red_deer_required, duration_hours,
-- expiry_months, sort_order and is_active before any row was removed.
--
-- Yearly programs (expiry_months = 12: Emergency Response, Hours of Service
-- Compliance, Red Deer Municipal Bylaws) recur through expiry_months on a
-- single catalogue row plus each employee's completion record, so collapsing
-- the catalogue to one row per program keeps the yearly behaviour intact.

BEGIN;

-- Keep a copy of the pre-cleanup catalogue so the change is reversible.
CREATE TABLE IF NOT EXISTS training_programs_dedupe_backup AS
SELECT *, NOW() AS backed_up_at FROM training_programs;

-- Re-point any child rows at the surviving (lowest-id) program. The foreign
-- key cascades on delete, so this must happen before the duplicates go.
UPDATE training_checklist_items AS tci
SET program_id = keeper.keep_id
FROM (
    SELECT program_name, MIN(program_id) AS keep_id
    FROM training_programs
    GROUP BY program_name
) AS keeper
JOIN training_programs AS tp ON tp.program_name = keeper.program_name
WHERE tci.program_id = tp.program_id
  AND tci.program_id <> keeper.keep_id;

-- Delete every duplicate, keeping the lowest program_id per program name.
DELETE FROM training_programs
WHERE program_id NOT IN (
    SELECT MIN(program_id) FROM training_programs GROUP BY program_name
);

-- Stop the duplicates from ever coming back.
CREATE UNIQUE INDEX IF NOT EXISTS uq_training_programs_name
    ON training_programs (program_name);

COMMIT;
