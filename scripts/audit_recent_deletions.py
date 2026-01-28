#!/usr/bin/env python3
"""
Audit recent receipt/invoice deletions and verify current state.

Checks:
1. Current receipts count (total and rent/utilities)
2. Recent pg_stat_user_tables data (if available)
3. Scans for DELETE statements in all scripts
4. Reports any receipts with missing bank_id links that should exist

READ-ONLY: No database modifications.
"""
import os
import psycopg2
from collections import defaultdict

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')


def main():
    conn = psycopg2.connect(**DSN)
    conn.autocommit = True  # Avoid transaction abort cascades
    cur = conn.cursor()

    print("=== RECEIPTS TABLE AUDIT ===\n")
    
    # Total counts
    cur.execute("SELECT COUNT(*) FROM receipts")
    total = cur.fetchone()[0]
    print(f"Total receipts: {total:,}")

    # Rent/utilities counts
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE COALESCE(category,'') ILIKE '%rent%' 
           OR COALESCE(category,'') ILIKE '%6820%' 
           OR COALESCE(category,'') ILIKE '%util%'
    """)
    rent_util = cur.fetchone()[0]
    print(f"Rent/Utilities receipts: {rent_util:,}")

    # Created from banking
    cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = TRUE")
    from_banking = cur.fetchone()[0]
    print(f"Created from banking: {from_banking:,}")

    # Check for orphaned receipts (created_from_banking but no bank linkage)
    # Note: receipts.bank_id doesn't exist; use banking_receipt_matching_ledger instead
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger l ON l.receipt_id = r.id
        WHERE r.created_from_banking = TRUE 
          AND l.banking_transaction_id IS NULL
    """)
    orphaned = cur.fetchone()[0]
    print(f"Orphaned (created_from_banking but no bank link): {orphaned:,}")

    # Recent receipts (last 30 days)
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    """)
    recent = cur.fetchone()[0]
    print(f"Created in last 30 days: {recent:,}")

    # Check for duplicate detection markers
    cur.execute("""
        SELECT source_system, COUNT(*) 
        FROM receipts 
        GROUP BY source_system 
        ORDER BY COUNT(*) DESC 
        LIMIT 10
    """)
    print("\nTop source systems:")
    for src, cnt in cur.fetchall():
        print(f"  {src or '(null)'}: {cnt:,}")

    # Invoice check
    try:
        cur.execute("SELECT COUNT(*) FROM invoices")
        inv_count = cur.fetchone()[0]
        print(f"\nTotal invoices: {inv_count:,}")
    except Exception as e:
        print(f"\nInvoices table check failed: {e}")

    # Check banking_receipt_matching_ledger integrity
    try:
        cur.execute("""
            SELECT COUNT(DISTINCT banking_transaction_id) AS txn_count,
                   COUNT(DISTINCT receipt_id) AS rcpt_count,
                   COUNT(*) AS link_count
            FROM banking_receipt_matching_ledger
        """)
        row = cur.fetchone()
        print(f"\nBanking-Receipt Links:")
        print(f"  Unique bank transactions: {row[0]:,}")
        print(f"  Unique receipts: {row[1]:,}")
        print(f"  Total links: {row[2]:,}")
    except Exception as e:
        print(f"\nBanking-receipt ledger check failed: {e}")

    print("\n=== DELETION AUDIT ===")
    print("\nScripts with DELETE statements:")
    
    # Scan scripts directory for DELETE patterns
    scripts_dir = os.path.join(os.path.dirname(__file__))
    delete_scripts = []
    
    for fname in os.listdir(scripts_dir):
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(scripts_dir, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'DELETE FROM receipts' in content or 'DELETE FROM invoices' in content:
                    # Count occurrences
                    delete_count = content.count('DELETE FROM receipts') + content.count('DELETE FROM invoices')
                    delete_scripts.append((fname, delete_count))
        except Exception:
            pass
    
    if delete_scripts:
        for script, count in sorted(delete_scripts, key=lambda x: x[1], reverse=True):
            print(f"  {script}: {count} DELETE statement(s)")
    else:
        print("  No scripts with DELETE FROM receipts/invoices found")

    print("\n=== SAFETY STATUS ===")
    if orphaned > 0:
        print(f"[WARN]  WARNING: {orphaned} receipts marked created_from_banking but missing bank_id")
    else:
        print("✓ No orphaned banking receipts")
    
    if delete_scripts:
        print(f"[WARN]  Found {len(delete_scripts)} scripts with DELETE statements")
    else:
        print("✓ No DELETE statements found in scripts")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
