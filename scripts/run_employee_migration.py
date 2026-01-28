import psycopg2
import sys

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

try:
    with open('migrations/2025-10-21_create_non_charter_employee_booking_system.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    print("✅ Successfully created employee work system tables:")
    
    # Verify tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name IN (
            'employee_work_classifications',
            'employee_schedules',
            'employee_time_off_requests',
            'monthly_work_assignments',
            'non_charter_payroll'
        )
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    for table in tables:
        print(f"  - {table[0]}")
    
    cur.close()
    print(f"\n✅ Created {len(tables)} tables successfully!")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    sys.exit(1)
finally:
    conn.close()
