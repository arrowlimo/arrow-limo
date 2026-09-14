-- Add a dedicated GL account for CRA "Requirement to Pay" / third-party
-- remittance enforcement payments. These are legally distinct from a normal
-- payroll remittance: CRA sends a Requirement to Pay letter directly to the
-- bank, which is then legally obligated to redirect funds from the company
-- account straight to CRA to satisfy an existing tax debt (payroll arrears,
-- GST/HST arrears, etc.) rather than paying the company. Historically these
-- were dumped into 6300 "Government Fees & Licenses" alongside routine
-- licensing costs, which buries this enforcement activity in an unrelated
-- bucket. Isolating it lets the business clearly see/report on any CRA
-- enforcement action separately from ordinary remittances.

INSERT INTO chart_of_accounts (
    account_code, parent_account, account_name, account_type, description,
    is_active, account_level, is_header_account, normal_balance, qb_account_type,
    is_business_expense, is_tax_applicable, requires_employee, requires_vehicle
) VALUES
    ('5255', '5200', 'CRA Third-Party Remittance (Requirement to Pay)', 'Expense',
        'Payments the bank sends directly to CRA under a Requirement to Pay '
        '(third-party demand) letter, satisfying an existing tax debt rather '
        'than a routine remittance.',
        TRUE, 2, FALSE, 'DEBIT', 'Expense', TRUE, FALSE, FALSE, FALSE)
ON CONFLICT (account_code) DO NOTHING;

-- Tag the one receipt already labeled exactly "REVENUE CANADA 3RD PARTY
-- REMITTANCE" that had no GL code assigned yet.
UPDATE receipts
SET gl_code = '5255'
WHERE receipt_id = 140024
  AND vendor_name = 'REVENUE CANADA 3RD PARTY REMITTANCE'
  AND (gl_code IS NULL OR gl_code = '');
