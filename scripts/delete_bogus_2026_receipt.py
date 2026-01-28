#!/usr/bin/env python3
"""
Delete the bogus 2026 receipt (ID 145324) that was created during date-fixing work.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 70)
    print("DELETE BOGUS 2026 RECEIPT")
    print("=" * 70)
    
    # Verify the receipt exists and show details
    print("\nReceipt to delete:")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id
        FROM receipts WHERE receipt_id = 145324
    """)
    
    result = cur.fetchone()
    if result:
        r_id, r_date, r_vendor, r_amount, r_banking = result
        print(f"ID {r_id} | {r_date} | {r_vendor} | ${r_amount:.2f} | Banking: {r_banking}")
    else:
        print("Receipt 145324 not found")
        cur.close()
        conn.close()
        exit(0)
    
    # Delete it
    response = input("\n⚠️  Delete this receipt? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("Cancelled. No changes made.")
        cur.close()
        conn.close()
        exit(0)
    
    cur.execute("DELETE FROM receipts WHERE receipt_id = 145324")
    
    if cur.rowcount > 0:
        conn.commit()
        print(f"\n✅ Deleted 1 receipt (ID 145324)")
        
        # Verify deletion
        cur.execute("SELECT COUNT(*) FROM receipts WHERE receipt_id = 145324")
        remaining = cur.fetchone()[0]
        if remaining == 0:
            print("✅ Verified: Receipt 145324 no longer exists")
            
            # Show remaining receipts for banking 69336
            print("\nRemaining receipts linked to banking transaction 69336:")
            cur.execute("""
                SELECT receipt_id, receipt_date, gross_amount
                FROM receipts WHERE banking_transaction_id = 69336
                ORDER BY receipt_id
            """)
            
            total = 0
            for r_id, r_date, r_amount in cur.fetchall():
                print(f"  ID {r_id} | {r_date} | ${r_amount:.2f}")
                total += float(r_amount) if r_amount else 0
            
            print(f"\n  Total: ${total:.2f}")
    else:
        print("❌ No rows deleted (receipt might not exist)")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
