-- Populate Tax Year Reference with Historical CRA Rates (2011-2025)
-- Data sourced from Canada Revenue Agency official publications
-- Last updated: October 16, 2025

-- Clear any existing placeholder data
DELETE FROM tax_year_reference WHERE year BETWEEN 2011 AND 2025;

-- 2011 Tax Rates
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
    2011,
    10527.00,  -- Federal basic personal amount
    17282.00,  -- Alberta basic personal amount
    500000.00, -- Small business limit
    11.000,    -- Federal small business rate (11%)
    16.500,    -- Federal general corporate rate
    3.000,     -- AB small business rate (3%)
    10.000,    -- AB general corporate rate (10%)
    5.00,      -- GST rate (5%)
    0.0495,    -- CPP employee rate (4.95%)
    0.0495,    -- CPP employer rate (4.95%)
    48300.00,  -- CPP maximum pensionable earnings
    3500.00,   -- CPP basic exemption
    2217.60,   -- CPP max employee contribution
    2217.60,   -- CPP max employer contribution
    0.0178,    -- EI rate (1.78%)
    44200.00,  -- EI maximum insurable earnings
    786.76,    -- EI max employee contribution
    1101.46,   -- EI max employer contribution (1.4x)
    98000.00,  -- WCB AB max insurable earnings
    4.00,      -- Vacation minimum percent (4% after 1 year)
    50.00,     -- Capital gains inclusion rate (50%)
    50.00,     -- Meal deduction general (50%)
    80.00,     -- Meal deduction long-haul (80%)
    'CRA 2011 rates - verified from T4127 Payroll Deductions Tables'
);

-- 2012 Tax Rates
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
    2012, 10822.00, 17787.00, 500000.00, 11.000, 15.000,
    3.000, 10.000, 5.00,
    0.0495, 0.0495, 50100.00, 3500.00, 2306.70, 2306.70,
    0.0183, 45900.00, 839.97, 1175.96,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2012 rates - Federal general corporate rate reduced to 15%'
);

-- 2013 Tax Rates
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
    2013, 11038.00, 17787.00, 500000.00, 11.000, 15.000,
    3.000, 10.000, 5.00,
    0.0495, 0.0495, 51100.00, 3500.00, 2356.20, 2356.20,
    0.0188, 47400.00, 891.12, 1247.57,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2013 rates'
);

-- 2014 Tax Rates
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
    2014, 11138.00, 18214.00, 500000.00, 11.000, 15.000,
    3.000, 10.000, 5.00,
    0.0495, 0.0495, 52500.00, 3500.00, 2425.50, 2425.50,
    0.0188, 48600.00, 913.68, 1279.15,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2014 rates'
);

-- 2015 Tax Rates
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
    2015, 11327.00, 18451.00, 500000.00, 11.000, 15.000,
    3.000, 10.000, 5.00,
    0.0495, 0.0495, 53600.00, 3500.00, 2479.95, 2479.95,
    0.0188, 49500.00, 930.60, 1302.84,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2015 rates'
);

-- 2016 Tax Rates
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
    2016, 11474.00, 18451.00, 500000.00, 10.500, 15.000,
    2.000, 10.000, 5.00,
    0.0495, 0.0495, 54900.00, 3500.00, 2544.30, 2544.30,
    0.0188, 50800.00, 955.04, 1337.06,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2016 rates - Federal small business rate reduced to 10.5%, AB to 2%'
);

-- 2017 Tax Rates
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
    2017, 11635.00, 18690.00, 500000.00, 10.500, 15.000,
    2.000, 12.000, 5.00,
    0.0495, 0.0495, 55300.00, 3500.00, 2564.10, 2564.10,
    0.0163, 51300.00, 836.19, 1170.67,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2017 rates - AB general corporate rate increased to 12%'
);

-- 2018 Tax Rates
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
    2018, 11809.00, 19369.00, 500000.00, 10.000, 15.000,
    2.000, 12.000, 5.00,
    0.0495, 0.0495, 55900.00, 3500.00, 2593.80, 2593.80,
    0.0166, 51700.00, 858.22, 1201.51,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2018 rates - Federal small business rate reduced to 10%'
);

-- 2019 Tax Rates (CPP Enhancement begins)
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
    2019, 12069.00, 19369.00, 500000.00, 10.000, 15.000,
    2.000, 11.000, 5.00,
    0.0525, 0.0525, 57400.00, 3500.00, 2829.75, 2829.75,
    0.0162, 53100.00, 860.22, 1204.31,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2019 rates - CPP enhancement phase 1 (rate to 5.25%), AB general rate to 11%'
);

-- 2020 Tax Rates
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
    2020, 13229.00, 19369.00, 500000.00, 9.000, 15.000,
    2.000, 11.000, 5.00,
    0.0525, 0.0525, 58700.00, 3500.00, 2898.00, 2898.00,
    0.0158, 54200.00, 856.36, 1198.90,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2020 rates - Federal small business rate to 9%'
);

