-- Add Tax-Free Threshold Columns and Populate with Accurate Data
-- These are the amounts you can earn without owing federal or provincial income tax
-- Based on basic personal amounts and other non-refundable tax credits

-- Add new columns for tax-free thresholds
ALTER TABLE tax_year_reference 
ADD COLUMN IF NOT EXISTS federal_tax_free_threshold NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS alberta_tax_free_threshold NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS minimum_taxable_income_federal NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS minimum_taxable_income_alberta NUMERIC(10,2);

COMMENT ON COLUMN tax_year_reference.federal_tax_free_threshold IS 'Annual income where federal tax owing becomes $0 (basic personal amount converted to income threshold)';
COMMENT ON COLUMN tax_year_reference.alberta_tax_free_threshold IS 'Annual income where Alberta provincial tax owing becomes $0 (basic personal amount converted to income threshold)';
COMMENT ON COLUMN tax_year_reference.minimum_taxable_income_federal IS 'Minimum income to be required to file federal tax return (typically matches federal_tax_free_threshold)';
COMMENT ON COLUMN tax_year_reference.minimum_taxable_income_alberta IS 'Minimum income where Alberta tax is owed (typically matches alberta_tax_free_threshold)';

-- Update 2008: Federal Basic Personal Amount $9,600, Alberta $16,161
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 9600.00,
    alberta_tax_free_threshold = 16161.00,
    minimum_taxable_income_federal = 9600.00,
    minimum_taxable_income_alberta = 16161.00
WHERE year = 2008;

-- Update 2009: Federal $10,320, Alberta $16,775
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 10320.00,
    alberta_tax_free_threshold = 16775.00,
    minimum_taxable_income_federal = 10320.00,
    minimum_taxable_income_alberta = 16775.00
WHERE year = 2009;

-- Update 2010: Federal $10,382, Alberta $16,977
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 10382.00,
    alberta_tax_free_threshold = 16977.00,
    minimum_taxable_income_federal = 10382.00,
    minimum_taxable_income_alberta = 16977.00
WHERE year = 2010;

-- Update 2011: Federal $10,527, Alberta $17,282
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 10527.00,
    alberta_tax_free_threshold = 17282.00,
    minimum_taxable_income_federal = 10527.00,
    minimum_taxable_income_alberta = 17282.00
WHERE year = 2011;

-- Update 2012: Federal $10,822, Alberta $17,787
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 10822.00,
    alberta_tax_free_threshold = 17787.00,
    minimum_taxable_income_federal = 10822.00,
    minimum_taxable_income_alberta = 17787.00
WHERE year = 2012;

-- Update 2013: Federal $11,038, Alberta $17,787
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 11038.00,
    alberta_tax_free_threshold = 17787.00,
    minimum_taxable_income_federal = 11038.00,
    minimum_taxable_income_alberta = 17787.00
WHERE year = 2013;

-- Update 2014: Federal $11,138, Alberta $18,214
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 11138.00,
    alberta_tax_free_threshold = 18214.00,
    minimum_taxable_income_federal = 11138.00,
    minimum_taxable_income_alberta = 18214.00
WHERE year = 2014;

-- Update 2015: Federal $11,327, Alberta $18,451
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 11327.00,
    alberta_tax_free_threshold = 18451.00,
    minimum_taxable_income_federal = 11327.00,
    minimum_taxable_income_alberta = 18451.00
WHERE year = 2015;

-- Update 2016: Federal $11,474, Alberta $18,451
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 11474.00,
    alberta_tax_free_threshold = 18451.00,
    minimum_taxable_income_federal = 11474.00,
    minimum_taxable_income_alberta = 18451.00
WHERE year = 2016;

-- Update 2017: Federal $11,635, Alberta $18,690
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 11635.00,
    alberta_tax_free_threshold = 18690.00,
    minimum_taxable_income_federal = 11635.00,
    minimum_taxable_income_alberta = 18690.00
WHERE year = 2017;

