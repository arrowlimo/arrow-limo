-- 019: Remove Karen Richard CHQ 205 receipt from Michael Richard CHQ 207.
--
-- Receipt 139731 is Karen Richard's CHQ 205 reimbursement: 2013-06-17,
-- $1,500.00. It was incorrectly linked to transaction 78571, which is
-- Michael Richard's CHQ 207 payment: 2013-07-03, $1,666.11.
--
-- There is no eligible CHQ 205 / $1,500 banking transaction in the checkbook
-- account within the permitted five-day window, so this receipt must remain
-- unlinked until actual bank evidence is available. Do not link it by payee
-- similarity or an unrelated same-dollar transaction.

BEGIN;

CREATE TABLE IF NOT EXISTS backup_karen_chq205_mislink_20260913 AS
SELECT r.*
FROM receipts r
WHERE FALSE;

INSERT INTO backup_karen_chq205_mislink_20260913
SELECT r.*
FROM receipts r
WHERE r.receipt_id = 139731
  AND r.receipt_date = DATE '2013-07-02'
  AND r.vendor_name = 'KAREN RICHARD'
  AND r.gross_amount = 1500.00
  AND r.description = 'CHQ 205 Karen Richard Reimbursement'
  AND r.banking_transaction_id = 78571
  AND NOT EXISTS (
      SELECT 1
      FROM backup_karen_chq205_mislink_20260913 backup
      WHERE backup.receipt_id = r.receipt_id
  );

UPDATE receipts
SET banking_transaction_id = NULL,
    updated_at = NOW()
WHERE receipt_id = 139731
  AND receipt_date = DATE '2013-07-02'
  AND vendor_name = 'KAREN RICHARD'
  AND gross_amount = 1500.00
  AND description = 'CHQ 205 Karen Richard Reimbursement'
  AND banking_transaction_id = 78571;

COMMIT;
