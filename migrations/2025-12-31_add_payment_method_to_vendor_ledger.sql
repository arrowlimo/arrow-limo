-- Add payment_method column to vendor_account_ledger
BEGIN;

ALTER TABLE vendor_account_ledger
  ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) CHECK (
    payment_method IS NULL OR payment_method::text = ANY (
      ARRAY[
        'cash',
        'check',
        'credit_card',
        'debit_card',
        'bank_transfer',
        'trade_of_services',
        'unknown',
        'credit_adjustment'
      ]::text[]
    )
  );

-- Add index for payment_method queries
CREATE INDEX IF NOT EXISTS idx_vendor_ledger_payment_method
  ON vendor_account_ledger(payment_method)
  WHERE payment_method IS NOT NULL;

COMMIT;
