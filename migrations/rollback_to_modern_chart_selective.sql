-- Migration: Rollback 2010 chart restoration and keep modern chart
-- Purpose: Remove 2010 codes that conflict with better modern structure
-- Keep useful unique 2010 codes that don't duplicate modern functionality
-- Created: 2026-02-02

BEGIN;

-- Remove all the 2010 restored codes
DELETE FROM chart_of_accounts 
WHERE restored_from_2010 = TRUE;

-- Now selectively add back only unique/useful 2010 codes that complement modern structure

-- Historical vehicle lease tracking (useful for pre-2012 reconciliation)
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active, description) VALUES
('1902', 'L-2 2006 Lincoln Town Car (Historical)', 'FixedAsset', FALSE, '2010 historical vehicle lease account'),
('1904', 'L-4 2006 Lincoln Town Car (Historical)', 'FixedAsset', FALSE, '2010 historical vehicle lease account'),
('1906', 'L-6 2001 Lincoln Town Car Limo (Historical)', 'FixedAsset', FALSE, '2010 historical vehicle lease account'),
('1907', 'L-7 2003 Ford Excursion (Historical)', 'FixedAsset', FALSE, '2010 historical vehicle lease account'),
('1908', 'L-8 2008 Ford Expedition (Historical)', 'FixedAsset', FALSE, '2010 historical vehicle lease account'),
('2802', 'L-2 Lease Liability (Historical)', 'Liability', FALSE, '2010 historical lease liability'),
('2804', 'L-4 Lease Liability (Historical)', 'Liability', FALSE, '2010 historical lease liability'),
('2806', 'L-6 Lease Liability (Historical)', 'Liability', FALSE, '2010 historical lease liability'),
('2807', 'L-7 Lease Liability (Historical)', 'Liability', FALSE, '2010 historical lease liability'),
('2808', 'L-8 Lease Liability (Historical)', 'Liability', FALSE, '2010 historical lease liability')
ON CONFLICT (account_code) DO NOTHING;

-- Useful equity share classes (for corporate structure flexibility)
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active, description) VALUES
('3110', 'Class A Voting Shares', 'Equity', TRUE, 'Voting shares class A'),
('3120', 'Class B Voting Shares', 'Equity', TRUE, 'Voting shares class B'),
('3700', 'Retained Earnings (Historical)', 'Equity', TRUE, 'Corporate retained earnings')
ON CONFLICT (account_code) DO NOTHING;

-- Add specific useful expense categories that modern chart lacks
INSERT INTO chart_of_accounts (account_code, account_name, account_type, is_active, description) VALUES
-- Amortization (CRA requires separate tracking)
('6040', 'Amortization Expense', 'Expense', TRUE, 'CCA/Amortization for fixed assets'),

-- Detailed advertising breakdown
('6130', 'Print Media Advertising', 'Expense', TRUE, 'Print advertising expenses'),
('6150', 'Radio/TV Advertising', 'Expense', TRUE, 'Broadcast media advertising'),

-- Home office (common CRA deduction)
('6810', 'Home Office - Mortgage Interest', 'Expense', TRUE, 'Proportional mortgage interest for home office'),
('6820', 'Home Office - Property Taxes', 'Expense', TRUE, 'Proportional property taxes for home office'),
('6830', 'Home Office - Insurance', 'Expense', TRUE, 'Proportional home insurance for home office'),

-- Bad debt (CRA specific requirement)
('6990', 'Bad Debt Expense', 'Expense', TRUE, 'Uncollectable accounts receivable')
ON CONFLICT (account_code) DO NOTHING;

-- Clean up the tracking column
ALTER TABLE chart_of_accounts DROP COLUMN IF EXISTS restored_from_2010;

COMMIT;

-- Verification
SELECT 
    account_type,
    COUNT(*) as count,
    COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_count
FROM chart_of_accounts
GROUP BY account_type
ORDER BY account_type;
