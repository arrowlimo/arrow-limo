-- Add invoice_number column to receipts table on Neon database
-- Run this in Neon SQL Editor: https://console.neon.tech/app/projects/

-- Check if column exists first
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name = 'invoice_number'
    ) THEN
        ALTER TABLE receipts ADD COLUMN invoice_number VARCHAR(100);
        RAISE NOTICE 'Added invoice_number column';
    ELSE
        RAISE NOTICE 'Column invoice_number already exists';
    END IF;
END $$;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_receipts_invoice_number ON receipts(invoice_number);

-- Verify the column was added
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'receipts' 
  AND column_name IN ('invoice_number', 'card_last_4', 'fuel_amount', 'reimbursement_amount')
ORDER BY column_name;
