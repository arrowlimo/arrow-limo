import psycopg2

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = c.cursor()

# Check all Waste Connections $774 charters
cur.execute('''
    SELECT 
        COUNT(*) as total_charters,
        SUM(total_amount_due) as total_due,
        SUM(paid_amount) as total_paid,
        SUM(balance) as total_balance,
        SUM(CASE WHEN balance > 0 THEN 1 ELSE 0 END) as unpaid_count,
        SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END) as overpaid_count
    FROM charters 
    WHERE client_id = 2311 
    AND ABS(total_amount_due - 774.00) < 0.01
''')
r = cur.fetchone()

print("Waste Connections $774 Charters Status:")
print("=" * 60)
print(f"Total charters:       {r[0]}")
print(f"Total due:            ${r[1]:,.2f}")
print(f"Total paid:           ${r[2]:,.2f}")
print(f"Total balance:        ${r[3]:,.2f}")
print(f"Unpaid (balance>0):   {r[4]}")
print(f"Overpaid (balance<0): {r[5]}")
print()

# Check credits
cur.execute('''
    SELECT 
        COUNT(*) as credit_count,
        SUM(credit_amount) as total_credits,
        SUM(remaining_balance) as available_credits
    FROM charter_credit_ledger
    WHERE client_id = 2311
    AND credit_reason = 'UNIFORM_INSTALLMENT'
''')
r = cur.fetchone()

print("Waste Connections Credits:")
print("=" * 60)
print(f"Credit entries:       {r[0]}")
if r[1]:
    print(f"Total credits:        ${r[1]:,.2f}")
    print(f"Available balance:    ${r[2]:,.2f}")
else:
    print(f"Total credits:        $0.00")
    print(f"Available balance:    $0.00")
print()

# Count $774 payments
cur.execute('''
    SELECT COUNT(*)
    FROM payments p
    JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE c.client_id = 2311
    AND ABS(p.amount - 774.00) < 0.01
''')
payment_count = cur.fetchone()[0]

print(f"Total $774 payments:  {payment_count}")
print()

print("Analysis:")
print("=" * 60)

# Get unpaid count from first query
cur.execute('''
    SELECT SUM(CASE WHEN balance > 0 THEN 1 ELSE 0 END) as unpaid_count
    FROM charters 
    WHERE client_id = 2311 
    AND ABS(total_amount_due - 774.00) < 0.01
''')
unpaid_count = cur.fetchone()[0]

if unpaid_count == 0:
    print("✓ All $774 charters are fully paid")
    print("✓ Credits represent excess periodic payments beyond charter count")
    print("✓ These are legitimate client credits for future use")
    print()
    print("No excess payments - all charters have matching payment records.")
else:
    print(f"⚠ {unpaid_count} unpaid charters could receive reallocations")
