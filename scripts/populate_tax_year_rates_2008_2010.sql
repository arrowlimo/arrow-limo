-- Add Tax Rates for 2008-2010 (extending historical coverage)
-- Data sourced from Canada Revenue Agency official publications
-- Last updated: October 16, 2025

-- 2008 Tax Rates
INSERT INTO tax_year_reference (
    year,
    federal_basic_personal_amount,
    alberta_basic_personal_amount,
    federal_small_business_limit,
    federal_small_business_rate,
    federal_general_corporate_rate,
    ab_corp_small_business_rate,
    ab_corp_general_rate,
    gst_rate,
    cpp_contribution_rate_employee,
    cpp_contribution_rate_employer,
    cpp_max_pensionable_earnings,
    cpp_basic_exemption,
    cpp_max_employee_contribution,
    cpp_max_employer_contribution,
    ei_rate,
    ei_max_insurable_earnings,
    ei_max_employee_contribution,
    ei_max_employer_contribution,
    wcb_ab_max_insurable_earnings,
    vacation_minimum_percent,
    capital_gains_inclusion_rate_percent,
    meal_deduction_percent_general,
    meal_deduction_percent_longhaul,
    notes
) VALUES (
    2008,
    9600.00,   -- Federal basic personal amount
    16161.00,  -- Alberta basic personal amount
    500000.00, -- Small business limit
    11.000,    -- Federal small business rate (11%)
    19.000,    -- Federal general corporate rate (was being phased down from 22.12% in 2007)
    3.000,     -- AB small business rate (3%)
    10.000,    -- AB general corporate rate (10%)
    5.00,      -- GST rate (reduced from 6% to 5% on Jan 1, 2008)
    0.0495,    -- CPP employee rate (4.95%)
    0.0495,    -- CPP employer rate (4.95%)
    44900.00,  -- CPP maximum pensionable earnings
    3500.00,   -- CPP basic exemption
    2049.30,   -- CPP max employee contribution
    2049.30,   -- CPP max employer contribution
    0.0173,    -- EI rate (1.73%)
    41100.00,  -- EI maximum insurable earnings
    711.03,    -- EI max employee contribution
    995.44,    -- EI max employer contribution (1.4x)
    98000.00,  -- WCB AB max insurable earnings
    4.00,      -- Vacation minimum percent (4% after 1 year)
    50.00,     -- Capital gains inclusion rate (50%)
    50.00,     -- Meal deduction general (50%)
    80.00,     -- Meal deduction long-haul (80%)
    'CRA 2008 rates - GST reduced to 5% (Jan 1), Federal general corp rate 19%'
) ON CONFLICT (year) DO UPDATE SET
    federal_basic_personal_amount = EXCLUDED.federal_basic_personal_amount,
    alberta_basic_personal_amount = EXCLUDED.alberta_basic_personal_amount,
    federal_small_business_limit = EXCLUDED.federal_small_business_limit,
    federal_small_business_rate = EXCLUDED.federal_small_business_rate,
    federal_general_corporate_rate = EXCLUDED.federal_general_corporate_rate,
    ab_corp_small_business_rate = EXCLUDED.ab_corp_small_business_rate,
    ab_corp_general_rate = EXCLUDED.ab_corp_general_rate,
    gst_rate = EXCLUDED.gst_rate,
    cpp_contribution_rate_employee = EXCLUDED.cpp_contribution_rate_employee,
    cpp_contribution_rate_employer = EXCLUDED.cpp_contribution_rate_employer,
    cpp_max_pensionable_earnings = EXCLUDED.cpp_max_pensionable_earnings,
    cpp_basic_exemption = EXCLUDED.cpp_basic_exemption,
    cpp_max_employee_contribution = EXCLUDED.cpp_max_employee_contribution,
    cpp_max_employer_contribution = EXCLUDED.cpp_max_employer_contribution,
    ei_rate = EXCLUDED.ei_rate,
    ei_max_insurable_earnings = EXCLUDED.ei_max_insurable_earnings,
    ei_max_employee_contribution = EXCLUDED.ei_max_employee_contribution,
    ei_max_employer_contribution = EXCLUDED.ei_max_employer_contribution,
    wcb_ab_max_insurable_earnings = EXCLUDED.wcb_ab_max_insurable_earnings,
    vacation_minimum_percent = EXCLUDED.vacation_minimum_percent,
    capital_gains_inclusion_rate_percent = EXCLUDED.capital_gains_inclusion_rate_percent,
    meal_deduction_percent_general = EXCLUDED.meal_deduction_percent_general,
    meal_deduction_percent_longhaul = EXCLUDED.meal_deduction_percent_longhaul,
    notes = EXCLUDED.notes;

