-- Seed CRA-verified CPP/EI payroll values for 2012-2026.
-- Source: CRA payroll tables (outside Quebec) for CPP and EI annual rates/maxima.

INSERT INTO tax_year_reference (
    year,
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
    notes
)
VALUES
    (2012, 0.0495, 0.0495, 50100.00, 3500.00, 2306.70, 2306.70, 0.0183, 45900.00, 839.97, 1175.96, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2013, 0.0495, 0.0495, 51100.00, 3500.00, 2356.20, 2356.20, 0.0188, 47400.00, 891.12, 1247.57, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2014, 0.0495, 0.0495, 52500.00, 3500.00, 2425.50, 2425.50, 0.0188, 48600.00, 913.68, 1279.15, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2015, 0.0495, 0.0495, 53600.00, 3500.00, 2479.95, 2479.95, 0.0188, 49500.00, 930.60, 1302.84, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2016, 0.0495, 0.0495, 54900.00, 3500.00, 2544.30, 2544.30, 0.0188, 50800.00, 955.04, 1337.06, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2017, 0.0495, 0.0495, 55300.00, 3500.00, 2564.10, 2564.10, 0.0163, 51300.00, 836.19, 1170.67, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2018, 0.0495, 0.0495, 55900.00, 3500.00, 2593.80, 2593.80, 0.0166, 51700.00, 858.22, 1201.51, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2019, 0.0510, 0.0510, 57400.00, 3500.00, 2748.90, 2748.90, 0.0162, 53100.00, 860.22, 1204.31, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2020, 0.0525, 0.0525, 58700.00, 3500.00, 2898.00, 2898.00, 0.0158, 54200.00, 856.36, 1198.90, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2021, 0.0545, 0.0545, 61600.00, 3500.00, 3166.45, 3166.45, 0.0158, 56300.00, 889.54, 1245.36, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2022, 0.0570, 0.0570, 64900.00, 3500.00, 3499.80, 3499.80, 0.0158, 60300.00, 952.74, 1333.84, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2023, 0.0595, 0.0595, 66600.00, 3500.00, 3754.45, 3754.45, 0.0163, 61500.00, 1002.45, 1403.43, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2024, 0.0595, 0.0595, 68500.00, 3500.00, 3867.50, 3867.50, 0.0166, 63200.00, 1049.12, 1468.77, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2025, 0.0595, 0.0595, 71300.00, 3500.00, 4034.10, 4034.10, 0.0164, 65700.00, 1077.48, 1508.47, 'CPP/EI values verified against CRA payroll tables (outside Quebec)'),
    (2026, 0.0595, 0.0595, 74600.00, 3500.00, 4230.45, 4230.45, 0.0163, 68900.00, 1123.07, 1572.30, 'CPP/EI values verified against CRA payroll tables (outside Quebec)')
ON CONFLICT (year) DO UPDATE SET
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
    notes = COALESCE(tax_year_reference.notes, EXCLUDED.notes);
