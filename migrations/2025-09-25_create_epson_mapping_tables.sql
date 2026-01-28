-- Create Epson mapping tables to align Receipt Manager lists with our accounting system

BEGIN;

CREATE TABLE IF NOT EXISTS epson_classifications_map (
    epson_classification TEXT PRIMARY KEY,
    mapped_account_id INTEGER NULL REFERENCES chart_of_accounts(account_id),
    mapped_account_name TEXT NULL,
    mapped_cash_flow_category TEXT NULL,
    confidence NUMERIC(5,2) NULL,
    alternatives TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed',
    notes TEXT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS epson_pay_accounts_map (
    epson_pay_account TEXT PRIMARY KEY,
    mapped_account_id INTEGER NULL REFERENCES chart_of_accounts(account_id),
    mapped_account_name TEXT NULL,
    confidence NUMERIC(5,2) NULL,
    alternatives TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed',
    notes TEXT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS epson_pay_methods_map (
    epson_pay_method TEXT PRIMARY KEY,
    canonical_method TEXT NULL,
    confidence NUMERIC(5,2) NULL,
    alternatives TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed',
    notes TEXT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

COMMIT;
