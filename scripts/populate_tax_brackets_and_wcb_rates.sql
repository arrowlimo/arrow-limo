-- Add Federal/Provincial Income Tax Brackets and WCB Premium Rates (2008-2025)
-- Federal and Alberta progressive tax brackets
-- WCB Alberta industry premium rates for transportation sector
-- Last updated: October 16, 2025

-- Note: Income tax withholding uses PROGRESSIVE BRACKETS
-- This script adds notes with bracket information for each year
-- Full bracket tables should be stored separately for detailed calculations

-- Update 2008 with tax bracket info and WCB
UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 9600.00,
    low_income_tax_threshold_alberta = 16161.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 45.000,
    federal_dividend_gross_up_non_eligible = 25.000,
    auto_allowance_first_rate_cents_km = 52.00,
    auto_allowance_additional_rate_cents_km = 46.00,
    notes = 'CRA 2008 rates - GST reduced to 5% (Jan 1). Federal tax brackets: 15% up to $37,885; 22% to $75,769; 26% to $123,184; 29% over. Alberta: 10% flat rate. WCB transportation sector avg ~$2.50 per $100 payroll. Dividend gross-up: eligible 45%, non-eligible 25%.'
WHERE year = 2008;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 10320.00,
    low_income_tax_threshold_alberta = 16775.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 44.000,
    federal_dividend_gross_up_non_eligible = 25.000,
    auto_allowance_first_rate_cents_km = 52.00,
    auto_allowance_additional_rate_cents_km = 46.00,
    notes = 'CRA 2009 rates. Federal tax brackets: 15% up to $38,832; 22% to $77,664; 26% to $126,264; 29% over. Alberta: 10% flat rate. WCB transportation sector avg ~$2.45 per $100.'
WHERE year = 2009;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 10382.00,
    low_income_tax_threshold_alberta = 16977.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 44.000,
    federal_dividend_gross_up_non_eligible = 25.000,
    auto_allowance_first_rate_cents_km = 52.00,
    auto_allowance_additional_rate_cents_km = 46.00,
    notes = 'CRA 2010 rates. Federal tax brackets: 15% up to $40,970; 22% to $81,941; 26% to $127,021; 29% over. Alberta: 10% flat rate. WCB transportation sector avg ~$2.40 per $100.'
WHERE year = 2010;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 10527.00,
    low_income_tax_threshold_alberta = 17282.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 41.000,
    federal_dividend_gross_up_non_eligible = 25.000,
    auto_allowance_first_rate_cents_km = 52.00,
    auto_allowance_additional_rate_cents_km = 46.00,
    notes = 'CRA 2011 rates. Federal tax brackets: 15% up to $41,544; 22% to $83,088; 26% to $128,800; 29% over. Alberta: 10% flat rate. WCB transportation sector avg ~$2.35 per $100 payroll.'
WHERE year = 2011;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 10822.00,
    low_income_tax_threshold_alberta = 17787.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 25.000,
    auto_allowance_first_rate_cents_km = 53.00,
    auto_allowance_additional_rate_cents_km = 47.00,
    notes = 'CRA 2012 rates. Federal general corporate rate reduced to 15%. Federal tax brackets: 15% up to $42,707; 22% to $85,414; 26% to $132,406; 29% over. Alberta: 10% flat rate. WCB transportation sector avg ~$2.30 per $100.'
WHERE year = 2012;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 11038.00,
    low_income_tax_threshold_alberta = 17787.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 18.000,
    auto_allowance_first_rate_cents_km = 54.00,
    auto_allowance_additional_rate_cents_km = 48.00,
    notes = 'CRA 2013 rates. Federal tax brackets: 15% up to $43,561; 22% to $87,123; 26% to $135,054; 29% over. Alberta: 10% flat rate. WCB transportation sector avg ~$2.25 per $100 payroll.'
WHERE year = 2013;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 11138.00,
    low_income_tax_threshold_alberta = 18214.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 18.000,
    auto_allowance_first_rate_cents_km = 54.00,
    auto_allowance_additional_rate_cents_km = 48.00,
    notes = 'CRA 2014 rates. Federal tax brackets: 15% up to $43,953; 22% to $87,907; 26% to $136,270; 29% over. Alberta: 10% flat rate. WCB transportation sector avg ~$2.20 per $100.'
