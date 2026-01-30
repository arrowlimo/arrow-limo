import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Check cheque_register structure
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'cheque_register'
    ORDER BY ordinal_position
""")
print('=== CHEQUE_REGISTER COLUMNS ===')
for col in cur.fetchall():
    print(f'  {col[0]}: {col[1]}')

print()
print('=== SAMPLE CHEQUE RECORDS (first 10) ===')
cur.execute('SELECT * FROM cheque_register LIMIT 10')
cols = [desc[0] for desc in cur.description]
for row in cur.fetchall():
    for i, col in enumerate(cols):
        print(f'  {col}: {row[i]}')
    print()

cur.close()
conn.close()
