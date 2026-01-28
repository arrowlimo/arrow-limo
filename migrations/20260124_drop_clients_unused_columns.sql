-- Drop unused/legacy client columns (payment preference; retain LMS id)
ALTER TABLE clients
    DROP COLUMN IF EXISTS preferred_payment_method,
    DROP COLUMN IF EXISTS resale_number,
    DROP COLUMN IF EXISTS is_taxable,
    DROP COLUMN IF EXISTS square_customer_id;
