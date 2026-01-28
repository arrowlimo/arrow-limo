#!/usr/bin/env python3
"""
Check if all charter payments in 2012 have been matched to banking transactions.
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("2012 CHARTER PAYMENT MATCHING ANALYSIS")
print("=" * 120)

# Get all 2012 payments
cur.execute("""
    SELECT 
        payment_id,
        payment_date,
        reserve_number,
        charter_id,
        amount,
        payment_method,
        square_transaction_id,
        notes
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
    ORDER BY payment_date
""")

payments_2012 = cur.fetchall()
print(f"\nTotal payments in 2012: {len(payments_2012)}")

if payments_2012:
    total_amount = sum(p[4] for p in payments_2012 if p[4])
    print(f"Total payment amount: ${total_amount:,.2f}")
    
    # Check payment methods
    cur.execute("""
        SELECT 
            payment_method,
            COUNT(*) as count,
            SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) = 2012
        GROUP BY payment_method
        ORDER BY count DESC
    """)
    
    print("\nPayment methods breakdown:")
    print(f"{'Method':<20} {'Count':<10} {'Total':<15}")
    print("-" * 50)
    for method, count, total in cur.fetchall():
        method_str = method if method else "(null)"
        total_str = f"${total:,.2f}" if total else "$0.00"
        print(f"{method_str:<20} {count:<10} {total_str:<15}")

# Check banking transactions that look like charter payments
print("\n" + "=" * 120)
print("BANKING TRANSACTIONS THAT MAY BE CHARTER PAYMENTS")
print("=" * 120)

cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.credit_amount,
        CASE 
            WHEN r.id IS NOT NULL THEN 'Linked to receipt'
            WHEN EXISTS (
                SELECT 1 FROM payments p 
                WHERE ABS(p.amount - bt.credit_amount) < 0.01 
                AND ABS(p.payment_date - bt.transaction_date) <= 2
            ) THEN 'Possible payment match'
            ELSE 'No match'
        END as match_status
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.mapped_bank_account_id = bt.transaction_id
    WHERE bt.account_number = '903990106011'
        AND EXTRACT(YEAR FROM bt.transaction_date) = 2012
        AND bt.credit_amount > 0
        AND bt.description NOT ILIKE '%transfer%'
        AND bt.description NOT ILIKE '%deposit%'
    ORDER BY bt.credit_amount DESC
    LIMIT 50
""")

credits = cur.fetchall()
print(f"\nFound {len(credits)} credit transactions (showing top 50 by amount):")
print()
print(f"{'Trans ID':<10} {'Date':<12} {'Amount':<12} {'Status':<25} {'Description':<40}")
print("-" * 120)

for trans_id, date, desc, amount, status in credits[:20]:
    print(f"{trans_id:<10} {str(date):<12} ${amount:>9.2f} {status:<25} {desc[:40]}")

if len(credits) > 20:
    print(f"... and {len(credits)-20} more credit transactions")

# Try to match payments to banking by amount and date
print("\n" + "=" * 120)
print("MATCHING PAYMENTS TO BANKING TRANSACTIONS")
print("=" * 120)

cur.execute("""
    SELECT 
        p.payment_id,
        p.payment_date,
        p.amount,
        p.payment_method,
        p.reserve_number,
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        bt.description
    FROM payments p
    LEFT JOIN banking_transactions bt ON 
        ABS(p.amount - bt.credit_amount) < 0.01
        AND ABS(p.payment_date - bt.transaction_date) <= 3
        AND bt.account_number = '903990106011'
        AND EXTRACT(YEAR FROM bt.transaction_date) = 2012
    WHERE EXTRACT(YEAR FROM p.payment_date) = 2012
        AND p.amount > 0
        AND p.payment_method IN ('Cash', 'Check', 'Credit Card', 'Debit', 'E-Transfer')
    ORDER BY p.payment_date
    LIMIT 30
""")

matches = cur.fetchall()
if matches:
    print(f"\nFound {len(matches)} potential payment-to-banking matches:")
    print()
    print(f"{'Pay ID':<8} {'Pay Date':<12} {'Amount':<10} {'Method':<15} {'Bank ID':<10} {'Bank Date':<12}")
    print("-" * 120)
    
    matched_count = 0
    unmatched_count = 0
    
    for pay_id, pay_date, amount, method, reserve, bank_id, bank_date, bank_amt, bank_desc in matches:
        if bank_id:
            matched_count += 1
            print(f"{pay_id:<8} {str(pay_date):<12} ${amount:>8.2f} {method or 'N/A':<15} {bank_id:<10} {str(bank_date):<12}")
        else:
            unmatched_count += 1
    
    print(f"\nMatched payments: {matched_count}")
    print(f"Unmatched payments: {unmatched_count}")

# Check for Square payments (don't appear in banking directly)
cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
        AND square_transaction_id IS NOT NULL
""")

square_count, square_total = cur.fetchone()
print(f"\nSquare payments (processed externally): {square_count} payments, ${square_total or 0:,.2f}")

# Summary
print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)
print("""
Charter payments may not directly match banking transactions because:
1. Square payments are batched and settled to banking in lump sums
2. Cash payments are deposited in batches
3. Credit card payments go through Square/merchant processor first
4. Checks may be deposited in batches

To verify charter payment matching, we should:
1. Check if payments table has reserve_number linking to charters
2. Verify payment amounts match charter balances
3. Confirm payment records exist for closed charters
""")

# Check charter-payment linkage
print("\n" + "=" * 120)
print("CHARTER-PAYMENT LINKAGE CHECK")
print("=" * 120)

cur.execute("""
    SELECT 
        COUNT(DISTINCT c.charter_id) as total_charters,
        COUNT(DISTINCT CASE WHEN p.payment_id IS NOT NULL THEN c.charter_id END) as charters_with_payments,
        SUM(c.rate) as total_charter_value,
        SUM(p.amount) as total_payments
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
""")

charter_stats = cur.fetchone()
total_charters, charters_with_pay, charter_value, payment_total = charter_stats

print(f"\n2012 Charters: {total_charters}")
print(f"Charters with linked payments: {charters_with_pay}")
print(f"Charters without payments: {total_charters - charters_with_pay}")
print(f"\nTotal charter value: ${charter_value or 0:,.2f}")
print(f"Total linked payments: ${payment_total or 0:,.2f}")

if charter_value and payment_total:
    coverage = (payment_total / charter_value) * 100
    print(f"Payment coverage: {coverage:.1f}%")

cur.close()
conn.close()

print("\n" + "=" * 120)
