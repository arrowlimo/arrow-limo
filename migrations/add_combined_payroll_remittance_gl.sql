-- Add a single combined liability GL account for everyday/voluntary CRA
-- remittance payments (paid in person at a bank, covering CPP + EI + Income
-- Tax withholding together) so a normal remittance doesn't have to be split
-- across 2310/2320/2330 every time. This is distinct from 5255, which is
-- reserved for CRA-enforced Requirement to Pay / third-party seizure
-- payments the bank makes without the business's initiation.

INSERT INTO chart_of_accounts (
    account_code, parent_account, account_name, account_type, description,
    is_active, account_level, is_header_account, normal_balance, qb_account_type,
    is_business_expense, is_tax_applicable, requires_employee, requires_vehicle
) VALUES
    ('2305', '2300', 'Payroll Remittance Payment (Combined CPP/EI/Tax)', 'Liability',
        'Voluntary combined CPP + EI + Income Tax remittance payments made '
        'directly to CRA (e.g. paid in person at a bank). Reduces the '
        'payroll liability already accrued when payroll was run. Not to be '
        'confused with 5255, which is for CRA-enforced Requirement to Pay '
        '(third-party) seizures.',
        TRUE, 2, FALSE, 'CREDIT', 'OtherCurrentLiability', TRUE, FALSE, FALSE, FALSE)
ON CONFLICT (account_code) DO NOTHING;
