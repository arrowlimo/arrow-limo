-- Migration: Create charter_beverages table for beverage snapshot storage
-- Date: 2026-01-08
-- Purpose: Store beverage prices/costs LOCKED at time of charter creation
--          Allows editing carts without affecting master beverage_products list

CREATE TABLE IF NOT EXISTS charter_beverages (
    id SERIAL PRIMARY KEY,
    
    -- Links
    charter_id INTEGER NOT NULL REFERENCES charters(charter_id) ON DELETE CASCADE,
    beverage_item_id INTEGER REFERENCES beverage_products(item_id),
    
    -- Item snapshot (what it was called and priced when added)
    item_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    
    -- SNAPSHOT prices (locked at time of addition, can be edited per-charter)
    unit_price_charged DECIMAL(10, 2) NOT NULL,      -- What we charge guest
    unit_our_cost DECIMAL(10, 2) NOT NULL,           -- What we paid supplier
    deposit_per_unit DECIMAL(10, 2) DEFAULT 0.00,    -- Bottle deposit
    
    -- Calculated lines (qty × unit)
    line_amount_charged DECIMAL(10, 2) GENERATED ALWAYS AS (quantity * unit_price_charged) STORED,
    line_cost DECIMAL(10, 2) GENERATED ALWAYS AS (quantity * unit_our_cost) STORED,
    
    -- Metadata
    notes TEXT,  -- "Price adjusted from $5.49 → $5.99", "Quantity changed 24 → 20"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_quantities CHECK (quantity > 0),
    CONSTRAINT valid_prices CHECK (unit_price_charged >= 0 AND unit_our_cost >= 0)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_charter_beverages_charter_id ON charter_beverages(charter_id);
CREATE INDEX IF NOT EXISTS idx_charter_beverages_beverage_item_id ON charter_beverages(beverage_item_id);
CREATE INDEX IF NOT EXISTS idx_charter_beverages_created_at ON charter_beverages(created_at);

-- Comment on table
COMMENT ON TABLE charter_beverages IS 
'Snapshot of beverages charged to charter. Prices are locked at time of charter creation.
Editing quantities/prices here does NOT affect master beverage_products table.
Used for historical accuracy, guest disputes, and profit margin tracking.';

COMMENT ON COLUMN charter_beverages.unit_price_charged IS 
'What we charged the GUEST for this item (includes GST). LOCKED at snapshot time.';

COMMENT ON COLUMN charter_beverages.unit_our_cost IS 
'What Arrow Limousine PAID the supplier (wholesale cost). LOCKED at snapshot time.';

COMMENT ON COLUMN charter_beverages.notes IS 
'Audit trail: "Price negotiated down $5.49→$4.99", "Guest requested substitution", etc.';
