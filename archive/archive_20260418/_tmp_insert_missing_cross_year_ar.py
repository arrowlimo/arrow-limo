"""
Insert missing A/R GL entries for cross-year charter payments
These are 2012-chartered charters with payments outside 2012
Total amount: $23,565.86
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost', port=5432, database='almsdata',
    user='postgres', password='ArrowLimousine'
)
cursor = conn.cursor()

print("=" * 80)
print("INSERT MISSING CROSS-YEAR A/R GL ENTRIES")
print("=" * 80)
print()

# Get all cross-year payment dates and amounts for 2012 charters
cursor.execute("""
SELECT 
  cp.payment_date,
  ROUND(SUM(cp.amount)::numeric, 2) AS daily_amount
FROM charter_payments cp
JOIN charters c ON c.reserve_number = cp.charter_id
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
  AND EXTRACT(YEAR FROM cp.payment_date) <> 2012
GROUP BY cp.payment_date
ORDER BY cp.payment_date
""")

entries_to_insert = []
total_amount = 0
for payment_date, daily_amount in cursor.fetchall():
    if daily_amount:
        daily_amount = float(daily_amount)
        total_amount += daily_amount
        entries_to_insert.append({
            'date': payment_date,
            'account_name': 'Accounts Receivable',
            'memo': 'Cross-year charter payment',
            'debit': 0,
            'credit': daily_amount,
            'source': 'charter_payments_cross_year'
        })

print(f"Found {len(entries_to_insert)} daily entries to insert")
print(f"Total A/R Credits: ${total_amount:,.2f}")
print()

# Insert into general_ledger
if entries_to_insert:
    inserted = 0
    for entry in entries_to_insert:
        cursor.execute("""
        INSERT INTO general_ledger (
          date, account, debit, credit,
          account_name, memo_description,
          source_file, imported_at,
          transaction_date
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            entry['date'],
            entry['account_name'],
            entry['debit'],
            entry['credit'],
            entry['account_name'],
            entry['memo'],
            'cross_year_ar',
            datetime.now(),
            entry['date']
        ))
        inserted += 1

    conn.commit()
    print(f"✓ Inserted {inserted} cross-year A/R GL entries")
    print()
    
    # Verify GL balance after insert
    cursor.execute("""
    SELECT 
      SUM(COALESCE(debit, 0))::numeric AS total_debit,
      SUM(COALESCE(credit, 0))::numeric AS total_credit
    FROM general_ledger
    WHERE EXTRACT(YEAR FROM date) = 2012
    """)
    
    total_debit, total_credit = cursor.fetchone()
    imbalance = total_debit - total_credit
    
    print("AFTER INSERT:")
    print(f"  Total Debit:  ${total_debit:,.2f}")
    print(f"  Total Credit: ${total_credit:,.2f}")
    print(f"  Imbalance:    ${imbalance:,.2f}")
    
    if abs(imbalance) < 0.01:
        print("  ✓ GL is BALANCED!")
    else:
        print(f"  ⚠ GL imbalance remains: ${imbalance:,.2f}")
    print()

cursor.close()
conn.close()

print("=" * 80)
print("DONE")
print("=" * 80)
