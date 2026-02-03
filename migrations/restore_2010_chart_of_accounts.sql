-- Migration: Restore 2010 Chart of Accounts
-- Purpose: Add missing 2010 GL codes to match historical accounting structure
-- Created: 2026-02-02
-- Note: This preserves existing accounts and adds missing 2010 accounts

BEGIN;

-- First, let's check if we need to handle any conflicts
-- Create a backup reference
CREATE TABLE IF NOT EXISTS chart_of_accounts_backup_2026 AS 
SELECT * FROM chart_of_accounts;

-- Bank accounts (missing from current)
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('990', 'Banks', 'Asset', TRUE),
('0965', 'Cash', 'Asset', TRUE),
('1050', 'Petty Cash', 'Asset', TRUE),
('1090', 'CIBC', 'Asset', TRUE),
('1105', 'Global', 'Asset', TRUE),
('1150', 'MasterCard', 'Asset', TRUE),
('1160', 'American Express', 'Asset', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Accounts Receivable and Other Current Assets
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('1190', 'Payroll Account', 'OtherCurrentAsset', TRUE),
('1260', 'Due to Proprietor I/C', 'OtherCurrentAsset', TRUE),
('1490', 'Prepaid lease charges', 'OtherCurrentAsset', TRUE),
('1550', 'Employee Advances', 'OtherCurrentAsset', TRUE),
('1570', 'Short Term P/R Loans', 'OtherCurrentAsset', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Fixed Assets - Fleet and Equipment
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('1610', 'Garage Construction', 'FixedAsset', TRUE),
('1700', 'Fleet', 'FixedAsset', TRUE),
('1710', 'Class 16 Limousines', 'FixedAsset', TRUE),
('1720', 'Accum. Dep''n Limousines', 'FixedAsset', TRUE),
('1730', 'Class 16 Sedans', 'FixedAsset', TRUE),
('1740', 'Accum. Dep''n Sedans', 'FixedAsset', TRUE),
('1810', 'Class 10 Computers', 'FixedAsset', TRUE),
('1820', 'Accum Dep''n Computers', 'FixedAsset', TRUE),
('1830', 'Class 8 Communications', 'FixedAsset', TRUE),
('1840', 'Accum. Dep''n Communications', 'FixedAsset', TRUE),
('1850', 'Furniture & Fixtures', 'FixedAsset', TRUE),
('1860', 'Accum. Dep''n Furniture & Fix.', 'FixedAsset', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Leased Vehicles
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('1900', 'Leased Limousines', 'FixedAsset', TRUE),
('1902', 'L-2 2006 Lincoln Town Car', 'FixedAsset', TRUE),
('1904', 'L-4 2006 Lincoln Town Car', 'FixedAsset', TRUE),
('1906', 'L-6 2001 Lincoln Town Car Limo', 'FixedAsset', TRUE),
('1907', 'L-7 2003 Ford Excursion', 'FixedAsset', TRUE),
('1908', 'L-8 2008 Ford Expedition', 'FixedAsset', TRUE),
('1932', 'Amortize 2006 Lincoln Town L2', 'FixedAsset', TRUE),
('1934', 'Amortize 2006 Lincoln Town L4', 'FixedAsset', TRUE),
('1936', 'Amorize 2001 Lincoln Town Car', 'FixedAsset', TRUE),
('1937', 'Amortize 2003 Ford Excursion', 'FixedAsset', TRUE),
('1938', 'Amortize 2008 Ford Expedition', 'FixedAsset', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Liabilities
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('2050', 'CIBC Visa', 'Liability', TRUE),
('2060', 'Capital One', 'Liability', TRUE),
('2430', 'Crash Fund Liability', 'Liability', TRUE),
('2450', 'Payroll Liabilities', 'Liability', TRUE),
('2480', 'Accrued Wages Payable', 'Liability', TRUE),
('2490', 'Accrued Vacation Pay', 'Liability', TRUE),
('2510', 'GST Payable', 'Liability', TRUE),
('2610', 'Line of Credit', 'Liability', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Loans & Leases
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('2795', 'Loans & Leases', 'Liability', TRUE),
('2800', 'Auto Lease', 'Liability', TRUE),
('2802', 'L-2 2006 Lincoln Town Car', 'Liability', TRUE),
('2804', 'L-4 2006 Lincoln Town Car', 'Liability', TRUE),
('2806', 'L-6 2001 Lincoln Town Car Limo', 'Liability', TRUE),
('2807', 'L-7 2003 Ford Excursion', 'Liability', TRUE),
('2808', 'L-8 2008 Ford Expedition', 'Liability', TRUE),
('2910', 'ShareHolder Loan', 'Liability', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Equity - Share Classes
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('3110', 'Class ''A'' Voting Shares', 'Equity', TRUE),
('3120', 'Class ''B'' Voting Shares', 'Equity', TRUE),
('3130', 'Class ''C'' Non-voting Shares', 'Equity', TRUE),
('3210', 'Class ''D'' Preferred Shares', 'Equity', TRUE),
('3220', 'Class ''E'' Preferred Shares', 'Equity', TRUE),
('3600', 'Opening Bal Equity', 'Equity', TRUE),
('3700', 'Retained Earnings', 'Equity', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Income
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('4200', 'Sedan Service', 'Income', TRUE),
('4790', 'Miscellaneous Income', 'Income', TRUE),
('4810', 'Collection Surcharges', 'Income', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Cost of Goods Sold / Operating Expenses
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('5190', 'Parking & Misc Ticket expense', 'Expense', TRUE),
('5260', 'Liability Insurance', 'Expense', TRUE),
('5265', 'Safety & Liability Expense', 'Expense', TRUE),
('5270', 'Safety Equipment', 'Expense', TRUE),
('5290', 'Security', 'Expense', TRUE),
('5480', 'Equipment & Supplies', 'Expense', TRUE),
('5495', 'Staffing', 'Expense', TRUE),
('5550', 'Vacation Pay Expense', 'Expense', TRUE),
('5570', 'Casual Labour', 'Expense', TRUE),
('5590', 'Recruiting', 'Expense', TRUE),
('5655', 'Contract Services', 'Expense', TRUE),
('5670', 'Drivers & Limousine Services', 'Expense', TRUE),
('5680', 'Subcontractor -Facilities Maint', 'Expense', TRUE),
('5790', 'Internet Service', 'Expense', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- 6000 Series - Operating Expenses (the big missing section)
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active) VALUES
('6040', 'Amortization Expense', 'Expense', TRUE),
('6090', 'Advertising & Promotion', 'Expense', TRUE),
('6130', 'Print Media', 'Expense', TRUE),
('6150', 'AirTime Media', 'Expense', TRUE),
('6170', 'Web Site', 'Expense', TRUE),
('6210', 'Promotional Services', 'Expense', TRUE),
('6230', 'Donations & Promotional Gifts', 'Expense', TRUE),
('6240', 'Trade Shows', 'Expense', TRUE),
('6250', 'Meals & Entertainment', 'Expense', TRUE),
('6255', 'Bank Charges & Interest expense', 'Expense', TRUE),
('6260', 'Service Charges', 'Expense', TRUE),
('6270', 'Credit Card Charges', 'Expense', TRUE),
('6280', 'Loan Interest & Finance Charges', 'Expense', TRUE),
('6290', 'Credit Insurance', 'Expense', TRUE),
('6410', 'Co. Vehicle Fuel & Oil', 'Expense', TRUE),
('6420', 'Co. Vehicle R&M', 'Expense', TRUE),
('6440', 'Co. Vehicle Insurance', 'Expense', TRUE),
('6460', 'Travel Expense', 'Expense', TRUE),
('6470', 'Delivery & Freight', 'Expense', TRUE),
('6480', 'Dividend Expense', 'Expense', TRUE),
('6490', 'Dues & Subscriptions', 'Expense', TRUE),
('6510', 'Office Supplies- Consumable', 'Expense', TRUE),
('6520', 'Office Small Tools & Supplies', 'Expense', TRUE),
('6525', 'Repair & Mtnce.', 'Expense', TRUE),
('6530', 'Office General Repairs & Mtnce', 'Expense', TRUE),
('6540', 'Office Equipment R&M', 'Expense', TRUE),
('6545', 'Office Utilities', 'Expense', TRUE),
('6560', 'Electrical', 'Expense', TRUE),
('6570', 'Heating', 'Expense', TRUE),
('6580', 'Water & Waste', 'Expense', TRUE),
('6700', 'Professional Fees', 'Expense', TRUE),
('6710', 'Accounting Fees', 'Expense', TRUE),
('6720', 'Legal', 'Expense', TRUE),
('6750', 'Consulting', 'Expense', TRUE),
('6790', 'Storage Expense', 'Expense', TRUE),
('6805', 'Home Office ___% Use', 'Expense', TRUE),
('6810', 'Mortgage Interest', 'Expense', TRUE),
('6820', 'Property Taxes', 'Expense', TRUE),
('6830', 'House Insurance', 'Expense', TRUE),
('6850', 'Janitorial Exp', 'Expense', TRUE),
('6855', 'Garage Expense', 'Expense', TRUE),
('6860', 'Construction -Preliminary Exp.', 'Expense', TRUE),
('6862', 'Licenses & Permits', 'Expense', TRUE),
('6864', 'Professional Fees', 'Expense', TRUE),
('6866', 'Tools & Supplies', 'Expense', TRUE),
('6870', 'Operating Supplies', 'Expense', TRUE),
('6920', 'Taxes- 6930 Fed., 6940 Prov.', 'Expense', TRUE),
('6990', 'Uncollectable Bad Debt', 'Expense', TRUE),
('6999', 'Uncategorized Expenses', 'Expense', TRUE)
ON CONFLICT (account_code) DO NOTHING;

-- Add metadata tracking
ALTER TABLE chart_of_accounts 
ADD COLUMN IF NOT EXISTS restored_from_2010 BOOLEAN DEFAULT FALSE;

UPDATE chart_of_accounts 
SET restored_from_2010 = TRUE
WHERE account_code IN (
    '990', '0965', '1050', '1090', '1105', '1150', '1160',
    '1190', '1260', '1490', '1550', '1570',
    '1610', '1700', '1710', '1720', '1730', '1740', '1810', '1820', '1830', '1840', '1850', '1860',
    '1900', '1902', '1904', '1906', '1907', '1908', '1932', '1934', '1936', '1937', '1938',
    '2050', '2060', '2430', '2450', '2480', '2490', '2510', '2610',
    '2795', '2800', '2802', '2804', '2806', '2807', '2808', '2910',
    '3110', '3120', '3130', '3210', '3220', '3600', '3700',
    '4200', '4790', '4810',
    '5190', '5260', '5265', '5270', '5290', '5480', '5495', '5550', '5570', '5590', '5655', '5670', '5680', '5790',
    '6040', '6090', '6130', '6150', '6170', '6210', '6230', '6240', '6250', '6255', '6260', '6270', '6280', '6290',
    '6410', '6420', '6440', '6460', '6470', '6480', '6490',
    '6510', '6520', '6525', '6530', '6540', '6545', '6560', '6570', '6580',
    '6700', '6710', '6720', '6750', '6790',
    '6805', '6810', '6820', '6830', '6850', '6855', '6860', '6862', '6864', '6866', '6870',
    '6920', '6990', '6999'
);

COMMIT;

-- Verification query
SELECT 
    COUNT(*) as total_accounts,
    SUM(CASE WHEN restored_from_2010 = TRUE THEN 1 ELSE 0 END) as restored_2010_accounts,
    SUM(CASE WHEN restored_from_2010 IS NULL OR restored_from_2010 = FALSE THEN 1 ELSE 0 END) as existing_accounts
FROM chart_of_accounts;
