"""Archive duplicate staging tables by renaming with _ARCHIVED_20251107 suffix."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Tables to archive (100% duplicates or already imported)
TABLES_TO_ARCHIVE = [
    ('gl_transactions_staging', 50947, '100% duplicates in journal/unified_general_ledger'),
    ('payment_imports', 18720, '100% promoted to payments table'),
    ('cibc_checking_staging', 6506, '109% duplicates in banking_transactions'),
    ('square_transactions_staging', 9989, 'Already imported via payment_imports'),
    ('cibc_ledger_staging', 53, 'Promoted to banking_transactions'),
    ('cibc_qbo_staging', 1200, 'Promoted to banking_transactions'),
]

print("=" * 80)
print("ARCHIVING DUPLICATE STAGING TABLES")
print("=" * 80)

for table_name, expected_rows, reason in TABLES_TO_ARCHIVE:
    print(f"\n{table_name}")
    print("-" * 80)
    print(f"Expected rows: {expected_rows:,}")
    print(f"Reason: {reason}")
    
    # Check if table exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = %s
    """, (table_name,))
    
    if cur.fetchone()[0] == 0:
        print(f"  ⚠ Table not found - skipping")
        continue
    
    # Get actual row count
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    actual_rows = cur.fetchone()[0]
    print(f"Actual rows: {actual_rows:,}")
    
    # Rename to archived
    archived_name = f"{table_name}_ARCHIVED_20251107"
    try:
        cur.execute(f"ALTER TABLE {table_name} RENAME TO {archived_name}")
        conn.commit()
        print(f"  ✓ Renamed to: {archived_name}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        conn.rollback()

print("\n" + "=" * 80)
print("ARCHIVE COMPLETE")
print("=" * 80)

cur.close()
conn.close()
