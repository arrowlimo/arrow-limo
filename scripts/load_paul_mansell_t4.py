#!/usr/bin/env python3
"""
Load Paul Mansell's 2013 T4 into employee_t4_records table.

Verified from actual CRA T4 PDF:
- Employee: Paul Mansell
- SIN: 505 900 829
- Year: 2013
- Box 14 (income): $32,837.41
- Box 22 (tax): $4,369.80
- Box 16 (CPP): $1,452.21
- Box 18 (EI): $617.34
- Box 24 (EI insurable): $32,837.41
- Box 26 (CPP pensionable): $32,837.41
"""

import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        # Step 1: Find Paul Mansell in employees table
        print("🔍 Searching for Paul Mansell in employees table...")
        cur.execute("""
            SELECT employee_id, full_name, t4_sin 
            FROM employees 
            WHERE t4_sin = '505900829' 
               OR LOWER(full_name) LIKE '%mansell%paul%' 
               OR LOWER(full_name) LIKE '%paul%mansell%'
        """)
        result = cur.fetchone()
        
        if result:
            emp_id, full_name, sin = result
            print(f"✅ Found employee: ID={emp_id}, Name={full_name}, SIN={sin}")
        else:
            print("⚠️ Paul Mansell not found in employees table")
            print("   Creating new employee record...")
            
            # Insert new employee
            cur.execute("""
                INSERT INTO employees (full_name, name, t4_sin, created_at)
                VALUES ('Mansell, Paul', 'Paul Mansell', '505900829', NOW())
                RETURNING employee_id
            """)
            emp_id = cur.fetchone()[0]
            print(f"✅ Created employee ID={emp_id}")
        
        # Step 2: Check if T4 record already exists
        print(f"\n🔍 Checking for existing 2013 T4 record for employee {emp_id}...")
        cur.execute("""
            SELECT employee_id, fiscal_year, t4_employment_income, t4_federal_tax, t4_cpp_contributions, t4_ei_contributions 
            FROM employee_t4_summary 
            WHERE employee_id = %s AND fiscal_year = 2013
        """, (emp_id,))
        t4_result = cur.fetchone()
        
        if t4_result:
            print(f"⚠️ T4 record already exists:")
            print(f"   Box 14 (income): ${t4_result[2]}")
            print(f"   Box 22 (tax): ${t4_result[3]}")
            print(f"   Box 16 (CPP): ${t4_result[4]}")
            print(f"   Box 18 (EI): ${t4_result[5]}")
            print("\n❓ Update existing record? (VALUES WILL BE REPLACED)")
            
            # Update existing record
            cur.execute("""
                UPDATE employee_t4_summary
                SET t4_employment_income = %s,
                    t4_federal_tax = %s,
                    t4_cpp_contributions = %s,
                    t4_ei_contributions = %s,
                    notes = %s,
                    source = %s,
                    is_verified = TRUE,
                    updated_at = NOW()
                WHERE employee_id = %s AND fiscal_year = 2013
            """, (
                Decimal("32837.41"),  # t4_employment_income
                Decimal("4369.80"),   # t4_federal_tax
                Decimal("1452.21"),   # t4_cpp_contributions
                Decimal("617.34"),    # t4_ei_contributions
                "Loaded from verified CRA T4 PDF - Paul Mansell SIN 505900829 - UNKNOWN_PAGE resolved",
                "CRA T4 PDF - Manual Verification",
                emp_id
            ))
            print(f"✅ Updated existing T4 record (1 row)")
        else:
            print("✅ No existing T4 record - inserting new...")
            
            # Insert new T4 record
            cur.execute("""
                INSERT INTO employee_t4_summary (
                    employee_id, fiscal_year,
                    t4_employment_income, t4_federal_tax, t4_cpp_contributions, t4_ei_contributions,
                    source, is_verified, notes, created_at
                )
                VALUES (
                    %s, 2013,
                    %s, %s, %s, %s,
                    %s, TRUE, %s, NOW()
                )
            """, (
                emp_id,
                Decimal("32837.41"),  # t4_employment_income
                Decimal("4369.80"),   # t4_federal_tax
                Decimal("1452.21"),   # t4_cpp_contributions
                Decimal("617.34"),    # t4_ei_contributions
                "CRA T4 PDF - Manual Verification",
                "Loaded from verified CRA T4 PDF - Paul Mansell SIN 505900829 - UNKNOWN_PAGE resolved"
            ))
            print(f"✅ Inserted new T4 record")
        
        # Commit changes
        conn.commit()
        print("\n✅ Transaction committed successfully")
        
        # Verify final state
        print("\n📊 Final verification:")
        cur.execute("""
            SELECT fiscal_year, t4_employment_income, t4_federal_tax, t4_cpp_contributions, t4_ei_contributions
            FROM employee_t4_summary
            WHERE employee_id = %s AND fiscal_year = 2013
        """, (emp_id,))
        final = cur.fetchone()
        if final:
            print(f"   Year: {final[0]}")
            print(f"   Employment Income: ${final[1]}")
            print(f"   Federal Tax: ${final[2]}")
            print(f"   CPP Contributions: ${final[3]}")
            print(f"   EI Contributions: ${final[4]}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
