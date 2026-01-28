#!/usr/bin/env python3
"""
Audit balance mismatches and suggest fixes
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*80)
print("BALANCE MISMATCH AUDIT")
print("="*80)

# Find balance mismatches
cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.total_amount_due, 
           c.balance,
           COALESCE(SUM(p.amount), 0) as total_paid,
           c.total_amount_due - COALESCE(SUM(p.amount), 0) as calculated_balance,
           c.balance - (c.total_amount_due - COALESCE(SUM(p.amount), 0)) as difference
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.balance
    HAVING ABS((c.total_amount_due - COALESCE(SUM(p.amount), 0)) - c.balance) > 0.01
    ORDER BY ABS(c.balance - (c.total_amount_due - COALESCE(SUM(p.amount), 0))) DESC
""")

mismatches = cur.fetchall()
print(f"\nFound {len(mismatches)} balance mismatches:\n")

print("Charter# | Reserve# | Due        | Stored Bal | Paid       | Calc Bal   | Diff")
print("-" * 90)

for cid, reserve, due, stored_bal, paid, calc_bal, diff in mismatches:
    print(f"{cid:8d} | {str(reserve):8s} | {due:10.2f} | {stored_bal:10.2f} | {paid:10.2f} | {calc_bal:10.2f} | {diff:7.2f}")

print("\n" + "="*80)
print("ANALYSIS")
print("="*80)

for cid, reserve, due, stored_bal, paid, calc_bal, diff in mismatches:
    print(f"\nCharter {cid} (Reserve {reserve}):")
    print(f"  Due:              ${due:,.2f}")
    print(f"  Paid:             ${paid:,.2f}")
    print(f"  Expected Balance: ${calc_bal:,.2f}")
    print(f"  Stored Balance:   ${stored_bal:,.2f}")
    print(f"  Difference:       ${diff:,.2f}")
    
    # Check for missing payments
    cur.execute("""
        SELECT COUNT(*) FROM payments 
        WHERE reserve_number = %s
    """, (reserve,))
    payment_count = cur.fetchone()[0]
    print(f"  Payments linked:  {payment_count}")
    
    # Suggest fix
    if diff > 0:
        print(f"  Issue: Balance is OVERSTATED by ${abs(diff):.2f}")
        print(f"  Fix: Either delete a payment of ${abs(diff):.2f} or decrease balance by ${abs(diff):.2f}")
    else:
        print(f"  Issue: Balance is UNDERSTATED by ${abs(diff):.2f}")
        print(f"  Fix: Either add a payment of ${abs(diff):.2f} or increase balance by ${abs(diff):.2f}")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("""
Options to fix balance mismatches:

1. MANUAL REVIEW (Safest)
   - Review each charter individually
   - Check payment records in source system
   - Determine if balance or payment data is incorrect
   - Apply corrections manually

2. AUTO-FIX (Faster, assumes calculation is correct)
   - Update charter.balance to match calculated value
   - Only if you're confident all payments are correct

3. AUDIT TRAIL (Most thorough)
   - Pull charter details from original system
   - Verify each payment
   - Document why each mismatch occurred

Next Step: Manual audit of these 5 charters to determine root cause
Risk Level: Medium (could hide data quality issues)
Effort: Low-Medium (only 5 charters)
Automation: Possible but manual review recommended first
""")

cur.close()
conn.close()
