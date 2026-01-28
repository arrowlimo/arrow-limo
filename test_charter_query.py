import psycopg2

conn = psycopg2.connect('host=localhost user=postgres password=***REMOVED*** dbname=almsdata')
cur = conn.cursor()
try:
    cur.execute('''
        SELECT 
            c.reserve_number,
            COALESCE(cl.company_name, cl.client_name),
            c.charter_date::date,
            e.full_name,
            v.vehicle_number,
            c.booking_status,
            c.total_amount_due,
            COALESCE(c.total_amount_due - 
                (SELECT COALESCE(SUM(amount), 0) FROM payments 
                 WHERE reserve_number = c.reserve_number), 
                c.total_amount_due) as balance_due
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        LEFT JOIN employees e ON c.employee_id = e.employee_id
        LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
        ORDER BY c.charter_date DESC
        LIMIT 5
    ''')
    rows = cur.fetchall()
    print(f'✅ Query successful, returned {len(rows)} rows')
    for row in rows[:2]:
        print('  -', row[0], row[1][:20] if row[1] else None)
except Exception as e:
    print(f'❌ Query failed: {type(e).__name__}: {e}')
finally:
    cur.close()
    conn.close()
