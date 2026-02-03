-- Add escrow_hold to payment_method allowed values
-- First drop the existing check constraint
ALTER TABLE payments 
DROP CONSTRAINT chk_payment_method;

-- Add new check constraint with escrow_hold included
ALTER TABLE payments
ADD CONSTRAINT chk_payment_method 
CHECK (payment_method IN ('credit_card', 'unknown', 'escrow_hold', 'square', 'check', 'cash', 'etransfer'));

-- Verify the constraint exists
SELECT constraint_name, pg_get_constraintdef(oid)
FROM pg_constraint 
WHERE conname = 'chk_payment_method';
