-- QuickBooks Unified Staging Table with Deduplication
-- Consolidates all QB file formats into a single staging table
-- Handles: QBW exports (CSV/IIF), Journal CSVs, GL CSVs, Square transactions, bank statements

CREATE TABLE IF NOT EXISTS qb_transactions_staging (
    staging_id SERIAL PRIMARY KEY,
    
    -- Source tracking
    source_file VARCHAR(500) NOT NULL,
    source_hash VARCHAR(64) NOT NULL,  -- SHA256 of (source_file + transaction_date + account + debit + credit + memo)
    source_type VARCHAR(50),  -- 'qb_export', 'journal', 'gl', 'square', 'bank_statement', 'iif'
    import_batch VARCHAR(100),
    import_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Transaction core
    transaction_date DATE NOT NULL,
    posted_date DATE,
    
    -- Accounting fields
    account_code VARCHAR(100),
    account_name VARCHAR(200),
    gl_account VARCHAR(100),
    
    debit_amount DECIMAL(12,2),
    credit_amount DECIMAL(12,2),
    amount DECIMAL(12,2),  -- For sources that only have one amount column
    
    -- Descriptive fields
    transaction_type VARCHAR(100),
    memo TEXT,
    description TEXT,
    reference VARCHAR(100),
    
    -- Entity tracking
    vendor_name VARCHAR(200),
    customer_name VARCHAR(200),
    employee_name VARCHAR(200),
    
    -- Additional context
    check_number VARCHAR(50),
    invoice_number VARCHAR(50),
    transaction_id_external VARCHAR(100),  -- Original QB/Square transaction ID
    
    -- Metadata
    year_extracted INTEGER GENERATED ALWAYS AS (EXTRACT(YEAR FROM transaction_date)) STORED,
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of INTEGER REFERENCES qb_transactions_staging(staging_id),
    notes TEXT,
    
    -- Deduplication constraint
    CONSTRAINT unique_transaction UNIQUE (source_hash)
);

-- Indexes for performance and deduplication
CREATE INDEX IF NOT EXISTS idx_qb_staging_date ON qb_transactions_staging(transaction_date);
CREATE INDEX IF NOT EXISTS idx_qb_staging_year ON qb_transactions_staging(year_extracted);
CREATE INDEX IF NOT EXISTS idx_qb_staging_source ON qb_transactions_staging(source_file);
CREATE INDEX IF NOT EXISTS idx_qb_staging_type ON qb_transactions_staging(source_type);
CREATE INDEX IF NOT EXISTS idx_qb_staging_account ON qb_transactions_staging(account_code, account_name);
CREATE INDEX IF NOT EXISTS idx_qb_staging_hash ON qb_transactions_staging(source_hash);
CREATE INDEX IF NOT EXISTS idx_qb_staging_duplicate ON qb_transactions_staging(is_duplicate);

-- View for year-by-year summary
CREATE OR REPLACE VIEW qb_staging_year_summary AS
SELECT 
    year_extracted as year,
    source_type,
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE is_duplicate = FALSE) as unique_records,
    COUNT(*) FILTER (WHERE is_duplicate = TRUE) as duplicate_records,
    SUM(COALESCE(debit_amount, 0)) as total_debits,
    SUM(COALESCE(credit_amount, 0)) as total_credits,
    COUNT(DISTINCT source_file) as source_files
FROM qb_transactions_staging
GROUP BY year_extracted, source_type
ORDER BY year_extracted DESC, source_type;

-- View for source file summary
CREATE OR REPLACE VIEW qb_staging_source_summary AS
SELECT 
    source_file,
    source_type,
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE is_duplicate = FALSE) as unique_records,
    MIN(transaction_date) as earliest_date,
    MAX(transaction_date) as latest_date,
    SUM(COALESCE(debit_amount, 0)) as total_debits,
    SUM(COALESCE(credit_amount, 0)) as total_credits,
    MAX(import_timestamp) as last_import
FROM qb_transactions_staging
GROUP BY source_file, source_type
ORDER BY last_import DESC;