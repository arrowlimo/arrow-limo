#!/usr/bin/env python3
"""
Create payroll_remittances table for tracking CRA source deduction payments.

This table links:
- Monthly PD7A calculations (from employee_pay_master)
- Actual payments to CRA (from receipts/banking)
- Official PD7A statements filed with CRA
- Reconciliation status and variances

Enables:
- Audit trail for CRA compliance
- Late payment detection
- Variance analysis (calculated vs filed vs paid)
"""

import psycopg2
import os

def create_remittance_table():
    """Create payroll remittance tracking table."""
    
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'arrow_limo'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '')
    )
    cur = conn.cursor()
    
    try:
        print("Creating payroll_remittances table...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payroll_remittances (
                remittance_id SERIAL PRIMARY KEY,
                fiscal_year INTEGER NOT NULL,
                remittance_month INTEGER NOT NULL CHECK (remittance_month BETWEEN 1 AND 12),
                
                -- Calculated amounts (from employee_pay_master aggregation)
                calculated_gross DECIMAL(10,2) DEFAULT 0.00,
                calculated_cpp_employee DECIMAL(10,2) DEFAULT 0.00,
                calculated_cpp_employer DECIMAL(10,2) DEFAULT 0.00,
                calculated_ei_employee DECIMAL(10,2) DEFAULT 0.00,
                calculated_ei_employer DECIMAL(10,2) DEFAULT 0.00,
                calculated_federal_tax DECIMAL(10,2) DEFAULT 0.00,
                calculated_provincial_tax DECIMAL(10,2) DEFAULT 0.00,
                calculated_total_remittance DECIMAL(10,2) DEFAULT 0.00,
                
                -- Payment information
                due_date DATE,                                      -- CRA deadline (15th of following month)
                payment_date DATE,                                  -- When actually paid
                payment_amount DECIMAL(10,2),                       -- Actual amount paid
                payment_method TEXT,                                -- Cheque, wire transfer, online banking
                payment_reference TEXT,                             -- Cheque #, confirmation #, etc.
                receipt_id INTEGER,                                 -- Link to receipts table (if tracked)
                
                -- PD7A reconciliation
                pd7a_statement_amount DECIMAL(10,2),               -- From official CRA PD7A statement
                pd7a_filed_date DATE,                              -- When PD7A was filed
                variance DECIMAL(10,2),                            -- calculated_total - pd7a_statement_amount
                reconciled BOOLEAN DEFAULT FALSE,
                
                -- Status tracking
                status TEXT DEFAULT 'pending',                     -- pending, paid, late, reconciled
                is_late BOOLEAN DEFAULT FALSE,                     -- payment_date > due_date
                
                -- Notes
                notes TEXT,
                
                -- Audit trail
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                created_by TEXT,
                
                -- Unique constraint: one record per year/month
                UNIQUE (fiscal_year, remittance_month)
            );
        """)
        print("✅ Created payroll_remittances table")
        
        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_payroll_remittances_year_month 
                ON payroll_remittances(fiscal_year, remittance_month);
        """)
        print("✅ Created index on fiscal_year, remittance_month")
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_payroll_remittances_status 
                ON payroll_remittances(status);
        """)
        print("✅ Created index on status")
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_payroll_remittances_reconciled 
                ON payroll_remittances(reconciled);
        """)
        print("✅ Created index on reconciled")
        
        # Create update trigger for updated_at
        cur.execute("""
            CREATE OR REPLACE FUNCTION update_payroll_remittances_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        cur.execute("""
            DROP TRIGGER IF EXISTS trigger_update_payroll_remittances_updated_at 
                ON payroll_remittances;
        """)
        
        cur.execute("""
            CREATE TRIGGER trigger_update_payroll_remittances_updated_at
            BEFORE UPDATE ON payroll_remittances
            FOR EACH ROW
            EXECUTE FUNCTION update_payroll_remittances_updated_at();
        """)
        print("✅ Created updated_at trigger")
        
        conn.commit()
        
        print("\n✅ Migration complete!")
        print("\n📝 Table Schema:")
        print("   - Tracks monthly remittances by fiscal_year + remittance_month")
        print("   - Links calculated amounts (PD7A) to actual payments")
        print("   - Stores CRA statement amounts for reconciliation")
        print("   - Flags late payments and unreconciled months")
        print("   - Supports partial payments and variance tracking")
        
        print("\n📝 Next Steps:")
        print("1. Create UI for entering/viewing remittance data")
        print("2. Add auto-calculation from employee_pay_master")
        print("3. Build reconciliation report")
        print("4. Add payment reminder system")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
        
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    create_remittance_table()
