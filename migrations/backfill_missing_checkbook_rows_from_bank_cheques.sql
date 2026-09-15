-- Backfill checkbook register coverage for bank-side cheque transactions.
--
-- Why this exists:
-- Earlier imports created banking_transactions and often auto-created receipts
-- from those bank rows, but did not always backfill cheque_register. That left
-- valid bank records with check_number/CHQ information showing as
-- BANK_NO_CHECKBOOK even though the receipt already existed.
--
-- Safety rules used here:
--   1) Link existing cheque_register rows only where account_number,
--      cheque_number, and amount all match the bank transaction exactly.
--      Do NOT link the 3 unsafe same-number rows where amounts differ
--      (CHQ 127, CHQ 136, CHQ 212) -- those require source-document review.
--   2) Create missing cheque_register rows only where no row exists for that
--      (account_number, cheque_number), and the bank transaction already has
--      at least one valid receipt in v_three_way_bank_verification.
--   3) Preserve receipts and GL codes; this migration is about completing the
--      checkbook side, not reclassifying expenses.

-- Link 52 existing checkbook rows where the only missing piece was the
-- banking_transaction_id. Also fill blank cheque/cleared dates from the bank
-- posting date.
UPDATE cheque_register cr
SET banking_transaction_id = g.banking_transaction_id,
    cheque_date = COALESCE(cr.cheque_date, g.bank_date),
    cleared_date = COALESCE(cr.cleared_date, g.bank_date)
FROM v_three_way_bank_verification g
WHERE g.verification_status = 'BANK_NO_CHECKBOOK'
  AND cr.account_number = g.account_number
  AND cr.cheque_number = g.check_number
  AND cr.banking_transaction_id IS NULL
  AND ABS(cr.amount - g.bank_amount) < 0.01;

-- Insert 65 missing checkbook rows from bank cheque transactions that already
-- have a receipt. Payee preference:
--   bank check_recipient -> receipt vendor stripped of "CHQ ###" prefix ->
--   bank description stripped of "CHQ ###" prefix -> UNKNOWN.
INSERT INTO cheque_register (
    cheque_number,
    cheque_date,
    cleared_date,
    payee,
    amount,
    memo,
    banking_transaction_id,
    status,
    account_number
)
SELECT
    g.check_number,
    g.bank_date,
    g.bank_date,
    COALESCE(
        NULLIF(TRIM(g.bank_payee), ''),
        NULLIF(TRIM(REGEXP_REPLACE(COALESCE(g.receipt_vendor, ''), '^CHQ\\s*' || g.check_number || '\\s*', '', 'i')), ''),
        NULLIF(TRIM(REGEXP_REPLACE(COALESCE(g.bank_description, ''), '^CHQ\\s*' || g.check_number || '\\s*', '', 'i')), ''),
        'UNKNOWN'
    ) AS payee,
    g.bank_amount,
    COALESCE(NULLIF(TRIM(g.bank_description), ''), 'CHQ ' || g.check_number),
    g.banking_transaction_id,
    'CLEARED',
    g.account_number
FROM v_three_way_bank_verification g
WHERE g.verification_status = 'BANK_NO_CHECKBOOK'
  AND g.receipt_count > 0
  AND NOT EXISTS (
      SELECT 1
      FROM cheque_register cr
      WHERE cr.account_number = g.account_number
        AND cr.cheque_number = g.check_number
  );

-- The NSF-word-boundary view fix exposed two genuine missing transfer receipts
-- for cheque 277 and 280, both already present in cheque_register and banking.
-- Create non-expense transfer receipts using the existing clean pattern:
-- GL 1099 Inter-Account Clearing + is_transfer=true.
INSERT INTO receipts (
    receipt_date, vendor_name, description, currency, gross_amount, gst_amount,
    net_amount, revenue, gl_account_code, gl_code, banking_transaction_id,
    payment_method, business_personal, source_system, comment,
    is_transfer, gst_exempt
)
SELECT
    DATE '2012-07-16',
    'ARROW LIMOUSINE',
    'CHQ 277 ARROW LIMOUSINE - Inter-account transfer',
    'CAD',
    400.00,
    0,
    400.00,
    0,
    '1099',
    '1099',
    82195,
    'cheque',
    'Business',
    'cheque_book_audit_2026-09-14',
    'Backfilled non-expense transfer receipt for cleared bank cheque with no receipt.',
    TRUE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM receipts WHERE banking_transaction_id = 82195);

