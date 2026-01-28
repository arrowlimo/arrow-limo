-- Create vendor accounts and ledger tables (idempotent)
CREATE TABLE IF NOT EXISTS vendor_accounts (
  account_id BIGSERIAL PRIMARY KEY,
  canonical_vendor VARCHAR(255) NOT NULL UNIQUE,
  display_name VARCHAR(255),
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vendor_account_ledger (
  ledger_id BIGSERIAL PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES vendor_accounts(account_id) ON DELETE CASCADE,
  entry_date DATE NOT NULL,
  entry_type VARCHAR(20) NOT NULL,
  amount NUMERIC(14,2) NOT NULL,
  balance_after NUMERIC(14,2),
  source_table VARCHAR(50),
  source_id VARCHAR(100),
  external_ref VARCHAR(100),
  match_confidence NUMERIC(4,2),
  notes TEXT,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  CONSTRAINT entry_type_ck CHECK (entry_type IN ('INVOICE','PAYMENT','ADJUSTMENT'))
);

-- Prevent duplicate links when source_table/source_id provided
CREATE UNIQUE INDEX IF NOT EXISTS uniq_vendor_ledger_source
ON vendor_account_ledger (account_id, source_table, source_id);
