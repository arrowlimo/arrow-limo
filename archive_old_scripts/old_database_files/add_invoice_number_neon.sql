-- Run this in Neon SQL Editor to add missing receipt columns
-- https://console.neon.tech/app/projects

ALTER TABLE receipts ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(100);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS card_last_4 VARCHAR(4);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS reimbursement_amount NUMERIC(10,2);

CREATE INDEX IF NOT EXISTS idx_receipts_invoice_number ON receipts(invoice_number);
CREATE INDEX IF NOT EXISTS idx_receipts_card_last4 ON receipts(card_last_4);

-- Verify columns were added
SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale
FROM information_schema.columns 
WHERE table_name = 'receipts' 
  AND column_name IN ('invoice_number', 'card_last_4', 'fuel_amount', 'reimbursement_amount')
ORDER BY column_name;