-- Update 2018: Federal $11,809, Alberta $19,369
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 11809.00,
    alberta_tax_free_threshold = 19369.00,
    minimum_taxable_income_federal = 11809.00,
    minimum_taxable_income_alberta = 19369.00
WHERE year = 2018;

-- Update 2019: Federal $12,069, Alberta $19,369
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 12069.00,
    alberta_tax_free_threshold = 19369.00,
    minimum_taxable_income_federal = 12069.00,
    minimum_taxable_income_alberta = 19369.00
WHERE year = 2019;

-- Update 2020: Federal $13,229, Alberta $19,369
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 13229.00,
    alberta_tax_free_threshold = 19369.00,
    minimum_taxable_income_federal = 13229.00,
    minimum_taxable_income_alberta = 19369.00
WHERE year = 2020;

-- Update 2021: Federal $13,808, Alberta $19,369
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 13808.00,
    alberta_tax_free_threshold = 19369.00,
    minimum_taxable_income_federal = 13808.00,
    minimum_taxable_income_alberta = 19369.00
WHERE year = 2021;

-- Update 2022: Federal $14,398, Alberta $19,814
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 14398.00,
    alberta_tax_free_threshold = 19814.00,
    minimum_taxable_income_federal = 14398.00,
    minimum_taxable_income_alberta = 19814.00
WHERE year = 2022;

-- Update 2023: Federal $15,000, Alberta $21,003
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 15000.00,
    alberta_tax_free_threshold = 21003.00,
    minimum_taxable_income_federal = 15000.00,
    minimum_taxable_income_alberta = 21003.00
WHERE year = 2023;

-- Update 2024: Federal $15,705, Alberta $21,885
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 15705.00,
    alberta_tax_free_threshold = 21885.00,
    minimum_taxable_income_federal = 15705.00,
    minimum_taxable_income_alberta = 21885.00
WHERE year = 2024;

-- Update 2025: Federal $16,129, Alberta $22,504
UPDATE tax_year_reference SET
    federal_tax_free_threshold = 16129.00,
    alberta_tax_free_threshold = 22504.00,
    minimum_taxable_income_federal = 16129.00,
    minimum_taxable_income_alberta = 22504.00
WHERE year = 2025;

-- Verification: Show tax-free thresholds by year
SELECT 
    year,
    federal_tax_free_threshold AS fed_tax_free,
    alberta_tax_free_threshold AS ab_tax_free,
    (federal_tax_free_threshold + alberta_tax_free_threshold) AS combined_tax_free,
    ROUND(federal_tax_free_threshold / 12, 2) AS fed_monthly_exempt,
    ROUND(alberta_tax_free_threshold / 12, 2) AS ab_monthly_exempt,
    ROUND((federal_tax_free_threshold + alberta_tax_free_threshold) / 12, 2) AS combined_monthly_exempt
FROM tax_year_reference
WHERE year BETWEEN 2008 AND 2025
ORDER BY year;

-- Show progression of tax-free amounts
SELECT 
    year,
    federal_tax_free_threshold,
    federal_tax_free_threshold - LAG(federal_tax_free_threshold) OVER (ORDER BY year) AS fed_increase,
    alberta_tax_free_threshold,
    alberta_tax_free_threshold - LAG(alberta_tax_free_threshold) OVER (ORDER BY year) AS ab_increase
FROM tax_year_reference
WHERE year BETWEEN 2008 AND 2025
ORDER BY year;

-- Important note about tax-free thresholds:
COMMENT ON TABLE tax_year_reference IS 'Complete Canadian tax reference data 2008-2025. 
Tax-free thresholds represent the basic personal amount - the income level where no federal or provincial tax is owed.
These are the LOWEST amounts to use for payroll calculations to avoid over-withholding.
Note: Actual tax owing may be less due to additional credits (spousal, disability, tuition, etc.) but these are the safe minimums for payroll withholding.';

