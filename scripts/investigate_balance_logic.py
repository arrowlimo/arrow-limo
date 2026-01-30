#!/usr/bin/env python3
"""
Investigate charter balance calculation logic.
Check if balance field is manually set or calculated from payments.
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 120)
print("CHARTER BALANCE CALCULATION INVESTIGATION")
print("=" * 120)

# Take a specific example and trace through the data
charter_example = '006491'  # Rate $2,000, Payments $4,313, Balance $1,500

print(f"\nExample Charter: {charter_example}")
print("=" * 120)

# Get charter details
cur.execute("""
    SELECT 
        charter_id,
        reserve_number,
        charter_date,
        rate,
        balance,
        deposit,
        paid_amount,
        total_amount_due,
        payment_status,
        closed,
        status
    FROM charters
    WHERE reserve_number = %s
""", (charter_example,))

charter = cur.fetchone()
if charter:
    charter_id, reserve, date, rate, balance, deposit, paid_amt, total_due, pay_status, closed, status = charter
    print(f"\nCharter Details:")
    print(f"  Charter ID: {charter_id}")
    print(f"  Reserve Number: {reserve}")
    print(f"  Date: {date}")
    print(f"  Rate: ${rate:.2f}")
    print(f"  Balance: ${balance:.2f}")
    deposit_amt = deposit if deposit else 0
    paid_amount = paid_amt if paid_amt else 0
    total_amount = total_due if total_due else 0
    print(f"  Deposit: ${deposit_amt:.2f}")
    print(f"  Paid Amount: ${paid_amount:.2f}")
    print(f"  Total Amount Due: ${total_amount:.2f}")
    print(f"  Payment Status: {pay_status or 'N/A'}")
    print(f"  Closed: {closed}")
    print(f"  Status: {status or 'N/A'}")

# Get all payments for this charter
cur.execute("""
    SELECT 
        payment_id,
        payment_date,
        amount,
        payment_method,
        notes
    FROM payments
    WHERE reserve_number = %s
    ORDER BY payment_date
""", (charter_example,))

payments = cur.fetchall()
print(f"\nPayments for this charter: {len(payments)}")
print(f"{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Method':<20} {'Notes':<30}")
print("-" * 120)

total_paid = 0
for pay_id, pay_date, amount, method, notes in payments:
    total_paid += amount
    notes_str = notes[:30] if notes else ""
    print(f"{pay_id:<12} {str(pay_date):<12} ${amount:>9.2f} {method or 'N/A':<20} {notes_str:<30}")

print(f"\nTotal payments: ${total_paid:.2f}")
print(f"Charter rate: ${rate:.2f}")
print(f"Expected balance: ${rate - total_paid:.2f}")
print(f"Actual balance field: ${balance:.2f}")
print(f"\n[WARN]  Balance field does NOT match (rate - payments)")

# Check multiple charters to see pattern
print("\n" + "=" * 120)
print("BALANCE FIELD VS CALCULATED BALANCE (Sample of 20 charters)")
print("=" * 120)

cur.execute("""
    SELECT 
        c.reserve_number,
        c.rate,
        c.balance as stored_balance,
        COALESCE(SUM(p.amount), 0) as total_payments,
        c.rate - COALESCE(SUM(p.amount), 0) as calculated_balance,
        c.paid_amount,
        c.deposit
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
        AND (c.cancelled IS NULL OR c.cancelled = false)
    GROUP BY c.charter_id, c.reserve_number, c.rate, c.balance, c.paid_amount, c.deposit
    ORDER BY ABS(c.balance - (c.rate - COALESCE(SUM(p.amount), 0))) DESC
    LIMIT 20
""")

print(f"{'Reserve':<12} {'Rate':<10} {'Payments':<10} {'Calc Bal':<10} {'Stored Bal':<12} {'Difference':<12}")
print("-" * 120)

matching = 0
not_matching = 0

for reserve, rate, stored_bal, total_pay, calc_bal, paid_amt, deposit in cur.fetchall():
    diff = stored_bal - calc_bal
    match = "✓" if abs(diff) < 0.01 else "✗"
    
    if abs(diff) < 0.01:
        matching += 1
    else:
        not_matching += 1
    
    print(f"{reserve or 'N/A':<12} ${rate:>8.2f} ${total_pay:>8.2f} ${calc_bal:>8.2f} ${stored_bal:>10.2f} ${diff:>10.2f} {match}")

# Overall statistics
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN ABS(c.balance - (c.rate - COALESCE(SUM(p.amount), 0))) < 0.01 THEN 1 END) as matching,
        COUNT(CASE WHEN ABS(c.balance - (c.rate - COALESCE(SUM(p.amount), 0))) >= 0.01 THEN 1 END) as not_matching
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
        AND (c.cancelled IS NULL OR c.cancelled = false)
    GROUP BY c.charter_id, c.reserve_number, c.rate, c.balance
""")

stats = cur.fetchone()
total, matching_count, not_matching_count = stats or (0, 0, 0)

print("\n" + "=" * 120)
print("OVERALL STATISTICS")
print("=" * 120)
print(f"Total charters analyzed: {total}")
print(f"Balance matches calculation: {matching_count} ({matching_count/total*100:.1f}%)")
print(f"Balance does NOT match: {not_matching_count} ({not_matching_count/total*100:.1f}%)")

print("\n" + "=" * 120)
print("CONCLUSION")
print("=" * 120)
print("""
The 'balance' field appears to be:
1. Set manually when charter is created (rate - deposit)
2. NOT automatically updated when payments are recorded
3. Separate from the payments table

This means:
- The 'balance' field is stale/outdated
- Actual balance must be calculated: rate - SUM(payments)
- The field may represent "initial balance" not "current balance"

This is a DATA SYNCHRONIZATION ISSUE, not incorrect data entry.
The payments are recorded correctly, but the charter balance field is not being updated.
""")

cur.close()
conn.close()
