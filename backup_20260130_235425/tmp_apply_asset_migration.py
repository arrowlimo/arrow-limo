import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
conn.autocommit = False
cur = conn.cursor()
try:
    with open(r'l:\limo\migrations\2025-12-27_create_asset_tracking.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    cur.execute(sql)
    conn.commit()
    print('✅ Asset tracking schema created and vehicles migrated')
except Exception as e:
    conn.rollback()
    print(f'❌ Migration failed: {e}')
    raise
finally:
    conn.close()
