#!/usr/bin/env python3
"""
ANALYZE REMAINING UNMATCHED - Find where records actually are
- Telus, Rogers, Shaw, etc. → should be in receipts (expense_date)
- Sobeys, Coop, fuel → should be in receipts
- Bank fees, interest → should be in receipts or payments
- Meals, car wash → should be in receipts
- Employee payments, client refunds → already linked
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("\n" + "=" * 120)
    print("ANALYZE REMAINING UNMATCHED BANKING - Find existing records")
    print("=" * 120)
    
    # Get remaining unmatched
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND reconciled_receipt_id IS NULL
        ORDER BY transaction_date DESC
        LIMIT 100
    """)
    
    unmatched = cur.fetchall()
    
    print(f"\n📊 SAMPLE OF REMAINING UNMATCHED (first 100):")
    print("-" * 120)
    
    # Categorize by description
    categories = {
        'TELUS/ROGERS/SHAW': [],
        'SOBEYS/COOP': [],
        'FUEL/FAS GAS': [],
        'BANK FEES/INTEREST': [],
        'MEAL/FOOD': [],
        'CAR WASH': [],
        'WITHDRAWAL': [],
        'DEPOSIT': [],
        'TRANSFER': [],
        'OTHER': []
    }
    
    for trans_id, date, credit, debit, desc in unmatched:
        amount = abs((credit if credit else 0) + (debit if debit else 0))
        desc_upper = (desc or "").upper()
        
        categorized = False
        for cat in categories.keys():
            if any(term in desc_upper for term in cat.split('/')):
                categories[cat].append((trans_id, date, amount, desc))
                categorized = True
                break
        
        if not categorized:
            categories['OTHER'].append((trans_id, date, amount, desc))
    
    print("\n📈 CATEGORY BREAKDOWN:")
    print("-" * 120)
    for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        if items:
            amount = sum(x[2] for x in items)
            print(f"{cat:20s}: {len(items):4d} trans | ${amount:12,.2f}")
            # Show first 2 samples
            for trans_id, date, amt, desc in items[:2]:
                print(f"                      {trans_id:8d} | {date} | ${amt:10,.2f} | {desc[:60]}")
    
    # Now check: do these records exist in receipts table?
    print(f"\n🔍 CHECKING IF CORRESPONDING RECORDS EXIST:")
    print("-" * 120)
    
    # Check Telus/Rogers/Shaw in receipts
    print("\n📱 Telus/Rogers/Shaw:")
    for term in ['TELUS', 'ROGERS', 'SHAW']:
        cur.execute("""
            SELECT COUNT(*) as cnt, SUM(amount) as total
            FROM receipts
            WHERE vendor_name ILIKE %s
        """, (f'%{term}%',))
        
        cnt, total = cur.fetchone()
        print(f"   {term:15s}: {cnt:6d} receipts | ${total if total else 0:12,.2f}")
    
    # Check Sobeys/Coop in receipts
    print("\n🛒 Sobeys/Coop:")
    for term in ['SOBEYS', 'COOP']:
        cur.execute("""
            SELECT COUNT(*) as cnt, SUM(amount) as total
            FROM receipts
            WHERE vendor_name ILIKE %s
        """, (f'%{term}%',))
        
        cnt, total = cur.fetchone()
        print(f"   {term:15s}: {cnt:6d} receipts | ${total if total else 0:12,.2f}")
    
    # Check FAS GAS/fuel
    print("\n⛽ Fuel:")
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(amount) as total
        FROM receipts
        WHERE vendor_name ILIKE '%FAS%' OR vendor_name ILIKE '%GAS%' OR vendor_name ILIKE '%FUEL%'
    """)
    
    cnt, total = cur.fetchone()
    print(f"   FAS/FUEL:       {cnt:6d} receipts | ${total if total else 0:12,.2f}")
    
    # Check bank fees
    print("\n💳 Bank fees/interest:")
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(amount) as total
        FROM receipts
        WHERE vendor_name ILIKE '%FEE%' OR vendor_name ILIKE '%INTEREST%' OR vendor_name ILIKE '%CHARGE%'
    """)
    
    cnt, total = cur.fetchone()
    print(f"   FEES/INTEREST:  {cnt:6d} receipts | ${total if total else 0:12,.2f}")
    
    # Check Payments table too
    print("\n💰 Checking payments table:")
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(amount) as total
        FROM payments
        WHERE reconciled_payment_id IS NULL
        AND (
            notes ILIKE '%fee%' OR
            notes ILIKE '%interest%' OR
            notes ILIKE '%withdrawal%'
        )
    """)
    
    cnt, total = cur.fetchone()
    print(f"   Special payments: {cnt:6d} records | ${total if total else 0:12,.2f}")
    
    print("\n" + "=" * 120 + "\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
