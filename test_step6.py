import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)

try:
    with open('migrations/20260122_step6_invoice_payment.sql', 'r') as f:
        sql_content = f.read()
    
    cursor = conn.cursor()
    cursor.execute(sql_content)
    conn.commit()
    cursor.close()
    print('✅ Step 6 migration succeeded')
except Exception as e:
    conn.rollback()
    print(f'❌ Step 6 migration failed: {e}')
finally:
    conn.close()
