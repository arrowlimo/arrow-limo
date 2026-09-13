-- 018: Remove the duplicate CHQ 129 Fibrenew receipt linked to CHQ 18.
--
-- Receipt 221545 (2013-01-30, Fibrenew, $1,268.48, "CHQ 129") was imported
-- with source_reference 69203 and incorrectly linked to bank transaction
-- 69203 (CHQ 18, 2012-08-09, $1,207.50). The canonical CHQ 129 receipt is
-- 139496, already correctly linked to banking transaction 77808.
--
-- Do not relink 221545 to 77808: that would leave two receipts for CHQ 129.
-- Preserve it first, then remove only this proven exact duplicate.

BEGIN;

CREATE TABLE IF NOT EXISTS backup_mislinked_duplicate_chq129_20260913 AS
SELECT r.*
FROM receipts r
WHERE FALSE;

INSERT INTO backup_mislinked_duplicate_chq129_20260913
SELECT r.*
FROM receipts r
WHERE r.receipt_id = 221545
  AND r.receipt_date = DATE '2013-01-30'
  AND r.vendor_name = 'FIBRENEW'
  AND r.gross_amount = 1268.48
  AND r.description = 'CHQ 129'
  AND r.banking_transaction_id = 69203
  AND NOT EXISTS (
      SELECT 1
      FROM backup_mislinked_duplicate_chq129_20260913 backup
      WHERE backup.receipt_id = r.receipt_id
  );

DELETE FROM receipts r
WHERE r.receipt_id = 221545
  AND r.receipt_date = DATE '2013-01-30'
  AND r.vendor_name = 'FIBRENEW'
  AND r.gross_amount = 1268.48
  AND r.description = 'CHQ 129'
  AND r.banking_transaction_id = 69203
  AND EXISTS (
      SELECT 1
      FROM receipts canonical
      WHERE canonical.receipt_id = 139496
        AND canonical.receipt_date = DATE '2013-01-30'
        AND canonical.vendor_name = 'FIBRENEW'
        AND canonical.gross_amount = 1268.48
        AND canonical.banking_transaction_id = 77808
  );

COMMIT;