-- 2009 Tax Rates
INSERT INTO tax_year_reference (
    year, federal_basic_personal_amount, alberta_basic_personal_amount,
    federal_small_business_limit, federal_small_business_rate, federal_general_corporate_rate,
    ab_corp_small_business_rate, ab_corp_general_rate, gst_rate,
    cpp_contribution_rate_employee, cpp_contribution_rate_employer,
    cpp_max_pensionable_earnings, cpp_basic_exemption,
    cpp_max_employee_contribution, cpp_max_employer_contribution,
    ei_rate, ei_max_insurable_earnings,
    ei_max_employee_contribution, ei_max_employer_contribution,
    wcb_ab_max_insurable_earnings, vacation_minimum_percent,
    capital_gains_inclusion_rate_percent, meal_deduction_percent_general,
    meal_deduction_percent_longhaul, notes
) VALUES (
    2009, 10320.00, 16775.00, 500000.00, 11.000, 19.000,
    3.000, 10.000, 5.00,
    0.0495, 0.0495, 46300.00, 3500.00, 2118.60, 2118.60,
    0.0173, 42300.00, 731.79, 1024.51,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2009 rates'
) ON CONFLICT (year) DO UPDATE SET
    federal_basic_personal_amount = EXCLUDED.federal_basic_personal_amount,
    alberta_basic_personal_amount = EXCLUDED.alberta_basic_personal_amount,
    federal_small_business_limit = EXCLUDED.federal_small_business_limit,
    federal_small_business_rate = EXCLUDED.federal_small_business_rate,
    federal_general_corporate_rate = EXCLUDED.federal_general_corporate_rate,
    ab_corp_small_business_rate = EXCLUDED.ab_corp_small_business_rate,
    ab_corp_general_rate = EXCLUDED.ab_corp_general_rate,
    gst_rate = EXCLUDED.gst_rate,
    cpp_contribution_rate_employee = EXCLUDED.cpp_contribution_rate_employee,
    cpp_contribution_rate_employer = EXCLUDED.cpp_contribution_rate_employer,
    cpp_max_pensionable_earnings = EXCLUDED.cpp_max_pensionable_earnings,
    cpp_basic_exemption = EXCLUDED.cpp_basic_exemption,
    cpp_max_employee_contribution = EXCLUDED.cpp_max_employee_contribution,
    cpp_max_employer_contribution = EXCLUDED.cpp_max_employer_contribution,
    ei_rate = EXCLUDED.ei_rate,
    ei_max_insurable_earnings = EXCLUDED.ei_max_insurable_earnings,
    ei_max_employee_contribution = EXCLUDED.ei_max_employee_contribution,
    ei_max_employer_contribution = EXCLUDED.ei_max_employer_contribution,
    wcb_ab_max_insurable_earnings = EXCLUDED.wcb_ab_max_insurable_earnings,
    vacation_minimum_percent = EXCLUDED.vacation_minimum_percent,
    capital_gains_inclusion_rate_percent = EXCLUDED.capital_gains_inclusion_rate_percent,
    meal_deduction_percent_general = EXCLUDED.meal_deduction_percent_general,
    meal_deduction_percent_longhaul = EXCLUDED.meal_deduction_percent_longhaul,
    notes = EXCLUDED.notes;

