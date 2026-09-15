-- Fix July/August 2013 cheque receipt rows whose receipt-side vendor names
-- and GL codes were auto-generated incorrectly from incomplete/bare banking
-- descriptions. The cheque register and enriched banking rows are the source
-- of truth for cheque payee/memo; these receipt rows were the bad side.
--
-- Problem examples from the receipt search screen:
--   - CHQ 211 showed CANADA REVENUE AGENCY / GL 6300, but cheque register
--     says DOUG REDMOND PAYROLL.
--   - CHQ 214 showed HEATHER GULLISON / GL 5210, but cheque register says
--     FIBRENEW RENT.
--   - CHQ 216 showed SARAH ODWALD / GL 6900, but cheque register and bank
--     row say A LIMO & SEDAN SERVICE.
--   - CHQ 218 and CHQ 222 had bare bank descriptions and unlinked cheque
--     register rows, leaving receipts as CHQ ### / CHQ ### NONE with GL 6900.

-- Enrich the remaining bare banking descriptions for CHQ 218/222 and link
-- the matching cheque_register rows now that the check_number/amount line up.
UPDATE banking_transactions
SET description = 'CHQ 218 THE DRIVE',
    check_recipient = 'THE DRIVE',
    reconciliation_status = 'reconciled',
    verified = TRUE,
    reconciled_at = COALESCE(reconciled_at, NOW()),
    reconciliation_notes = COALESCE(reconciliation_notes || ' | ', '') ||
        'Cheque audit 2026-09-14: enriched from cheque_register row 445.'
WHERE transaction_id = 78678;

UPDATE cheque_register
SET banking_transaction_id = 78678
WHERE id = 445
  AND cheque_number = '218'
  AND banking_transaction_id IS NULL;

UPDATE banking_transactions
SET description = 'CHQ 222 MARC COTE PAYROLL',
    check_recipient = 'MARC COTE',
    reconciliation_status = 'reconciled',
    verified = TRUE,
    reconciled_at = COALESCE(reconciled_at, NOW()),
    reconciliation_notes = COALESCE(reconciliation_notes || ' | ', '') ||
        'Cheque audit 2026-09-14: enriched from cheque_register row 449.'
WHERE transaction_id = 78751;

UPDATE cheque_register
SET banking_transaction_id = 78751
WHERE id = 449
  AND cheque_number = '222'
  AND banking_transaction_id IS NULL;

-- Correct receipt-side vendor/GL naming for the bad rows in the visible block.
-- Use the app's authoritative GL column (gl_account_code) and set gl_code too
-- for legacy consistency.
UPDATE receipts
SET vendor_name = 'CHQ 211 DOUG REDMOND PAYROLL',
    description = 'CHQ 211 DOUG REDMOND PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139751;

UPDATE receipts
SET vendor_name = 'CHQ 214 FIBRENEW RENT',
    description = 'CHQ 214 FIBRENEW RENT',
    gl_account_code = '5440',
    gl_code = '5440',
    payment_method = 'cheque'
WHERE receipt_id = 139758;

UPDATE receipts
SET vendor_name = 'CHQ 215 KEVIN BOULLEY PAYROLL',
    description = 'CHQ 215 KEVIN BOULLEY PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139743;

UPDATE receipts
SET vendor_name = 'CHQ 216 A LIMO & SEDAN SERVICE',
    description = 'CHQ 216 A LIMO & SEDAN SERVICE',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139750;

UPDATE receipts
SET vendor_name = 'CHQ 218 THE DRIVE',
    description = 'CHQ 218 THE DRIVE',
    gl_account_code = '6150',
    gl_code = '6150',
    payment_method = 'cheque'
WHERE receipt_id = 139772;

UPDATE receipts
SET vendor_name = 'CHQ 222 MARC COTE PAYROLL',
    description = 'CHQ 222 MARC COTE PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139795;

UPDATE receipts
SET vendor_name = 'CHQ 223 MICHAEL RICHARD PAYROLL',
    description = 'CHQ 223 MICHAEL RICHARD PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139804;

-- Correct related-party repayment coding for the cheque 219 loan repayment.
UPDATE receipts
SET vendor_name = 'CHQ 219 KAREN RICHARD LOAN REPAYMENT',
    description = 'CHQ 219 KAREN RICHARD LOAN REPAYMENT',
    gl_account_code = '2550',
    gl_code = '2550',
    payment_method = 'cheque'
WHERE receipt_id = 139782;

-- Correct receipt 139760's vendor/GL only. Do NOT link cheque_register row
-- 439 automatically because the cheque register amount ($668.78) and the
-- bank/receipt amount ($668.38) differ by $0.40; that needs source-document
-- review before changing the cheque register.
UPDATE receipts
SET vendor_name = 'CHQ 212 MARC COTE PAYROLL',
    description = 'CHQ 212 MARC COTE PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139760;

UPDATE banking_transactions
SET description = 'CHQ 212 MARC COTE PAYROLL',
    check_recipient = 'MARC COTE'
WHERE transaction_id = 78630;

UPDATE banking_transactions
SET description = 'CHQ 219 KAREN RICHARD LOAN REPAYMENT'
WHERE transaction_id = 78711;
