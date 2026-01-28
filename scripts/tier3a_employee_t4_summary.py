#!/usr/bin/env python
"""TIER 3A: Create employee_t4_summary table.
T4 anchor data: known totals per employee per year from historical T4 forms.
This is the ground truth for reconciliation.
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("TIER 3A: CREATE EMPLOYEE_T4_SUMMARY TABLE")
print("="*100)
print()

# Drop if exists
cur.execute("DROP TABLE IF EXISTS employee_t4_summary CASCADE")
print("✅ Dropped existing employee_t4_summary table")

# Create table
cur.execute("""
    CREATE TABLE employee_t4_summary (
        t4_id SERIAL PRIMARY KEY,
        employee_id INT NOT NULL REFERENCES employees(employee_id),
        fiscal_year INT NOT NULL,
        
        -- T4 Boxes (2023 T4 form references)
        t4_employment_income NUMERIC(12,2),     -- Box 14: Total employment income
        t4_federal_tax NUMERIC(12,2),            -- Box 22: Federal income tax deducted
        t4_provincial_tax NUMERIC(12,2),         -- Box 21: Provincial income tax deducted
        t4_cpp_contributions NUMERIC(12,2),      -- Box 16: Employee CPP contributions
        t4_ei_contributions NUMERIC(12,2),       -- Box 18: Employee EI contributions
        t4_union_dues NUMERIC(12,2),             -- Box 44: Union dues paid
        t4_other_deductions NUMERIC(12,2),       -- Box 52: Other deductions
        
        -- Data source
        source TEXT,  -- 'revenue_canada_file' | 'manual_entry' | 'reconstructed'
        confidence_level NUMERIC(5,2),  -- 0-100% (100=verified, 50=from forms, <50=estimated)
        is_verified BOOLEAN DEFAULT false,
        
        -- Audit trail
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        created_by TEXT DEFAULT 'system',
        notes TEXT,
        
        -- Constraint
        UNIQUE(employee_id, fiscal_year)
    );
    
    CREATE INDEX idx_t4_employee_year ON employee_t4_summary(employee_id, fiscal_year);
    CREATE INDEX idx_t4_year ON employee_t4_summary(fiscal_year);
    CREATE INDEX idx_t4_confidence ON employee_t4_summary(confidence_level);
""")
print("✅ Created employee_t4_summary table with indexes")

# Check for existing T4 data in system
print("\nSearching for existing T4 data to import...")
print("-" * 100)

# Check for T4 records already in database
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema='public' AND table_name LIKE '%t4%'
""")
t4_tables = [row[0] for row in cur.fetchall()]
print(f"Found {len(t4_tables)} T4-related tables:")
for tbl in t4_tables[:10]:  # Show first 10
    print(f"  - {tbl}")

# Try to extract T4 data from existing tables if available
cur.execute("""
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema='public'
      AND (column_name LIKE '%t4%' OR column_name LIKE '%box%')
    ORDER BY table_name
""")
t4_cols = cur.fetchall()
if t4_cols:
    print(f"\nFound {len(t4_cols)} T4-related columns:")
    for tbl, col in t4_cols[:10]:
        print(f"  - {tbl}.{col}")

# Sample data: 2024 stub calculation
print("\nInserting 2024 calculated T4 stubs (for validation)...")
print("-" * 100)

# Get all drivers with 2024 pay data
cur.execute("""
    SELECT 
        employee_id,
        SUM(gross_income_before_deductions) as total_income,
        SUM(federal_tax_calc) as fed_tax,
        SUM(provincial_tax_calc) as prov_tax,
        SUM(cpp_employee_calc) as cpp_emp,
        SUM(ei_employee_calc) as ei_emp
    FROM employee_pay_calc
    WHERE fiscal_year = 2024
    GROUP BY employee_id
""")

inserted = 0
for emp_id, income, fed, prov, cpp, ei in cur.fetchall():
    if income and income > 0:
        cur.execute("""
            INSERT INTO employee_t4_summary 
            (employee_id, fiscal_year, t4_employment_income, t4_federal_tax, 
             t4_provincial_tax, t4_cpp_contributions, t4_ei_contributions,
             source, confidence_level, created_by, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'reconstructed', 75, 'system',
                    'Calculated from 2024 charter hours - needs verification')
        """, (emp_id, 2024, income, fed, prov, cpp, ei))
        inserted += 1

conn.commit()
print(f"✅ Inserted {inserted} 2024 calculated T4 stubs")

# Show summary
print("\n2024 T4 Summary (Calculated Stubs):")
print("-" * 100)
cur.execute("""
    SELECT 
        e.full_name,
        t.t4_employment_income,
        t.t4_federal_tax,
        t.t4_provincial_tax,
        t.t4_cpp_contributions,
        t.t4_ei_contributions,
        t.confidence_level
    FROM employee_t4_summary t
    JOIN employees e ON t.employee_id = e.employee_id
    WHERE t.fiscal_year = 2024
    ORDER BY t.t4_employment_income DESC
    LIMIT 10
""")
print("Employee | Employment Income | Fed Tax | Prov Tax | CPP | EI | Confidence")
print("-" * 100)
for name, income, fed, prov, cpp, ei, conf in cur.fetchall():
    print(f"{name:<30} | ${income:>15,.2f} | ${fed:>6,.0f} | ${prov:>7,.0f} | ${cpp:>6,.0f} | ${ei:>6,.0f} | {conf:>3.0f}%")

# Verify table
cur.execute("SELECT COUNT(*) FROM employee_t4_summary")
total_records = cur.fetchone()[0]
print(f"\nTotal T4 records: {total_records}")

conn.commit()
cur.close()
conn.close()

print("\n✅ TIER 3A COMPLETE - EMPLOYEE_T4_SUMMARY TABLE CREATED!")