-- 2010 Tax Rates
INSERT INTO tax_year_reference (
    year, federal_basic_personal_amount, alberta_basic_personal_amount,
    federal_small_business_limit, federal_small_business_rate, federal_general_corporate_rate,
    ab_corp_small_business_rate, ab_corp_general_rate, gst_rate,
    cpp_contribution_rate_employee, cpp_contribution_rate_employer,
    cpp_max_pensionable_earnings, cpp_basic_exemption,
    cpp_max_employee_contribution, cpp_max_employer_contribution,
    ei_rate, ei_max_insurable_earnings,
    ei_max_employee_contribution, ei_max_employer_contribution,
    wcb_ab_max_insurable_earnings, vacation_minimum_percent,
    capital_gains_inclusion_rate_percent, meal_deduction_percent_general,
    meal_deduction_percent_longhaul, notes
) VALUES (
    2010, 10382.00, 16977.00, 500000.00, 11.000, 18.000,
    3.000, 10.000, 5.00,
    0.0495, 0.0495, 47200.00, 3500.00, 2163.15, 2163.15,
    0.0173, 43200.00, 747.36, 1046.30,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2010 rates - Federal general corporate rate reduced to 18%'
) ON CONFLICT (year) DO UPDATE SET
    federal_basic_personal_amount = EXCLUDED.federal_basic_personal_amount,
    alberta_basic_personal_amount = EXCLUDED.alberta_basic_personal_amount,
    federal_small_business_limit = EXCLUDED.federal_small_business_limit,
    federal_small_business_rate = EXCLUDED.federal_small_business_rate,
    federal_general_corporate_rate = EXCLUDED.federal_general_corporate_rate,
    ab_corp_small_business_rate = EXCLUDED.ab_corp_small_business_rate,
    ab_corp_general_rate = EXCLUDED.ab_corp_general_rate,
    gst_rate = EXCLUDED.gst_rate,
    cpp_contribution_rate_employee = EXCLUDED.cpp_contribution_rate_employee,
    cpp_contribution_rate_employer = EXCLUDED.cpp_contribution_rate_employer,
    cpp_max_pensionable_earnings = EXCLUDED.cpp_max_pensionable_earnings,
    cpp_basic_exemption = EXCLUDED.cpp_basic_exemption,
    cpp_max_employee_contribution = EXCLUDED.cpp_max_employee_contribution,
    cpp_max_employer_contribution = EXCLUDED.cpp_max_employer_contribution,
    ei_rate = EXCLUDED.ei_rate,
    ei_max_insurable_earnings = EXCLUDED.ei_max_insurable_earnings,
    ei_max_employee_contribution = EXCLUDED.ei_max_employee_contribution,
    ei_max_employer_contribution = EXCLUDED.ei_max_employer_contribution,
    wcb_ab_max_insurable_earnings = EXCLUDED.wcb_ab_max_insurable_earnings,
    vacation_minimum_percent = EXCLUDED.vacation_minimum_percent,
    capital_gains_inclusion_rate_percent = EXCLUDED.capital_gains_inclusion_rate_percent,
    meal_deduction_percent_general = EXCLUDED.meal_deduction_percent_general,
    meal_deduction_percent_longhaul = EXCLUDED.meal_deduction_percent_longhaul,
    notes = EXCLUDED.notes;

-- Verification query for 2008-2025 coverage
SELECT 
    year,
    federal_basic_personal_amount AS fed_basic,
    cpp_contribution_rate_employee AS cpp_rate,
    cpp_max_pensionable_earnings AS cpp_max_earn,
    ei_rate,
    ei_max_insurable_earnings AS ei_max_earn,
    gst_rate
FROM tax_year_reference 
WHERE year BETWEEN 2008 AND 2025 
ORDER BY year;

-- Summary statistics
SELECT 
    COUNT(*) as years_populated,
    MIN(year) as earliest_year,
    MAX(year) as latest_year,
    COUNT(*) FILTER (WHERE cpp_contribution_rate_employee IS NOT NULL) as cpp_populated,
    COUNT(*) FILTER (WHERE ei_rate IS NOT NULL) as ei_populated,
    COUNT(*) FILTER (WHERE gst_rate IS NOT NULL) as gst_populated
FROM tax_year_reference 
WHERE year BETWEEN 2008 AND 2025;

-- Show CPP rate progression over time
SELECT 
    year,
    cpp_contribution_rate_employee AS cpp_rate,
    cpp_max_pensionable_earnings AS max_earnings,
    cpp_max_employee_contribution AS max_contribution,
    CASE 
        WHEN year <= 2018 THEN 'Pre-Enhancement'
        WHEN year BETWEEN 2019 AND 2023 THEN 'CPP Enhancement Phase'
        ELSE 'CPP2 Era'
    END as era
FROM tax_year_reference 
WHERE year BETWEEN 2008 AND 2025 
ORDER BY year;
