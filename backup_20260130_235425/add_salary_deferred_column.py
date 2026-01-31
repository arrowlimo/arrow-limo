import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

try:
    # Add to employees table
    cur.execute("""
        ALTER TABLE employees 
        ADD COLUMN IF NOT EXISTS salary_deferred NUMERIC(10,2) DEFAULT 0.00
    """)
    print("✅ Added salary_deferred column to employees table")
    
    # Add to employee_work_classifications table
    cur.execute("""
        ALTER TABLE employee_work_classifications 
        ADD COLUMN IF NOT EXISTS salary_deferred NUMERIC(10,2) DEFAULT 0.00
    """)
    print("✅ Added salary_deferred column to employee_work_classifications table")
    
    conn.commit()
except Exception as e:
    conn.rollback()
    print(f"❌ Failed: {e}")
finally:
    cur.close()
    conn.close()
