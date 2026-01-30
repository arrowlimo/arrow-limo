import psycopg2
import os

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_type = 'BASE TABLE'
          AND table_name LIKE '%charter%'
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    print("Tables containing 'charter':")
    for t in tables:
        print(f"  - {t[0]}")
    
    # Get all views
    cur.execute("""
        SELECT table_name 
        FROM information_schema.views 
        WHERE table_schema = 'public'
          AND table_name LIKE '%charter%'
        ORDER BY table_name
    """)
    
    views = cur.fetchall()
    print("\nViews containing 'charter':")
    for v in views:
        print(f"  - {v[0]}")
    
    # If we found any, show columns
    if tables:
        table_name = tables[0][0]
        print(f"\nColumns in {table_name}:")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
              AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        cols = cur.fetchall()
        for col in cols:
            print(f"  - {col[0]} ({col[1]})")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
