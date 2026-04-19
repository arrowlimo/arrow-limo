"""
Generate pg_dump exclude flags for Neon sync.
Excludes: backup_*, _tmp_* tables, and selected large empty analysis tables.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Get all tables
cur.execute("""
SELECT t.table_name, COALESCE(s.n_live_tup, 0)
FROM information_schema.tables t
LEFT JOIN pg_stat_user_tables s ON s.relname = t.table_name
WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name
""")
all_tables = cur.fetchall()

# Always-exclude patterns
EXCLUDE_PREFIXES = ('backup_', '_tmp_')

# Large empty analysis tables to exclude from Neon (confirmed unused by web app)
ADDITIONAL_EXCLUDES = {
    'banking_receipt_matching_ledger',  # 32MB empty
    'master_relationships',             # 104MB empty
    'orphaned_charges_archive',         # 14MB empty
    'square_raw_records',               # 25MB empty
    'qb_journal_entries',               # 19MB empty
    'unified_general_ledger',           # 18MB empty
    'email_financial_events',           # 36MB empty
    'square_api_audit',                 # 12MB empty
    'receipts_backup_before_dedup_20260224_084445',  # 28MB empty
    # LMS staging (used for import, not needed in Neon)
    'lms2026_payment_matches',
    'lms2026_payments_staging',
    'square_cc_staging',
    'square_fees_staging',
    'square_raw_imports',
    'lms_charges',
    'lms_deposits',
    'lms_driver_pay_staging',
    'lms_customers_enhanced',
    'income_ledger_garbage_quarantine_20260410',
    'income_ledger_garbage_quarantine_20260410_b',
    'income_ledger_payment_archive',
    'orphan_bank_flow_registry',
}

excluded = []
included = []

for table_name, row_count in all_tables:
    if any(table_name.startswith(p) for p in EXCLUDE_PREFIXES) or table_name in ADDITIONAL_EXCLUDES:
        excluded.append(table_name)
    else:
        included.append((table_name, row_count))

cur.close()
conn.close()

print(f"Tables to INCLUDE in Neon sync: {len(included)}")
print(f"Tables to EXCLUDE from Neon: {len(excluded)}")
print()

# Generate the --exclude-table flags
exclude_flags = ' '.join([f'--exclude-table={t}' for t in excluded])
print("=== EXCLUDE FLAGS ===")
print(exclude_flags)
print()

# Write to files for use in pg_dump commands
with open('L:\\limo\\archive\\neon_exclude_flags.txt', 'w') as f:
    f.write(exclude_flags)

with open('L:\\limo\\archive\\neon_excluded_tables.txt', 'w') as f:
    for t in excluded:
        f.write(t + '\n')

with open('L:\\limo\\archive\\neon_included_tables.txt', 'w') as f:
    for t, r in included:
        f.write(f"{t}\t{r}\n")

print(f"Exclude flags saved to: L:\\limo\\archive\\neon_exclude_flags.txt")
print(f"Excluded table list: L:\\limo\\archive\\neon_excluded_tables.txt")
print(f"Included table list: L:\\limo\\archive\\neon_included_tables.txt")
print()
print("=== INCLUDED TABLES WITH DATA ===")
for t, r in included:
    if r > 0:
        print(f"  {t}: {r} rows")
