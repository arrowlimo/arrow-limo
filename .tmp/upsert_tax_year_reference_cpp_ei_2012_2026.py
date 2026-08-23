from dotenv import load_dotenv
import os, psycopg2

load_dotenv('L:/limo/.env')
load_dotenv('L:/limo/.env.neon')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', '5432')),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', ''),
    sslmode=(os.getenv('DB_SSLMODE') or 'prefer'),
)
cur = conn.cursor()

rates = {
    2026: dict(cpp_rate=0.0595, cpp_max_pensionable=74600.00, cpp_exempt=3500.00, cpp_max_employee=4230.45, ei_rate=0.0163, ei_max_insurable=68900.00, ei_max_employee=1123.07),
    2025: dict(cpp_rate=0.0595, cpp_max_pensionable=71300.00, cpp_exempt=3500.00, cpp_max_employee=4034.10, ei_rate=0.0164, ei_max_insurable=65700.00, ei_max_employee=1077.48),
    2024: dict(cpp_rate=0.0595, cpp_max_pensionable=68500.00, cpp_exempt=3500.00, cpp_max_employee=3867.50, ei_rate=0.0166, ei_max_insurable=63200.00, ei_max_employee=1049.12),
    2023: dict(cpp_rate=0.0595, cpp_max_pensionable=66600.00, cpp_exempt=3500.00, cpp_max_employee=3754.45, ei_rate=0.0163, ei_max_insurable=61500.00, ei_max_employee=1002.45),
    2022: dict(cpp_rate=0.0570, cpp_max_pensionable=64900.00, cpp_exempt=3500.00, cpp_max_employee=3499.80, ei_rate=0.0158, ei_max_insurable=60300.00, ei_max_employee=952.74),
    2021: dict(cpp_rate=0.0545, cpp_max_pensionable=61600.00, cpp_exempt=3500.00, cpp_max_employee=3166.45, ei_rate=0.0158, ei_max_insurable=56300.00, ei_max_employee=889.54),
    2020: dict(cpp_rate=0.0525, cpp_max_pensionable=58700.00, cpp_exempt=3500.00, cpp_max_employee=2898.00, ei_rate=0.0158, ei_max_insurable=54200.00, ei_max_employee=856.36),
    2019: dict(cpp_rate=0.0510, cpp_max_pensionable=57400.00, cpp_exempt=3500.00, cpp_max_employee=2748.90, ei_rate=0.0162, ei_max_insurable=53100.00, ei_max_employee=860.22),
    2018: dict(cpp_rate=0.0495, cpp_max_pensionable=55900.00, cpp_exempt=3500.00, cpp_max_employee=2593.80, ei_rate=0.0166, ei_max_insurable=51700.00, ei_max_employee=858.22),
    2017: dict(cpp_rate=0.0495, cpp_max_pensionable=55300.00, cpp_exempt=3500.00, cpp_max_employee=2564.10, ei_rate=0.0163, ei_max_insurable=51300.00, ei_max_employee=836.19),
    2016: dict(cpp_rate=0.0495, cpp_max_pensionable=54900.00, cpp_exempt=3500.00, cpp_max_employee=2544.30, ei_rate=0.0188, ei_max_insurable=50800.00, ei_max_employee=955.04),
    2015: dict(cpp_rate=0.0495, cpp_max_pensionable=53600.00, cpp_exempt=3500.00, cpp_max_employee=2479.95, ei_rate=0.0188, ei_max_insurable=49500.00, ei_max_employee=930.60),
    2014: dict(cpp_rate=0.0495, cpp_max_pensionable=52500.00, cpp_exempt=3500.00, cpp_max_employee=2425.50, ei_rate=0.0188, ei_max_insurable=48600.00, ei_max_employee=913.68),
    2013: dict(cpp_rate=0.0495, cpp_max_pensionable=51100.00, cpp_exempt=3500.00, cpp_max_employee=2356.20, ei_rate=0.0188, ei_max_insurable=47400.00, ei_max_employee=891.12),
    2012: dict(cpp_rate=0.0495, cpp_max_pensionable=50100.00, cpp_exempt=3500.00, cpp_max_employee=2306.70, ei_rate=0.0183, ei_max_insurable=45900.00, ei_max_employee=839.97),
}

sql = """
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
) VALUES (
    %(year)s,
    %(cpp_rate)s,
    %(cpp_rate)s,
    %(cpp_max_pensionable)s,
    %(cpp_exempt)s,
    %(cpp_max_employee)s,
    %(cpp_max_employee)s,
    %(ei_rate)s,
    %(ei_max_insurable)s,
    %(ei_max_employee)s,
    %(ei_max_employer)s,
    %(notes)s
)
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
    notes = COALESCE(tax_year_reference.notes, EXCLUDED.notes)
"""

for year, v in rates.items():
    payload = dict(v)
    payload['year'] = year
    payload['ei_max_employer'] = round(v['ei_max_employee'] * 1.4, 2)
    payload['notes'] = 'CPP/EI values verified against CRA payroll tables (outside Quebec)'
    cur.execute(sql, payload)

conn.commit()

cur.execute("""
SELECT year, cpp_contribution_rate_employee, cpp_max_employee_contribution,
       ei_rate, ei_max_employee_contribution
FROM tax_year_reference
WHERE year BETWEEN 2012 AND 2026
ORDER BY year
""")
for row in cur.fetchall():
    print(row)

cur.close(); conn.close()
