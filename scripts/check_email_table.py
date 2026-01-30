import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check if table exists
cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'email_financial_events')")
exists = cur.fetchone()[0]

if exists:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='email_financial_events' ORDER BY ordinal_position")
    cols = cur.fetchall()
    print("email_financial_events columns:")
    for c in cols:
        print(f"  {c[0]}")
    
    # Show sample data
    cur.execute("SELECT * FROM email_financial_events LIMIT 5")
    print(f"\nSample data:")
    for row in cur.fetchall():
        print(row)
else:
    print("email_financial_events table does not exist")
    print("\nSearching for email-related tables...")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public' 
          AND table_name LIKE '%email%' 
          OR table_name LIKE '%outlook%'
          OR table_name LIKE '%transfer%'
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    if tables:
        print("Found tables:")
        for t in tables:
            print(f"  {t[0]}")
    else:
        print("No email-related tables found")

cur.close()
conn.close()