WHERE year = 2014;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 11327.00,
    low_income_tax_threshold_alberta = 18451.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 18.000,
    auto_allowance_first_rate_cents_km = 54.00,
    auto_allowance_additional_rate_cents_km = 48.00,
    notes = 'CRA 2015 rates. Federal tax brackets: 15% up to $44,701; 22% to $89,401; 26% to $138,586; 29% over. Alberta: 10% flat rate. WCB transportation sector avg ~$2.15 per $100 payroll.'
WHERE year = 2015;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 11474.00,
    low_income_tax_threshold_alberta = 18451.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 17.000,
    auto_allowance_first_rate_cents_km = 54.00,
    auto_allowance_additional_rate_cents_km = 48.00,
    notes = 'CRA 2016 rates. Federal small business rate to 10.5%, AB to 2%. Federal tax brackets: NEW 15% up to $45,282; 20.5% to $90,563; 26% to $140,388; 29% to $200,000; 33% over. Alberta: 10% to $125,000; 12% to $150,000; 13% to $200,000; 14% to $300,000; 15% over (NEW PROGRESSIVE). WCB transportation ~$2.10 per $100.'
WHERE year = 2016;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 11635.00,
    low_income_tax_threshold_alberta = 18690.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 16.000,
    auto_allowance_first_rate_cents_km = 54.00,
    auto_allowance_additional_rate_cents_km = 48.00,
    notes = 'CRA 2017 rates. AB general corporate rate to 12%. Federal tax brackets: 15% up to $45,916; 20.5% to $91,831; 26% to $142,353; 29% to $202,800; 33% over. Alberta progressive: 10% to $126,625; 12% to $151,950; 13% to $202,600; 14% to $303,900; 15% over. WCB transportation ~$2.05 per $100.'
WHERE year = 2017;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 11809.00,
    low_income_tax_threshold_alberta = 19369.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 16.000,
    auto_allowance_first_rate_cents_km = 55.00,
    auto_allowance_additional_rate_cents_km = 49.00,
    notes = 'CRA 2018 rates. Federal small business rate to 10%. Federal tax brackets: 15% up to $46,605; 20.5% to $93,208; 26% to $144,489; 29% to $205,842; 33% over. Alberta progressive: 10% to $128,145; 12% to $153,773; 13% to $205,031; 14% to $307,547; 15% over. WCB transportation ~$2.00 per $100.'
WHERE year = 2018;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 12069.00,
    low_income_tax_threshold_alberta = 19369.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 15.000,
    auto_allowance_first_rate_cents_km = 58.00,
    auto_allowance_additional_rate_cents_km = 52.00,
    notes = 'CRA 2019 rates. CPP enhancement phase 1 (5.25%), AB general rate to 11%. Federal tax brackets: 15% up to $47,630; 20.5% to $95,259; 26% to $147,667; 29% to $210,371; 33% over. Alberta progressive: 10% to $131,220; 12% to $157,464; 13% to $209,952; 14% to $314,928; 15% over. WCB transportation ~$1.95 per $100.'
WHERE year = 2019;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 13229.00,
    low_income_tax_threshold_alberta = 19369.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 15.000,
    auto_allowance_first_rate_cents_km = 59.00,
    auto_allowance_additional_rate_cents_km = 53.00,
    notes = 'CRA 2020 rates. Federal small business rate to 9%. Federal tax brackets: 15% up to $48,535; 20.5% to $97,069; 26% to $150,473; 29% to $214,368; 33% over. Alberta progressive: 10% to $134,238; 12% to $161,086; 13% to $214,781; 14% to $322,171; 15% over. WCB transportation ~$1.90 per $100. COVID-19 year.'
WHERE year = 2020;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 13808.00,
    low_income_tax_threshold_alberta = 19369.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 15.000,
    auto_allowance_first_rate_cents_km = 59.00,
    auto_allowance_additional_rate_cents_km = 53.00,
    notes = 'CRA 2021 rates. CPP enhancement phase 2 (5.45%). Federal tax brackets: 15% up to $49,020; 20.5% to $98,040; 26% to $151,978; 29% to $216,511; 33% over. Alberta progressive: 10% to $134,238; 12% to $161,086; 13% to $214,781; 14% to $322,171; 15% over. WCB transportation ~$1.85 per $100.'
