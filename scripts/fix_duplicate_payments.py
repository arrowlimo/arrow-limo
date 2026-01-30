"""
Investigate and fix suspicious duplicate payments
Same reserve, same amount, dates within 3 days - may be legitimate or duplicates
"""
import psycopg2
from datetime import datetime

pg_conn = psycopg2.connect(
    host='localhost', database='almsdata',
    user='postgres', password='***REDACTED***'
)
pg_cur = pg_conn.cursor()

print("=" * 120)
print("SUSPICIOUS DUPLICATE PAYMENTS ANALYSIS")
print("=" * 120)
print()

# Find suspicious pairs
pg_cur.execute("""
    SELECT 
        p1.payment_id as id1, 
        p2.payment_id as id2,
        p1.reserve_number, 
        p1.amount, 
        p1.payment_date as date1, 
        p2.payment_date as date2,
        p1.payment_key as key1,
        p2.payment_key as key2,
        p1.payment_method as method1,
        p2.payment_method as method2,
        p1.created_at as created1,
        p2.created_at as created2
    FROM payments p1
    JOIN payments p2 ON p1.reserve_number = p2.reserve_number
                     AND p1.amount = p2.amount
                     AND p1.payment_id < p2.payment_id
                     AND ABS(DATE_PART('day', p2.payment_date::timestamp - p1.payment_date::timestamp)) <= 3
    WHERE p1.reserve_number IS NOT NULL 
      AND p1.amount IS NOT NULL
      AND p1.amount > 0
    ORDER BY p1.amount DESC, p1.reserve_number
""")
suspicious_pairs = pg_cur.fetchall()

print(f"Found {len(suspicious_pairs)} suspicious payment pairs")
print()

# Analyze each pair
definite_duplicates = []
likely_legitimate = []

for pair in suspicious_pairs:
    id1, id2, reserve, amount, date1, date2, key1, key2, method1, method2, created1, created2 = pair
    
    # Criteria for duplicate:
    # 1. Same payment_key = definitely duplicate
    # 2. Same payment date = likely duplicate
    # 3. Created at exact same time = import duplicate
    # 4. Different keys, different dates within 3 days = likely legitimate (deposit + final)
    
    is_duplicate = False
    reason = ""
    
    if key1 == key2 and key1 is not None:
        is_duplicate = True
        reason = "Same payment_key"
    elif date1 == date2:
        is_duplicate = True
        reason = "Same payment_date"
    elif created1 and created2 and abs((created2 - created1).total_seconds()) < 10:
        is_duplicate = True
        reason = "Created within 10 seconds (import duplicate)"
    elif key1 and key2 and key1.startswith('LMS:') and key2.startswith('LMS:'):
        # Both from LMS but different keys - check if same LMS ID
        lms_id1 = key1.split(':')[1] if ':' in key1 else None
        lms_id2 = key2.split(':')[1] if ':' in key2 else None
        if lms_id1 == lms_id2:
            is_duplicate = True
            reason = "Same LMS payment ID"
    
    if is_duplicate:
        definite_duplicates.append((pair, reason))
    else:
        likely_legitimate.append(pair)

print(f"Analysis results:")
print(f"  Definite duplicates (to delete): {len(definite_duplicates)}")
print(f"  Likely legitimate (keep both): {len(likely_legitimate)}")
print()

