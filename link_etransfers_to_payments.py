#!/usr/bin/env python3
"""Link already-created e-transfer payments to banking by updating reconciled_payment_id."""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

DRY_RUN = False  # Set to False to execute

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "=" * 140)
print("LINK E-TRANSFERS TO PAYMENTS: Update banking_transactions.reconciled_payment_id".center(140))
if DRY_RUN:
    print("*** DRY RUN MODE ***".center(140))
print("=" * 140)

# Find matches: e-transfers in banking that match payments by amount + date
cur.execute('''
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        p.payment_id,
        p.payment_date,
        p.amount
    FROM banking_transactions bt
    INNER JOIN payments p ON 
        ABS(p.amount - bt.credit_amount) < 0.01
        AND (p.payment_date::date = bt.transaction_date::date 
             OR p.payment_date::date = bt.transaction_date::date - interval '1 day'
             OR p.payment_date::date = bt.transaction_date::date + interval '1 day')
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
      AND bt.reconciled_payment_id IS NULL
    ORDER BY bt.transaction_date DESC;
''')

matches = cur.fetchall()
print(f"\n📊 Found {len(matches)} e-transfer to payment matches")
print(f"   Total Amount: ${sum(m[2] for m in matches):,.2f}\n")

if matches:
    print("SAMPLE MATCHES (showing first 20):")
    print("-" * 140)
    print(f"{'Bank Date':<12} | {'Amount':>10} | {'Payment Date':<12} | {'Payment ID':>10} | Action")
    print("-" * 140)
    
    for i, match in enumerate(matches[:20]):
        bt_trans_id, bt_date, bt_amount, p_id, p_date, p_amount = match
        bt_date_str = bt_date.strftime('%Y-%m-%d') if bt_date else 'N/A'
        p_date_str = p_date.strftime('%Y-%m-%d') if p_date else 'N/A'
        print(f"{bt_date_str} | ${bt_amount:>9.2f} | {p_date_str} | {p_id:>10} | SET reconciled_payment_id = {p_id}")
    
    if len(matches) > 20:
        print(f"... and {len(matches) - 20} more")
    
    if not DRY_RUN:
        print(f"\n" + "=" * 140)
        print("EXECUTING UPDATE:")
        print("=" * 140)
        
        # Perform the update
        update_count = 0
        for match in matches:
            bt_trans_id, bt_date, bt_amount, p_id, p_date, p_amount = match
            cur.execute('''
                UPDATE banking_transactions
                SET reconciled_payment_id = %s,
                    updated_at = NOW()
                WHERE transaction_id = %s;
            ''', (p_id, bt_trans_id))
            update_count += cur.rowcount
        
        conn.commit()
        
        print(f"\n✅ Updated {update_count} banking_transactions records")
        print(f"   All now have reconciled_payment_id linked to charter payments")
        
        # Verify
        cur.execute('''
            SELECT COUNT(*) as matched_count, SUM(credit_amount) as total_matched
            FROM banking_transactions
            WHERE credit_amount > 0
              AND (description ILIKE '%E-TRANSFER%' OR description ILIKE '%ETRANSFER%')
              AND reconciled_payment_id IS NOT NULL;
        ''')
        
        matched_check = cur.fetchone()
        print(f"\n📊 VERIFICATION:")
        print(f"   E-transfers now linked: {matched_check[0]}")
        print(f"   Total amount: ${matched_check[1] if matched_check[1] else 0:,.2f}")
        
        # Check remaining unlinked
        cur.execute('''
            SELECT COUNT(*) as unlinked_count, SUM(credit_amount) as total_unlinked
            FROM banking_transactions
            WHERE credit_amount > 0
              AND (description ILIKE '%E-TRANSFER%' OR description ILIKE '%ETRANSFER%')
              AND reconciled_payment_id IS NULL;
        ''')
        
        unlinked_check = cur.fetchone()
        print(f"   E-transfers still unlinked: {unlinked_check[0]}")
        print(f"   Total amount: ${unlinked_check[1] if unlinked_check[1] else 0:,.2f}")

print(f"\n" + "=" * 140)
if DRY_RUN:
    print("💡 TO EXECUTE: Set DRY_RUN = False")
else:
    print("✅ UPDATE COMPLETE")
print("=" * 140 + "\n")

cur.close()
conn.close()
