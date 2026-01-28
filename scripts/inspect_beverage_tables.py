"""Restore beverage inventory from other tables"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

try:
    # First, get all items from beverages table
    cur.execute("SELECT * FROM beverages")
    beverages = cur.fetchall()
    
    if beverages:
        print(f"Found {len(beverages)} items in 'beverages' table")
        # Get column names
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='beverages'")
        cols = [c[0] for c in cur.fetchall()]
        print(f"Columns: {cols}\n")
    
    # Get all items from raw_file_inventory
    cur.execute("SELECT * FROM raw_file_inventory LIMIT 5")
    sample = cur.fetchall()
    
    print(f"Sample from 'raw_file_inventory' (first 5 items):")
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='raw_file_inventory'")
    cols = [c[0] for c in cur.fetchall()]
    print(f"Columns: {cols}\n")
    
    for row in sample:
        print(f"  {row[:3]}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
