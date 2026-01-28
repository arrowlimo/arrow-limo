#!/usr/bin/env python3
"""
Check 2012 Data Completeness Status
===================================

Quick audit script to determine what 2012 data exists in the database:
- Banking transactions (by account)
- Receipts (count, GST totals, date coverage)
- General ledger entries
- QuickBooks reconciliation status

Outputs a simple report to guide import/reconciliation decisions.
"""
from __future__ import annotations

import os
import psycopg2
from datetime import date

DSN = dict(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    port=int(os.environ.get('DB_PORT', '5432')),
)

def safe_fetch(cur, query, params=None):
    """Execute query and return first row or None."""
    try:
        cur.execute(query, params or [])
        return cur.fetchone()
    except Exception as e:
        return None

def main():
    year = 2012
    print(f"\n{'='*60}")
    print(f"2012 DATA COMPLETENESS AUDIT")
    print(f"{'='*60}\n")

    with psycopg2.connect(**DSN) as conn:
        cur = conn.cursor()

        # 1. Banking transactions
        print("📊 BANKING TRANSACTIONS (2012)")
        print("-" * 60)
        
        # Check for account 00339 (CIBC from PDF)
        row = safe_fetch(cur, """
            SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date),
                   SUM(debit_amount), SUM(credit_amount)
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
              AND account_number = '00339'
        """, [year])
        if row and row[0]:
            print(f"  Account 00339 (CIBC): {row[0]:,} transactions")
            print(f"    Date range: {row[1]} to {row[2]}")
            print(f"    Debits: ${float(row[3] or 0):,.2f}")
            print(f"    Credits: ${float(row[4] or 0):,.2f}")
        else:
            print("  Account 00339 (CIBC): [FAIL] NO DATA")

        # Check for account 0228362 (seen in earlier reports)
        row = safe_fetch(cur, """
            SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date),
                   SUM(debit_amount), SUM(credit_amount)
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
              AND account_number = '0228362'
        """, [year])
        if row and row[0]:
            print(f"  Account 0228362: {row[0]:,} transactions")
            print(f"    Date range: {row[1]} to {row[2]}")
            print(f"    Debits: ${float(row[3] or 0):,.2f}")
            print(f"    Credits: ${float(row[4] or 0):,.2f}")
        else:
            print("  Account 0228362: [FAIL] NO DATA")

        # Check all accounts
        row = safe_fetch(cur, """
            SELECT COUNT(DISTINCT account_number), COUNT(*),
                   MIN(transaction_date), MAX(transaction_date)
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
        """, [year])
        if row and row[1]:
            print(f"  ALL ACCOUNTS: {row[0]} distinct accounts, {row[1]:,} total transactions")
            print(f"    Date range: {row[2]} to {row[3]}")
        else:
            print("  ALL ACCOUNTS: [FAIL] NO BANKING DATA FOR 2012")

        # 2. Receipts
        print(f"\n💰 RECEIPTS (2012)")
        print("-" * 60)
        row = safe_fetch(cur, """
            SELECT COUNT(*), MIN(receipt_date), MAX(receipt_date),
                   SUM(gross_amount), SUM(gst_amount), SUM(net_amount)
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
        """, [year])
        if row and row[0]:
            print(f"  Total receipts: {row[0]:,}")
            print(f"  Date range: {row[1]} to {row[2]}")
            print(f"  Gross: ${float(row[3] or 0):,.2f}")
            print(f"  GST: ${float(row[4] or 0):,.2f}")
            print(f"  Net: ${float(row[5] or 0):,.2f}")
        else:
            print("  [FAIL] NO RECEIPTS FOR 2012")

        # Receipt categories
        cur.execute("""
            SELECT COALESCE(category, 'uncategorized') AS cat, COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 10
        """, [year])
        cats = cur.fetchall()
        if cats:
            print("\n  Top categories:")
            for cat, cnt, amt in cats:
                print(f"    - {cat}: {cnt} receipts, ${float(amt or 0):,.2f}")

        # 3. General Ledger
        print(f"\n📒 GENERAL LEDGER (2012)")
        print("-" * 60)
        row = safe_fetch(cur, """
            SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date),
                   SUM(debit_amount), SUM(credit_amount)
            FROM unified_general_ledger
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
        """, [year])
        if row and row[0]:
            print(f"  Total entries: {row[0]:,}")
            print(f"  Date range: {row[1]} to {row[2]}")
            print(f"  Debits: ${float(row[3] or 0):,.2f}")
            print(f"  Credits: ${float(row[4] or 0):,.2f}")
        else:
            print("  [FAIL] NO GENERAL LEDGER DATA FOR 2012")

        # 4. QuickBooks data
        print(f"\n📚 QUICKBOOKS (2012)")
        print("-" * 60)
        
        # Check for QB staging
        row = safe_fetch(cur, """
            SELECT COUNT(*) FROM qb_transactions_staging
            WHERE year_extracted = %s
        """, [year])
        if row and row[0]:
            print(f"  QB staging records: {row[0]:,}")
        else:
            print("  QB staging: [FAIL] NO DATA")

        # Summary and recommendations
        print(f"\n{'='*60}")
        print("RECOMMENDATIONS")
        print(f"{'='*60}\n")

        # Banking assessment
        row = safe_fetch(cur, """
            SELECT COUNT(*) FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
              AND account_number IN ('00339', '0228362')
        """, [year])
        banking_count = row[0] if row and row[0] else 0

        # Receipts assessment
        row = safe_fetch(cur, """
            SELECT COUNT(*) FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
        """, [year])
        receipt_count = row[0] if row and row[0] else 0

        if banking_count == 0:
            print("[FAIL] BANKING: Import the CIBC PDF statements first")
            print("   Use a PDF parser script to extract transaction details")
        elif banking_count < 500:
            print("[WARN]  BANKING: Sparse data - verify all months are present")
        else:
            print("[OK] BANKING: Looks complete")

        if receipt_count == 0:
            print("[FAIL] RECEIPTS: Scan and import all 2012 receipts")
            print("   Or create receipts from banking transactions")
        elif receipt_count < 100:
            print("[WARN]  RECEIPTS: Limited data - scan missing receipts")
        else:
            print("[OK] RECEIPTS: Reasonable coverage")

        print("\n📋 NEXT STEPS:")
        if banking_count == 0:
            print("  1. Parse CIBC PDF and import transactions")
            print("  2. Then scan/import receipts")
            print("  3. Then run reconciliation")
        elif receipt_count < 50:
            print("  1. Scan missing receipts OR create from banking")
            print("  2. Then run reconciliation")
        else:
            print("  1. Run full reconciliation report")
            print("  2. Generate tax summaries")

        cur.close()

if __name__ == '__main__':
    main()