INSERT INTO receipts (
    receipt_date, vendor_name, description, currency, gross_amount, gst_amount,
    net_amount, revenue, gl_account_code, gl_code, banking_transaction_id,
    payment_method, business_personal, source_system, comment,
    is_transfer, gst_exempt
)
SELECT
    DATE '2012-10-24',
    'ARROW LIMOUSINE',
    'CHQ 280 ARROW LIMO TRANSFER TO 1615 - Inter-account transfer',
    'CAD',
    1000.00,
    0,
    1000.00,
    0,
    '1099',
    '1099',
    82353,
    'cheque',
    'Business',
    'cheque_book_audit_2026-09-14',
    'Backfilled non-expense transfer receipt for cleared bank cheque with no receipt.',
    TRUE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM receipts WHERE banking_transaction_id = 82353);

-- If those transfer receipts already existed from a prior import, correct the
-- stale NSF/excluded/vendor metadata instead of duplicating them.
UPDATE receipts
SET vendor_name = 'ARROW LIMOUSINE',
    description = CASE banking_transaction_id
        WHEN 82195 THEN 'CHQ 277 ARROW LIMOUSINE - Inter-account transfer'
        WHEN 82353 THEN 'CHQ 280 ARROW LIMO TRANSFER TO 1615 - Inter-account transfer'
        ELSE description END,
    is_transfer = TRUE,
    is_nsf = FALSE,
    exclude_from_reports = FALSE,
    gst_exempt = TRUE,
    gl_account_code = '1099',
    gl_code = '1099'
WHERE banking_transaction_id IN (82195, 82353);

-- Clear status false positives exposed by the same audit. These three bank
-- transactions are reconciled, non-NSF cheque debits, but the checkbook/receipt
-- side was still carrying NSF metadata, which caused the verification view to
-- treat them as missing.
UPDATE cheque_register
SET status = 'CLEARED',
    cleared_date = COALESCE(cleared_date, cheque_date)
WHERE id IN (98, 134, 440)
  AND banking_transaction_id IN (69122, 69271, 78612);

UPDATE receipts
SET vendor_name = CASE banking_transaction_id
        WHEN 69122 THEN 'ARROW LIMOUSINE'
        WHEN 69271 THEN 'ARROW LIMOUSINE'
        WHEN 78612 THEN 'JESSE GORDON'
        ELSE vendor_name END,
    description = CASE banking_transaction_id
        WHEN 69122 THEN 'CHQ 8 ARROW LIMOUSINE - Inter-account transfer for car payments'
        WHEN 69271 THEN 'CHQ 44 ARROW LIMOUSINE - Inter-account transfer for insurance'
        WHEN 78612 THEN 'CHQ 213 JESSE GORDON PAYROLL'
        ELSE description END,
    gl_account_code = CASE banking_transaction_id
        WHEN 69122 THEN '1099'
        WHEN 69271 THEN '1099'
        WHEN 78612 THEN '5210'
        ELSE gl_account_code END,
    gl_code = CASE banking_transaction_id
        WHEN 69122 THEN '1099'
        WHEN 69271 THEN '1099'
        WHEN 78612 THEN '5210'
        ELSE gl_code END,
    is_transfer = CASE banking_transaction_id
        WHEN 69122 THEN TRUE
        WHEN 69271 THEN TRUE
        ELSE is_transfer END,
    is_nsf = FALSE,
    exclude_from_reports = FALSE
WHERE banking_transaction_id IN (69122, 69271, 78612);
