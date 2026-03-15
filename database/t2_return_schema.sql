-- T2 Corporation Income Tax Return Generator - Database Schema
-- Creates tables for T2 return metadata, tax rates, and adjustments

-- ============================================================================
-- 1. CORPORATE TAX RATES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS corporate_tax_rates (
    tax_year INT PRIMARY KEY,
    federal_small_business_rate DECIMAL(5,4) NOT NULL,
    federal_general_rate DECIMAL(5,4) NOT NULL,
    alberta_small_business_rate DECIMAL(5,4) NOT NULL,
    alberta_general_rate DECIMAL(5,4) NOT NULL,
    small_business_limit DECIMAL(12,2) NOT NULL,
    gst_rate DECIMAL(5,4) NOT NULL,
    hst_rate DECIMAL(5,4),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert tax rates for 2012-2025
INSERT INTO corporate_tax_rates (tax_year, federal_small_business_rate, federal_general_rate, 
    alberta_small_business_rate, alberta_general_rate, small_business_limit, gst_rate, notes)
VALUES
    (2012, 0.1100, 0.1500, 0.0300, 0.1000, 500000.00, 0.0500, 'Federal SBD 11%, General 15%; Alberta 3%, 10%'),
    (2013, 0.1100, 0.1500, 0.0300, 0.1000, 500000.00, 0.0500, 'Rates unchanged from 2012'),
    (2014, 0.1100, 0.1500, 0.0300, 0.1000, 500000.00, 0.0500, 'Rates unchanged from 2013'),
    (2015, 0.1100, 0.1500, 0.0300, 0.1000, 500000.00, 0.0500, 'Rates unchanged from 2014'),
    (2016, 0.1050, 0.1500, 0.0300, 0.1000, 500000.00, 0.0500, 'Federal SBD reduced to 10.5%'),
    (2017, 0.1050, 0.1500, 0.0200, 0.1200, 500000.00, 0.0500, 'Alberta rates changed: 2% SBD, 12% general'),
    (2018, 0.1000, 0.1500, 0.0200, 0.1200, 500000.00, 0.0500, 'Federal SBD reduced to 10%'),
    (2019, 0.0900, 0.1500, 0.0200, 0.1100, 500000.00, 0.0500, 'Federal SBD 9%; Alberta general 11%'),
    (2020, 0.0900, 0.1500, 0.0200, 0.1100, 500000.00, 0.0500, 'Rates unchanged from 2019'),
    (2021, 0.0900, 0.1500, 0.0200, 0.0800, 500000.00, 0.0500, 'Alberta general rate reduced to 8%'),
    (2022, 0.0900, 0.1500, 0.0200, 0.0800, 500000.00, 0.0500, 'Rates unchanged from 2021'),
    (2023, 0.0900, 0.1500, 0.0200, 0.0800, 500000.00, 0.0500, 'Rates unchanged from 2022'),
    (2024, 0.0900, 0.1500, 0.0200, 0.0800, 500000.00, 0.0500, 'Rates unchanged from 2023'),
    (2025, 0.0900, 0.1500, 0.0200, 0.0800, 500000.00, 0.0500, 'Rates unchanged from 2024')
ON CONFLICT (tax_year) DO UPDATE SET
    federal_small_business_rate = EXCLUDED.federal_small_business_rate,
    federal_general_rate = EXCLUDED.federal_general_rate,
    alberta_small_business_rate = EXCLUDED.alberta_small_business_rate,
    alberta_general_rate = EXCLUDED.alberta_general_rate,
    small_business_limit = EXCLUDED.small_business_limit,
    gst_rate = EXCLUDED.gst_rate,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- ============================================================================
-- 2. T2 RETURN METADATA TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS t2_return_metadata (
    return_id SERIAL PRIMARY KEY,
    tax_year INT NOT NULL,
    corporation_name VARCHAR(200) NOT NULL,
    business_number VARCHAR(15),
    fiscal_year_end DATE NOT NULL,
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'draft', -- draft, calculated, generated, filed
    generated_date TIMESTAMP,
    filed_date TIMESTAMP,
    
    -- Financial totals
    total_revenue DECIMAL(15,2),
    total_expenses DECIMAL(15,2),
    net_income DECIMAL(15,2),
    taxable_income DECIMAL(15,2),
    federal_tax DECIMAL(15,2),
    provincial_tax DECIMAL(15,2),
    total_tax DECIMAL(15,2),
    
    -- File references
    pdf_path VARCHAR(500),
    supporting_docs_path VARCHAR(500),
    
    -- Audit trail
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(tax_year),
    FOREIGN KEY (tax_year) REFERENCES corporate_tax_rates(tax_year)
);

CREATE INDEX idx_t2_metadata_year ON t2_return_metadata(tax_year);
CREATE INDEX idx_t2_metadata_status ON t2_return_metadata(status);

-- ============================================================================
-- 3. T2 SCHEDULE DATA TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS t2_schedule_data (
    schedule_id SERIAL PRIMARY KEY,
    return_id INT NOT NULL,
    schedule_number VARCHAR(10) NOT NULL, -- '1', '3', '4', '8', '50', '100', '125'
    line_number VARCHAR(20) NOT NULL,     -- e.g., '8000', '8299', '9369'
    line_description TEXT,
    amount DECIMAL(15,2),
    calculation_notes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (return_id) REFERENCES t2_return_metadata(return_id) ON DELETE CASCADE,
    UNIQUE(return_id, schedule_number, line_number)
);

CREATE INDEX idx_t2_schedule_return ON t2_schedule_data(return_id);
CREATE INDEX idx_t2_schedule_number ON t2_schedule_data(schedule_number);

-- ============================================================================
-- 4. T2 ADJUSTMENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS t2_adjustments (
    adjustment_id SERIAL PRIMARY KEY,
    return_id INT NOT NULL,
    adjustment_type VARCHAR(50) NOT NULL, -- 'manual', 'cca', 'meals_entertainment', 'non_deductible'
    category VARCHAR(100),
    description TEXT NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    
    -- Affects which schedule
    schedule_number VARCHAR(10),
    line_number VARCHAR(20),
    
    -- Justification
    reason TEXT,
    supporting_document VARCHAR(500),
    
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (return_id) REFERENCES t2_return_metadata(return_id) ON DELETE CASCADE
);

CREATE INDEX idx_t2_adj_return ON t2_adjustments(return_id);
CREATE INDEX idx_t2_adj_type ON t2_adjustments(adjustment_type);

-- ============================================================================
-- 5. T2 CCA (CAPITAL COST ALLOWANCE) TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS t2_cca_schedule (
    cca_id SERIAL PRIMARY KEY,
    return_id INT NOT NULL,
    asset_class INT NOT NULL,           -- CCA class (e.g., 10, 10.1, 54)
    asset_description VARCHAR(200),
    
    -- UCC calculations
    ucc_beginning DECIMAL(15,2) DEFAULT 0,
    additions DECIMAL(15,2) DEFAULT 0,
    disposals DECIMAL(15,2) DEFAULT 0,
    ucc_before_cca DECIMAL(15,2),
    cca_rate DECIMAL(5,4),
    cca_claimed DECIMAL(15,2),
    ucc_end DECIMAL(15,2),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (return_id) REFERENCES t2_return_metadata(return_id) ON DELETE CASCADE
);

CREATE INDEX idx_t2_cca_return ON t2_cca_schedule(return_id);

-- ============================================================================
-- 6. T2 SHAREHOLDER INFORMATION TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS t2_shareholder_info (
    shareholder_id SERIAL PRIMARY KEY,
    return_id INT NOT NULL,
    shareholder_name VARCHAR(200) NOT NULL,
    shareholder_address TEXT,
    sin_or_bn VARCHAR(20),
    
    -- Share information
    share_class VARCHAR(50),
    number_of_shares INT,
    percentage_owned DECIMAL(5,2),
    
    -- Schedule 50 data
    is_related BOOLEAN DEFAULT false,
    is_controlling BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (return_id) REFERENCES t2_return_metadata(return_id) ON DELETE CASCADE
);

CREATE INDEX idx_t2_shareholder_return ON t2_shareholder_info(return_id);

-- ============================================================================
-- 7. GRANT PERMISSIONS (if needed)
-- ============================================================================
-- GRANT ALL ON TABLE corporate_tax_rates TO your_app_user;
-- GRANT ALL ON TABLE t2_return_metadata TO your_app_user;
-- GRANT ALL ON TABLE t2_schedule_data TO your_app_user;
-- GRANT ALL ON TABLE t2_adjustments TO your_app_user;
-- GRANT ALL ON TABLE t2_cca_schedule TO your_app_user;
-- GRANT ALL ON TABLE t2_shareholder_info TO your_app_user;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- View tax rates by year
SELECT 
    tax_year,
    (federal_small_business_rate + alberta_small_business_rate) * 100 AS combined_sbd_pct,
    (federal_general_rate + alberta_general_rate) * 100 AS combined_general_pct,
    small_business_limit,
    gst_rate * 100 AS gst_pct
FROM corporate_tax_rates
ORDER BY tax_year;

-- Show rate changes over time
SELECT 
    tax_year,
    federal_small_business_rate,
    federal_small_business_rate - LAG(federal_small_business_rate) OVER (ORDER BY tax_year) AS fed_change,
    alberta_general_rate,
    alberta_general_rate - LAG(alberta_general_rate) OVER (ORDER BY tax_year) AS ab_change
FROM corporate_tax_rates
ORDER BY tax_year;

COMMENT ON TABLE corporate_tax_rates IS 'Canadian federal and Alberta provincial corporate tax rates by year';
COMMENT ON TABLE t2_return_metadata IS 'T2 Corporation Income Tax Return metadata and summary data';
COMMENT ON TABLE t2_schedule_data IS 'Detailed line items for all T2 schedules';
COMMENT ON TABLE t2_adjustments IS 'Manual and calculated adjustments to T2 returns';
COMMENT ON TABLE t2_cca_schedule IS 'Capital Cost Allowance (depreciation) calculations for Schedule 8';
COMMENT ON TABLE t2_shareholder_info IS 'Shareholder information for Schedule 50';
