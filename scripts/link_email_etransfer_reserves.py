#!/usr/bin/env python3
"""Link email E-Transfer reserve numbers to payments table"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("\n" + "="*80)
print("LINKING EMAIL E-TRANSFER RESERVE NUMBERS TO PAYMENTS")
print("="*80)

# Check email_financial_events for e-transfers with reserve numbers
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as with_reserve,
        COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as with_banking,
        MIN(event_date) as earliest,
        MAX(event_date) as latest,
        SUM(amount) as total_amount
    FROM email_financial_events
    WHERE source LIKE '%etransfer%'
""")

total, with_res, with_bank, earliest, latest, amt = cur.fetchone()
print(f"\n📧 Email E-Transfer Events:")
print(f"   Total: {total:,}")
print(f"   With reserve_number: {with_res:,} ({with_res/total*100:.1f}%)" if total else "   None")
print(f"   With banking_transaction_id: {with_bank:,}" if total else "   None")
print(f"   Date range: {earliest} to {latest}" if total else "")
print(f"   Total amount: ${amt:,.2f}" if total and amt else "")

# Match email events to payments via ETR: payment_key
cur.execute("""
    SELECT 
        p.payment_id,
        p.payment_key,
        p.amount,
        p.payment_date,
        p.reserve_number as payment_reserve,
        e.reserve_number as email_reserve,
        e.event_id
    FROM payments p
    LEFT JOIN email_financial_events e ON e.reference_code = SUBSTRING(p.payment_key FROM 5)
    WHERE p.payment_key LIKE 'ETR:%'
    AND p.reserve_number IS NULL
    LIMIT 20
""")

print(f"\n🔍 Sample ETR Payments Linkable to Email Events:")
print(f"{'Payment ID':<12} {'Key':<15} {'Amount':<12} {'Date':<12} {'Email Reserve':<15}")
print("-"*80)

matches = []
for payment_id, key, amt, date, p_res, e_res, event_id in cur.fetchall():
    print(f"{payment_id:<12} {key:<15} ${amt:<11,.2f} {str(date):<12} {e_res or 'NULL':<15}")
    if e_res:
        matches.append((payment_id, e_res))

print(f"\nFound {len(matches)} payments with email reserve numbers")

# Count total linkable
cur.execute("""
    SELECT COUNT(DISTINCT p.payment_id)
    FROM payments p
    INNER JOIN email_financial_events e ON e.reference_code = SUBSTRING(p.payment_key FROM 5)
    WHERE p.payment_key LIKE 'ETR:%'
    AND p.reserve_number IS NULL
    AND e.reserve_number IS NOT NULL
""")

linkable = cur.fetchone()[0]
print(f"\n📊 Total ETR payments linkable via email: {linkable:,}")

# Apply updates (dry-run first)
print(f"\n" + "="*80)
print("UPDATE PREVIEW")
print("="*80)

cur.execute("""
    UPDATE payments p
    SET reserve_number = e.reserve_number
    FROM email_financial_events e
    WHERE e.reference_code = SUBSTRING(p.payment_key FROM 5)
    AND p.payment_key LIKE 'ETR:%'
    AND p.reserve_number IS NULL
    AND e.reserve_number IS NOT NULL
""")

print(f"\n✅ Would update {cur.rowcount:,} payments with reserve_number from emails")

response = input("\nApply updates? (yes/no): ").strip().lower()

if response == 'yes':
    conn.commit()
    print(f"✅ Committed {cur.rowcount:,} reserve_number updates")
    
    # Verify
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve
        FROM payments
        WHERE payment_key LIKE 'ETR:%'
    """)
    total, no_res = cur.fetchone()
    print(f"\n📈 ETR Payment Status:")
    print(f"   Total: {total:,}")
    print(f"   Missing reserve: {no_res:,} ({no_res/total*100:.1f}%)")
else:
    conn.rollback()
    print("❌ Rolled back (no changes)")

cur.close()
conn.close()

print("\n" + "="*80)
