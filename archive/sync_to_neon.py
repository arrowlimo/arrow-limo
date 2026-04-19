"""
Neon Sync Script - Local almsdata -> Neon Cloud
Overwrites Neon with local data, excluding backup_*, _tmp_*, and large analysis tables.
Run this AFTER confirming D:\almsdata_backup_20260418.dump exists and is valid.
"""
import os
import subprocess
import sys
from pathlib import Path

import psycopg2

# ========================
# CONFIGURATION
# ========================
BASE_DIR = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def build_conn(env_values: dict[str, str]) -> dict[str, object]:
    conn: dict[str, object] = {
        'host': env_values.get('DB_HOST', 'localhost'),
        'port': int(env_values.get('DB_PORT', '5432')),
        'dbname': env_values.get('DB_NAME', 'almsdata'),
        'user': env_values.get('DB_USER', 'postgres'),
    }
    if env_values.get('DB_PASSWORD'):
        conn['password'] = env_values['DB_PASSWORD']
    if env_values.get('DB_SSLMODE'):
        conn['sslmode'] = env_values['DB_SSLMODE']
    if env_values.get('DB_CHANNEL_BINDING'):
        conn['channel_binding'] = env_values['DB_CHANNEL_BINDING']
    return conn


LOCAL_CONN = build_conn(load_env_file(BASE_DIR / '.env'))
NEON_CONN = build_conn(load_env_file(BASE_DIR / '.env.neon'))
DUMP_FILE = r"D:\almsdata_neon_filtered_20260418.dump"
RESTORE_LIST_FILE = r"D:\almsdata_neon_filtered_20260418.list"
PG_DUMP = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
PG_RESTORE = r"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe"
PSQL = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"

EXCLUDE_PREFIXES = ('backup_', '_tmp_')
ADDITIONAL_EXCLUDES = {
    'banking_receipt_matching_ledger', 'master_relationships', 'orphaned_charges_archive',
    'square_raw_records', 'qb_journal_entries', 'unified_general_ledger',
    'email_financial_events', 'square_api_audit', 'receipts_backup_before_dedup_20260224_084445',
    'lms2026_payment_matches', 'lms2026_payments_staging', 'square_cc_staging',
    'square_fees_staging', 'square_raw_imports', 'lms_charges', 'lms_deposits',
    'lms_driver_pay_staging', 'lms_customers_enhanced',
    'income_ledger_garbage_quarantine_20260410', 'income_ledger_garbage_quarantine_20260410_b',
    'income_ledger_payment_archive', 'orphan_bank_flow_registry',
}

# ========================
# STEP 1: Get table list
# ========================
print("=== STEP 1: Connecting to local DB to get table list ===")
conn = psycopg2.connect(**LOCAL_CONN)
cur = conn.cursor()
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")
all_tables = [r[0] for r in cur.fetchall()]
cur.close(); conn.close()

excluded = [t for t in all_tables if any(t.startswith(p) for p in EXCLUDE_PREFIXES) or t in ADDITIONAL_EXCLUDES]
included = [t for t in all_tables if t not in excluded]

conn = psycopg2.connect(**LOCAL_CONN)
cur = conn.cursor()
cur.execute(
    """
    WITH RECURSIVE excluded_rel AS (
        SELECT c.oid, c.relname, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND c.relname = ANY(%s)
    ), dependent_views AS (
        SELECT oid, relname, relkind FROM excluded_rel
        UNION
        SELECT DISTINCT c.oid, c.relname, c.relkind
        FROM pg_depend d
        JOIN pg_rewrite r ON r.oid = d.objid
        JOIN pg_class c ON c.oid = r.ev_class
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN dependent_views dv ON dv.oid = d.refobjid
        WHERE n.nspname = 'public'
          AND c.relkind IN ('v', 'm')
    ), owned_sequences AS (
        SELECT DISTINCT seq.relname, seq.relkind
        FROM pg_class seq
        JOIN pg_namespace seq_ns ON seq_ns.oid = seq.relnamespace
        JOIN pg_depend d ON d.objid = seq.oid
        WHERE seq_ns.nspname = 'public'
          AND seq.relkind = 'S'
          AND d.refobjid IN (SELECT oid FROM excluded_rel)
    )
    SELECT relname, relkind
    FROM dependent_views
    WHERE relkind IN ('v', 'm')
    UNION
    SELECT relname, relkind
    FROM owned_sequences
    ORDER BY relkind, relname
    """,
    (excluded,),
)
dependent_relations = cur.fetchall()