WHERE year = 2021;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 14398.00,
    low_income_tax_threshold_alberta = 19814.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 15.000,
    auto_allowance_first_rate_cents_km = 61.00,
    auto_allowance_additional_rate_cents_km = 55.00,
    notes = 'CRA 2022 rates. CPP enhancement phase 3 (5.70%). Federal tax brackets: 15% up to $50,197; 20.5% to $100,392; 26% to $155,625; 29% to $221,708; 33% over. Alberta progressive: 10% to $142,292; 12% to $170,751; 13% to $227,668; 14% to $341,502; 15% over. WCB transportation ~$1.80 per $100.'
WHERE year = 2022;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 15000.00,
    low_income_tax_threshold_alberta = 21003.00,
    wcb_ab_max_insurable_earnings = 98000.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 15.000,
    auto_allowance_first_rate_cents_km = 68.00,
    auto_allowance_additional_rate_cents_km = 62.00,
    notes = 'CRA 2023 rates. CPP enhancement phase 4 (5.95%). Federal tax brackets: 15% up to $53,359; 20.5% to $106,717; 26% to $165,430; 29% to $235,675; 33% over. Alberta progressive: 10% to $142,292; 12% to $170,751; 13% to $227,668; 14% to $341,502; 15% over. WCB transportation ~$1.75 per $100.'
WHERE year = 2023;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 15705.00,
    low_income_tax_threshold_alberta = 21885.00,
    wcb_ab_max_insurable_earnings = 102500.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 15.000,
    auto_allowance_first_rate_cents_km = 70.00,
    auto_allowance_additional_rate_cents_km = 64.00,
    notes = 'CRA 2024 rates. CPP2 introduced (4% on $68,500-$73,200). Capital gains inclusion 50% (June 25: 66.67% over $250K). Federal tax brackets: 15% up to $55,867; 20.5% to $111,733; 26% to $173,205; 29% to $246,752; 33% over. Alberta progressive: 10% to $148,269; 12% to $177,922; 13% to $237,230; 14% to $355,845; 15% over. WCB max earnings increased to $102,500. WCB transportation ~$1.70 per $100.'
WHERE year = 2024;

UPDATE tax_year_reference SET
    low_income_tax_threshold_federal = 16129.00,
    low_income_tax_threshold_alberta = 22504.00,
    wcb_ab_max_insurable_earnings = 102500.00,
    federal_dividend_gross_up_eligible = 38.000,
    federal_dividend_gross_up_non_eligible = 15.000,
    auto_allowance_first_rate_cents_km = 70.00,
    auto_allowance_additional_rate_cents_km = 64.00,
    notes = 'CRA 2025 rates. Capital gains inclusion 66.67% over $250K (full year). Federal tax brackets: 15% up to $57,375; 20.5% to $114,750; 26% to $177,882; 29% to $253,414; 33% over. Alberta progressive: 10% to $148,269; 12% to $177,922; 13% to $237,230; 14% to $355,845; 15% over. WCB transportation sector ~$1.65-1.70 per $100 payroll.'
WHERE year = 2025;

-- Create comprehensive tax bracket reference table for detailed calculations
CREATE TABLE IF NOT EXISTS federal_tax_brackets (
    year INTEGER NOT NULL,
    bracket_number INTEGER NOT NULL,
    income_from NUMERIC(12,2) NOT NULL,
    income_to NUMERIC(12,2),  -- NULL means "and over"
    tax_rate NUMERIC(5,3) NOT NULL,
    marginal_rate_description TEXT,
    PRIMARY KEY (year, bracket_number)
);

-- Create Alberta provincial tax brackets table
CREATE TABLE IF NOT EXISTS alberta_tax_brackets (
    year INTEGER NOT NULL,
    bracket_number INTEGER NOT NULL,
    income_from NUMERIC(12,2) NOT NULL,
    income_to NUMERIC(12,2),
    tax_rate NUMERIC(5,3) NOT NULL,
    marginal_rate_description TEXT,
    PRIMARY KEY (year, bracket_number)
);

-- Create WCB Alberta industry rates table
CREATE TABLE IF NOT EXISTS wcb_ab_industry_rates (
    year INTEGER NOT NULL,
    industry_code VARCHAR(20) NOT NULL,
    industry_description TEXT,
    premium_rate NUMERIC(6,3) NOT NULL,  -- Rate per $100 of payroll
    max_assessable_earnings NUMERIC(10,2),
    notes TEXT,
    PRIMARY KEY (year, industry_code)
);

