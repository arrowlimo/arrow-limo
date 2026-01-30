#!/usr/bin/env python3
"""Check what's in the PD7A staging table"""
import os, psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

conn = get_conn()
cur = conn.cursor()

cur.execute("""
    SELECT year, source_file, gross_payroll, cpp_employee, ei_employee, 
           tax_deductions, num_employees_paid
    FROM staging_pd7a_year_end_summary 
    ORDER BY year, gross_payroll DESC
""")

print(f"\n{'Year':<6} {'Gross':>15} {'CPP':>12} {'EI':>12} {'Tax':>12} {'Emp':>5} Source File")
print(f"{'-'*120}")

for row in cur.fetchall():
    year = row[0]
    source = row[1].split('\\')[-1] if row[1] else 'Unknown'
    print(f"{year:<6} ${row[2]:>14,.2f} ${row[3]:>11,.2f} ${row[4]:>11,.2f} ${row[5]:>11,.2f} {row[6]:>5} {source}")

cur.close()
conn.close()
