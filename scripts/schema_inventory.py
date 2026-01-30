import os
import sys
from pathlib import Path
import csv
import psycopg2

# Ensure project root is on sys.path so we can import `api.get_db_connection`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import get_db_connection

OUTPUT = os.path.join(os.path.dirname(__file__), '..', 'reports', 'schema_inventory.csv')
OUTPUT = os.path.abspath(OUTPUT)
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

SQL = """
SELECT 
    c.table_schema,
    c.table_name,
    c.ordinal_position,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.character_maximum_length,
    c.numeric_precision,
    c.numeric_scale
FROM information_schema.columns c
WHERE c.table_schema NOT IN ('information_schema','pg_catalog')
ORDER BY c.table_schema, c.table_name, c.ordinal_position;
"""

INDEXES_SQL = """
SELECT 
    ns.nspname as schema_name,
    t.relname as table_name,
    i.relname as index_name,
    pg_get_indexdef(ix.indexrelid) as index_def
FROM pg_class t
JOIN pg_namespace ns ON ns.oid = t.relnamespace
JOIN pg_index ix ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
WHERE ns.nspname NOT IN ('pg_catalog','information_schema')
ORDER BY schema_name, table_name, index_name;
"""

FKEYS_SQL = """
SELECT
    tc.constraint_schema,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    tc.constraint_name
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.constraint_schema = kcu.constraint_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.constraint_schema = tc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.constraint_schema, tc.table_name, tc.constraint_name;
"""

if __name__ == '__main__':
    # Attempt connection and print the parameters being used for easier troubleshooting
    try:
        conn = get_db_connection()
    except Exception as e:
        print('Failed to connect to PostgreSQL. Please verify environment variables:')
        print('  DB_HOST =', os.environ.get('DB_HOST', 'localhost'))
        print('  DB_PORT =', os.environ.get('DB_PORT', '5432'))
        print('  DB_NAME =', os.environ.get('DB_NAME', 'almsdata'))
        print('  DB_USER =', os.environ.get('DB_USER', 'postgres'))
        print('  DB_PASSWORD =', '(set)' if os.environ.get('DB_PASSWORD') else '***REDACTED*** (default)')
        raise
    cur = conn.cursor()

    cur.execute(SQL)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()

    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)

    # Indexes
    idx_out = OUTPUT.replace('.csv', '_indexes.csv')
    cur.execute(INDEXES_SQL)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(idx_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)

    # Foreign keys
    fk_out = OUTPUT.replace('.csv', '_foreign_keys.csv')
    cur.execute(FKEYS_SQL)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(fk_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)

    print('Schema inventory written to:')
    print(' -', OUTPUT)
    print(' -', idx_out)
    print(' -', fk_out)
