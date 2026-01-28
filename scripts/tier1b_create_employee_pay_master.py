#!/usr/bin/env python
"""TIER 1B - FOUNDATION: Create employee_pay_master table.
Master record per employee per pay period (link to charters for hours).
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD",os.environ.get("DB_PASSWORD"))

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("TIER 1B: CREATING EMPLOYEE_PAY_MASTER TABLE")
print("="*100)
print()

# Drop if exists
cur.execute("DROP TABLE IF EXISTS employee_pay_master CASCADE")
print("✅ Dropped existing employee_pay_master table")

# Create table
cur.execute("""
    CREATE TABLE employee_pay_master (
        employee_pay_id SERIAL PRIMARY KEY,
        employee_id INT NOT NULL REFERENCES employees(employee_id),
        pay_period_id INT NOT NULL REFERENCES pay_periods(pay_period_id),
        fiscal_year INT NOT NULL,
        
        -- Hours (from charters/dispatcher data)
        charter_hours_sum NUMERIC(10,2),
        approved_hours NUMERIC(10,2),
        overtime_hours NUMERIC(10,2),
        manual_hours_adjustment NUMERIC(10,2),
        total_hours_worked NUMERIC(10,2),
        
        -- Rate info
        hourly_rate NUMERIC(10,2),
        rate_source TEXT,  -- 'employee_master' | 'charter_default' | 'manual_override'
        
        -- Pay components (gross)
        base_pay NUMERIC(12,2),
        gratuity_percent NUMERIC(5,2),
        gratuity_amount NUMERIC(12,2),
        float_draw NUMERIC(12,2),
        reimbursements NUMERIC(12,2),
        other_income NUMERIC(12,2),
        gross_pay NUMERIC(12,2),
        
        -- Deductions
        federal_tax NUMERIC(12,2),
        provincial_tax NUMERIC(12,2),
        cpp_employee NUMERIC(12,2),
        ei_employee NUMERIC(12,2),
        union_dues NUMERIC(12,2),
        radio_dues NUMERIC(12,2),
        voucher_deductions NUMERIC(12,2),
        misc_deductions NUMERIC(12,2),
        total_deductions NUMERIC(12,2),
        
        -- Net
        net_pay NUMERIC(12,2),
        
        -- Data quality indicators
        data_completeness NUMERIC(5,2),  -- 0-100%, % of period covered by data
        data_source TEXT,  -- 'charter_hours' | 'manual_entry' | 'reconstructed' | 'mixed'
        confidence_level NUMERIC(5,2),  -- 0-100%, how confident is this data
        notes TEXT,
        
        -- Audit trail
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        created_by TEXT DEFAULT 'system',
        
        -- Constraints
        UNIQUE(employee_id, pay_period_id),
        CONSTRAINT check_hours CHECK (total_hours_worked >= 0),
        CONSTRAINT check_pay CHECK (gross_pay >= 0),
        CONSTRAINT check_net CHECK (net_pay IS NULL OR net_pay >= 0)
    );
    
    CREATE INDEX idx_emp_pay_employee ON employee_pay_master(employee_id);
    CREATE INDEX idx_emp_pay_period ON employee_pay_master(pay_period_id);
    CREATE INDEX idx_emp_pay_year ON employee_pay_master(fiscal_year);
    CREATE INDEX idx_emp_pay_employee_year ON employee_pay_master(employee_id, fiscal_year);
    CREATE INDEX idx_emp_pay_completeness ON employee_pay_master(data_completeness);
""")
print("✅ Created employee_pay_master table with indexes")

# Verify structure
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='employee_pay_master'
    ORDER BY ordinal_position
""")
cols = cur.fetchall()
print(f"\nTable structure ({len(cols)} columns):")
print("-" * 100)
for col, dtype in cols:
    print(f"  {col:<30} {dtype}")

conn.commit()
cur.close()
conn.close()

print("\n✅ EMPLOYEE_PAY_MASTER TABLE CREATED!")
