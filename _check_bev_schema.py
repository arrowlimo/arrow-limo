import sys
sys.path.insert(0, 'desktop_app')
from app_settings import load_db_settings
import psycopg2
s = load_db_settings()
conn = psycopg2.connect(host=s['host'], port=s['port'], dbname=s['dbname'],
                        user=s['user'], password=s['password'], sslmode='require')
cur = conn.cursor()
cur.execute("""SELECT column_name, data_type, is_generated, column_default
               FROM information_schema.columns
               WHERE table_name='charter_beverages'
               ORDER BY ordinal_position""")
print("charter_beverages columns:")
for r in cur.fetchall():
    print(r)

# Also check data for charter 18797 (the one in the invoice)
cur.execute("""SELECT id, item_name, quantity, unit_price_charged,
               line_amount_charged, line_cost
               FROM charter_beverages WHERE charter_id = 18797""")
print("\nBeverages for charter 18797:")
for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
