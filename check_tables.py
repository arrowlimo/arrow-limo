import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

tables_to_check = ['beverages', 'beverage_menu', 'incidents', 'incident_damage_tracking']

for table in tables_to_check:
    try:
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}' ORDER BY ordinal_position")
        cols = cur.fetchall()
        print(f"\n{'='*60}")
        print(f"TABLE: {table} ({len(cols)} columns)")
        print('='*60)
        for col, dtype in cols:
            print(f"  {col:<30} {dtype}")
        
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"\nRow count: {count}")
    except Exception as e:
        print(f"\n❌ {table}: {str(e)}")

cur.close()
conn.close()
