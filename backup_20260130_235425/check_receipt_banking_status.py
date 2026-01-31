#!/usr/bin/env python
"""Check if receipts have been matched to banking transactions."""

import psycopg2
import os

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    cur = conn.cursor()
    
    # Check receipts table columns
    print("=== RECEIPTS TABLE SCHEMA ===")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    print(f"Total columns: {len(columns)}")
    for col_name, col_type in columns:
        print(f"  {col_name}: {col_type}")
    
    # Check for banking-related columns
    banking_cols = [c for c, _ in columns if 'bank' in c.lower() or 'transaction' in c.lower()]
    print(f"\nBanking-related columns: {banking_cols if banking_cols else 'NONE'}")
    
    # Count 2012 receipts
    print("\n=== 2012 RECEIPT STATUS ===")
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE receipt_date >= '2012-01-01' 
        AND receipt_date <= '2012-12-31'
    """)
    total_receipts = cur.fetchone()[0]
    print(f"Total 2012 receipts: {total_receipts}")
    
    # Check if there's any junction table for receipt-banking links
    print("\n=== CHECKING FOR JUNCTION TABLES ===")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND (
            table_name LIKE '%receipt%bank%' 
            OR table_name LIKE '%bank%receipt%'
        )
    """)
    junction_tables = cur.fetchall()
    if junction_tables:
        print("Found junction tables:")
        for table in junction_tables:
            print(f"  {table[0]}")
    else:
        print("No junction tables found")
    
    cur.close()
    conn.close()
    
    # Final verdict
    print("\n=== VERDICT ===")
    if banking_cols or junction_tables:
        print("[OK] Receipts MAY be linked to banking (has banking columns or junction table)")
    else:
        print("[FAIL] Receipts CANNOT be linked to banking (no banking columns, no junction table)")
        print("   Schema enhancement required to match receipts to banking transactions")

if __name__ == '__main__':
    main()
