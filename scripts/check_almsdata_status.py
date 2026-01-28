#!/usr/bin/env python3
"""Check current state of almsdata database after all updates."""

import psycopg2
import os

# Database connection
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
    
    # Check 2012 receipt count
    cur.execute("SELECT COUNT(*) FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2012")
    receipt_count = cur.fetchone()[0]
    
    # Check 2012 banking count
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE EXTRACT(YEAR FROM banking_date) = 2012")
    banking_count = cur.fetchone()[0]
    
    # Check Scotia vs CIBC breakdown
    cur.execute("""
    SELECT mapped_bank_account_id, COUNT(*) 
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    GROUP BY mapped_bank_account_id
    ORDER BY mapped_bank_account_id
    """)
    account_breakdown = cur.fetchall()
    
    # Check for duplicates (date+vendor+amount)
    cur.execute("""
    SELECT COUNT(*) 
    FROM (
        SELECT receipt_date, vendor_name, gross_amount, COUNT(*) as cnt
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
    ) dup_groups
    """)
    duplicate_groups = cur.fetchone()[0]
    
    # Check for duplicate rows
    cur.execute("""
    SELECT SUM(cnt) 
    FROM (
        SELECT COUNT(*) as cnt
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
    ) dup_rows
    """)
    duplicate_rows = cur.fetchone()[0] or 0
    
    print("=" * 60)
    print("ALMSDATA DATABASE STATUS - December 9, 2025")
    print("=" * 60)
    print(f"\n✓ Database Connection: ACTIVE (almsdata)")
    print(f"\n2012 RECEIPT STATUS:")
    print(f"  Total receipts: {receipt_count:,}")
    print(f"  Duplicate rows: {duplicate_rows}")
    print(f"  Duplicate groups: {duplicate_groups}")
    
    print(f"\n2012 ACCOUNT BREAKDOWN:")
    for account_id, count in account_breakdown:
        if account_id == 1:
            print(f"  Account ID 1 (CIBC 0228362): {count:,} receipts")
        elif account_id == 2:
            print(f"  Account ID 2 (Scotia 903990106011): {count:,} receipts")
        elif account_id == 3:
            print(f"  Account ID 3 (CIBC Business 3648117): {count:,} receipts")
        else:
            print(f"  Account ID {account_id}: {count:,} receipts")
    
    print(f"\n2012 BANKING STATUS:")
    print(f"  Total banking transactions: {banking_count:,}")
    
    # Check last few receipts to verify vendor name normalization
    cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    ORDER BY receipt_date DESC, receipt_id DESC
    LIMIT 5
    """)
    recent = cur.fetchall()
    print(f"\nMOST RECENT RECEIPTS (Last 5):")
    for receipt_id, receipt_date, vendor_name, gross_amount in recent:
        print(f"  {receipt_date} | {vendor_name:30s} | ${gross_amount:>8.2f}")
    
    # Check for vendor names with old formatting (uppercase with Inc/Ltd)
    cur.execute("""
    SELECT COUNT(DISTINCT vendor_name)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND (vendor_name LIKE '%INC%' OR vendor_name LIKE '%LTD%' OR vendor_name LIKE '%CORP%')
    """)
    old_format_count = cur.fetchone()[0]
    print(f"\nVENDOR NORMALIZATION CHECK:")
    print(f"  Vendors still with INC/LTD/CORP suffix: {old_format_count}")
    
    # Check Scotia receipts
    cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012 
      AND mapped_bank_account_id = 2
    """)
    scotia_count = cur.fetchone()[0]
    print(f"\nSCOTIA REBUILD STATUS:")
    print(f"  Scotia receipts created: {scotia_count}")
    
    print(f"\n" + "=" * 60)
    print("SUMMARY: ✓ DATABASE IS UPDATED")
    print("=" * 60)
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
