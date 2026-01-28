#!/usr/bin/env python3
"""
Delete the 4 journal entry receipts that shouldn't be in the receipts table.
IDs: 126123, 135160, 126071, 118604
"""
import psycopg2

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    journal_entry_ids = [126123, 135160, 126071, 118604]
    
    print("="*70)
    print("DELETE JOURNAL ENTRY RECEIPTS")
    print("="*70)
    
    # First, verify these receipts exist and show details
    print("\n📋 Journal entry receipts to delete:\n")
    
    cur.execute("""
        SELECT receipt_id, receipt_date, description, gross_amount, revenue
        FROM receipts
        WHERE receipt_id = ANY(%s)
        ORDER BY receipt_id
    """, (journal_entry_ids,))
    
    receipts = cur.fetchall()
    
    if not receipts:
        print("❌ No receipts found with these IDs")
        cur.close()
        conn.close()
        return
    
    print(f"{'ID':<10} {'Date':<12} {'Amount':>12} {'Description':<40}")
    print("-" * 80)
    
    for rid, rdate, desc, gross, revenue in receipts:
        amount = gross or revenue or 0
        print(f"{rid:<10} {rdate} ${amount:>10,.2f} {(desc or '')[:38]}")
    
    # Check if any are linked to banking transactions
    print("\n🔗 Banking transaction links:")
    cur.execute("""
        SELECT receipt_id, banking_transaction_id
        FROM receipts
        WHERE receipt_id = ANY(%s) AND banking_transaction_id IS NOT NULL
    """, (journal_entry_ids,))
    
    banking_links = cur.fetchall()
    if banking_links:
        print(f"  Found {len(banking_links)} receipts linked to banking transactions")
        for rid, btid in banking_links:
            print(f"    Receipt {rid} → Banking Transaction {btid}")
    else:
        print("  ✅ No banking transaction links")
    
    # Check if any banking transactions reference these receipts
    print("\n🔍 Reverse banking references:")
    cur.execute("""
        SELECT transaction_id, receipt_id
        FROM banking_transactions
        WHERE receipt_id = ANY(%s)
    """, (journal_entry_ids,))
    
    reverse_links = cur.fetchall()
    if reverse_links:
        print(f"  ⚠️ Found {len(reverse_links)} banking transactions referencing these receipts")
        for tid, rid in reverse_links:
            print(f"    Banking Transaction {tid} → Receipt {rid}")
        print("  Will set receipt_id = NULL before deleting")
    else:
        print("  ✅ No reverse references")
    
    print(f"\n{'='*70}")
    response = input(f"\nDelete {len(receipts)} journal entry receipts? (yes/no): ")
    
    if response.strip().lower() != 'yes':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        return
    
    # Clear reverse references if any
    if reverse_links:
        print("\n🧹 Clearing banking transaction references...")
        cur.execute("""
            UPDATE banking_transactions
            SET receipt_id = NULL
            WHERE receipt_id = ANY(%s)
        """, (journal_entry_ids,))
        print(f"  ✅ Cleared {cur.rowcount} references")
    
    # Delete the receipts
    print("\n🗑️ Deleting receipts...")
    cur.execute("""
        DELETE FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (journal_entry_ids,))
    
    deleted = cur.rowcount
    conn.commit()
    
    print(f"\n✅ Successfully deleted {deleted} journal entry receipts")
    
    # Verify
    print("\n📊 Verification - checking for remaining journal entries:")
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (journal_entry_ids,))
    
    remaining = cur.fetchone()[0]
    if remaining == 0:
        print("  ✅ All journal entry receipts successfully removed")
    else:
        print(f"  ⚠️ WARNING: {remaining} receipts still exist!")
    
    # Show total receipts count
    cur.execute("SELECT COUNT(*) FROM receipts")
    total = cur.fetchone()[0]
    print(f"\n📊 Total receipts remaining: {total:,}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
