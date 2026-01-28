#!/usr/bin/env python3
"""
List Uncategorized Banking Transactions
"""

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("=== UNCATEGORIZED BANKING TRANSACTIONS ===\n")
    cur.execute("""
        SELECT receipt_date, vendor_name, expense, gross_amount, description
        FROM receipts
        WHERE created_from_banking = true AND category = 'UNCATEGORIZED'
        ORDER BY receipt_date DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    for row in rows:
        print(f"Date: {row[0]} | Vendor: {row[1][:30]} | Amount: ${row[2]:,.2f} | Gross: ${row[3]:,.2f}")
        print(f"  Description: {row[4]}")
        print()
    print(f"Total shown: {len(rows)} (showing most recent)")
    
    # Show total count
    cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = true AND category = 'UNCATEGORIZED'")
    total = cur.fetchone()[0]
    print(f"Total UNCATEGORIZED transactions: {total}")
    conn.close()

if __name__ == "__main__":
    main()