if definite_duplicates:
    print("=" * 120)
    print("DEFINITE DUPLICATES TO DELETE (keeping older payment)")
    print("=" * 120)
    print()
    print(f"{'Reserve':<12} {'Amount':<12} {'ID1 (Keep)':<12} {'ID2 (Delete)':<12} {'Date1':<12} {'Date2':<12} {'Reason':<30}")
    print("-" * 120)
    
    for pair, reason in definite_duplicates[:20]:
        id1, id2, reserve, amount, date1, date2 = pair[:6]
        print(f"{reserve:<12} ${amount:>10,.2f} {id1:<12} {id2:<12} {str(date1):<12} {str(date2):<12} {reason:<30}")
    
    if len(definite_duplicates) > 20:
        print(f"... and {len(definite_duplicates) - 20} more")
    
    print()
    print("=" * 120)
    print("DRY RUN - No changes made")
    print("Run with --apply to delete duplicate payments (newer payment of each pair)")
    print("=" * 120)
    
    import sys
    if '--apply' in sys.argv:
        print()
        print("APPLYING DUPLICATE DELETION...")
        print()
        
        # Create backup
        backup_table = f"payments_duplicate_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ids_to_delete = [pair[0][1] for pair in definite_duplicates]  # id2 from each pair
        
        pg_cur.execute(f"""
            CREATE TABLE {backup_table} AS 
            SELECT * FROM payments 
            WHERE payment_id = ANY(%s)
        """, (ids_to_delete,))
        
        pg_cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
        backup_count = pg_cur.fetchone()[0]
        print(f"✓ Backup created: {backup_table} ({backup_count} payments)")
        
        # Delete from all foreign key tables first
        fk_tables = [
            'multi_charter_payments',
            'payment_customer_links', 
            'income_ledger',
            'banking_payment_links',
            'payment_reconciliation_ledger'
        ]
        
        total_fk_deleted = 0
        for table in fk_tables:
            pg_cur.execute(f"""
                DELETE FROM {table}
                WHERE payment_id = ANY(%s)
            """, (ids_to_delete,))
            fk_deleted = pg_cur.rowcount
            if fk_deleted > 0:
                print(f"✓ Deleted {fk_deleted} entries from {table}")
                total_fk_deleted += fk_deleted
        
        if total_fk_deleted > 0:
            print(f"Total foreign key entries deleted: {total_fk_deleted}")
        
        # Delete duplicates
        pg_cur.execute("""
            DELETE FROM payments
            WHERE payment_id = ANY(%s)
        """, (ids_to_delete,))
        deleted_count = pg_cur.rowcount
        
        pg_conn.commit()
        
        print(f"✓ Deleted {deleted_count} duplicate payments")
        print()
        
        # Recalculate affected charter balances
        print("Recalculating balances for affected charters...")
        affected_reserves = list(set(pair[0][2] for pair in definite_duplicates))
        
        pg_cur.execute("""
            WITH payment_sums AS (
                SELECT 
                    reserve_number,
                    ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
                FROM payments
                WHERE reserve_number = ANY(%s)
                GROUP BY reserve_number
            )
            UPDATE charters c
            SET 
                paid_amount = COALESCE(ps.actual_paid, 0),
                balance = c.total_amount_due - COALESCE(ps.actual_paid, 0)
            FROM payment_sums ps
            WHERE c.reserve_number = ps.reserve_number
        """, (affected_reserves,))
        
        updated_charters = pg_cur.rowcount
        pg_conn.commit()
        
        print(f"✓ Recalculated balances for {updated_charters} charters")
        print()
        
        print("=" * 120)
        print("✓ SUCCESS! Duplicate payments deleted and balances recalculated")
        print("=" * 120)
        print(f"Backup table: {backup_table}")
        print(f"Rollback: INSERT INTO payments SELECT * FROM {backup_table};")

else:
    print("✅ No definite duplicates found!")

if likely_legitimate:
    print()
    print("=" * 120)
    print("LIKELY LEGITIMATE PAIRS (Different keys/dates - probably deposit + final payment)")
    print("=" * 120)
    print()
    print(f"{'Reserve':<12} {'Amount':<12} {'Date1':<12} {'Date2':<12} {'Key1':<20} {'Key2':<20}")
    print("-" * 120)
    
    for pair in likely_legitimate[:10]:
        id1, id2, reserve, amount, date1, date2, key1, key2 = pair[:8]
        key1_short = (key1[:17] + '...') if key1 and len(key1) > 20 else (key1 or 'NULL')
        key2_short = (key2[:17] + '...') if key2 and len(key2) > 20 else (key2 or 'NULL')
        print(f"{reserve:<12} ${amount:>10,.2f} {str(date1):<12} {str(date2):<12} {key1_short:<20} {key2_short:<20}")
    
    if len(likely_legitimate) > 10:
        print(f"... and {len(likely_legitimate) - 10} more")
    
    print()
    print("These appear to be legitimate multiple payments (deposits, installments, etc.)")
    print("No action needed.")

pg_cur.close()
pg_conn.close()
