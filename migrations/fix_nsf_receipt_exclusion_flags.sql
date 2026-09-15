-- Fix NSF receipts that are still being counted as real expenses even
-- though their underlying banking_transaction is flagged is_nsf_charge =
-- TRUE (i.e. the cheque bounced and the money came back). Without this fix
-- these amounts double up: once as the (never-actually-paid) original
-- disbursement, and again wherever the debt was actually settled (e.g. by
-- e-transfer replacement, as explicitly noted for the two Heffner Auto
-- cases below).
--
-- This mirrors the treatment already correctly applied elsewhere in the
-- system to receipts tied to other is_nsf_charge=TRUE transactions (Kevin
-- Boulley cheque 121, Tredd Mayfair cheque 275, etc: is_nsf=TRUE,
-- exclude_from_reports=TRUE).
--
-- Verified before applying:
--   - 139452 (Heffner Auto Finance $2525.25, cheque 30 / L-10 lease):
--     banking_transactions.reconciliation_notes = "NSF - replacement paid
--     by e-transfer" -- confirms the real payment happened separately.
--   - 217303 (Heffner Auto Finance $1900.50, cheque 230 / L-11 lease):
--     same NSF event pattern, is_nsf_charge = TRUE.
--   - 139890 (Kevin Kosik $811.75, cheque 122 payroll): is_nsf_charge = TRUE.
--   - 142849 (Dusten Townsend $279.78, cheque 279 payroll): is_nsf_charge = TRUE.
--   - 150646 (Parr's Automotive $1000.00, cheque 282): is_nsf_charge = TRUE.
--
-- Also confirmed (no fix needed, already correct): cheque 135 (Jeannie
-- Shillington NSF $1216.20) and cheque 94 (Jack Carter NSF $1885.65) have
-- NO receipt at all in the system -- which is the correct state for money
-- that bounced and was never re-sent; no phantom expense was recorded for
-- either.

UPDATE receipts
SET is_nsf = TRUE, exclude_from_reports = TRUE
WHERE receipt_id IN (139452, 217303, 139890, 142849, 150646)
  AND (is_nsf IS DISTINCT FROM TRUE OR exclude_from_reports IS DISTINCT FROM TRUE);

-- One more: receipt 150681 (banking_transaction 82544, "CHQ 285 ARROW
-- LIMOUSINE" NSF transfer) is the second of two banking_transactions
-- recording the same real $200 NSF event as receipt 143326 (which is
-- already correctly is_nsf=TRUE/excluded, GL 6900). 150681 was miscoded to
-- 5710 "Bank Fees & Service Charges" (wrong -- $200 is the face value of
-- the bounced cheque itself, not a small bank fee) and not excluded,
-- meaning this NSF transfer was being counted as a real $200 expense.
-- banking_transactions.reconciliation_notes on 82544 already flags this
-- exact issue: "linked receipt flagged NON_EXPENSE_REV ... Review category
-- if needed." Recode to match its sibling's treatment.
UPDATE receipts
SET is_nsf = TRUE, exclude_from_reports = TRUE, gl_account_code = '6900'
WHERE receipt_id = 150681;
