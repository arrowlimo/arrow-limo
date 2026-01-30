import psycopg2
from collections import defaultdict

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = c.cursor()

# Get all $774 payments for Waste Connections
cur.execute('''
    SELECT 
        p.payment_id,
        p.reserve_number,
        p.amount,
        p.payment_date,
        p.payment_key,
        p.created_at,
        ch.charter_id,
        ch.charter_date
    FROM payments p
    JOIN charters ch ON ch.reserve_number = p.reserve_number
    WHERE ch.client_id = 2311
    AND ABS(p.amount - 774.00) < 0.01
    ORDER BY p.payment_date, p.payment_id
''')

payments = cur.fetchall()
print(f"Total $774 payments: {len(payments)}")
print()

# Check for exact duplicates by (date, amount, reserve)
duplicates_by_signature = defaultdict(list)
for payment_id, reserve, amount, payment_date, payment_key, created_at, charter_id, charter_date in payments:
    sig = (payment_date, float(amount), reserve)
    duplicates_by_signature[sig].append({
        'payment_id': payment_id,
        'reserve': reserve,
        'amount': float(amount),
        'payment_date': payment_date,
        'payment_key': payment_key,
        'created_at': created_at,
        'charter_id': charter_id,
        'charter_date': charter_date,
    })

# Find duplicates
print("Duplicate Payments (same date, amount, reserve):")
print("=" * 80)
dup_count = 0
for sig, pmts in duplicates_by_signature.items():
    if len(pmts) > 1:
        dup_count += len(pmts) - 1  # Count extras
        print(f"\n{len(pmts)} payments on {sig[0]} for reserve {sig[2]} (${sig[1]:.2f}):")
        for p in pmts:
            print(f"  payment_id={p['payment_id']:6d} key={p['payment_key'] or 'NULL':20s} "
                  f"created={p['created_at']} charter_date={p['charter_date']}")

if dup_count == 0:
    print("No exact duplicates found (same date + amount + reserve)")
    print()
    
    # Check for payment key duplicates
    print("\nChecking for duplicate payment_key values:")
    print("=" * 80)
    key_map = defaultdict(list)
    for payment_id, reserve, amount, payment_date, payment_key, created_at, charter_id, charter_date in payments:
        if payment_key:
            key_map[payment_key].append({
                'payment_id': payment_id,
                'reserve': reserve,
                'payment_date': payment_date,
                'charter_date': charter_date,
            })
    
    key_dup_count = 0
    for key, pmts in key_map.items():
        if len(pmts) > 1:
            key_dup_count += len(pmts) - 1
            print(f"\nKey '{key}' used {len(pmts)} times:")
            for p in pmts:
                print(f"  payment_id={p['payment_id']:6d} reserve={p['reserve']} "
                      f"payment_date={p['payment_date']} charter_date={p['charter_date']}")
    
    if key_dup_count == 0:
        print("No duplicate payment keys found")
        print()
        
        # Show which reserves had multiple $774 payments
        print("\nReserves with Multiple $774 Payments:")
        print("=" * 80)
        reserve_map = defaultdict(list)
        for payment_id, reserve, amount, payment_date, payment_key, created_at, charter_id, charter_date in payments:
            reserve_map[reserve].append(payment_date)
        
        multi_payment_reserves = [(r, dates) for r, dates in reserve_map.items() if len(dates) > 1]
        multi_payment_reserves.sort(key=lambda x: len(x[1]), reverse=True)
        
        print(f"\nFound {len(multi_payment_reserves)} reserves with >1 payment:")
        for reserve, dates in multi_payment_reserves[:20]:
            print(f"  {reserve}: {len(dates)} payments from {min(dates)} to {max(dates)}")
        
        total_multi = sum(len(dates) for r, dates in multi_payment_reserves)
        print(f"\nTotal payments on multi-payment reserves: {total_multi}")
        print(f"These {total_multi} payments spread across {len(multi_payment_reserves)} reserves")
        print()
        print("This is the 'uniform installment' pattern - multiple payments pooled on")
        print("single reserves instead of distributed to individual charter dates.")
else:
    print(f"\nTotal duplicate payments found: {dup_count}")
    print(f"These appear to be true duplicates that should be removed")
