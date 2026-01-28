"""
Comprehensive verification of 2025 receipts data quality.
Run this to understand all issues before cleanup.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("2025 RECEIPTS - COMPLETE DATA QUALITY VERIFICATION")
    print("=" * 100)
    
    # Overview
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2025")
    total, amount = cur.fetchone()
    print(f"\n📊 OVERVIEW:")
    print(f"   Total 2025 receipts: {total:,}")
    print(f"   Total amount: ${amount:,.2f}")
    
    # Issue 1: Misdated batch
    print(f"\n{'=' * 100}")
    print("🔴 ISSUE 1: Misdated 2025-10-17 Banking Batch (2012 data)")
    print("=" * 100)
    
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE created_at::date = '2025-10-17'
        AND account_number = '0228362'
    """)
    bt_count, debit, credit = cur.fetchone()
    print(f"\n   Banking transactions misdated as 2025-10-17: {bt_count}")
    print(f"   Total debits: ${debit:,.2f}")
    print(f"   Total credits: ${credit:,.2f}")
    
    cur.execute("""
        SELECT COUNT(DISTINCT r.receipt_id), SUM(r.gross_amount)
        FROM receipts r
        JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        WHERE bt.created_at::date = '2025-10-17'
        AND bt.account_number = '0228362'
    """)
    receipt_count, receipt_amount = cur.fetchone()
    print(f"   Receipts linked to misdated batch: {receipt_count}")
    print(f"   Receipt amount: ${receipt_amount:,.2f}")
    
    # Sample evidence
    cur.execute("""
        SELECT DISTINCT description
        FROM banking_transactions
        WHERE created_at::date = '2025-10-17'
        AND account_number = '0228362'
        AND (description ILIKE '%2012%' OR description ILIKE '%may%' OR description ILIKE '%june%')
        LIMIT 5
    """)
    print(f"\n   Evidence (descriptions showing 2012):")
    for row in cur.fetchall():
        print(f"     • {row[0][:60]}")
    
    # Issue 2: Duplicates
    print(f"\n{'=' * 100}")
    print("🔴 ISSUE 2: Duplicate Bank Fee Receipts")
    print("=" * 100)
    
    cur.execute("""
        SELECT COUNT(*) as groups, SUM(cnt-1) as duplicates
        FROM (
            SELECT COUNT(*) as cnt
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2025
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
        ) x
    """)
    groups, dup_count = cur.fetchone()
    print(f"\n   Duplicate groups: {groups}")
    print(f"   Total duplicate receipts: {dup_count}")
    
    cur.execute("""
        SELECT vendor_name, COUNT(*) as groups
        FROM (
            SELECT vendor_name, receipt_date, gross_amount
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2025
            GROUP BY vendor_name, receipt_date, gross_amount
            HAVING COUNT(*) > 1
        ) x
        GROUP BY vendor_name
        ORDER BY COUNT(*) DESC
    """)
    print(f"\n   Duplicate patterns:")
    for row in cur.fetchall():
        vendor = row[0][:50] if row[0] else 'None'
        print(f"     • {vendor}: {row[1]} duplicate groups")
    
    # Issue 3: ACE TRUCK
    print(f"\n{'=' * 100}")
    print("🔴 ISSUE 3: ACE TRUCK Duplicates (2012 Vehicle Financing)")
    print("=" * 100)
    
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
               created_from_banking, mapped_bank_account_id
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2025
        AND UPPER(vendor_name) LIKE '%ACE TRUCK%'
        ORDER BY receipt_id
    """)
    ace_receipts = cur.fetchall()
    print(f"\n   ACE TRUCK receipts in 2025: {len(ace_receipts)}")
    for row in ace_receipts:
        acct = 'CIBC' if row[5] == 1 else ('Scotia' if row[5] == 2 else f'ID:{row[5]}')
        print(f"     • ID {row[0]:6} | {row[1]} | ${row[3]:>10.2f} | {row[2][:30]:30} | Acct:{acct}")
    
    # Check if these match Scotia 2012
    cur.execute("""
        SELECT transaction_date, debit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND UPPER(description) LIKE '%ACE TRUCK%'
        AND (ABS(debit_amount - 2695.40) < 0.01 OR ABS(debit_amount - 2695.41) < 0.01)
        ORDER BY transaction_date
    """)
    scotia_matches = cur.fetchall()
    print(f"\n   Matching Scotia 2012 transactions: {len(scotia_matches)}")
    for row in scotia_matches[:3]:
        print(f"     • {row[0]} | ${row[1]:>10.2f} | Scotia 903990106011")
    if len(scotia_matches) > 3:
        print(f"     • ... and {len(scotia_matches) - 3} more")
    
    # Issue 4: mapped_bank_account_id misuse
    print(f"\n{'=' * 100}")
    print("⚠️  ISSUE 4: mapped_bank_account_id Field Misuse (Non-Critical)")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN mapped_bank_account_id IS NULL THEN 'NULL (Manual)'
                WHEN mapped_bank_account_id = 1 THEN '1 (CIBC)'
                WHEN mapped_bank_account_id = 2 THEN '2 (Scotia)'
                WHEN mapped_bank_account_id < 1000 THEN 'Other (<1000)'
                ELSE 'Transaction ID (>1000)'
            END as category,
            COUNT(*) as cnt
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2025
        GROUP BY 
            CASE 
                WHEN mapped_bank_account_id IS NULL THEN 'NULL (Manual)'
                WHEN mapped_bank_account_id = 1 THEN '1 (CIBC)'
                WHEN mapped_bank_account_id = 2 THEN '2 (Scotia)'
                WHEN mapped_bank_account_id < 1000 THEN 'Other (<1000)'
                ELSE 'Transaction ID (>1000)'
            END
        ORDER BY cnt DESC
    """)
    print(f"\n   mapped_bank_account_id distribution:")
    for row in cur.fetchall():
        print(f"     • {row[0]:30}: {row[1]:>5} receipts")
    
    # Summary
    print(f"\n{'=' * 100}")
    print("📋 CLEANUP SUMMARY")
    print("=" * 100)
    
    total_to_remove = receipt_count + dup_count
    final_count = total - total_to_remove
    
    print(f"\n   Current: {total:,} receipts")
    print(f"   Remove: {total_to_remove:,} receipts")
    print(f"     - {receipt_count:,} from misdated batch")
    print(f"     - {dup_count:,} duplicate bank fees")
    print(f"   Final:  {final_count:,} receipts")
    
    print(f"\n{'=' * 100}")
    print("🔧 CLEANUP SCRIPTS")
    print("=" * 100)
    print(f"\n   1. python l:\\limo\\scripts\\delete_misdated_2025_10_17_batch.py --write")
    print(f"   2. python l:\\limo\\scripts\\delete_duplicate_2025_bank_fees.py --write")
    
    print(f"\n{'=' * 100}")
    print("📄 FULL REPORT: l:\\limo\\reports\\2025_RECEIPTS_DUPLICATION_REPORT.md")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
