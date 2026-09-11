-- 014: make employee_training_history trustworthy as permanent proof.
--
-- Two gaps, both found reviewing the driver-submission approval path.
--
-- 1. Duplicates. employee_training_records is protected by
--    ON CONFLICT (employee_id, program_id), but history had no unique
--    constraint at all, so re-approving the same completion (a driver
--    correcting a typo and resubmitting, say) appended a second identical
--    row. Keying on the completion date collapses those while still
--    allowing a genuine annual renewal, which has a different date.
--
-- 2. No reviewer. recorded_by is a FK to employees(employee_id), but the
--    authenticated administrator is a row in users, which has no
--    employee_id. There was no way to record who authorized an entry, so
--    it was left NULL on every insert. A username column records the
--    actual actor instead of guessing at an employee row.
--
-- Migration 012 made this table ON DELETE RESTRICT because it is the
-- record of last resort; these two changes make it able to answer "who
-- said so, and when" without contradiction.

BEGIN;

ALTER TABLE employee_training_history
    ADD COLUMN IF NOT EXISTS recorded_by_username TEXT;

-- Collapse any pre-existing duplicates before the constraint is added,
-- keeping the earliest row so the original authorization survives.
DELETE FROM employee_training_history a
      USING employee_training_history b
 WHERE a.employee_id = b.employee_id
   AND a.program_id = b.program_id
   AND a.completed_date IS NOT DISTINCT FROM b.completed_date
   AND a.history_id > b.history_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_training_history_completion
    ON employee_training_history (employee_id, program_id, completed_date);

COMMIT;