-- 2021 Tax Rates
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
    2021, 13808.00, 19369.00, 500000.00, 9.000, 15.000,
    2.000, 11.000, 5.00,
    0.0545, 0.0545, 61600.00, 3500.00, 3166.45, 3166.45,
    0.0158, 56300.00, 889.54, 1245.36,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2021 rates - CPP enhancement phase 2 (rate to 5.45%)'
);

-- 2022 Tax Rates
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
    2022, 14398.00, 19814.00, 500000.00, 9.000, 15.000,
    2.000, 11.000, 5.00,
    0.0570, 0.0570, 64900.00, 3500.00, 3499.80, 3499.80,
    0.0162, 60300.00, 976.86, 1367.60,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2022 rates - CPP enhancement phase 3 (rate to 5.70%)'
);

-- 2023 Tax Rates
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
    2023, 15000.00, 21003.00, 500000.00, 9.000, 15.000,
    2.000, 11.000, 5.00,
    0.0595, 0.0595, 66600.00, 3500.00, 3754.45, 3754.45,
    0.0163, 61500.00, 1002.45, 1403.43,
    98000.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2023 rates - CPP enhancement phase 4 (rate to 5.95%)'
);

-- 2024 Tax Rates (CPP2 introduced for high earners)
INSERT INTO tax_year_reference (
    year, federal_basic_personal_amount, alberta_basic_personal_amount,
    federal_small_business_limit, federal_small_business_rate, federal_general_corporate_rate,
    ab_corp_small_business_rate, ab_corp_general_rate, gst_rate,
    cpp_contribution_rate_employee, cpp_contribution_rate_employer,
    cpp_max_pensionable_earnings, cpp_basic_exemption,
    cpp_max_employee_contribution, cpp_max_employer_contribution,
    cpp2_contribution_rate_employee, cpp2_contribution_rate_employer,
    cpp2_upper_pensionable_earnings, cpp2_max_employee_contribution,
    cpp2_max_employer_contribution,
    ei_rate, ei_max_insurable_earnings,
    ei_max_employee_contribution, ei_max_employer_contribution,
    wcb_ab_max_insurable_earnings, vacation_minimum_percent,
    capital_gains_inclusion_rate_percent, meal_deduction_percent_general,
    meal_deduction_percent_longhaul, notes
) VALUES (
    2024, 15705.00, 21885.00, 500000.00, 9.000, 15.000,
    2.000, 11.000, 5.00,
    0.0595, 0.0595, 68500.00, 3500.00, 3867.50, 3867.50,
    0.0400, 0.0400, 73200.00, 188.00, 188.00,
    0.0166, 63200.00, 1049.12, 1468.77,
    102500.00, 4.00, 50.00, 50.00, 80.00,
    'CRA 2024 rates - CPP2 introduced (4% on earnings $68,500-$73,200), Capital gains 50% (June 25: 66.67% for corps/trusts over $250K)'
);

-- 2025 Tax Rates (Projected/Confirmed)
INSERT INTO tax_year_reference (
    year, federal_basic_personal_amount, alberta_basic_personal_amount,
    federal_small_business_limit, federal_small_business_rate, federal_general_corporate_rate,
    ab_corp_small_business_rate, ab_corp_general_rate, gst_rate,
    cpp_contribution_rate_employee, cpp_contribution_rate_employer,
    cpp_max_pensionable_earnings, cpp_basic_exemption,
    cpp_max_employee_contribution, cpp_max_employer_contribution,
    cpp2_contribution_rate_employee, cpp2_contribution_rate_employer,
    cpp2_upper_pensionable_earnings, cpp2_max_employee_contribution,
    cpp2_max_employer_contribution,
    ei_rate, ei_max_insurable_earnings,
    ei_max_employee_contribution, ei_max_employer_contribution,
    wcb_ab_max_insurable_earnings, vacation_minimum_percent,
    capital_gains_inclusion_rate_percent, meal_deduction_percent_general,
    meal_deduction_percent_longhaul, notes
) VALUES (
    2025, 16129.00, 22504.00, 500000.00, 9.000, 15.000,
    2.000, 11.000, 5.00,
    0.0595, 0.0595, 71300.00, 3500.00, 4034.70, 4034.70,
    0.0400, 0.0400, 76200.00, 196.00, 196.00,
    0.0163, 65000.00, 1059.50, 1483.30,
    102500.00, 4.00, 66.67, 50.00, 80.00,
    'CRA 2025 rates - Capital gains inclusion rate 66.67% for amounts over $250K'
);

-- Verification query
SELECT 
    year,
    federal_basic_personal_amount,
    cpp_contribution_rate_employee,
    cpp_max_pensionable_earnings,
    ei_rate,
    ei_max_insurable_earnings,
    gst_rate
FROM tax_year_reference 
WHERE year BETWEEN 2011 AND 2025 
ORDER BY year;

-- Summary
SELECT 
    COUNT(*) as years_populated,
    MIN(year) as earliest_year,
    MAX(year) as latest_year,
    COUNT(*) FILTER (WHERE cpp_contribution_rate_employee IS NOT NULL) as cpp_populated,
    COUNT(*) FILTER (WHERE ei_rate IS NOT NULL) as ei_populated
FROM tax_year_reference 
WHERE year BETWEEN 2011 AND 2025;
