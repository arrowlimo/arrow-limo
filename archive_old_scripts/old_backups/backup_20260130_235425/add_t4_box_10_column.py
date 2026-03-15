"""
Add t4_box_10 (province) column to driver_payroll table
"""
import psycopg2
import sys

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    try:
        # Check if column already exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'driver_payroll' AND column_name = 't4_box_10'
        """)
        
        if cur.fetchone():
            print("[OK] Column t4_box_10 already exists")
            return
        
        print("Adding t4_box_10 column to driver_payroll table...")
        
        # Add the column
        cur.execute("""
            ALTER TABLE driver_payroll 
            ADD COLUMN t4_box_10 VARCHAR(2)
        """)
        
        # Add comment
        cur.execute("""
            COMMENT ON COLUMN driver_payroll.t4_box_10 
            IS 'T4 Box 10: Province of employment (AB, BC, SK, etc.)'
        """)
        
        conn.commit()
        print("[OK] Successfully added t4_box_10 column")
        
    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Error: {e}", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
