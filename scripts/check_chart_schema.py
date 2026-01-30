import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check if table exists
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'chart_of_accounts'
""")
exists = cur.fetchone()

if exists:
    print("chart_of_accounts table EXISTS")
    print("\nColumns:")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'chart_of_accounts'
        ORDER BY ordinal_position
    """)
    for col, dtype in cur.fetchall():
        print(f"  {col:30} {dtype}")
else:
    print("chart_of_accounts table DOES NOT EXIST")
    print("The create_table function will create it.")

conn.close()
