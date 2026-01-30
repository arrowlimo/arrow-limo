"""Check journal table schema to determine correct column names"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get column names and types
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'journal'
        ORDER BY ordinal_position
    """)
    
    print("JOURNAL TABLE SCHEMA:")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"{row[0]}: {row[1]}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
