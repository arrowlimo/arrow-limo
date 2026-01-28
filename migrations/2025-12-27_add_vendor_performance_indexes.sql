-- Add performance indexes for vendor account operations
-- Run: psql -h localhost -U postgres -d almsdata -f migrations/2025-12-27_add_vendor_performance_indexes.sql

-- Index for canonical vendor lookups in receipts
CREATE INDEX IF NOT EXISTS idx_receipts_canonical_vendor ON receipts(canonical_vendor);

-- Index for vendor name lookups (used in matching)
CREATE INDEX IF NOT EXISTS idx_receipts_vendor_name ON receipts(vendor_name);

-- Composite index for banking transaction date/amount queries (payment matching)
CREATE INDEX IF NOT EXISTS idx_banking_transactions_date_amounts 
ON banking_transactions(transaction_date, debit_amount, credit_amount);

-- Index for banking transaction descriptions (text search)
CREATE INDEX IF NOT EXISTS idx_banking_transactions_description 
ON banking_transactions USING gin(to_tsvector('english', description));

-- Composite index for vendor ledger queries
CREATE INDEX IF NOT EXISTS idx_vendor_ledger_account_date 
ON vendor_account_ledger(account_id, entry_date);

-- Index for source lookups in vendor ledger
CREATE INDEX IF NOT EXISTS idx_vendor_ledger_source 
ON vendor_account_ledger(source_table, source_id);

-- Performance optimization completed
