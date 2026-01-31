#!/usr/bin/env python3
"""
Check receipts table column constraints and generated columns
"""

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("=== RECEIPTS TABLE COLUMN ANALYSIS ===")
    
    # Check column properties
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND (column_name LIKE '%amount%' OR column_name LIKE '%expense%' OR column_name LIKE '%revenue%')
        ORDER BY ordinal_position
    """)
    
    print("\nAmount/Revenue related columns:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]}, Nullable: {row[2]}, Default: {row[3]}")
    
    # Check if we can update gross_amount
    try:
        cur.execute("UPDATE receipts SET gross_amount = 0 WHERE id = -1")  # Test update on non-existent row
        print("\n[OK] gross_amount is updatable")
    except Exception as e:
        print(f"\n[FAIL] gross_amount update error: {e}")
        
    # Check current values 
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN gross_amount > 0 THEN 1 END) as has_gross,
            COUNT(CASE WHEN net_amount > 0 THEN 1 END) as has_net,
            COUNT(CASE WHEN expense != 0 THEN 1 END) as has_expense
        FROM receipts 
        WHERE created_from_banking = true
    """)
    
    row = cur.fetchone()
    print(f"\nBanking records analysis:")
    print(f"  Total records: {row[0]}")
    print(f"  Has gross_amount > 0: {row[1]}")  
    print(f"  Has net_amount > 0: {row[2]}")
    print(f"  Has expense != 0: {row[3]}")
    
    conn.close()

if __name__ == "__main__":
    main()