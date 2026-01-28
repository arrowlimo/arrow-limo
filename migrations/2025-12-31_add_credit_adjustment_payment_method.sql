-- Add credit_adjustment to allowed payment_method values
BEGIN;

ALTER TABLE payments
  DROP CONSTRAINT IF EXISTS chk_payment_method,
  ADD CONSTRAINT chk_payment_method CHECK (
    payment_method::text = ANY (
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

COMMIT;
