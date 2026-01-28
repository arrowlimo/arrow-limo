BEGIN;

-- Mark existing placeholders using the same rules as the trigger
UPDATE charters
SET is_placeholder = true
WHERE (status IN ('refund_pair','AUDIT_REVIEW'))
   OR ((COALESCE(total_amount_due,0) = 0 AND COALESCE(paid_amount,0) = 0)
       AND reserve_number ~ '^(REF|AUDIT)');

COMMIT;
