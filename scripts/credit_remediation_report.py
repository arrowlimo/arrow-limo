import psycopg2
import csv

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()

print("=" * 70)
print("CREDIT LEDGER REMEDIATION - COMPLETION REPORT")
print("=" * 70)
print()

# Credits created
cur.execute('''
    SELECT 
        credit_reason,
        COUNT(*) as count,
        SUM(credit_amount) as total,
        AVG(credit_amount) as avg
    FROM charter_credit_ledger
    GROUP BY credit_reason
    ORDER BY total DESC
''')
print("CREDITS CREATED:")
print("-" * 70)
total_credits = 0
total_amount = 0
for reason, count, total, avg in cur.fetchall():
    print(f"  {reason:30s} {count:4d} credits  ${total:12,.2f}  (avg ${avg:,.2f})")
    total_credits += count
    total_amount += total
print("-" * 70)
print(f"  {'TOTAL':30s} {total_credits:4d} credits  ${total_amount:12,.2f}")
print()

# Before/After comparison
print("CHARTER BALANCE CORRECTIONS:")
print("-" * 70)
cur.execute('''
    SELECT COUNT(*), SUM(total_amount_due), SUM(paid_amount), SUM(balance)
    FROM charters_backup_credit_ledger_20251123_000216
    WHERE paid_amount > total_amount_due
''')
before = cur.fetchone()
cur.execute('''
    SELECT COUNT(*), SUM(total_amount_due), SUM(paid_amount), SUM(balance)
    FROM charters
    WHERE reserve_number IN (
        SELECT source_reserve_number FROM charter_credit_ledger
    )
''')
after = cur.fetchone()
print(f"  Before: {before[0]:4d} overpaid, Due=${before[1]:12,.2f}, Paid=${before[2]:12,.2f}, Balance=${before[3]:12,.2f}")
print(f"  After:  {after[0]:4d} overpaid, Due=${after[1]:12,.2f}, Paid=${after[2]:12,.2f}, Balance=${after[3]:12,.2f}")
print(f"  Corrected: {before[0]-after[0]:4d} charters, ${before[2]-after[2]:12,.2f} moved to credits")
print()

# Remaining work
cur.execute('SELECT COUNT(*) FROM charters WHERE paid_amount > total_amount_due')
remaining = cur.fetchone()[0]
print("REMAINING OVERPAID CHARTERS:")
print("-" * 70)
rows = list(csv.DictReader(open('l:/limo/reports/credit_ledger_proposal.csv')))
actions = {}
for r in rows:
    if r['proposed_action'] != 'CREDIT_LEDGER':
        action = r['proposed_action']
        actions[action] = actions.get(action, 0) + 1
for action, count in sorted(actions.items()):
    print(f"  {action:40s} {count:4d} charters")
print("-" * 70)
print(f"  {'TOTAL':40s} {remaining:4d} charters")
print()

print("NEXT STEPS:")
print("-" * 70)
print("  1. VERIFY_DEPOSIT_NONREFUNDABLE (90 charters):")
print("     - Review cancelled charters with overpayments")
print("     - Confirm nonrefundable deposit policy with clients")
print("     - Convert to credits or issue refunds per contract")
print()
print("  2. REALLOCATE_MULTI_CHARTER (63 charters):")
print("     - Large ETR payments likely for multiple charters")
print("     - Identify target charters for same client")
print("     - Create payment allocation splits")
print()
print("  Script: propose_multi_charter_allocations.py (to be created)")
print()
