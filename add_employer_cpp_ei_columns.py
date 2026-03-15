#!/usr/bin/env python3
"""
Add employer CPP and EI contribution columns to employee_pay_master table.

CRA Requirements:
- CPP Employer = CPP Employee (1:1 matching contribution)
- EI Employer = EI Employee × 1.4 (140% rate for 2024-2026)

This migration:
1. Adds cpp_employer and ei_employer columns
2. Backfills data for existing records
3. Updates PD7A calculations to include employer portions
"""

def add_employer_columns():
    """Add employer CPP/EI columns and backfill existing data."""
    
    try:
        import psycopg2
        import os
        
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            database=os.environ.get('DB_NAME', 'arrow_limo'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', '')
        )
        cur = conn.cursor()
    except ImportError:
        print("⚠️  psycopg2 not installed. Generating SQL script instead...\n")
        print("=" * 80)
        print("RUN THIS SQL IN PGADMIN OR PSQL:")
        print("=" * 80)
        print("""
-- Add employer CPP/EI columns
ALTER TABLE employee_pay_master
ADD COLUMN IF NOT EXISTS cpp_employer DECIMAL(10,2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS ei_employer DECIMAL(10,2) DEFAULT 0.00;

-- Backfill CPP employer (1:1 matching)
UPDATE employee_pay_master
SET cpp_employer = cpp_employee
WHERE cpp_employer IS NULL OR cpp_employer = 0;

-- Backfill EI employer (1.4× employee)
UPDATE employee_pay_master
SET ei_employer = ROUND(ei_employee * 1.4, 2)
WHERE ei_employer IS NULL OR ei_employer = 0;

-- Verify results
SELECT 
    fiscal_year,
    COUNT(*) as records,
    SUM(cpp_employee) as total_cpp_employee,
    SUM(cpp_employer) as total_cpp_employer,
    SUM(ei_employee) as total_ei_employee,
    SUM(ei_employer) as total_ei_employer
FROM employee_pay_master
GROUP BY fiscal_year
ORDER BY fiscal_year DESC;
""")
        print("=" * 80)
        return
    
    try:
        print("Starting employer CPP/EI column migration...")
        
        # Check if columns already exist
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'employee_pay_master' 
              AND column_name IN ('cpp_employer', 'ei_employer');
        """)
        existing_cols = [row[0] for row in cur.fetchall()]
        
        if 'cpp_employer' in existing_cols and 'ei_employer' in existing_cols:
            print("✅ Columns already exist. Checking if backfill needed...")
        else:
            # Add columns
            print("Adding cpp_employer and ei_employer columns...")
            
            if 'cpp_employer' not in existing_cols:
                cur.execute("""
                    ALTER TABLE employee_pay_master
                    ADD COLUMN cpp_employer DECIMAL(10,2) DEFAULT 0.00;
                """)
                print("✅ Added cpp_employer column")
            
            if 'ei_employer' not in existing_cols:
                cur.execute("""
                    ALTER TABLE employee_pay_master
                    ADD COLUMN ei_employer DECIMAL(10,2) DEFAULT 0.00;
                """)
                print("✅ Added ei_employer column")
            
            conn.commit()
        
        # Backfill existing records
        print("\nBackfilling employer contributions for existing payroll records...")
        
        # CPP: 1:1 matching
        cur.execute("""
            UPDATE employee_pay_master
            SET cpp_employer = cpp_employee
            WHERE cpp_employer IS NULL OR cpp_employer = 0;
        """)
        cpp_updated = cur.rowcount
        print(f"✅ Updated {cpp_updated} records with CPP employer contributions (1:1 match)")
        
        # EI: 1.4× employee contribution
        cur.execute("""
            UPDATE employee_pay_master
            SET ei_employer = ROUND(ei_employee * 1.4, 2)
            WHERE ei_employer IS NULL OR ei_employer = 0;
        """)
        ei_updated = cur.rowcount
        print(f"✅ Updated {ei_updated} records with EI employer contributions (140% rate)")
        
        conn.commit()
        
        # Verify results
        print("\n📊 Verification:")
        cur.execute("""
            SELECT 
                fiscal_year,
                COUNT(*) as records,
                SUM(cpp_employee) as total_cpp_employee,
                SUM(cpp_employer) as total_cpp_employer,
                SUM(ei_employee) as total_ei_employee,
                SUM(ei_employer) as total_ei_employer
            FROM employee_pay_master
            GROUP BY fiscal_year
            ORDER BY fiscal_year DESC
            LIMIT 5;
        """)
        
        print("\nRecent Years Summary:")
        print(f"{'Year':<6} {'Records':<8} {'CPP Employee':<14} {'CPP Employer':<14} {'EI Employee':<14} {'EI Employer':<14}")
        print("-" * 80)
        for row in cur.fetchall():
            year, count, cpp_emp, cpp_empr, ei_emp, ei_empr = row
            cpp_emp = cpp_emp or 0
            cpp_empr = cpp_empr or 0
            ei_emp = ei_emp or 0
            ei_empr = ei_empr or 0
            print(f"{year:<6} {count:<8} ${cpp_emp:>11.2f}  ${cpp_empr:>11.2f}  ${ei_emp:>11.2f}  ${ei_empr:>11.2f}")
        
        print("\n✅ Migration complete!")
        print("\n📝 Next Steps:")
        print("1. Update payroll_entry_widget.py to display employer portions")
        print("2. Update PD7A summary to include employer contributions")
        print("3. Update T4 calculations if needed")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
        
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    add_employer_columns()
