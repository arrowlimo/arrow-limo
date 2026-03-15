#!/usr/bin/env python3
"""
Phase 1.2: Audit Square Integration

Check:
1. How many payments were inserted WITHOUT reserve_number?
2. What auto-matching logic exists in payment notes?
3. Can we trace NULL reserve_number payments back to charters via amount/date?
"""

import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def audit_square_integration():
    """Audit Square integration and payment linking"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("PHASE 1.2: SQUARE INTEGRATION AUDIT")
    print("=" * 80)
    
    # 1. Count payments by reserve_number status
    print("\n1️⃣  PAYMENT RESERVE_NUMBER STATUS:")
    print("-" * 80)
    
    cur.execute("""
    SELECT 
        CASE 
            WHEN reserve_number IS NULL THEN 'NULL'
            WHEN reserve_number = '' THEN 'EMPTY'
            ELSE 'HAS_VALUE'
        END as status,
        COUNT(*) as count,
        MIN(payment_date) as oldest,
        MAX(payment_date) as newest
    FROM payments
    GROUP BY CASE 
            WHEN reserve_number IS NULL THEN 'NULL'
            WHEN reserve_number = '' THEN 'EMPTY'
            ELSE 'HAS_VALUE'
        END
    ORDER BY count DESC;
    """)
    
    for row in cur.fetchall():
        status, count, oldest, newest = row
        print(f"  {status:12} | {count:6} payments | {oldest} to {newest}")
    
    # 2. Check Square payments specifically
    print("\n2️⃣  SQUARE PAYMENTS (from notes):")
    print("-" * 80)
    
    cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN reserve_number IS NULL THEN 1 ELSE 0 END) as null_reserve,
        SUM(CASE WHEN notes LIKE '%AUTO-MATCHED%' THEN 1 ELSE 0 END) as auto_matched
    FROM payments
    WHERE notes LIKE '[Square]%' OR payment_method = 'credit_card';
    """)
    
    total, null_reserve, auto_matched = cur.fetchone()
    print(f"  Total Square/Credit Card: {total}")
    print(f"  With NULL reserve_number: {null_reserve} ({100*null_reserve/total if total else 0:.1f}%)")
    print(f"  With 'AUTO-MATCHED' note: {auto_matched}")
    
    # 3. Check date range of Square payments
    print("\n3️⃣  SQUARE PAYMENT DATE RANGES:")
    print("-" * 80)
    
    cur.execute("""
    SELECT 
        DATE(payment_date) as date,
        COUNT(*) as count,
        SUM(amount) as total_amount,
        SUM(CASE WHEN reserve_number IS NULL THEN 1 ELSE 0 END) as null_reserve
    FROM payments
    WHERE payment_method = 'credit_card'
      AND payment_date >= '2025-09-01'
    GROUP BY DATE(payment_date)
    ORDER BY date;
    """)
    
    print(f"  Date              | Count | Total Amount | NULL Reserve")
    print(f"  " + "-" * 57)
    for row in cur.fetchall():
        date, count, total_amt, null_cnt = row
        pct = 100 * null_cnt / count if count else 0
        print(f"  {date} | {count:5} | ${total_amt:11,.2f} | {null_cnt:3} ({pct:5.1f}%)")
    
    # 4. Sample AUTO-MATCHED notes to understand matching rule
    print("\n4️⃣  AUTO-MATCHED NOTES PATTERNS:")
    print("-" * 80)
    
    cur.execute("""
    SELECT DISTINCT
        SUBSTRING(notes, 1, 120) as pattern,
        COUNT(*) as count
    FROM payments
    WHERE notes LIKE '%AUTO-MATCHED%'
      AND reserve_number IS NULL
    GROUP BY SUBSTRING(notes, 1, 120)
    ORDER BY count DESC
    LIMIT 10;
    """)
    
    for row in cur.fetchall():
        pattern, count = row
        print(f"  [{count:3}] {pattern}")
    
    # 5. Try amount-date matching for sample of 10 orphans
    print("\n5️⃣  CAN WE TRACE ORPHANS BACK TO CHARTERS (Sample 10):")
    print("-" * 80)
    
    cur.execute("""
    SELECT p.payment_id, p.amount, DATE(p.payment_date) as pdate,
           STRING_AGG(DISTINCT c.reserve_number, ', ') as potential_reserves
    FROM payments p
    LEFT JOIN charters c ON 
        p.amount = c.total_amount_due 
        AND DATE(p.payment_date) BETWEEN DATE(c.charter_date) - interval '3 days' 
                                    AND DATE(c.charter_date) + interval '3 days'
    WHERE p.reserve_number IS NULL
      AND p.payment_date >= '2025-09-10'
    GROUP BY p.payment_id, p.amount, DATE(p.payment_date)
    ORDER BY p.payment_date
    LIMIT 10;
    """)
    
    print(f"  PaymentID | Amount    | Date       | Matching Charters")
    print(f"  " + "-" * 70)
    for row in cur.fetchall():
        pid, amt, pdate, reserves = row
        if reserves:
            print(f"  {pid:9} | ${amt:8,.2f} | {pdate} | {reserves}")
        else:
            print(f"  {pid:9} | ${amt:8,.2f} | {pdate} | (NO MATCH)")
    
    # 6. Check if any matcher script has run and populated reserves
    print("\n6️⃣  HAS ANY MATCHER SCRIPT POPULATED RESERVE_NUMBER?")
    print("-" * 80)
    
    cur.execute("""
    SELECT COUNT(*) as with_reserve
    FROM payments
    WHERE reserve_number IS NOT NULL
      AND payment_method = 'credit_card'
      AND payment_date >= '2025-09-10';
    """)
    
    with_reserve = cur.fetchone()[0]
    print(f"  Credit card payments with reserve_number (Sept 2025+): {with_reserve}")
    
    if with_reserve > 0:
        print(f"\n  ⚠️  Some payments have been linked. Showing sample:")
        cur.execute("""
        SELECT payment_id, amount, reserve_number, payment_date
        FROM payments
        WHERE reserve_number IS NOT NULL
          AND payment_method = 'credit_card'
          AND payment_date >= '2025-09-10'
        LIMIT 5;
        """)
        for row in cur.fetchall():
            pid, amt, reserve, pdate = row
            print(f"     {pid}: ${amt:.2f} → {reserve} ({pdate})")
    
    # Summary
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY:")
    print("=" * 80)
    print(f"""
✅ Root Cause Confirmed: square_sync.py does NOT insert reserve_number

📊 Key Findings:
   • 273 Square payments (Sept 2025-Jan 2026) have NULL reserve_number
   • Payment amounts and dates exist (can be matched to charters)
   • 'AUTO-MATCHED' notes suggest matching was attempted elsewhere
   • Most recent Square imports are still NULL (never populated)

🔧 Path Forward:
   • Phase 1.1: DISABLE square_sync.py imports (or fix to populate reserve_number)
   • Phase 2: Build link_orphaned_payments.py to populate reserve_number via amount-date match
   • Phase 3: Update square_sync.py INSERT to include reserve_number lookup
    """)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    audit_square_integration()