cur.execute(
    """
    SELECT con.conname
    FROM pg_constraint con
    JOIN pg_class src ON src.oid = con.conrelid
    JOIN pg_namespace src_ns ON src_ns.oid = src.relnamespace
    JOIN pg_class ref ON ref.oid = con.confrelid
    JOIN pg_namespace ref_ns ON ref_ns.oid = ref.relnamespace
    WHERE con.contype = 'f'
      AND src_ns.nspname = 'public'
      AND ref_ns.nspname = 'public'
      AND ref.relname = ANY(%s)
    ORDER BY con.conname
    """,
    (excluded,),
)
foreign_keys_to_skip = [row[0] for row in cur.fetchall()]
cur.close(); conn.close()

excluded_relation_names = set(excluded)
excluded_relation_names.update(name for name, _kind in dependent_relations)
views_to_exclude = {name for name, kind in dependent_relations if kind in ('v', 'm')}
sequences_to_exclude = {name for name, kind in dependent_relations if kind == 'S'}

print(f"  Total tables: {len(all_tables)}")
print(f"  Excluding: {len(excluded)}")
print(f"  Including: {len(included)}")
if dependent_relations:
    print(f"  Also excluding dependent views/materialized views: {len(views_to_exclude)}")
    print(f"  Also excluding owned sequences: {len(sequences_to_exclude)}")
if foreign_keys_to_skip:
    print(f"  Also skipping foreign keys to excluded tables: {len(foreign_keys_to_skip)}")

# ========================
# STEP 2: Create filtered dump
# ========================
print(f"\n=== STEP 2: Creating filtered pg_dump -> {DUMP_FILE} ===")
exclude_args = []
for t in sorted(excluded_relation_names):
    exclude_args += [f'--exclude-table={t}']

env = os.environ.copy()
env['PGPASSWORD'] = LOCAL_CONN['password']

cmd = [PG_DUMP, '-h', 'localhost', '-p', '5432', '-U', 'postgres', '-d', 'almsdata',
       '-F', 'c', '-f', DUMP_FILE] + exclude_args
result = subprocess.run(cmd, env=env, capture_output=True, text=True)
if result.returncode != 0:
    print(f"DUMP FAILED: {result.stderr}")
    sys.exit(1)
size_mb = os.path.getsize(DUMP_FILE) / (1024*1024)
print(f"  Dump created: {size_mb:.1f} MB")

toc_result = subprocess.run([PG_RESTORE, '-l', DUMP_FILE], capture_output=True, text=True)
if toc_result.returncode != 0:
    print(f"TOC LIST FAILED: {toc_result.stderr}")
    sys.exit(1)

filtered_toc_lines = []
skipped_toc_entries = 0
for line in toc_result.stdout.splitlines():
    if not line or line.startswith(';'):
        filtered_toc_lines.append(line)
        continue

    skip_line = False
    if any(f" {name} " in line for name in views_to_exclude):
        if ' VIEW public ' in line or ' MATERIALIZED VIEW public ' in line:
            skip_line = True

    if not skip_line and any(f" {name} " in line for name in sequences_to_exclude):
        if ' SEQUENCE public ' in line or ' ACL public SEQUENCE ' in line or ' SEQUENCE SET public ' in line:
            skip_line = True

    if not skip_line and any(f" {name} " in line for name in foreign_keys_to_skip):
        if ' FK CONSTRAINT public ' in line:
            skip_line = True

    if skip_line:
        skipped_toc_entries += 1
        filtered_toc_lines.append(f'; {line}')
    else:
        filtered_toc_lines.append(line)

