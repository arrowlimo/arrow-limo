-- Migration: Add Corporate Tax Rates for 2007-2011 (Historical Data Entry Support)
-- Purpose: Enable T2 data entry for years 2007-2012 from paper forms
-- Date: 2024
-- 
-- Federal + Alberta Corporate Tax Rates (Historical)
-- Small Business Deduction (SBD) applies to first $500,000 of active business income
-- General rate applies to income over $500,000

-- Delete existing 2007-2011 entries if any (idempotent)
DELETE FROM corporate_tax_rates WHERE tax_year BETWEEN 2007 AND 2011;

-- 2007 Tax Rates
INSERT INTO corporate_tax_rates (
    tax_year,
    federal_small_business_rate,
    federal_general_rate,
    alberta_small_business_rate,
    alberta_general_rate,
    small_business_limit,
    gst_rate,
    notes
) VALUES (
    2007,
    0.1200,  -- Federal SBD rate dropped from 13.12% to 12% in 2007
    0.2212,  -- Federal general rate (before province-specific abatement)
    0.0300,  -- Alberta small business rate
    0.1000,  -- Alberta general rate
    500000.00, -- Small business income limit
    0.0600,  -- GST was 6% from July 2006 - December 2007
    'Federal SBD reduction began. GST reduced to 6% mid-2006, then 5% in 2008.'
);

-- 2008 Tax Rates
INSERT INTO corporate_tax_rates (
    tax_year,
    federal_small_business_rate,
    federal_general_rate,
    alberta_small_business_rate,
    alberta_general_rate,
    small_business_limit,
    gst_rate,
    notes
) VALUES (
    2008,
    0.1100,  -- Federal SBD reduced to 11%
    0.1950,  -- Federal general rate reduced
    0.0300,  -- Alberta small business rate
    0.1000,  -- Alberta general rate
    500000.00,
    0.0500,  -- GST reduced to 5% from January 1, 2008
    'Federal rate reductions continued. GST dropped to 5%.'
);

-- 2009 Tax Rates
INSERT INTO corporate_tax_rates (
    tax_year,
    federal_small_business_rate,
    federal_general_rate,
    alberta_small_business_rate,
    alberta_general_rate,
    small_business_limit,
    gst_rate,
    notes
) VALUES (
    2009,
    0.1100,  -- Federal SBD stable at 11%
    0.1900,  -- Federal general rate reduced from 19.5%
    0.0300,  -- Alberta small business rate
    0.1000,  -- Alberta general rate
    500000.00,
    0.0500,
    'Federal general rate reduction to 19%. Economic recession year.'
);

-- 2010 Tax Rates
INSERT INTO corporate_tax_rates (
    tax_year,
    federal_small_business_rate,
    federal_general_rate,
    alberta_small_business_rate,
    alberta_general_rate,
    small_business_limit,
    gst_rate,
    notes
) VALUES (
    2010,
    0.1100,  -- Federal SBD stable at 11%
    0.1800,  -- Federal general rate reduced from 19%
    0.0300,  -- Alberta small business rate
    0.1000,  -- Alberta general rate
    500000.00,
    0.0500,
    'Federal general rate reduction to 18%.'
);

-- 2011 Tax Rates
INSERT INTO corporate_tax_rates (
    tax_year,
    federal_small_business_rate,
    federal_general_rate,
    alberta_small_business_rate,
    alberta_general_rate,
    small_business_limit,
    gst_rate,
    notes
) VALUES (
    2011,
    0.1100,  -- Federal SBD stable at 11%
    0.1650,  -- Federal general rate reduced from 18%
    0.0300,  -- Alberta small business rate
    0.1000,  -- Alberta general rate
    500000.00,
    0.0500,
    'Federal general rate reduction to 16.5%.'
);

-- Verify insertion
SELECT 
    tax_year,
    (federal_small_business_rate * 100) || '%' as fed_sbd,
    (federal_general_rate * 100) || '%' as fed_gen,
    (alberta_small_business_rate * 100) || '%' as ab_sbd,
    (alberta_general_rate * 100) || '%' as ab_gen,
    small_business_limit as sbd_limit,
    (gst_rate * 100) || '%' as gst,
    notes
FROM corporate_tax_rates 
WHERE tax_year BETWEEN 2007 AND 2011
ORDER BY tax_year;

-- Summary verification
SELECT 
    COUNT(*) as total_years_loaded,
    MIN(tax_year) as earliest_year,
    MAX(tax_year) as latest_year
FROM corporate_tax_rates;
