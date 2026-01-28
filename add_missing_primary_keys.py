"""
Add Primary Keys to Tables Missing Them
========================================
Based on analysis, add PKs to 3 high-priority core business tables.

Tables to fix:
1. income_ledger_payment_archive (8 rows) - PK: income_id
2. payment_customer_links (172 rows) - PK: payment_id  
3. zero_payment_resolutions (106 rows) - PK: payment_id

Note: Some tables have composite PKs, so we'll check for uniqueness first.
"""

import psycopg2
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

def check_column_uniqueness(cur, table, column):
    """Check if a column has unique values (suitable for PK)."""
    cur.execute(f"""
        SELECT COUNT(*) as total, 
               COUNT(DISTINCT {column}) as distinct_count,
               COUNT(*) - COUNT({column}) as null_count
        FROM {table}
    """)
    total, distinct, nulls = cur.fetchone()
    
    is_unique = (total == distinct and nulls == 0)
    return {
        'is_unique': is_unique,
        'total_rows': total,
        'distinct_values': distinct,
        'null_values': nulls
    }

def add_primary_key(cur, table, column):
    """Add primary key to a table."""
    print(f"\n{'='*60}")
    print(f"Table: {table}")
    print(f"Proposed PK: {column}")
    print(f"{'='*60}")
    
    # Check uniqueness
    uniqueness = check_column_uniqueness(cur, table, column)
    print(f"Total rows: {uniqueness['total_rows']}")
    print(f"Distinct values: {uniqueness['distinct_values']}")
    print(f"NULL values: {uniqueness['null_values']}")
    
    if not uniqueness['is_unique']:
        print(f"❌ SKIPPED - {column} is not unique or has NULLs")
        
        if uniqueness['null_values'] > 0:
            print(f"   Fix: UPDATE {table} SET {column} = generate_id() WHERE {column} IS NULL")
        
        if uniqueness['total_rows'] != uniqueness['distinct_values']:
            print(f"   Issue: {uniqueness['total_rows'] - uniqueness['distinct_values']} duplicate values")
            cur.execute(f"""
                SELECT {column}, COUNT(*) as cnt 
                FROM {table} 
                GROUP BY {column} 
                HAVING COUNT(*) > 1
                LIMIT 5
            """)
            dupes = cur.fetchall()
            print(f"   Sample duplicates: {dupes}")
        
        return False
    
    # Add primary key
    try:
        print(f"\n🔧 Adding PRIMARY KEY constraint...")
        cur.execute(f"ALTER TABLE {table} ADD PRIMARY KEY ({column})")
        print(f"✅ SUCCESS - Primary key added to {table}.{column}")
        return True
    except Exception as e:
        print(f"❌ ERROR - {e}")
        return False

def main():
    print("=" * 80)
    print("ADDING PRIMARY KEYS TO CORE BUSINESS TABLES")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Tables to fix (from analysis)
    tables_to_fix = [
        ('income_ledger_payment_archive', 'income_id'),
        ('payment_customer_links', 'payment_id'),
        ('zero_payment_resolutions', 'payment_id'),
    ]
    
    try:
        success_count = 0
        
        for table, pk_column in tables_to_fix:
            if add_primary_key(cur, table, pk_column):
                conn.commit()
                success_count += 1
            else:
                conn.rollback()
        
        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"✅ Successfully added PKs: {success_count} / {len(tables_to_fix)}")
        print(f"❌ Failed/Skipped: {len(tables_to_fix) - success_count}")
        
        # Verify results
        print()
        print("Verification:")
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.table_constraints 
            WHERE constraint_type = 'PRIMARY KEY'
                AND table_name IN ('income_ledger_payment_archive', 
                                   'payment_customer_links', 
                                   'zero_payment_resolutions')
        """)
        pk_count = cur.fetchone()[0]
        print(f"Tables with PKs now: {pk_count} / 3")
        
        print()
        print(f"Completed: {datetime.now()}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ CRITICAL ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
