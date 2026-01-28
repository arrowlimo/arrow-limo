-- Create vendor synonyms table for dynamic vendor name mapping
-- Run: psql -h localhost -U postgres -d almsdata -f migrations/2025-12-27_create_vendor_synonyms.sql

CREATE TABLE IF NOT EXISTS vendor_synonyms (
  synonym_id BIGSERIAL PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES vendor_accounts(account_id) ON DELETE CASCADE,
  synonym VARCHAR(255) NOT NULL,
  match_type VARCHAR(20) NOT NULL DEFAULT 'exact',
  confidence NUMERIC(4,2) NOT NULL DEFAULT 0.95,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  CONSTRAINT match_type_ck CHECK (match_type IN ('exact', 'contains', 'regex'))
);

-- Unique constraint: one synonym can only map to one account
CREATE UNIQUE INDEX IF NOT EXISTS uniq_vendor_synonym ON vendor_synonyms(UPPER(synonym));

-- Index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_vendor_synonyms_account ON vendor_synonyms(account_id);

-- Seed with existing keyword mappings from code
INSERT INTO vendor_synonyms (account_id, synonym, match_type, confidence)
SELECT 
  va.account_id,
  s.synonym,
  'contains' as match_type,
  0.95 as confidence
FROM vendor_accounts va
CROSS JOIN LATERAL (VALUES
  ('LEASE FINANCE GROUP', 'LEASE FINANCE GROUP'),
  ('LEASE FINANCE GROUP', 'LEASE FINANCE GR'),
  ('LEASE FINANCE GROUP', 'LFG BUSINESS PAD'),
  ('LEASE FINANCE GROUP', 'LFG'),
  ('PRE AUTHORIZED DEBIT', 'PRE AUTH'),
  ('PRE AUTHORIZED DEBIT', 'PRE-AUTH'),
  ('PRE AUTHORIZED DEBIT', 'PREAUTHORIZED'),
  ('PRE AUTHORIZED DEBIT', 'PRE AUTHORIZED DEBIT'),
  ('JACK CARTER', 'JACK CARTER'),
  ('JACK CARTER', 'AUTO LEASE JACK CARTER'),
  ('JACK CARTER', 'RENT/LEASE JACK CARTER'),
  ('JACK CARTER', 'AUTO LEASE PAYMENT'),
  ('ROYNAT LEASE FINANCE', 'ROYNAT LEASE FINANCE'),
  ('ROYNAT LEASE FINANCE', 'ROYNAT'),
  ('FIBRENEW', 'FIBRENEW CALGARY'),
  ('106.7 THE DRIVE', '106.7 THE DRIVE'),
  ('106.7 THE DRIVE', 'THE DRIVE')
) s(canonical, synonym)
WHERE UPPER(va.canonical_vendor) = UPPER(s.canonical)
ON CONFLICT (UPPER(synonym)) DO NOTHING;

COMMENT ON TABLE vendor_synonyms IS 'Dynamic vendor name synonym mapping for canonicalization';
