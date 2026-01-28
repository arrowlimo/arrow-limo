-- Create staging tables for driver pay ingestion
BEGIN;

-- Optional: dedicated schema
-- CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS public.staging_driver_pay_files (
    id               BIGSERIAL PRIMARY KEY,
    file_path        TEXT NOT NULL,
    file_name        TEXT NOT NULL,
    file_type        TEXT NOT NULL,
    source_hash      TEXT,
    rows_parsed      INTEGER DEFAULT 0,
    status           TEXT DEFAULT 'pending', -- pending|parsed|error|loaded
    error_message    TEXT,
    first_txn_date   DATE,
    last_txn_date    DATE,
    processed_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (file_path)
);

CREATE TABLE IF NOT EXISTS public.staging_driver_pay (
    id               BIGSERIAL PRIMARY KEY,
    file_id          BIGINT REFERENCES public.staging_driver_pay_files(id) ON DELETE CASCADE,
    source_row_id    TEXT,
    source_line_no   INTEGER,
    txn_date         DATE,
    driver_name      TEXT,
    driver_id        TEXT,
    pay_type         TEXT, -- e.g., cheque, payroll, bank_txn, gratuity, expense, etc.
    gross_amount     NUMERIC(14,2),
    expense_amount   NUMERIC(14,2),
    net_amount       NUMERIC(14,2),
    amount           NUMERIC(14,2), -- alias for generic amount when gross/expense/net unknown
    currency         TEXT DEFAULT 'CAD',
    memo             TEXT,
    check_no         TEXT,
    account          TEXT,
    category         TEXT,
    vendor           TEXT,
    source_sheet     TEXT,
    source_file      TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (file_id, COALESCE(source_row_id,''), COALESCE(source_line_no,0), COALESCE(txn_date,'1900-01-01'), COALESCE(amount,0), COALESCE(memo,''))
);

-- Indexes to speed up validation/dedup
CREATE INDEX IF NOT EXISTS idx_sdp_txn_date ON public.staging_driver_pay(txn_date);
CREATE INDEX IF NOT EXISTS idx_sdp_driver_name ON public.staging_driver_pay(driver_name);
CREATE INDEX IF NOT EXISTS idx_sdp_file_id ON public.staging_driver_pay(file_id);

-- Validation findings table
CREATE TABLE IF NOT EXISTS public.staging_driver_pay_issues (
    id           BIGSERIAL PRIMARY KEY,
    file_id      BIGINT REFERENCES public.staging_driver_pay_files(id) ON DELETE CASCADE,
    row_id       BIGINT REFERENCES public.staging_driver_pay(id) ON DELETE CASCADE,
    issue_type   TEXT NOT NULL, -- missing_date|missing_driver|amount_zero|dup_candidate|no_charter_match|other
    issue_detail TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

COMMIT;
