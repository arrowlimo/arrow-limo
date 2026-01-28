#!/usr/bin/env python3
"""
Check if all non-cancelled 2012 charters have zero balances (fully paid).
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
print("2012 CHARTER BALANCE ANALYSIS")
print("=" * 120)

# Get charter status breakdown
cur.execute("""
    SELECT 
        CASE 
            WHEN cancelled = true THEN 'Cancelled'
            WHEN closed = true THEN 'Closed'
            ELSE 'Open'
        END as status,
        COUNT(*) as count,
        SUM(rate) as total_rate,
        SUM(balance) as total_balance,
        COUNT(CASE WHEN balance = 0 THEN 1 END) as zero_balance_count,
        COUNT(CASE WHEN balance > 0 THEN 1 END) as positive_balance_count,
        COUNT(CASE WHEN balance < 0 THEN 1 END) as negative_balance_count
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    GROUP BY 
        CASE 
            WHEN cancelled = true THEN 'Cancelled'
            WHEN closed = true THEN 'Closed'
            ELSE 'Open'
        END
    ORDER BY status
""")

print("\nCharter status breakdown:")
print(f"{'Status':<15} {'Count':<8} {'Total Rate':<15} {'Total Balance':<15} {'Zero Bal':<10} {'Pos Bal':<10} {'Neg Bal':<10}")
print("-" * 120)

total_charters = 0
total_unpaid = 0
total_unpaid_amount = 0

for status, count, rate, balance, zero_bal, pos_bal, neg_bal in cur.fetchall():
    rate_str = f"${rate:,.2f}" if rate else "$0.00"
    balance_str = f"${balance:,.2f}" if balance else "$0.00"
    print(f"{status:<15} {count:<8} {rate_str:<15} {balance_str:<15} {zero_bal:<10} {pos_bal:<10} {neg_bal:<10}")
    total_charters += count
    if status != 'Cancelled':
        total_unpaid += pos_bal
        total_unpaid_amount += (balance if balance and balance > 0 else 0)

print(f"\nTotal charters: {total_charters}")
print(f"Non-cancelled charters with balance > 0: {total_unpaid}")
print(f"Total unpaid balance: ${total_unpaid_amount:,.2f}")

# Get details of non-cancelled charters with outstanding balances
print("\n" + "=" * 120)
print("NON-CANCELLED CHARTERS WITH OUTSTANDING BALANCES")
print("=" * 120)

cur.execute("""
    SELECT 
        charter_id,
        reserve_number,
        charter_date,
        client_id,
        rate,
        balance,
        deposit,
        paid_amount,
        closed,
        status
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
        AND (cancelled IS NULL OR cancelled = false)
        AND balance > 0
    ORDER BY balance DESC
    LIMIT 50
""")

unpaid_charters = cur.fetchall()

if unpaid_charters:
    print(f"\nFound {len(unpaid_charters)} non-cancelled charters with outstanding balances (showing top 50):")
    print()
    print(f"{'Charter ID':<12} {'Reserve #':<12} {'Date':<12} {'Rate':<10} {'Paid':<10} {'Balance':<10} {'Status':<15}")
    print("-" * 120)
    
    for charter_id, reserve, date, client, rate, balance, deposit, paid, closed, status in unpaid_charters[:20]:
        rate_str = f"${rate:.2f}" if rate else "$0.00"
        paid_str = f"${paid:.2f}" if paid else "$0.00"
        balance_str = f"${balance:.2f}" if balance else "$0.00"
        closed_str = "Closed" if closed else "Open"
        status_str = status if status else "N/A"
        print(f"{charter_id:<12} {reserve or 'N/A':<12} {str(date):<12} {rate_str:<10} {paid_str:<10} {balance_str:<10} {closed_str:<15}")
    
    if len(unpaid_charters) > 20:
        remaining = sum(c[5] for c in unpaid_charters[20:])
        print(f"\n... and {len(unpaid_charters)-20} more charters with ${remaining:,.2f} outstanding")
else:
    print("\n✓ All non-cancelled charters have zero balance!")

# Check closed charters with balances
print("\n" + "=" * 120)
print("CLOSED CHARTERS WITH NON-ZERO BALANCES")
print("=" * 120)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END) as positive_total,
        SUM(CASE WHEN balance < 0 THEN balance ELSE 0 END) as negative_total
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
        AND closed = true
        AND (cancelled IS NULL OR cancelled = false)
        AND balance != 0
""")

closed_with_balance = cur.fetchone()
if closed_with_balance:
    count, pos_total, neg_total = closed_with_balance
    print(f"\nClosed charters with non-zero balance: {count}")
    print(f"  Positive balances (owed to us): ${pos_total or 0:,.2f}")
    print(f"  Negative balances (credits/overpayments): ${neg_total or 0:,.2f}")

# Check payment coverage per charter
print("\n" + "=" * 120)
print("PAYMENT COVERAGE ANALYSIS")
print("=" * 120)

cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.rate,
        c.balance,
        c.paid_amount,
        c.deposit,
        COALESCE(SUM(p.amount), 0) as total_payments,
        COUNT(p.payment_id) as payment_count
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
        AND (c.cancelled IS NULL OR c.cancelled = false)
        AND c.balance > 0
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.rate, c.balance, c.paid_amount, c.deposit
    ORDER BY c.balance DESC
    LIMIT 20
""")

print(f"\n{'Reserve #':<12} {'Date':<12} {'Rate':<10} {'Payments':<10} {'Paid Amt':<10} {'Balance':<10} {'Pay Count':<10}")
print("-" * 120)

for charter_id, reserve, date, rate, balance, paid_amt, deposit, total_pay, pay_count in cur.fetchall():
    reserve_str = reserve or "N/A"
    rate_str = f"${rate:.2f}" if rate else "$0.00"
    pay_str = f"${total_pay:.2f}"
    paid_str = f"${paid_amt:.2f}" if paid_amt else "$0.00"
    balance_str = f"${balance:.2f}" if balance else "$0.00"
    print(f"{reserve_str:<12} {str(date):<12} {rate_str:<10} {pay_str:<10} {paid_str:<10} {balance_str:<10} {pay_count:<10}")

print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)
print("""
Charter balance status indicates:
- Zero balance: Charter fully paid
- Positive balance: Amount still owed by customer
- Negative balance: Overpayment/credit on account
- Closed + balance > 0: Completed trip but not fully paid (collections needed)
- Open + balance > 0: Ongoing or future booking with partial payment
""")

cur.close()
conn.close()

print("\n" + "=" * 120)
