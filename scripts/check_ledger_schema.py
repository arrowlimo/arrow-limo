import psycopg2
DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'rent_debt_ledger'
            ORDER BY ordinal_position
        """)
        print("rent_debt_ledger columns:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
