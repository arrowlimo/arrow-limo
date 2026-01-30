import psycopg2
from collections import defaultdict

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = c.cursor()

print("Checking for $774 payments that may have been imported multiple times...")
print("=" * 80)
print()

# Get all $774 Waste Connections payments with source indicators
cur.execute('''
    SELECT 
        p.payment_id,
        p.reserve_number,
        p.payment_date,
        p.payment_key,
        p.created_at::date as import_date,
        CASE 
            WHEN p.payment_key LIKE 'ETR:%' THEN 'Email E-Transfer'
            WHEN p.payment_key LIKE 'LMS%' THEN 'LMS Import'
            WHEN p.payment_key ~ '^[0-9]+$' THEN 'LMS Payment'
            WHEN p.payment_key IS NULL THEN 'Legacy/Unknown'
            ELSE 'Other: ' || LEFT(p.payment_key, 10)
        END as source_type
    FROM payments p
    JOIN charters ch ON ch.reserve_number = p.reserve_number
    WHERE ch.client_id = 2311
    AND ABS(p.amount - 774.00) < 0.01
    ORDER BY p.payment_date, p.reserve_number
''')

payments = cur.fetchall()

# Group by (payment_date, reserve_number) to find multiple payments same day/reserve
by_date_reserve = defaultdict(list)
for payment_id, reserve, payment_date, payment_key, import_date, source_type in payments:
    key = (payment_date, reserve)
    by_date_reserve[key].append({
        'payment_id': payment_id,
        'payment_key': payment_key,
        'import_date': import_date,
        'source_type': source_type,
    })

# Find potential duplicates
duplicates = []
for (payment_date, reserve), pmts in by_date_reserve.items():
    if len(pmts) > 1:
        # Check if from different sources
        sources = set(p['source_type'] for p in pmts)
        if len(sources) > 1:
            duplicates.append({
                'payment_date': payment_date,
                'reserve': reserve,
                'count': len(pmts),
                'payments': pmts,
                'sources': sources,
            })

if duplicates:
    print(f"Found {len(duplicates)} reserves with duplicate $774 payments from different sources:")
    print()
    
    total_excess = 0
    for dup in duplicates:
        print(f"Reserve {dup['reserve']} on {dup['payment_date']}:")
        print(f"  {dup['count']} payments from sources: {', '.join(dup['sources'])}")
        for p in dup['payments']:
            print(f"    ID={p['payment_id']:6d} key={p['payment_key'] or 'NULL':20s} "
                  f"source={p['source_type']:20s} imported={p['import_date']}")
        print(f"  Excess: ${774 * (dup['count'] - 1):.2f}")
        print()
        total_excess += 774 * (dup['count'] - 1)
    
    print(f"Total excess from duplicates: ${total_excess:,.2f}")
else:
    print("No duplicates found from different import sources on same date/reserve")
    print()
    
    # Check: Were credits created from reserves that actually have the charter?
    print("Checking if credits were created from reserves with actual charters...")
    print("=" * 80)
    print()
    
    cur.execute('''
        SELECT 
            cl.source_reserve_number,
            cl.credit_amount,
            ch.reserve_number as actual_reserve,
            ch.charter_date,
            ch.total_amount_due,
            COUNT(p.payment_id) as payment_count
        FROM charter_credit_ledger cl
        JOIN charters ch ON ch.charter_id = cl.source_charter_id
        LEFT JOIN payments p ON p.reserve_number = cl.source_reserve_number 
            AND ABS(p.amount - 774.00) < 0.01
        WHERE cl.client_id = 2311
        AND cl.credit_reason = 'UNIFORM_INSTALLMENT'
        GROUP BY cl.source_reserve_number, cl.credit_amount, ch.reserve_number, 
                 ch.charter_date, ch.total_amount_due
        ORDER BY cl.credit_amount DESC
        LIMIT 10
    ''')
    
    print("Top 10 credited reserves:")
    for source_res, credit_amt, actual_res, charter_date, total_due, pmt_count in cur.fetchall():
        print(f"  {source_res}: ${credit_amt:8.2f} credit, {pmt_count} payments of $774, "
              f"charter due=${total_due:.2f} on {charter_date}")
