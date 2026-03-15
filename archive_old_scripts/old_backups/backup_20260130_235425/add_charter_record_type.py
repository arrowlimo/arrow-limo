"""
Add record_type column to charters table to differentiate:
- 'charter': Real customer bookings (revenue charters)
- 'employment_record': Host hours/tips tracking (non-revenue)
- 'unknown': Needs classification

This is a schema fix for H## driver records that may be employment
tracking rather than actual customer bookings.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")

def add_record_type_column():
    """Add record_type enum column to charters table."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    conn.autocommit = False  # Explicit transaction control
    cur = conn.cursor()
    
    try:
        # Check if enum exists
        cur.execute("""
            SELECT 1 FROM pg_type WHERE typname = 'charter_record_type';
        """)
        enum_exists = cur.fetchone() is not None
        
        if not enum_exists:
            print("Creating record_type enum...")
            cur.execute("""
                CREATE TYPE charter_record_type AS ENUM ('charter', 'employment_record', 'unknown');
            """)
            print("✅ Enum created")
        else:
            print("✅ Enum already exists")
        
        # Check if column exists
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'charters' AND column_name = 'record_type';
        """)
        column_exists = cur.fetchone() is not None
        
        if not column_exists:
            print("Adding record_type column...")
            cur.execute("""
                ALTER TABLE charters 
                ADD COLUMN record_type charter_record_type DEFAULT 'charter';
            """)
            print("✅ Column added")
        else:
            print("✅ Column already exists")
        
        # Flag employment records: $0 total with $0 rate (duty tracking, not charters)
        print("\nFlagging employment records (duty tracking)...")
        cur.execute("""
            UPDATE charters
            SET record_type = 'employment_record'
            WHERE (total_amount_due = 0 OR total_amount_due IS NULL)
              AND (rate = 0 OR rate IS NULL);
        """)
        flagged = cur.rowcount
        print(f"✅ Flagged {flagged} records as employment_record ($0 total + $0 rate)")
        
        # Keep all other records as 'charter' (including H## hosts with real revenue)
        print(f"✅ Remaining records kept as 'charter' (real customer bookings)")
        
        # Show breakdown
        print("\n" + "="*80)
        print("RECORD TYPE DISTRIBUTION:")
        print("="*80)
        cur.execute("""
            SELECT record_type, COUNT(*) as count,
                   SUM(total_amount_due) as total_revenue,
                   AVG(total_amount_due) as avg_revenue
            FROM charters
            GROUP BY record_type
            ORDER BY count DESC;
        """)
        for row in cur.fetchall():
            rec_type, count, total_rev, avg_rev = row
            print(f"{rec_type:20} {count:6,} charters | Total: ${total_rev:15,.2f} | Avg: ${avg_rev:8,.2f}")
        
        conn.commit()
        print("\n✅ Schema update committed!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_record_type_column()