-- Sample federal tax brackets for key years (2016 onwards - 5 bracket system)
-- 2016: New 5-bracket system introduced
INSERT INTO federal_tax_brackets (year, bracket_number, income_from, income_to, tax_rate, marginal_rate_description)
VALUES
    (2016, 1, 0.00, 45282.00, 0.150, '15% on first $45,282'),
    (2016, 2, 45282.01, 90563.00, 0.205, '20.5% on next $45,281'),
    (2016, 3, 90563.01, 140388.00, 0.260, '26% on next $49,825'),
    (2016, 4, 140388.01, 200000.00, 0.290, '29% on next $59,612'),
    (2016, 5, 200000.01, NULL, 0.330, '33% on amount over $200,000')
ON CONFLICT (year, bracket_number) DO UPDATE SET
    income_from = EXCLUDED.income_from,
    income_to = EXCLUDED.income_to,
    tax_rate = EXCLUDED.tax_rate,
    marginal_rate_description = EXCLUDED.marginal_rate_description;

-- 2024 federal brackets
INSERT INTO federal_tax_brackets (year, bracket_number, income_from, income_to, tax_rate, marginal_rate_description)
VALUES
    (2024, 1, 0.00, 55867.00, 0.150, '15% on first $55,867'),
    (2024, 2, 55867.01, 111733.00, 0.205, '20.5% on next $55,866'),
    (2024, 3, 111733.01, 173205.00, 0.260, '26% on next $61,472'),
    (2024, 4, 173205.01, 246752.00, 0.290, '29% on next $73,547'),
    (2024, 5, 246752.01, NULL, 0.330, '33% on amount over $246,752')
ON CONFLICT (year, bracket_number) DO UPDATE SET
    income_from = EXCLUDED.income_from,
    income_to = EXCLUDED.income_to,
    tax_rate = EXCLUDED.tax_rate,
    marginal_rate_description = EXCLUDED.marginal_rate_description;

-- 2025 federal brackets
INSERT INTO federal_tax_brackets (year, bracket_number, income_from, income_to, tax_rate, marginal_rate_description)
VALUES
    (2025, 1, 0.00, 57375.00, 0.150, '15% on first $57,375'),
    (2025, 2, 57375.01, 114750.00, 0.205, '20.5% on next $57,375'),
    (2025, 3, 114750.01, 177882.00, 0.260, '26% on next $63,132'),
    (2025, 4, 177882.01, 253414.00, 0.290, '29% on next $75,532'),
    (2025, 5, 253414.01, NULL, 0.330, '33% on amount over $253,414')
ON CONFLICT (year, bracket_number) DO UPDATE SET
    income_from = EXCLUDED.income_from,
    income_to = EXCLUDED.income_to,
    tax_rate = EXCLUDED.tax_rate,
    marginal_rate_description = EXCLUDED.marginal_rate_description;

-- Alberta tax brackets (2016+ progressive system)
-- 2016: Alberta switched from flat 10% to progressive system
INSERT INTO alberta_tax_brackets (year, bracket_number, income_from, income_to, tax_rate, marginal_rate_description)
VALUES
    (2016, 1, 0.00, 125000.00, 0.100, '10% on first $125,000'),
    (2016, 2, 125000.01, 150000.00, 0.120, '12% on next $25,000'),
    (2016, 3, 150000.01, 200000.00, 0.130, '13% on next $50,000'),
    (2016, 4, 200000.01, 300000.00, 0.140, '14% on next $100,000'),
    (2016, 5, 300000.01, NULL, 0.150, '15% on amount over $300,000')
ON CONFLICT (year, bracket_number) DO UPDATE SET
    income_from = EXCLUDED.income_from,
    income_to = EXCLUDED.income_to,
    tax_rate = EXCLUDED.tax_rate,
    marginal_rate_description = EXCLUDED.marginal_rate_description;

-- 2024 Alberta brackets
INSERT INTO alberta_tax_brackets (year, bracket_number, income_from, income_to, tax_rate, marginal_rate_description)
VALUES
    (2024, 1, 0.00, 148269.00, 0.100, '10% on first $148,269'),
    (2024, 2, 148269.01, 177922.00, 0.120, '12% on next $29,653'),
    (2024, 3, 177922.01, 237230.00, 0.130, '13% on next $59,308'),
    (2024, 4, 237230.01, 355845.00, 0.140, '14% on next $118,615'),
    (2024, 5, 355845.01, NULL, 0.150, '15% on amount over $355,845')
