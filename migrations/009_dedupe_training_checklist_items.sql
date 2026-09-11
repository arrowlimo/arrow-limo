-- 009_dedupe_training_checklist_items.sql
--
-- Completes the dedupe work started in 006/007.
--
-- PROBLEM
-- training_checklist_items holds 12 rows that are really 6 items duplicated
-- twice (item_id 1-6 and 7-12). Verified byte-exact: grouping by item_name and
-- counting DISTINCT (program_id, description, is_required, sort_order,
-- completion_verification_required) returns exactly 1 variant for all 6 names,
-- so no information is lost by collapsing them.
--
-- 006 deduped training_programs but missed this child table because the
-- duplicate programs had already been removed by the time the checklist was
-- inspected; the orphaned item copies remained pointing at program_id = 1.
--
-- SAFETY
-- training_checklist_items has no inbound foreign keys (verified via
-- pg_constraint), so nothing references the item_ids being deleted and there
-- is no cascade risk. The lowest item_id in each group is kept so that the
-- surviving rows are the original inserts.

BEGIN;

CREATE TABLE IF NOT EXISTS training_checklist_items_dedupe_backup AS
SELECT *, NOW() AS backed_up_at FROM training_checklist_items;

-- Guard: refuse to run if any duplicate group is not byte-identical.
DO $$
DECLARE
    divergent integer;
BEGIN
    SELECT COUNT(*) INTO divergent
      FROM (
        SELECT item_name
          FROM training_checklist_items
         GROUP BY item_name
        HAVING COUNT(DISTINCT (program_id, description, is_required,
                               sort_order, completion_verification_required)) > 1
      ) q;

    IF divergent > 0 THEN
        RAISE EXCEPTION
            'Refusing to dedupe: % checklist item name(s) have differing content. Reconcile manually.',
            divergent;
    END IF;
END $$;

DELETE FROM training_checklist_items a
      USING training_checklist_items b
      WHERE a.item_id > b.item_id
        AND a.program_id = b.program_id
        AND a.item_name  = b.item_name;

-- Prevent the duplicates from being re-seeded.
CREATE UNIQUE INDEX IF NOT EXISTS uq_training_checklist_items_program_name
    ON training_checklist_items (program_id, item_name);

COMMIT;

-- VERIFICATION (expected results)
--   SELECT COUNT(*) FROM training_checklist_items;  -> 6 (was 12)
--   duplicate (program_id, item_name) groups ......  -> 0
--   re-inserting an existing item .................  -> rejected (UniqueViolation)
