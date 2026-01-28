#!/usr/bin/env python3
"""
ANALYZE THE 26,875 REMAINING UNMATCHED BANKING TRANSACTIONS
What are they? Business expenses? Personal? Transfers?
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("\n" + "=" * 120)
    print("REMAINING 26,875 UNMATCHED BANKING TRANSACTIONS - WHAT ARE THEY?")
    print("=" * 120)
    
    # Get all unmatched
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, 
               description, vendor_extracted
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND reconciled_receipt_id IS NULL
        ORDER BY ABS(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0)) DESC
        LIMIT 500
    """)
    
    all_trans = cur.fetchall()
    
    # Categorize by type
    categories = {
        'DEPOSITS (likely customer payments)': [],
        'E-TRANSFERS IN (customer/other)': [],
        'RETAIL PURCHASES (business expenses)': [],
        'FUEL/GAS': [],
        'FOOD/MEALS': [],
        'WITHDRAWALS': [],
        'BANK FEES/INTEREST': [],
        'TRANSFERS': [],
        'UNKNOWN': []
    }
    
    for trans_id, date, credit, debit, desc, vendor in all_trans:
        amount = abs((credit if credit else 0) + (debit if debit else 0))
        desc_upper = (desc or "").upper()
        
        categorized = False
        
        if 'DEPOSIT' in desc_upper and credit:
            categories['DEPOSITS (likely customer payments)'].append((trans_id, date, amount, desc))
            categorized = True
        elif 'E-TRANSFER' in desc_upper and credit:
            categories['E-TRANSFERS IN (customer/other)'].append((trans_id, date, amount, desc))
            categorized = True
        elif any(x in desc_upper for x in ['RETAIL PURCHASE', 'POINT OF SALE', 'INTERAC']):
            categories['RETAIL PURCHASES (business expenses)'].append((trans_id, date, amount, desc))
            categorized = True
        elif any(x in desc_upper for x in ['FAS GAS', 'FUEL', 'SHELL', 'PETRO', 'HUSKY', 'ESSO']):
            categories['FUEL/GAS'].append((trans_id, date, amount, desc))
            categorized = True
        elif any(x in desc_upper for x in ['RESTAURANT', 'COFFEE', 'TIM HORTONS', 'MCDONALDS', 'SUBWAY', 'FOOD']):
            categories['FOOD/MEALS'].append((trans_id, date, amount, desc))
            categorized = True
        elif 'WITHDRAWAL' in desc_upper:
            categories['WITHDRAWALS'].append((trans_id, date, amount, desc))
            categorized = True
        elif any(x in desc_upper for x in ['FEE', 'INTEREST', 'CHARGE']):
            categories['BANK FEES/INTEREST'].append((trans_id, date, amount, desc))
            categorized = True
        elif 'TRANSFER' in desc_upper:
            categories['TRANSFERS'].append((trans_id, date, amount, desc))
            categorized = True
        
        if not categorized:
            categories['UNKNOWN'].append((trans_id, date, amount, desc))
    
    print(f"\n📊 CATEGORY BREAKDOWN (sample of 500 largest):")
    print("-" * 120)
    
    for cat, items in sorted(categories.items(), key=lambda x: -sum(i[2] for i in x[1])):
        if items:
            amount = sum(i[2] for i in items)
            print(f"\n{cat}:")
            print(f"   {len(items):4d} trans | ${amount:12,.2f}")
            # Show first 3 samples
            for trans_id, date, amt, desc in items[:3]:
                print(f"      {trans_id:8d} | {date} | ${amt:10,.2f} | {desc[:70]}")
    
    # Get total count by category for ALL unmatched
    print(f"\n\n📈 FULL BREAKDOWN OF ALL 26,875 UNMATCHED:")
    print("-" * 120)
    
    # Count by description patterns
    cur.execute("""
        SELECT 
            CASE
                WHEN description ILIKE '%DEPOSIT%' AND credit_amount IS NOT NULL THEN 'DEPOSITS'
                WHEN description ILIKE '%E-TRANSFER%' AND credit_amount IS NOT NULL THEN 'E-TRANSFERS IN'
                WHEN description ILIKE '%RETAIL PURCHASE%' OR description ILIKE '%POINT OF SALE%' THEN 'RETAIL PURCHASES'
                WHEN description ILIKE '%FAS GAS%' OR description ILIKE '%FUEL%' THEN 'FUEL/GAS'
                WHEN description ILIKE '%WITHDRAWAL%' THEN 'WITHDRAWALS'
                WHEN description ILIKE '%FEE%' OR description ILIKE '%INTEREST%' THEN 'BANK FEES'
                WHEN description ILIKE '%TRANSFER%' THEN 'TRANSFERS'
                ELSE 'OTHER'
            END as category,
            COUNT(*) as cnt,
            SUM(ABS(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0))) as total
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND reconciled_receipt_id IS NULL
        GROUP BY category
        ORDER BY total DESC
    """)
    
    for cat, cnt, total in cur.fetchall():
        print(f"   {cat:25s}: {cnt:6d} trans | ${total if total else 0:12,.2f}")
    
    # Total unmatched
    cur.execute("""
        SELECT COUNT(*), SUM(ABS(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0)))
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND reconciled_receipt_id IS NULL
    """)
    
    cnt, total = cur.fetchone()
    print(f"\n   {'TOTAL UNMATCHED':25s}: {cnt:6d} trans | ${total if total else 0:12,.2f}")
    
    print("\n" + "=" * 120 + "\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
