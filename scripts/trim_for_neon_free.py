"""
Identify tables to exclude to fit Neon free tier (512 MB limit)
Current: 766 MB -> Need to reduce by ~254 MB
"""
import psycopg2
import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

def pg_size_pretty(bytes_val):
    """Convert bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"

# Get all tables with sizes
cur.execute("""
    SELECT 
        tablename,
        pg_size_pretty(pg_total_relation_size('public.'||tablename)) as size_pretty,
        pg_total_relation_size('public.'||tablename) as bytes
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size('public.'||tablename) DESC
""")
all_tables = cur.fetchall()

print(f"\n{'='*80}")
print(f"NEON FREE TIER OPTIMIZATION (512 MB Target)")
print(f"{'='*80}\n")

# Staging/archive tables (already identified)
staging_tables = [
    'lms_staging_reserve_archived_20251109',
    'square_transactions_staging_archived_20251107',
    'orphaned_charges_archive',
    'payment_imports_archived_20251107',
    'gl_transactions_staging_archived_20251107',
    'lms_staging_customer_archived_20251109',
    'lms_staging_payment_archived_20251109',
    'cibc_checking_staging_archived_20251107',
    'pdf_staging',
    'staging_receipts_raw_archived_20251109',
    'charters_backup_cancelled_20260120_174741',
    'cibc_qbo_staging_archived_20251107',
    'staging_driver_pay_files',
    'payments_archived',
    'staging_scotia_2012_verified',
    'staging_scotia_2012_verified_archived_20251109',
    'staging_driver_pay_links',
    'raw_file_inventory',
    'bank_transactions_staging',
    'email_scanner_staging',
    'lms_staging_vehicles',
    'legacy_import_status',
    'schema_migrations',
    'staging_employee_reference_data',
    'staging_pd7a_year_end_summary',
    'migration_log',
    'charters_backup_closed_nopay_20260120_175447',
    'income_ledger_payment_archive',
]

# Historical/duplicate data candidates
historical_candidates = [
    'receipts_missing_creation_20251206_235143',  # Duplicate diagnostic
    'receipts_missing_creation_20251206_235121',  # Duplicate diagnostic
    'charters_zero_balance_fix_20251111_191705',  # Historical fix audit
    'payroll_fix_audit',  # Historical fix audit
    'payroll_fix_rollback_audit',  # Historical fix audit
    'comprehensive_payment_reconciliation',  # Can regenerate
    'email_financial_events',  # 35 MB - can exclude if not actively used
    'master_relationships',  # 104 MB - largest table, check if needed
]

# Calculate savings
staging_bytes = 0
staging_list = []
for table, size, bytes_val in all_tables:
    if table in staging_tables:
        staging_bytes += bytes_val
        staging_list.append((table, size, bytes_val))

historical_bytes = 0
historical_list = []
for table, size, bytes_val in all_tables:
    if table in historical_candidates:
        historical_bytes += bytes_val
        historical_list.append((table, size, bytes_val))

total_bytes = sum(b for _, _, b in all_tables)
target_bytes = 512 * 1024 * 1024  # 512 MB

print(f"Current Database Size: {pg_size_pretty(total_bytes)}")
print(f"Target (Neon Free): 512 MB")
print(f"Need to reduce by: {pg_size_pretty(total_bytes - target_bytes)}\n")

print(f"{'='*80}")
print(f"TIER 1: STAGING/ARCHIVE TABLES (Safe to exclude)")
print(f"{'='*80}\n")
print(f"{'TABLE':<50} {'SIZE':<15}")
print(f"{'-'*50} {'-'*15}")
for table, size, bytes_val in sorted(staging_list, key=lambda x: x[2], reverse=True):
    print(f"{table:<50} {size:<15}")
print(f"\nTotal Tier 1 Savings: {pg_size_pretty(staging_bytes)}\n")

after_tier1 = total_bytes - staging_bytes
print(f"After Tier 1 exclusions: {pg_size_pretty(after_tier1)}")
print(f"Still need to cut: {pg_size_pretty(after_tier1 - target_bytes) if after_tier1 > target_bytes else 'DONE!'}\n")

if after_tier1 > target_bytes:
    print(f"{'='*80}")
    print(f"TIER 2: HISTORICAL/DUPLICATE DATA (Consider excluding)")
    print(f"{'='*80}\n")
    print(f"{'TABLE':<50} {'SIZE':<15} {'NOTES':<30}")
    print(f"{'-'*50} {'-'*15} {'-'*30}")
    
    notes = {
        'receipts_missing_creation_20251206_235143': 'Diagnostic table',
        'receipts_missing_creation_20251206_235121': 'Diagnostic table',
        'charters_zero_balance_fix_20251111_191705': 'Historical fix',
        'payroll_fix_audit': 'Historical audit',
        'payroll_fix_rollback_audit': 'Historical audit',
        'comprehensive_payment_reconciliation': 'Can regenerate',
        'email_financial_events': 'Check if actively used',
        'master_relationships': 'LARGEST - verify need',
    }
    
    for table, size, bytes_val in sorted(historical_list, key=lambda x: x[2], reverse=True):
        note = notes.get(table, '')
        print(f"{table:<50} {size:<15} {note:<30}")
    
    print(f"\nTotal Tier 2 Savings: {pg_size_pretty(historical_bytes)}\n")
    
    after_tier2 = after_tier1 - historical_bytes
    print(f"After Tier 1+2 exclusions: {pg_size_pretty(after_tier2)}")
    print(f"Still need to cut: {pg_size_pretty(after_tier2 - target_bytes) if after_tier2 > target_bytes else 'TARGET REACHED!'}\n")

# Core operational tables (must keep)
core_tables = [
    'charters', 'payments', 'receipts', 'clients', 'employees', 'vehicles',
    'banking_transactions', 'general_ledger', 'users', 'security_audit',
    'charter_charges', 'charter_payments', 'driver_payroll', 'lms_charges',
]

print(f"{'='*80}")
print(f"CORE OPERATIONAL TABLES (Must Keep)")
print(f"{'='*80}\n")

core_bytes = 0
print(f"{'TABLE':<40} {'SIZE':<15}")
print(f"{'-'*40} {'-'*15}")
for table, size, bytes_val in all_tables:
    if table in core_tables:
        print(f"{table:<40} {size:<15}")
        core_bytes += bytes_val

print(f"\nCore tables total: {pg_size_pretty(core_bytes)}\n")

# Generate exclusion list
exclude_list = staging_tables.copy()

# Add historical tables if needed
if after_tier1 > target_bytes:
    # Add diagnostic tables first
    exclude_list.extend([
        'receipts_missing_creation_20251206_235143',
        'receipts_missing_creation_20251206_235121',
        'charters_zero_balance_fix_20251111_191705',
        'payroll_fix_audit',
        'payroll_fix_rollback_audit',
    ])
    
    # Check if we need more
    current = after_tier1
    for table, size, bytes_val in historical_list:
        if table not in exclude_list:
            current -= bytes_val
            if current <= target_bytes:
                exclude_list.append(table)
                break

print(f"{'='*80}")
print(f"RECOMMENDED EXCLUSION LIST")
print(f"{'='*80}\n")

print("Copy this list for pg_dump exclude pattern:\n")
for table in sorted(exclude_list):
    print(f"  --exclude-table=public.{table}")

print(f"\n{'='*80}")
print(f"EXPORT COMMAND")
print(f"{'='*80}\n")

exclude_flags = ' '.join([f'--exclude-table=public.{t}' for t in exclude_list])
print(f"""
pg_dump -h localhost -U postgres -d almsdata \\
  -F c -f almsdata_neon_optimized.dump \\
  {exclude_flags}
""")

cur.close()
conn.close()
