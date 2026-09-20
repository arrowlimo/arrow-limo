CREATE TABLE IF NOT EXISTS tax_year_settings (
    tax_year INT PRIMARY KEY,
    previous_loss_balance NUMERIC(14,2) NOT NULL DEFAULT 0,
    gst_previous_balance NUMERIC(14,2) NOT NULL DEFAULT 0,
    gst_previous_credit NUMERIC(14,2) NOT NULL DEFAULT 0,
    federal_basic_personal_amount NUMERIC(14,2) NOT NULL DEFAULT 16129,
    provincial_basic_personal_amount NUMERIC(14,2) NOT NULL DEFAULT 22323,
    owner_safe_threshold NUMERIC(14,2) NOT NULL DEFAULT 16129,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE tax_year_settings
    ADD COLUMN IF NOT EXISTS federal_basic_personal_amount
        NUMERIC(14,2) NOT NULL DEFAULT 16129,
    ADD COLUMN IF NOT EXISTS provincial_basic_personal_amount
        NUMERIC(14,2) NOT NULL DEFAULT 22323;

ALTER TABLE tax_year_settings
    ALTER COLUMN owner_safe_threshold SET DEFAULT 16129;
