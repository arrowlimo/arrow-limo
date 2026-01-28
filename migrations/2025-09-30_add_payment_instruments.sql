-- Migration: Add payment instruments (cards) and linking for banking transactions and receipts
-- Date: 2025-09-30
-- Purpose: Support linking card-based receipt purchases and bank account payments (e.g., credit card payments) using last4 and institution/account aliases.

BEGIN;

-- 1. Master table for payment instruments (credit cards, virtual cards, debit card numbers if needed)
CREATE TABLE IF NOT EXISTS payment_instruments (
    instrument_id SERIAL PRIMARY KEY,
    instrument_type VARCHAR(30) NOT NULL CHECK (instrument_type IN ('credit_card','debit_card','virtual_card','gift_card','other')),
    display_name VARCHAR(100) NOT NULL, -- e.g. 'Canadian Tire Mastercard'
    institution_name VARCHAR(120),      -- Issuer bank name
    last4 VARCHAR(4) NOT NULL,
    full_identifier_hash VARCHAR(64),   -- Optional SHA256 hash of full number for uniqueness without storing PAN
    currency_code CHAR(3) DEFAULT 'CAD',
    active BOOLEAN DEFAULT TRUE,
    opened_date DATE,
    closed_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(last4, instrument_type, COALESCE(closed_date,'9999-12-31'))
);

CREATE INDEX IF NOT EXISTS idx_payment_instruments_last4 ON payment_instruments(last4);

-- 2. Aliases for bank accounts (different statement naming conventions / short codes)
CREATE TABLE IF NOT EXISTS bank_account_aliases (
    alias_id SERIAL PRIMARY KEY,
    bank_id INTEGER REFERENCES bank_accounts(bank_id) ON DELETE CASCADE,
    alias_code VARCHAR(50) NOT NULL,     -- e.g. '8117', '8362', '4462', '0534', '3265'
    alias_type VARCHAR(30) DEFAULT 'branch_or_mask',
    source VARCHAR(50) DEFAULT 'user',   -- user, import, inferred
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bank_id, alias_code)
);

CREATE INDEX IF NOT EXISTS idx_bank_account_aliases_code ON bank_account_aliases(alias_code);

-- 3. Link table for transactions to payment instruments (some bank tx represent card payments)
CREATE TABLE IF NOT EXISTS transaction_payment_links (
    link_id SERIAL PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES banking_transactions(transaction_id) ON DELETE CASCADE,
    instrument_id INTEGER NOT NULL REFERENCES payment_instruments(instrument_id) ON DELETE CASCADE,
    link_type VARCHAR(30) NOT NULL DEFAULT 'payment' CHECK (link_type IN ('payment','refund','fee','interest')),
    confidence DECIMAL(4,3) DEFAULT 0.0,
    auto_linked BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(transaction_id, instrument_id, link_type)
);

CREATE INDEX IF NOT EXISTS idx_transaction_payment_links_instrument ON transaction_payment_links(instrument_id);

-- 4. Add columns to banking_transactions for detected instrument/card info
ALTER TABLE banking_transactions
    ADD COLUMN IF NOT EXISTS card_last4 VARCHAR(4),
    ADD COLUMN IF NOT EXISTS related_instrument_id INTEGER REFERENCES payment_instruments(instrument_id),
    ADD COLUMN IF NOT EXISTS instrument_match_confidence DECIMAL(4,3),
    ADD COLUMN IF NOT EXISTS instrument_link_method VARCHAR(20) CHECK (instrument_link_method IN ('parsed','rule','manual'));

-- 5. Add helper view to see unresolved card last4 occurrences
CREATE OR REPLACE VIEW vw_unlinked_card_last4 AS
SELECT bt.card_last4, COUNT(*) AS occurrence_count, MIN(bt.trans_date) AS first_date, MAX(bt.trans_date) AS last_date
FROM banking_transactions bt
LEFT JOIN payment_instruments pi ON bt.card_last4 = pi.last4
WHERE bt.card_last4 IS NOT NULL
  AND bt.related_instrument_id IS NULL
GROUP BY bt.card_last4
ORDER BY occurrence_count DESC;

COMMIT;
