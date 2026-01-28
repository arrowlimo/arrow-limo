import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

updates = [
    ('Dr114', 'Ofougwuka Melissa', '149848-830', 'Rtmanz@outlook.com' if 'Dr114' == 'Dr128' else None),
    ('Dr128', 'Manz, Robert', '140142-761', 'Rtmanz@outlook.com'),
]

try:
    cur.execute("""
        UPDATE employees 
        SET full_name = 'Ofougwuka Melissa',
            driver_license_number = '149848-830',
            phone = '403',
            cell_phone = '403'
        WHERE employee_number = 'Dr114'
    """)
    print(f"✅ Updated Dr114: Ofougwuka Melissa")
    
    cur.execute("""
        UPDATE employees 
        SET full_name = 'Manz, Robert',
            driver_license_number = '140142-761',
            phone = '4035970673',
            cell_phone = '403',
            email = 'Rtmanz@outlook.com'
        WHERE employee_number = 'Dr128'
    """)
    print(f"✅ Updated Dr128: Manz, Robert")
    
    conn.commit()
    print(f"\n✅ Committed name updates")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Rolled back: {e}")
finally:
    cur.close()
    conn.close()