-- Create a helper view for quick payroll calculations
CREATE OR REPLACE VIEW v_current_tax_thresholds AS
SELECT 
    year,
    federal_tax_free_threshold,
    alberta_tax_free_threshold,
    (federal_tax_free_threshold + alberta_tax_free_threshold) AS total_tax_free,
    ROUND(federal_tax_free_threshold / 52, 2) AS fed_weekly_exempt,
    ROUND(federal_tax_free_threshold / 26, 2) AS fed_biweekly_exempt,
    ROUND(federal_tax_free_threshold / 24, 2) AS fed_semimonthly_exempt,
    ROUND(federal_tax_free_threshold / 12, 2) AS fed_monthly_exempt,
    ROUND(alberta_tax_free_threshold / 52, 2) AS ab_weekly_exempt,
    ROUND(alberta_tax_free_threshold / 26, 2) AS ab_biweekly_exempt,
    ROUND(alberta_tax_free_threshold / 24, 2) AS ab_semimonthly_exempt,
    ROUND(alberta_tax_free_threshold / 12, 2) AS ab_monthly_exempt
FROM tax_year_reference
WHERE year = EXTRACT(YEAR FROM CURRENT_DATE);

COMMENT ON VIEW v_current_tax_thresholds IS 'Current year tax-free thresholds broken down by pay period frequency for easy payroll calculations';

-- Show current year thresholds
SELECT * FROM v_current_tax_thresholds;

-- Practical example: Calculate tax withholding for bi-weekly payroll
DO $$
DECLARE
    v_year INT := 2024;
    v_gross_biweekly NUMERIC := 2000.00;
    v_annual_gross NUMERIC;
    v_fed_threshold NUMERIC;
    v_ab_threshold NUMERIC;
    v_fed_taxable NUMERIC;
    v_ab_taxable NUMERIC;
BEGIN
    -- Get thresholds
    SELECT federal_tax_free_threshold, alberta_tax_free_threshold
    INTO v_fed_threshold, v_ab_threshold
    FROM tax_year_reference WHERE year = v_year;
    
    -- Annualize gross pay
    v_annual_gross := v_gross_biweekly * 26;
    
    -- Calculate taxable income
    v_fed_taxable := GREATEST(0, v_annual_gross - v_fed_threshold);
    v_ab_taxable := GREATEST(0, v_annual_gross - v_ab_threshold);
    
    RAISE NOTICE '';
    RAISE NOTICE '=== PAYROLL TAX CALCULATION EXAMPLE (% Bi-weekly, $% gross) ===', v_year, v_gross_biweekly;
    RAISE NOTICE 'Annual gross income: $%', v_annual_gross;
    RAISE NOTICE '';
    RAISE NOTICE 'Federal tax-free threshold: $%', v_fed_threshold;
    RAISE NOTICE 'Federal taxable income: $%', v_fed_taxable;
    RAISE NOTICE '';
    RAISE NOTICE 'Alberta tax-free threshold: $%', v_ab_threshold;
    RAISE NOTICE 'Alberta taxable income: $%', v_ab_taxable;
    RAISE NOTICE '';
    RAISE NOTICE 'If earning below $% federally, NO federal tax owing', v_fed_threshold;
    RAISE NOTICE 'If earning below $% in Alberta, NO provincial tax owing', v_ab_threshold;
    RAISE NOTICE '';
    RAISE NOTICE 'SAFE APPROACH: Use these as minimum exemptions in payroll calculations';
    RAISE NOTICE 'to avoid over-withholding and employee refund claims';
END $$;

-- Summary report
SELECT 
    '2008-2025 Tax-Free Threshold Coverage' AS report_title,
    COUNT(*) AS years_covered,
    MIN(year) AS earliest_year,
    MAX(year) AS latest_year,
    ROUND(AVG(federal_tax_free_threshold), 2) AS avg_fed_threshold,
    ROUND(AVG(alberta_tax_free_threshold), 2) AS avg_ab_threshold,
    MIN(federal_tax_free_threshold) AS min_fed_threshold,
    MAX(federal_tax_free_threshold) AS max_fed_threshold,
    MIN(alberta_tax_free_threshold) AS min_ab_threshold,
    MAX(alberta_tax_free_threshold) AS max_ab_threshold
FROM tax_year_reference
WHERE year BETWEEN 2008 AND 2025;
