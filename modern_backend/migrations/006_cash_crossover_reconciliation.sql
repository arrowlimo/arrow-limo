-- 2012 cash crossover reconciliation:
-- - Payments ledger tracks charter cash/cheque inflows.
-- - Receipts ledger tracks expense-side cash/reimbursement outflows.
-- - Funding source and source_category keep owner/RPL vs employee vs business separate.

BEGIN;

CREATE TABLE IF NOT EXISTS cash_crossover_reconciliation (
    reconciliation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_table TEXT NOT NULL,
    source_id BIGINT NOT NULL,
    row_type TEXT NOT NULL,
    flow_direction TEXT NOT NULL,
    source_date DATE NOT NULL,
    source_amount NUMERIC(12,2) NOT NULL,
    payment_method TEXT,
    source_category TEXT NOT NULL,
    funding_source TEXT NOT NULL,
    classification_basis TEXT NOT NULL,
    charter_id INTEGER,
    reserve_number TEXT,
    banking_transaction_id INTEGER,
    cash_box_transaction_id INTEGER,
    gl_account_code TEXT,
    gl_account_name TEXT,
    receipt_source TEXT,
    created_from_banking BOOLEAN,
    is_driver_reimbursement BOOLEAN,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reconciliation_status TEXT NOT NULL DEFAULT 'unreviewed',
    confidence NUMERIC(5,2) NOT NULL DEFAULT 1.00,
    matched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cash_crossover_source UNIQUE (source_table, source_id),
    CONSTRAINT ck_cash_crossover_row_type CHECK (row_type IN ('payment', 'receipt')),
    CONSTRAINT ck_cash_crossover_flow_direction CHECK (flow_direction IN ('in', 'out'))
);

CREATE INDEX IF NOT EXISTS idx_cash_crossover_recon_source_date
    ON cash_crossover_reconciliation (source_date DESC, source_table, source_id);

CREATE INDEX IF NOT EXISTS idx_cash_crossover_recon_category
    ON cash_crossover_reconciliation (row_type, source_category, funding_source);

CREATE INDEX IF NOT EXISTS idx_cash_crossover_recon_charter
    ON cash_crossover_reconciliation (charter_id, reserve_number);

CREATE INDEX IF NOT EXISTS idx_cash_crossover_recon_banking
    ON cash_crossover_reconciliation (banking_transaction_id)
    WHERE banking_transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cash_crossover_recon_cash_box
    ON cash_crossover_reconciliation (cash_box_transaction_id)
    WHERE cash_box_transaction_id IS NOT NULL;

CREATE OR REPLACE FUNCTION cash_crossover_reconciliation_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cash_crossover_reconciliation_touch_updated_at
ON cash_crossover_reconciliation;

CREATE TRIGGER trg_cash_crossover_reconciliation_touch_updated_at
BEFORE UPDATE ON cash_crossover_reconciliation
FOR EACH ROW
EXECUTE FUNCTION cash_crossover_reconciliation_touch_updated_at();

CREATE OR REPLACE VIEW v_cash_crossover_monthly_summary AS
SELECT
    date_trunc('month', source_date)::date AS month,
    row_type,
    flow_direction,
    source_category,
    funding_source,
    COUNT(*) AS item_count,
    SUM(source_amount) AS total_amount
FROM cash_crossover_reconciliation
GROUP BY 1, 2, 3, 4, 5;

COMMIT;
