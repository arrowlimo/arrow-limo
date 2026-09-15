-- Fix two receipts.banking_transaction_id / duplicate issues found via
-- grouped (SUM per bank transaction) three-way reconciliation, scoped to
-- cheque-linked banking transactions only.
--
-- 1) Receipt 139623 (Heffner Auto Finance, $1475.25, 2013-04-29, L-9 lease)
--    was wrongly linked to banking_transaction 78263 -- which is actually
--    the UNRELATED $700.00 "CHQ 168 JEANNIE SHILLINGTON" cheque (a totally
--    different amount/payee). The real $1475.25 Heffner Auto transaction
--    (78251, "CHQ 24 HEFFNER AUTO (L-9)", same date/amount) already has its
--    own reverse-FK (banking_transactions.receipt_id = 139623) pointing
--    back at this exact receipt -- the forward FK on the receipt was simply
--    never updated to match. Fix the forward link so both sides agree.
UPDATE receipts
SET banking_transaction_id = 78251
WHERE receipt_id = 139623 AND banking_transaction_id = 78263;

-- 2) Receipt 216371 ("CIBC", $500.00, GL 5710 Bank Fees & Service Charges,
--    2012-10-29) is a duplicate of receipt 214985 (ARROW LIMOUSINE, $500.00,
--    GL 1099 transfer/suspense) -- both linked to the SAME banking_transaction
--    100033 (cheque 281, "CHQ 281 TRANSFER OF FUNDS", a single $500
--    inter-account transfer). 216371 double-counts the transfer as a "Bank
--    Fees" expense when it is really the same $500 movement already
--    correctly captured by 214985. Mark it a duplicate and exclude it from
--    reports rather than deleting (preserves audit trail).
UPDATE receipts
SET exclude_from_reports = TRUE,
    potential_duplicate = TRUE,
    parent_receipt_id = 214985
WHERE receipt_id = 216371;