Path(RESTORE_LIST_FILE).write_text('\n'.join(filtered_toc_lines) + '\n', encoding='utf-8')
print(f"  Restore list created: {RESTORE_LIST_FILE}")
print(f"  TOC entries skipped during restore: {skipped_toc_entries}")

# ========================
# STEP 3: Drop all tables on Neon
# ========================
print("\n=== STEP 3: Dropping all existing tables on Neon ===")
env_neon = os.environ.copy()
env_neon['PGPASSWORD'] = NEON_CONN['password']
if NEON_CONN.get('sslmode'):
    env_neon['PGSSLMODE'] = str(NEON_CONN['sslmode'])
if NEON_CONN.get('channel_binding'):
    env_neon['PGCHANNELBINDING'] = str(NEON_CONN['channel_binding'])

reset_sql = """
DO $$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT nspname
        FROM pg_namespace
        WHERE nspname NOT IN ('pg_catalog', 'information_schema')
          AND nspname NOT LIKE 'pg_toast%'
          AND nspname NOT LIKE 'pg_temp_%'
    ) LOOP
        EXECUTE 'DROP SCHEMA IF EXISTS ' || quote_ident(r.nspname) || ' CASCADE';
    END LOOP;
END $$;
CREATE SCHEMA IF NOT EXISTS public;
GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO PUBLIC;
"""
result = subprocess.run(
    [PSQL, '-h', NEON_CONN['host'], '-p', '5432', '-U', NEON_CONN['user'], '-d', NEON_CONN['dbname'],
     '-v', 'ON_ERROR_STOP=1', '-c', reset_sql],
    env=env_neon, capture_output=True, text=True
)
if result.returncode != 0:
    print(f"DROP FAILED: {result.stderr}")
    sys.exit(1)
print("  All Neon user schemas dropped OK")

# ========================
# STEP 4: Confirm clean restore target
# ========================
print("\n=== STEP 4: Target reset complete ===")
print("  Public schema recreated")

# ========================
# STEP 5: Restore to Neon
# ========================
print("\n=== STEP 5: Restoring filtered dump to Neon ===")
result = subprocess.run(
    [PG_RESTORE, '-h', NEON_CONN['host'], '-p', '5432', '-U', NEON_CONN['user'], '-d', NEON_CONN['dbname'],
     '--no-privileges', '--no-owner', '--exit-on-error', '-F', 'c', '-L', RESTORE_LIST_FILE, DUMP_FILE],
    env=env_neon, capture_output=True, text=True
)
# pg_restore returns non-zero on real errors and sometimes warnings; separate them for reporting.
errors = [l for l in result.stderr.splitlines() if 'pg_restore: error:' in l.lower()]
warnings = [l for l in result.stderr.splitlines() if 'pg_restore: warning:' in l.lower()]
print(f"  pg_restore exit code: {result.returncode}")
print(f"  Warnings: {len(warnings)}")
if errors:
    print(f"  ERRORS ({len(errors)}):")
    for e in errors[:20]:
        print(f"    {e}")
    sys.exit(1)
else:
    print("  No errors!")

# ========================
# STEP 6: Verify
# ========================
print("\n=== STEP 6: Verifying Neon table counts ===")
conn_neon = psycopg2.connect(**NEON_CONN)
cur = conn_neon.cursor()
cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
neon_table_count = cur.fetchone()[0]

# Check key tables
for tbl in ['charters', 'charter_payments', 'receipts', 'banking_transactions', 'vendor_invoices', 'payments']:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (tbl,),
    )
    if not cur.fetchone()[0]:
        print(f"  {tbl}: MISSING from public schema")
        continue

    cur.execute(f'SELECT COUNT(*) FROM public."{tbl}"')
    cnt = cur.fetchone()[0]
    print(f"  {tbl}: {cnt} rows")

cur.close(); conn_neon.close()
print(f"\n  Neon total tables: {neon_table_count} (expected ~{len(included)})")
print("\n=== NEON SYNC COMPLETE ===")