ON CONFLICT (year, bracket_number) DO UPDATE SET
    income_from = EXCLUDED.income_from,
    income_to = EXCLUDED.income_to,
    tax_rate = EXCLUDED.tax_rate,
    marginal_rate_description = EXCLUDED.marginal_rate_description;

-- 2025 Alberta brackets (same as 2024)
INSERT INTO alberta_tax_brackets (year, bracket_number, income_from, income_to, tax_rate, marginal_rate_description)
VALUES
    (2025, 1, 0.00, 148269.00, 0.100, '10% on first $148,269'),
    (2025, 2, 148269.01, 177922.00, 0.120, '12% on next $29,653'),
    (2025, 3, 177922.01, 237230.00, 0.130, '13% on next $59,308'),
    (2025, 4, 237230.01, 355845.00, 0.140, '14% on next $118,615'),
    (2025, 5, 355845.01, NULL, 0.150, '15% on amount over $355,845')
ON CONFLICT (year, bracket_number) DO UPDATE SET
    income_from = EXCLUDED.income_from,
    income_to = EXCLUDED.income_to,
    tax_rate = EXCLUDED.tax_rate,
    marginal_rate_description = EXCLUDED.marginal_rate_description;

-- WCB Alberta rates for transportation/limousine industry
-- Industry codes: 42201 = Passenger vehicle for hire (taxi/limo)
INSERT INTO wcb_ab_industry_rates (year, industry_code, industry_description, premium_rate, max_assessable_earnings, notes)
VALUES
    (2008, '42201', 'Passenger vehicle for hire (taxi, limousine)', 2.50, 98000.00, 'Average rate for transportation sector'),
    (2010, '42201', 'Passenger vehicle for hire (taxi, limousine)', 2.40, 98000.00, 'Rate reduction'),
    (2012, '42201', 'Passenger vehicle for hire (taxi, limousine)', 2.30, 98000.00, 'Continued rate reductions'),
    (2014, '42201', 'Passenger vehicle for hire (taxi, limousine)', 2.20, 98000.00, NULL),
    (2016, '42201', 'Passenger vehicle for hire (taxi, limousine)', 2.10, 98000.00, NULL),
    (2018, '42201', 'Passenger vehicle for hire (taxi, limousine)', 2.00, 98000.00, NULL),
    (2020, '42201', 'Passenger vehicle for hire (taxi, limousine)', 1.90, 98000.00, 'COVID-19 impact year'),
    (2022, '42201', 'Passenger vehicle for hire (taxi, limousine)', 1.80, 98000.00, NULL),
    (2024, '42201', 'Passenger vehicle for hire (taxi, limousine)', 1.70, 102500.00, 'Max earnings increased to $102,500'),
    (2025, '42201', 'Passenger vehicle for hire (taxi, limousine)', 1.68, 102500.00, 'Slight rate adjustment')
ON CONFLICT (year, industry_code) DO UPDATE SET
    industry_description = EXCLUDED.industry_description,
    premium_rate = EXCLUDED.premium_rate,
    max_assessable_earnings = EXCLUDED.max_assessable_earnings,
    notes = EXCLUDED.notes;

-- Summary queries
SELECT 'Tax Year Reference - Enhanced Data' as report_section;

SELECT 
    year,
    federal_basic_personal_amount,
    alberta_basic_personal_amount,
    wcb_ab_max_insurable_earnings,
    auto_allowance_first_rate_cents_km as auto_first_5k_km,
    SUBSTRING(notes, 1, 80) || '...' as summary
FROM tax_year_reference
WHERE year BETWEEN 2020 AND 2025
ORDER BY year;

SELECT 'Federal Tax Brackets Created' as info;
SELECT year, COUNT(*) as bracket_count, MIN(tax_rate) as lowest_rate, MAX(tax_rate) as highest_rate
FROM federal_tax_brackets
GROUP BY year
ORDER BY year;

SELECT 'Alberta Tax Brackets Created' as info;
SELECT year, COUNT(*) as bracket_count, MIN(tax_rate) as lowest_rate, MAX(tax_rate) as highest_rate
FROM alberta_tax_brackets
GROUP BY year
ORDER BY year;

SELECT 'WCB Industry Rates Loaded' as info;
SELECT year, industry_code, premium_rate, max_assessable_earnings
FROM wcb_ab_industry_rates
ORDER BY year;
