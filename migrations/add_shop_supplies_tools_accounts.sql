-- Add Shop Supplies / Small Tools / Maintenance Supplies / Tools & Equipment accounts.
-- The user's originally proposed codes (6100, 6150, 6200, 1500) are already in use by
-- unrelated accounts (Staff Meals & Entertainment, Radio/TV Advertising,
-- Client Hospitality - Charter Supplies, Fixed Assets - Equipment), so new codes were
-- chosen that fit the existing numbering scheme without conflict.

INSERT INTO chart_of_accounts (
    account_code, parent_account, account_name, account_type, description,
    is_active, account_level, is_header_account, normal_balance, qb_account_type,
    is_business_expense, is_tax_applicable, requires_employee, requires_vehicle
) VALUES
    ('5481', '5480', 'Shop Supplies', 'Expense',
        'Consumable shop/garage supplies (fasteners, cleaning supplies, small hardware, etc.)',
        TRUE, 2, FALSE, 'DEBIT', 'Expense', TRUE, FALSE, FALSE, FALSE),
    ('5482', '5480', 'Small Tools Expense', 'Expense',
        'Low-cost hand tools and small equipment expensed rather than capitalized (screwdrivers, wrenches, etc.)',
        TRUE, 2, FALSE, 'DEBIT', 'Expense', TRUE, FALSE, FALSE, FALSE),
    ('5483', '5480', 'Maintenance Supplies', 'Expense',
        'Supplies used for facility/vehicle maintenance work',
        TRUE, 2, FALSE, 'DEBIT', 'Expense', TRUE, FALSE, FALSE, FALSE),
    ('1540', '1500', 'Tools & Equipment', 'Asset',
        'Capitalized tools & equipment purchases (fixed asset)',
        TRUE, 2, FALSE, 'DEBIT', 'FixedAsset', TRUE, FALSE, FALSE, FALSE)
ON CONFLICT (account_code) DO NOTHING;
