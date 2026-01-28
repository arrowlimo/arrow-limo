"""
Check income_ledger foreign key constraint blocking payment deletion.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 100)
print("INCOME_LEDGER FOREIGN KEY CONSTRAINT CHECK")
print("=" * 100)

# Check income_ledger table structure
print("\n1. income_ledger Table Structure")
print("-" * 100)

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'income_ledger'
    ORDER BY ordinal_position
""")

columns = cur.fetchall()
for col, dtype in columns:
    print(f"  - {col:<30} ({dtype})")

# Check how many records in income_ledger
print("\n2. income_ledger Record Count")
print("-" * 100)

cur.execute("SELECT COUNT(*) FROM income_ledger")
total = cur.fetchone()[0]
print(f"Total income_ledger records: {total:,}")

# Check if any of our 2012 duplicates are referenced
print("\n3. 2012 Duplicate Payments Referenced in income_ledger")
print("-" * 100)

cur.execute("""
    WITH duplicates AS (
        SELECT 
            payment_id,
            payment_date,
            amount,
            ROW_NUMBER() OVER (
                PARTITION BY payment_date, amount, COALESCE(account_number, '')
                ORDER BY payment_id
            ) as row_num
        FROM payments
        WHERE charter_id IS NULL
        AND EXTRACT(YEAR FROM payment_date) = 2012
        AND amount > 0
    )
    SELECT 
        d.payment_id,
        d.payment_date,
        d.amount,
        COUNT(il.income_id) as ledger_entries
    FROM duplicates d
    LEFT JOIN income_ledger il ON il.payment_id = d.payment_id
    WHERE d.row_num > 1
    GROUP BY d.payment_id, d.payment_date, d.amount
    HAVING COUNT(il.income_id) > 0
    ORDER BY d.amount DESC
""")

referenced = cur.fetchall()
print(f"\nFound {len(referenced)} duplicate payments referenced in income_ledger")

if referenced:
    print(f"\n{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Ledger Entries':<15}")
    print("-" * 51)
    for pid, date, amount, entries in referenced[:20]:
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        amount_str = f"${float(amount):,.2f}" if amount else "$0.00"
        print(f"{pid:<12} {date_str:<12} {amount_str:<12} {entries:<15}")
    
    if len(referenced) > 20:
        print(f"... and {len(referenced) - 20} more")

# Check the paired payment (one we're keeping) - does it have ledger entries?
print("\n4. Do the KEPT payments have income_ledger entries?")
print("-" * 100)

cur.execute("""
    WITH duplicates AS (
        SELECT 
            payment_id,
            payment_date,
            amount,
            account_number,
            ROW_NUMBER() OVER (
                PARTITION BY payment_date, amount, COALESCE(account_number, '')
                ORDER BY payment_id
            ) as row_num
        FROM payments
        WHERE charter_id IS NULL
        AND EXTRACT(YEAR FROM payment_date) = 2012
        AND amount > 0
    ),
    pairs AS (
        SELECT 
            payment_date,
            amount,
            account_number,
            MIN(CASE WHEN row_num = 1 THEN payment_id END) as keep_id,
            MAX(CASE WHEN row_num > 1 THEN payment_id END) as delete_id
        FROM duplicates
        GROUP BY payment_date, amount, account_number
        HAVING COUNT(*) > 1
    )
    SELECT 
        p.payment_date,
        p.amount,
        p.keep_id,
        p.delete_id,
        COUNT(DISTINCT il_keep.income_id) as keep_ledger_count,
        COUNT(DISTINCT il_delete.income_id) as delete_ledger_count
    FROM pairs p
    LEFT JOIN income_ledger il_keep ON il_keep.payment_id = p.keep_id
    LEFT JOIN income_ledger il_delete ON il_delete.payment_id = p.delete_id
    GROUP BY p.payment_date, p.amount, p.keep_id, p.delete_id
    HAVING COUNT(DISTINCT il_delete.income_id) > 0
    ORDER BY p.amount DESC
    LIMIT 10
""")

pairs = cur.fetchall()
if pairs:
    print(f"\n{'Date':<12} {'Amount':<12} {'Keep ID':<12} {'Delete ID':<12} {'Keep Entries':<13} {'Delete Entries':<15}")
    print("-" * 86)
    for date, amount, keep_id, delete_id, keep_count, delete_count in pairs:
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        amount_str = f"${float(amount):,.2f}" if amount else "$0.00"
        print(f"{date_str:<12} {amount_str:<12} {keep_id:<12} {delete_id:<12} {keep_count:<13} {delete_count:<15}")
else:
    print("No pairs with ledger entries found in top 10")

# Strategy recommendation
print("\n" + "=" * 100)
print("RECOMMENDED STRATEGY")
print("=" * 100)

print("""
Option 1: Update income_ledger to point to kept payment_id (if kept payment has no entries)
  - For each delete pair: UPDATE income_ledger SET payment_id = keep_id WHERE payment_id = delete_id
  - Then delete the duplicate payment

Option 2: Delete income_ledger entries first (if they're duplicates too)
  - DELETE FROM income_ledger WHERE payment_id IN (duplicate_payment_ids)
  - Then delete the duplicate payments

Option 3: Skip payments with ledger entries
  - Only delete duplicates that have NO income_ledger references
  - Keep the ones with ledger entries for manual review

Checking which option applies...
""")

# Check if income_ledger entries are also duplicates
cur.execute("""
    WITH duplicates AS (
        SELECT 
            payment_id,
            payment_date,
            amount,
            account_number,
            ROW_NUMBER() OVER (
                PARTITION BY payment_date, amount, COALESCE(account_number, '')
                ORDER BY payment_id
            ) as row_num
        FROM payments
        WHERE charter_id IS NULL
        AND EXTRACT(YEAR FROM payment_date) = 2012
        AND amount > 0
    ),
    pairs AS (
        SELECT 
            payment_date,
            amount,
            account_number,
            MIN(CASE WHEN row_num = 1 THEN payment_id END) as keep_id,
            MAX(CASE WHEN row_num > 1 THEN payment_id END) as delete_id
        FROM duplicates
        GROUP BY payment_date, amount, account_number
        HAVING COUNT(*) > 1
    )
    SELECT 
        COUNT(DISTINCT p.payment_date || '|' || p.amount::text) as unique_pairs,
        COUNT(*) as total_delete_payments,
        SUM(CASE WHEN il.income_id IS NOT NULL THEN 1 ELSE 0 END) as with_ledger_entries,
        SUM(CASE WHEN il.income_id IS NULL THEN 1 ELSE 0 END) as without_ledger_entries
    FROM pairs p
    LEFT JOIN income_ledger il ON il.payment_id = p.delete_id
""")

strategy = cur.fetchone()
print(f"\nUnique payment pairs: {strategy[0]:,}")
print(f"Total payments to delete: {strategy[1]:,}")
print(f"  With income_ledger entries: {strategy[2]:,}")
print(f"  Without income_ledger entries: {strategy[3]:,}")

if strategy[2] > 0:
    print(f"\n✓ BEST APPROACH: Update {strategy[2]} income_ledger entries to point to kept payment_id")
    print(f"  Then delete all {strategy[1]} duplicate payments")
else:
    print(f"\n✓ BEST APPROACH: Delete all {strategy[1]} duplicate payments (no ledger conflicts)")

cur.close()
conn.close()
