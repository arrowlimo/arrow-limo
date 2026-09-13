-- 020: Restore the authoritative Karen Richard CHQ 205 three-way chain.
--
-- The $1,500 bank transaction 78556 dated 2013-07-02 already identifies
-- receipt 139731. Receipt 139731 has the same date and amount. Checkbook row
-- 434 is Karen Richard's CHQ 205 for the same exact amount. Its recorded
-- cleared date is earlier than the bank posting date, but is retained as
-- historical source data rather than rewritten.

BEGIN;

CREATE TABLE IF NOT EXISTS backup_karen_chq205_chain_restore_20260913 AS
SELECT r.*
FROM receipts r
WHERE FALSE;

INSERT INTO backup_karen_chq205_chain_restore_20260913
SELECT r.*
FROM receipts r
WHERE r.receipt_id = 139731
  AND r.receipt_date = DATE '2013-07-02'
  AND r.vendor_name = 'KAREN RICHARD'
  AND r.gross_amount = 1500.00
  AND r.description = 'CHQ 205 Karen Richard Reimbursement'
  AND r.banking_transaction_id IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM backup_karen_chq205_chain_restore_20260913 backup
      WHERE backup.receipt_id = r.receipt_id
  );

CREATE TABLE IF NOT EXISTS backup_karen_chq205_checkbook_link_20260913 AS
SELECT cr.*
FROM cheque_register cr
WHERE FALSE;

INSERT INTO backup_karen_chq205_checkbook_link_20260913
SELECT cr.*
FROM cheque_register cr
WHERE cr.id = 434
  AND cr.account_number = '903990106011'
  AND cr.cheque_number = '205'
  AND cr.payee = 'KAREN RICHARD'
  AND cr.amount = 1500.00
  AND cr.banking_transaction_id IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM backup_karen_chq205_checkbook_link_20260913 backup
      WHERE backup.id = cr.id
  );

UPDATE receipts
SET banking_transaction_id = 78556,
    updated_at = NOW()
WHERE receipt_id = 139731
  AND receipt_date = DATE '2013-07-02'
  AND vendor_name = 'KAREN RICHARD'
  AND gross_amount = 1500.00
  AND description = 'CHQ 205 Karen Richard Reimbursement'
  AND banking_transaction_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM banking_transactions bt
      WHERE bt.transaction_id = 78556
        AND bt.account_number = '903990106011'
        AND bt.transaction_date = DATE '2013-07-02'
        AND bt.description = 'DEPOSIT CHQ'
        AND bt.debit_amount = 1500.00
        AND bt.receipt_id = 139731
  );

UPDATE cheque_register
SET banking_transaction_id = 78556
WHERE id = 434
  AND account_number = '903990106011'
  AND cheque_number = '205'
  AND payee = 'KAREN RICHARD'
  AND amount = 1500.00
  AND banking_transaction_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM receipts r
      WHERE r.receipt_id = 139731
        AND r.banking_transaction_id = 78556
  );

COMMIT;
