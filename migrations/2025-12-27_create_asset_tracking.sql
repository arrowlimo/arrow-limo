-- Asset Tracking System for CRA Compliance
-- Run: psql -h localhost -U postgres -d almsdata -f migrations/2025-12-27_create_asset_tracking.sql

-- Asset ownership status types
CREATE TYPE asset_ownership_type AS ENUM ('owned', 'leased', 'loaned_in', 'rental');

-- Asset categories
CREATE TYPE asset_category AS ENUM ('vehicle', 'equipment', 'furniture', 'electronics', 'real_estate', 'other');

-- Depreciation methods
CREATE TYPE depreciation_method AS ENUM ('straight_line', 'declining_balance', 'none');

-- Main assets table
CREATE TABLE IF NOT EXISTS assets (
  asset_id BIGSERIAL PRIMARY KEY,
  asset_name VARCHAR(255) NOT NULL,
  asset_category asset_category NOT NULL DEFAULT 'other',
  ownership_status asset_ownership_type NOT NULL DEFAULT 'owned',
  
  -- Identification
  serial_number VARCHAR(100),
  vin VARCHAR(17), -- For vehicles
  make VARCHAR(100),
  model VARCHAR(100),
  year INTEGER,
  
  -- Financial
  acquisition_date DATE,
  acquisition_cost NUMERIC(14,2),
  current_book_value NUMERIC(14,2),
  salvage_value NUMERIC(14,2) DEFAULT 0.00,
  
  -- Depreciation
  depreciation_method depreciation_method DEFAULT 'straight_line',
  useful_life_years INTEGER,
  cca_class VARCHAR(10), -- CRA Capital Cost Allowance class
  cca_rate NUMERIC(5,2), -- CRA depreciation rate percentage
  
  -- Ownership details
  legal_owner VARCHAR(255), -- For leased/loaned items
  lender_contact VARCHAR(255),
  loan_agreement_ref VARCHAR(100),
  lease_start_date DATE,
  lease_end_date DATE,
  lease_monthly_payment NUMERIC(14,2),
  
  -- Documentation
  purchase_receipt_id BIGINT REFERENCES receipts(receipt_id),
  insurance_policy_number VARCHAR(100),
  
  -- Location & Status
  location VARCHAR(255),
  status VARCHAR(20) DEFAULT 'active',
  
  -- Notes
  notes TEXT,
  
  -- Audit trail
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  
  CONSTRAINT status_ck CHECK (status IN ('active', 'sold', 'disposed', 'stolen', 'retired'))
);

-- Asset documentation links (contracts, photos, appraisals)
CREATE TABLE IF NOT EXISTS asset_documentation (
  doc_id BIGSERIAL PRIMARY KEY,
  asset_id BIGINT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
  document_type VARCHAR(50) NOT NULL, -- contract, photo, appraisal, loan_agreement, lease, title, registration
  file_path TEXT,
  description TEXT,
  document_date DATE,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  
  CONSTRAINT document_type_ck CHECK (document_type IN (
    'purchase_contract', 'loan_agreement', 'lease_agreement', 'title_deed', 
    'registration', 'photo', 'appraisal', 'insurance_policy', 'maintenance_record', 'other'
  ))
);

-- Depreciation schedule tracking
CREATE TABLE IF NOT EXISTS asset_depreciation_schedule (
  schedule_id BIGSERIAL PRIMARY KEY,
  asset_id BIGINT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
  fiscal_year INTEGER NOT NULL,
  opening_book_value NUMERIC(14,2) NOT NULL,
  depreciation_expense NUMERIC(14,2) NOT NULL,
  closing_book_value NUMERIC(14,2) NOT NULL,
  cca_claimed NUMERIC(14,2), -- CRA Capital Cost Allowance claimed
  notes TEXT,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  
  CONSTRAINT unique_asset_year UNIQUE (asset_id, fiscal_year)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_assets_ownership ON assets(ownership_status);
CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(asset_category);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_acquisition_date ON assets(acquisition_date);
CREATE INDEX IF NOT EXISTS idx_asset_docs_asset ON asset_documentation(asset_id);
CREATE INDEX IF NOT EXISTS idx_depreciation_asset ON asset_depreciation_schedule(asset_id);
CREATE INDEX IF NOT EXISTS idx_depreciation_year ON asset_depreciation_schedule(fiscal_year);

-- Migrate existing vehicles to asset tracking
INSERT INTO assets (
  asset_name, asset_category, ownership_status, serial_number, vin, make, model, year,
  acquisition_date, acquisition_cost, legal_owner, status, notes, created_at
)
SELECT 
  CONCAT(v.year, ' ', v.make, ' ', v.model) as asset_name,
  'vehicle' as asset_category,
  CASE 
    WHEN v.finance_partner IS NOT NULL THEN 'leased'::asset_ownership_type
    ELSE 'owned'::asset_ownership_type
  END as ownership_status,
  v.unit_number as serial_number,
  v.vin_number as vin,
  v.make,
  v.model,
  v.year,
  v.purchase_date as acquisition_date,
  v.purchase_price as acquisition_cost,
  v.finance_partner as legal_owner,
  CASE 
    WHEN v.decommission_date IS NOT NULL THEN 'retired'
    WHEN v.status = 'active' OR v.is_active = true THEN 'active'
    ELSE 'disposed'
  END as status,
  CONCAT('Imported from vehicles table. License: ', COALESCE(v.license_plate, 'N/A'), 
         CASE WHEN v.fleet_number IS NOT NULL THEN CONCAT(', Fleet #: ', v.fleet_number) ELSE '' END) as notes,
  NOW()
FROM vehicles v
WHERE NOT EXISTS (
  SELECT 1 FROM assets a WHERE a.vin = v.vin_number AND a.asset_category = 'vehicle'
)
ON CONFLICT DO NOTHING;

COMMENT ON TABLE assets IS 'Business asset tracking for CRA compliance - owned, leased, and loaned items';
COMMENT ON COLUMN assets.ownership_status IS 'owned=business asset, leased=monthly payments, loaned_in=borrowed from others';
COMMENT ON COLUMN assets.cca_class IS 'CRA Capital Cost Allowance class (e.g., Class 10 for vehicles)';
COMMENT ON COLUMN assets.legal_owner IS 'Owner name for leased/loaned items (e.g., Lease Finance Group, Jack Carter)';
