import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Add missing calendar_color column
try:
    cur.execute("""
        ALTER TABLE charters 
        ADD COLUMN IF NOT EXISTS calendar_color VARCHAR(7) DEFAULT '#3b82f6'
    """)
    conn.commit()
    print("✅ Successfully added calendar_color column to charters table")
except psycopg2.Error as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
