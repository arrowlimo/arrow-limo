-- 012_protect_training_history_and_catalogue_edit.sql
--
-- Prepares the training catalogue for manual admin review.
--
-- PROBLEM
-- All three child tables cascade from training_programs:
--   training_checklist_items   ON DELETE CASCADE
--   employee_training_records  ON DELETE CASCADE
--   employee_training_history  ON DELETE CASCADE   <-- dangerous
--
-- employee_training_history is the permanent record that driver X completed
-- training Y on date Z. Deleting a program would silently erase that proof for
-- every driver who ever completed it, with no warning and no recovery. That is
-- unacceptable for a compliance record, and it is precisely the kind of silent
-- data loss that the manual catalogue review is about to risk.
--
-- FIX
-- employee_training_history now uses ON DELETE RESTRICT. A program that any
-- driver has ever completed can no longer be deleted at all; it must be
-- deactivated instead (is_active = FALSE), which hides it from the checklist
-- while preserving the completion history.
--
-- employee_training_records keeps ON DELETE CASCADE deliberately: those rows
-- are current assignment state, not historical proof, so removing a program
-- the company no longer runs should clear its outstanding assignments.
--
-- training_checklist_items keeps ON DELETE CASCADE: items are owned by their
-- program and are meaningless without it.
--
-- ALSO
-- Adds is_active to the catalogue editor's reach by ensuring the column has a
-- sane default, and indexes is_active for the filtered catalogue queries.

BEGIN;

ALTER TABLE employee_training_history
    DROP CONSTRAINT IF EXISTS employee_training_history_program_id_fkey;

ALTER TABLE employee_training_history
    ADD CONSTRAINT employee_training_history_program_id_fkey
    FOREIGN KEY (program_id) REFERENCES training_programs(program_id)
    ON DELETE RESTRICT;

ALTER TABLE training_programs
    ALTER COLUMN is_active SET DEFAULT TRUE;

UPDATE training_programs SET is_active = TRUE WHERE is_active IS NULL;

CREATE INDEX IF NOT EXISTS ix_training_programs_active
    ON training_programs (is_active);

COMMIT;

-- VERIFICATION (expected results)
--   employee_training_history FK ......... ON DELETE RESTRICT
--   deleting a program with history ...... rejected (ForeignKeyViolation)
--   deleting a program without history ... permitted
--   is_active NULLs ...................... 0
