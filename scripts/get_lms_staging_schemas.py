"""Get schemas of LMS staging tables."""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

tables = ['lms_staging_customer', 'lms_staging_payment', 'lms_staging_reserve']

for table in tables:
    print(f"\n{table.upper()}")
    print("=" * 60)
    
    cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    
    cols = cur.fetchall()
    for col, dtype in cols:
        print(f"  {col:<30} {dtype}")
    
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"\nTotal rows: {count:,}")

cur.close()
conn.close()
