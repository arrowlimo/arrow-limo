import psycopg2, os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Check pay entry table columns
for table in ['chauffeur_pay_entries', 'driver_pay_entries', 'employee_pay_entries', 'staging_driver_pay']:
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    
    cols = cur.fetchall()
    print(f"\n{table}:")
    print("-" * 60)
    if cols:
        for col, dtype in cols:
            print(f"  {col:<30} {dtype}")
    else:
        print("  (table does not exist or has no columns)")

# Check row counts
for table in ['chauffeur_pay_entries', 'driver_pay_entries', 'employee_pay_entries', 'staging_driver_pay']:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"\n{table}: {count} records")
    except Exception as e:
        print(f"\n{table}: Error - {e}")

cur.close()
conn.close()
