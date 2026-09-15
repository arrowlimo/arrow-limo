-- Enrich 89 cheque-linked banking_transactions.description fields that are
-- just a bare "chq ###" / "CHQ ###" placeholder, using the full payee/memo
-- text already present in the linked cheque_register row (which the user
-- confirmed is the accurate source -- the mistakes are in receipts and
-- missing banking descriptions, not the cheque register).
--
-- Example: banking_transactions.description 'chq 125' -> cheque_register
-- memo 'CHQ 125 DOUG REDMOND' for the same linked row.

UPDATE banking_transactions bt
SET description = cr.memo
FROM cheque_register cr
WHERE cr.banking_transaction_id = bt.transaction_id
  AND bt.description ~* '^(CHQ|CHECK|CHEQUE)\s*[0-9]*\s*$'
  AND cr.memo IS NOT NULL
  AND TRIM(cr.memo) <> '';
