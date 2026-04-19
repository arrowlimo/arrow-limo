"""
Comprehensive Charter Reconciliation Report: 2012-2014
- Itemized charges (billing) with dates
- Itemized payments with dates and type
- Cancelled charters have $0 billing
- Grouped by cancelled status, then by balance owing
"""
from decimal import Decimal
import psycopg2
import csv
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

def q2(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))

# Get all charters for 2012-2014
print("=" * 100)
print("CHARTER RECONCILIATION REPORT: 2012-2014")
print("=" * 100)
print("\nGathering charter data...")

cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.charter_date, c.status, c.cancelled
    FROM charters c
    WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013, 2014)
    ORDER BY c.reserve_number
""")

charters = cur.fetchall()
print(f"Found {len(charters):,} charters\n")

# Build detailed data structure
data = {}
for cid, reserve, charter_date, status, cancelled in charters:
    # Get charges (billing)
    cur.execute("""
        SELECT amount, created_at, description, charge_type
        FROM charter_charges
        WHERE charter_id = %s
        ORDER BY created_at
    """, (cid,))
    charges = cur.fetchall()
    
    # Get payments
    cur.execute("""
        SELECT cp.amount, cp.payment_date, cp.payment_method, cp.source
        FROM charter_payments cp
        WHERE cp.charter_id = %s::VARCHAR
        ORDER BY cp.payment_date
    """, (reserve,))
    payments = cur.fetchall()
    
    # Calculate totals
    total_charged = sum(q2(c[0]) for c in charges) if charges else Decimal('0.00')
    total_paid = sum(q2(p[0]) for p in payments) if payments else Decimal('0.00')
    
    # For cancelled charters, billing = $0
    if cancelled:
        total_charged = Decimal('0.00')
        charges = []
    
    balance = total_charged - total_paid
    
    data[reserve] = {
        'charter_id': cid,
        'charter_date': charter_date,
        'status': status,
        'cancelled': cancelled,
        'charges': charges,
        'total_charged': total_charged,
        'payments': payments,
        'total_paid': total_paid,
        'balance': balance
    }

# Group by cancelled status first
cancelled_reserves = {k: v for k, v in data.items() if v['cancelled']}
active_reserves = {k: v for k, v in data.items() if not v['cancelled']}

# Sort each group by balance (owing first, then credit)
cancelled_sorted = sorted(cancelled_reserves.items(), key=lambda x: x[1]['balance'], reverse=True)
active_sorted = sorted(active_reserves.items(), key=lambda x: x[1]['balance'], reverse=True)

print("\nGenerating detailed report...\n")

# Prepare CSV data
csv_rows = []

# SECTION 1: CANCELLED CHARTERS
print("=" * 100)
print("SECTION 1: CANCELLED CHARTERS")
print("=" * 100)

for reserve, record in cancelled_sorted:
    print(f"\nReserve: {reserve} | Charter ID: {record['charter_id']} | Date: {record['charter_date']}")
    print(f"Status: CANCELLED | Unpaid Balance: ${record['balance']:.2f}")
    print("-" * 100)
    
    # Charges (should be empty for cancelled)
    if record['charges']:
        print("BILLING:")
        total_billed = Decimal('0.00')
        for amt, date, desc, ctype in record['charges']:
            amt = q2(amt)
            total_billed += amt
            print(f"  {date} | ${amt:>10} | {ctype:20} | {desc}")
        print(f"  {'TOTAL BILLED':<50} ${total_billed:>10}")
    else:
        print("BILLING: None (Cancelled)")
    
    # Payments
    if record['payments']:
        print("\nPAYMENTS:")
        total_paid = Decimal('0.00')
        for amt, date, method, source in record['payments']:
            amt = q2(amt)
            total_paid += amt
            print(f"  {date} | ${amt:>10} | {method:20} | {source}")
        print(f"  {'TOTAL PAID':<50} ${total_paid:>10}")
    else:
        print("\nPAYMENTS: None")
    
    print(f"  {'BALANCE':<50} ${record['balance']:>10}")
    
    # CSV row
    charges_str = "; ".join([f"{date}: ${q2(amt)}" for amt, date, _, _ in record['charges']])
    payments_str = "; ".join([f"{date}: ${q2(amt)} ({method})" for amt, date, method, _ in record['payments']])
    csv_rows.append([
        reserve,
        record['charter_id'],
        record['charter_date'],
        'CANCELLED',
        record['total_charged'],
        charges_str,
        record['total_paid'],
        payments_str,
        record['balance']
    ])

# SECTION 2: ACTIVE CHARTERS (sorted by balance in descending order)
print("\n\n" + "=" * 100)
print("SECTION 2: ACTIVE CHARTERS (sorted by balance owing)")
print("=" * 100)

# Group active charters by balance for summary
balance_groups = defaultdict(list)
for reserve, record in active_sorted:
    balance_groups[record['balance']].append((reserve, record))

# Print by balance group
for balance in sorted(balance_groups.keys(), reverse=True):
    group = balance_groups[balance]
    print(f"\n--- BALANCE OWING: ${balance:.2f} ({len(group)} charters) ---\n")
    
    for reserve, record in group:
        print(f"Reserve: {reserve} | Charter ID: {record['charter_id']} | Date: {record['charter_date']}")
        print(f"Status: {record['status'] or 'ACTIVE'} | Unpaid Balance: ${record['balance']:.2f}")
        print("-" * 100)
        
        # Charges
        if record['charges']:
            print("BILLING:")
            total_billed = Decimal('0.00')
            for amt, date, desc, ctype in record['charges']:
                amt = q2(amt)
                total_billed += amt
                print(f"  {date} | ${amt:>10} | {ctype:20} | {desc}")
            print(f"  {'TOTAL BILLED':<50} ${total_billed:>10}")
        else:
            print("BILLING: None")
        
        # Payments
        if record['payments']:
            print("\nPAYMENTS:")
            total_paid = Decimal('0.00')
            for amt, date, method, source in record['payments']:
                amt = q2(amt)
                total_paid += amt
                print(f"  {date} | ${amt:>10} | {method:20} | {source}")
            print(f"  {'TOTAL PAID':<50} ${total_paid:>10}")
        else:
            print("\nPAYMENTS: None")
        
        print(f"  {'BALANCE':<50} ${record['balance']:>10}\n")
        
        # CSV row
        charges_str = "; ".join([f"{date}: ${q2(amt)}" for amt, date, _, _ in record['charges']])
        payments_str = "; ".join([f"{date}: ${q2(amt)} ({method})" for amt, date, method, _ in record['payments']])
        csv_rows.append([
            reserve,
            record['charter_id'],
            record['charter_date'],
            record['status'] or 'ACTIVE',
            record['total_charged'],
            charges_str,
            record['total_paid'],
            payments_str,
            record['balance']
        ])

# SUMMARY
print("\n" + "=" * 100)
print("SUMMARY STATISTICS: 2012-2014")
print("=" * 100)

total_charters = len(data)
total_cancelled = len(cancelled_reserves)
total_active = len(active_reserves)
total_billed = sum(q2(v['total_charged']) for v in data.values())
total_paid = sum(q2(v['total_paid']) for v in data.values())
total_balance = total_billed - total_paid
unpaid_count = sum(1 for v in data.values() if v['balance'] > 0)
overpaid_count = sum(1 for v in data.values() if v['balance'] < 0)

print(f"\n  Total Charters:              {total_charters:>10,}")
print(f"  Cancelled:                   {total_cancelled:>10,}")
print(f"  Active:                      {total_active:>10,}")
print(f"\n  Total Billed:                ${total_billed:>18}")
print(f"  Total Paid:                  ${total_paid:>18}")
print(f"  Net Balance (Unpaid):        ${total_balance:>18}")
print(f"\n  Charters with balance owing: {unpaid_count:>10,}")
print(f"  Charters with overpayment:   {overpaid_count:>10,}")

# Export to CSV
print(f"\n\nExporting detailed CSV report...")
with open(r'l:\limo\charter_reconciliation_2012_2014.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Reserve Number', 'Charter ID', 'Charter Date', 'Status', 
        'Total Billed', 'Charges (itemized)', 
        'Total Paid', 'Payments (itemized)', 
        'Balance Owing'
    ])
    writer.writerows(csv_rows)

print(f"OK: Exported to: charter_reconciliation_2012_2014.csv")

cur.close()
conn.close()
