#!/usr/bin/env python3
"""
Audit journal table integrity and check for any previous deletion incidents.

Checks:
1. Journal table exists and row count
2. Schema structure and key columns
3. Date coverage and gaps
4. Relationship to receipts/banking
5. Any backup tables that might indicate recovery from deletion
"""
import psycopg2

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')


def get_columns(cur, table):
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = %s 
        ORDER BY ordinal_position
    """, (table,))
    return cur.fetchall()


def main():
    conn = psycopg2.connect(**DSN)
    conn.autocommit = True
    cur = conn.cursor()

    print("=== JOURNAL TABLE AUDIT ===\n")

    # Check if table exists
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'journal'
    """)
    exists = cur.fetchone()[0]

    if not exists:
        print("[FAIL] CRITICAL: journal table does NOT exist!")
        
        # Check for backup tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name ILIKE '%journal%'
            ORDER BY table_name
        """)
        journal_tables = cur.fetchall()
        if journal_tables:
            print("\nFound related tables:")
            for (tname,) in journal_tables:
                cur.execute(f"SELECT COUNT(*) FROM {tname}")
                cnt = cur.fetchone()[0]
                print(f"  {tname}: {cnt:,} rows")
        else:
            print("\nNo journal-related tables found!")
        
        cur.close()
        conn.close()
        return

    print("✓ Journal table exists")

    # Get row count
    cur.execute("SELECT COUNT(*) FROM journal")
    count = cur.fetchone()[0]
    print(f"Total entries: {count:,}")

    if count == 0:
        print("\n[WARN]  WARNING: Journal table is EMPTY!")
        cur.close()
        conn.close()
        return

    # Get schema
    cols = get_columns(cur, 'journal')
    print(f"\nColumns ({len(cols)}):")
    for cname, dtype in cols[:10]:  # First 10
        print(f"  {cname}: {dtype}")
    if len(cols) > 10:
        print(f"  ... and {len(cols)-10} more")

    # Check for date columns
    date_cols = [c[0] for c in cols if 'date' in c[0].lower() or c[1] in ('date', 'timestamp', 'timestamp without time zone')]
    print(f"\nDate columns: {', '.join(date_cols) if date_cols else '(none)'}")

    # Get date range if possible
    if date_cols:
        date_col = date_cols[0]
        try:
            cur.execute(f'SELECT MIN("{date_col}"), MAX("{date_col}") FROM journal WHERE "{date_col}" IS NOT NULL')
            min_date, max_date = cur.fetchone()
            print(f"Date range ({date_col}): {min_date} to {max_date}")
        except Exception as e:
            print(f"Could not get date range: {e}")

    # Check for primary key
    cur.execute("""
        SELECT column_name 
        FROM information_schema.key_column_usage 
        WHERE table_name = 'journal' 
          AND constraint_name LIKE '%pkey%'
    """)
    pk = cur.fetchone()
    print(f"Primary key: {pk[0] if pk else '(none)'}")

    # Sample some rows
    print("\nSample entries:")
    # Quote column names to handle special characters
    quoted_cols = [f'"{c[0]}"' for c in cols[:5]]
    try:
        cur.execute(f"SELECT {', '.join(quoted_cols)} FROM journal ORDER BY journal_id DESC LIMIT 3")
        for row in cur.fetchall():
            print(f"  {row}")
    except Exception as e:
        print(f"Could not retrieve sample: {e}")

    # Check for backup/recovery tables
    print("\n=== BACKUP/RECOVERY CHECK ===")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND (table_name LIKE '%journal%backup%' 
               OR table_name LIKE '%journal%old%'
               OR table_name LIKE '%journal%restore%'
               OR table_name LIKE 'backup%journal%')
        ORDER BY table_name
    """)
    backups = cur.fetchall()
    if backups:
        print("Found backup tables:")
        for (tname,) in backups:
            cur.execute(f"SELECT COUNT(*) FROM {tname}")
            cnt = cur.fetchone()[0]
            print(f"  {tname}: {cnt:,} rows")
    else:
        print("No backup tables found")

    # Check for deletion-related scripts
    print("\n=== SCRIPT AUDIT FOR JOURNAL DELETES ===")
    import os
    scripts_dir = os.path.dirname(__file__)
    delete_journal_scripts = []
    
    for fname in os.listdir(scripts_dir):
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(scripts_dir, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'DELETE FROM journal' in content or 'TRUNCATE journal' in content:
                    delete_journal_scripts.append(fname)
        except Exception:
            pass
    
    if delete_journal_scripts:
        print(f"[WARN]  Found {len(delete_journal_scripts)} scripts with DELETE/TRUNCATE for journal:")
        for script in delete_journal_scripts:
            print(f"  - {script}")
    else:
        print("✓ No scripts found with DELETE FROM journal")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
