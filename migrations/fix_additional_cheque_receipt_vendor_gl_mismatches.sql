-- Fix additional cheque-linked receipt rows where the bank/checkbook link is
-- correct but the receipt-side vendor and GL code were copied from the wrong
-- payee or left as 6900/incorrect category. These were found by comparing:
--   cheque_register.payee/memo -> banking_transactions.description/check_number
--   -> receipts.vendor_name/gl_account_code
--
-- The cheque register and banking row agree on payee, amount, and cheque
-- number in these cases; the receipt row is the bad side.

UPDATE receipts
SET vendor_name = 'CHQ 220 JESSE GORDON PAYROLL',
    description = 'CHQ 220 JESSE GORDON PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139789;

UPDATE receipts
SET vendor_name = 'CHQ 225 JEANNIE SHILLINGTON PAYROLL ADVANCE',
    description = 'CHQ 225 JEANNIE SHILLINGTON PAYROLL ADVANCE',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139808;

UPDATE receipts
SET vendor_name = 'CHQ 226 JESSE GORDON PAYROLL ARREARS',
    description = 'CHQ 226 JESSE GORDON PAYROLL ARREARS',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139807;

UPDATE receipts
SET vendor_name = 'CHQ 228 FIBRENEW RENT',
    description = 'CHQ 228 FIBRENEW RENT',
    gl_account_code = '5440',
    gl_code = '5440',
    payment_method = 'cheque'
WHERE receipt_id = 139821;

UPDATE receipts
SET vendor_name = 'CHQ 231 PAT FRASER PAYROLL',
    description = 'CHQ 231 PAT FRASER PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139827;

UPDATE receipts
SET vendor_name = 'CHQ 234 MARC COTE PAYROLL',
    description = 'CHQ 234 MARC COTE PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139829;

UPDATE receipts
SET vendor_name = 'CHQ 257 KAREN RICHARD REIMBURSEMENT FOR CREDIT CARD',
    description = 'CHQ 257 KAREN RICHARD REIMBURSEMENT FOR CREDIT CARD',
    gl_account_code = '2550',
    gl_code = '2550',
    payment_method = 'cheque'
WHERE receipt_id = 139941;

UPDATE receipts
SET vendor_name = 'CHQ 257 PAUL MANSELL',
    description = 'CHQ 257 PAUL MANSELL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 150493;

UPDATE receipts
SET vendor_name = 'CHQ 261 JAMES ROSS PAYROLL',
    description = 'CHQ 261 JAMES ROSS PAYROLL',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 139948;

UPDATE receipts
SET vendor_name = 'CHQ 269 FIBRENEW RENT',
    description = 'CHQ 269 FIBRENEW RENT',
    gl_account_code = '5440',
    gl_code = '5440',
    payment_method = 'cheque'
WHERE receipt_id = 139960;

UPDATE receipts
SET vendor_name = 'CHQ 270 FIBRENEW UTILITIES',
    description = 'CHQ 270 FIBRENEW UTILITIES',
    gl_account_code = '5440',
    gl_code = '5440',
    payment_method = 'cheque'
WHERE receipt_id = 139961;

UPDATE receipts
SET vendor_name = 'CHQ 272 FULL SPECTRUM PAINT AND BODY',
    description = 'CHQ 272 FULL SPECTRUM PAINT AND BODY JEANNIE SHILLINGTON FAULT ACCIDENT',
    gl_account_code = '5120',
    gl_code = '5120',
    payment_method = 'cheque'
WHERE receipt_id = 139972;

UPDATE receipts
SET vendor_name = 'CHQ 273 COMMUNITY NETWORK SOLUTIONS',
    description = 'CHQ 273 COMMUNITY NETWORK SOLUTIONS INV 10057',
    gl_account_code = '5430',
    gl_code = '5430',
    payment_method = 'cheque'
WHERE receipt_id = 139978;

UPDATE receipts
SET vendor_name = 'CHQ 273 BARRY FORESBERG',
    description = 'CHQ 273 BARRY FORESBERG',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 142474;

UPDATE banking_transactions
SET description = 'CHQ 273 BARRY FORESBERG',
    check_recipient = 'BARRY FORESBERG'
WHERE transaction_id = 82088;

-- Final cleanups from the mismatch scan:
--   - specific people incorrectly stored as UNCLASSIFIED EXPENSE / 5710
--   - CRA source deduction remittance sitting in generic 6300
--   - Heffner lease payment in repair/maintenance instead of lease payments
--   - radio advertising shorthand/header code normalized to the specific
--     radio/TV advertising account.
UPDATE receipts
SET vendor_name = 'CHQ 209 106.7 THE DRIVE',
    description = 'CHQ 209 106.7 THE DRIVE - radio advertising',
    gl_account_code = '6150',
    gl_code = '6150',
    payment_method = 'cheque'
WHERE receipt_id = 141284;

UPDATE receipts
SET vendor_name = 'CHQ 210 JEANNIE SHILLINGTON',
    description = 'CHQ 210 JEANNIE SHILLINGTON',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 150391;

UPDATE receipts
SET vendor_name = 'CHQ 211 CRA SOURCE DEDUCTION REMITTANCE',
    description = 'CHQ 211 CRA SOURCE DED PMT',
    gl_account_code = '2305',
    gl_code = '2305',
    payment_method = 'cheque'
WHERE receipt_id = 141337;

UPDATE receipts
SET vendor_name = 'CHQ 212 ANDREW LAFONT',
    description = 'CHQ 212 ANDREW LAFONT',
    gl_account_code = '5210',
    gl_code = '5210',
    payment_method = 'cheque'
WHERE receipt_id = 150371;

UPDATE receipts
SET vendor_name = 'CHQ 224 HEFFNER AUTO FINANCE',
    description = 'CHQ 224 HEFFNER AUTO FINANCE (L-10)',
    gl_account_code = '5150',
    gl_code = '5150',
    payment_method = 'cheque'
WHERE receipt_id = 141963;
