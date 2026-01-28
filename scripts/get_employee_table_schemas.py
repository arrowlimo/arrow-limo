"""Quick script to get employee-related table schemas"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

tables = ['driver_documents', 'training_programs', 'training_checklist_items', 
          'employee_certifications', 'compliance_alerts']

for table in tables:
    print(f"\n{'='*60}")
    print(f"TABLE: {table}")
    print('='*60)
    try:
        cur.execute(f"""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table,))
        
        rows = cur.fetchall()
        if rows:
            for col_name, dtype, max_len, nullable in rows:
                length = f"({max_len})" if max_len else ""
                null = "NULL" if nullable == 'YES' else "NOT NULL"
                print(f"  {col_name:30} {dtype}{length:15} {null}")
        else:
            print(f"  Table not found or no columns")
    except Exception as e:
        print(f"  Error: {e}")

cur.close()
conn.close()
