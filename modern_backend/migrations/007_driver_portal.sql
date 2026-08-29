CREATE TABLE IF NOT EXISTS driver_receipt_submissions (
    receipt_id INTEGER PRIMARY KEY REFERENCES receipts(receipt_id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    paid_from_float BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_driver_receipt_submissions_employee
    ON driver_receipt_submissions (employee_id, submitted_at DESC);

CREATE TABLE IF NOT EXISTS driver_float_returns (
    return_id BIGSERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    charter_id INTEGER NULL REFERENCES charters(charter_id),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    notes TEXT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_driver_float_returns_employee
    ON driver_float_returns (employee_id, submitted_at DESC);
