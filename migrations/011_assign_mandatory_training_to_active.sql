-- 011_assign_mandatory_training_to_active.sql
--
-- Seeds the checklist so the new training feature is populated on first open
-- rather than showing an empty grid for every driver.
--
-- WHAT THIS DOES
-- Creates one 'not_started' employee_training_records row for each active
-- employee x each mandatory, active program (30 x 7 = 210 rows at time of
-- writing).
--
-- WHAT THIS DELIBERATELY DOES NOT DO
-- No completion dates, expiry dates, trainer names or scores are invented.
-- Every row is created as 'not_started', which is the honest position: the
-- company has never tracked this training, so its true state is unknown and
-- must be established by verification, not by assumption. Fabricating
-- completion dates here would produce exactly the kind of false compliance
-- signal that migration 007 had to unwind for driver_documents.
--
-- Inactive employees are skipped - there is no value in generating 119 x 7
-- outstanding rows for people who have left. Assign them individually from
-- the PC app if someone is rehired.
--
-- SAFETY
-- ON CONFLICT DO NOTHING makes this idempotent and non-destructive: a driver
-- who already has progress recorded against a program keeps it untouched, and
-- re-running the migration inserts nothing.

BEGIN;

INSERT INTO employee_training_records (employee_id, program_id, status)
SELECT e.employee_id, p.program_id, 'not_started'
  FROM employees e
 CROSS JOIN training_programs p
 WHERE e.employment_status = 'active'
   AND p.is_mandatory IS TRUE
   AND p.is_active IS NOT FALSE
ON CONFLICT (employee_id, program_id) DO NOTHING;

COMMIT;

-- VERIFICATION (expected results)
--   SELECT COUNT(*) FROM employee_training_records;          -> 210
--   rows with a completed_date .............................  -> 0
--   rows with an expiry_date ...............................  -> 0
--   re-running this migration ..............................  -> inserts 0
