import psycopg2
import os

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'charters'
        ORDER BY ordinal_position
    """)
    
    cols = cur.fetchall()
    print("Columns in 'charters' table:")
    for col in cols:
        print(f"  {col[0]} ({col[1]})")
    
    # Get sample data
    print("\nSample charter records (first 5):")
    cur.execute("SELECT * FROM charters LIMIT 5")
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    
    for row in rows:
        print("\n---")
        for i, val in enumerate(row):
            print(f"  {colnames[i]}: {val}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
