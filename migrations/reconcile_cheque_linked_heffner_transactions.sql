-- Mark 18 banking_transactions linked to cheque_register rows as reconciled.
-- All 18 are Heffner Auto Finance lease payments (L-9/L-10/L-11, 3 separate
-- vehicle leases each with its own recurring monthly amount) plus one Arrow
-- Limousine transfer, all still tagged reconciliation_status='unreconciled'
-- despite the cheque_register row itself being CLEARED (or, for cheque 230,
-- already-handled NSF) with a cheque number, date, payee, and dollar amount
-- that all match cleanly and consistently with the surrounding monthly
-- sequence (verified: cheque_register.amount == banking_transactions.
-- debit_amount for every single linked row system-wide, zero mismatches).
-- This was simply a backlog item in the reconciliation workflow, not an
-- unresolved discrepancy.

UPDATE banking_transactions
SET reconciliation_status = 'reconciled',
    verified = TRUE,
    reconciled_at = NOW(),
    reconciliation_notes = COALESCE(reconciliation_notes || ' | ', '') ||
        'Reconciled via cheque book audit 2026-09-14: matches cheque_register row (payee, date, amount all verified).'
WHERE transaction_id IN (
    99963, 99807, 99780, 99781, 99804, 99714, 99873, 99878, 99929, 99930,
    99931, 99964, 99808, 99879, 99719, 99720, 99750, 100033
);
