-- =====================================================================
-- Phase 2a: Fixes for Column Extension Errors
-- Date: October 16, 2025
-- Purpose: Fix foreign key reference and data type issues
-- =====================================================================

\echo 'Fixing payments table (invoices FK issue)...'

-- Drop the problematic FK constraint if it exists, we'll add it after invoices table is created
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_applied_to_invoice_fkey;

-- Add columns without FK constraint for now
ALTER TABLE payments
ADD COLUMN IF NOT EXISTS qb_payment_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS applied_to_invoice INTEGER,  -- FK will be added in Phase 2b
ADD COLUMN IF NOT EXISTS qb_trans_num VARCHAR(50),
ADD COLUMN IF NOT EXISTS payment_account VARCHAR(50),
ADD COLUMN IF NOT EXISTS reference_number VARCHAR(50),
ADD COLUMN IF NOT EXISTS is_deposited BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS deposit_to_account VARCHAR(50);

-- Default qb_payment_type based on payment_method
UPDATE payments 
SET qb_payment_type = CASE 
    WHEN payment_method = 'Credit Card' THEN 'CreditCard'
    WHEN payment_method = 'Cash' THEN 'Cash'
    WHEN payment_method = 'Cheque' THEN 'Check'
    WHEN payment_method = 'E-Transfer' THEN 'EFT'
    WHEN payment_method LIKE '%Square%' THEN 'CreditCard'
    ELSE 'Other'
END
WHERE qb_payment_type IS NULL;

-- Set default payment account for credit cards
UPDATE payments 
SET payment_account = '1099' -- Undeposited Funds
WHERE payment_account IS NULL AND qb_payment_type = 'CreditCard';

SELECT 'payments fixed' AS status, 
       COUNT(*) FILTER (WHERE qb_payment_type IS NOT NULL) AS with_qb_type
FROM payments;

\echo 'Fixing clients table (country column issue)...'

-- Add province/country if not exists
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS province VARCHAR(50),
ADD COLUMN IF NOT EXISTS country VARCHAR(50) DEFAULT 'Canada';

-- Update tax codes for Canadian clients (where we can infer)
UPDATE clients 
SET tax_code = 'GST',
    sales_tax_code = 'GST',
    country = 'Canada'
WHERE tax_code IS NULL AND (province IS NOT NULL OR postal_code LIKE '%[A-Z][0-9][A-Z]%');

SELECT 'clients fixed' AS status,
       COUNT(*) FILTER (WHERE tax_code IS NOT NULL) AS with_tax_code
FROM clients;

\echo 'Fixing payables table (aging calculation)...'

-- Fix aging calculation - due_date is likely TEXT, need to cast or handle properly
-- Check what data type due_date actually is
DO $$ 
DECLARE
    col_type TEXT;
BEGIN
    SELECT data_type INTO col_type
    FROM information_schema.columns
    WHERE table_name = 'payables' AND column_name = 'due_date';
    
    IF col_type = 'date' THEN
        UPDATE payables 
        SET aging_days = (CURRENT_DATE - due_date)::integer
        WHERE due_date IS NOT NULL AND aging_days IS NULL;
    ELSIF col_type = 'text' THEN
        UPDATE payables 
        SET aging_days = (CURRENT_DATE - due_date::date)::integer
        WHERE due_date IS NOT NULL 
          AND due_date ~ '^\d{4}-\d{2}-\d{2}$'
          AND aging_days IS NULL;
    END IF;
    
    RAISE NOTICE 'due_date column type: %', col_type;
END $$;

SELECT 'payables fixed' AS status,
       COUNT(*) FILTER (WHERE aging_days IS NOT NULL) AS with_aging
FROM payables;

\echo ''
\echo '====================================================================='
\echo '✓ Phase 2a Fixes Complete!'
\echo '====================================================================='

-- Final column count verification
SELECT 
    'chart_of_accounts' AS table_name,
    COUNT(*) AS column_count
FROM information_schema.columns 
WHERE table_name = 'chart_of_accounts'

UNION ALL

SELECT 'payments', COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'payments'

UNION ALL

SELECT 'clients', COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'clients'

UNION ALL

SELECT 'payables', COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'payables';
