import psycopg2, os
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REDACTED***')
    )

def main():
    print(f"== Analyze Missing client_display_name {datetime.now():%Y-%m-%d %H:%M:%S} ==")
    conn = get_conn(); cur = conn.cursor()

    # Total NULLs
    cur.execute("SELECT COUNT(*) FROM charters WHERE client_display_name IS NULL")
    total_null = cur.fetchone()[0]

    # Break down by client_id presence
    cur.execute("""
        SELECT 
            CASE WHEN client_id IS NULL THEN 'client_id_null' ELSE 'client_id_present' END as bucket,
            COUNT(*)
        FROM charters
        WHERE client_display_name IS NULL
        GROUP BY 1
    """)
    by_client_id = cur.fetchall()

    # Rows where client_id present but no matching clients row
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.client_display_name IS NULL
          AND c.client_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM clients cl WHERE cl.client_id = c.client_id
          )
    """)
    missing_client_row = cur.fetchone()[0]

    # Rows where client row exists but client_name NULL or blank
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.client_display_name IS NULL
          AND (cl.client_name IS NULL OR TRIM(cl.client_name) = '')
    """)
    blank_client_name = cur.fetchone()[0]

    # Sample problematic charter_ids for inspection
    cur.execute("""
        SELECT c.charter_id, c.client_id
        FROM charters c
        WHERE c.client_display_name IS NULL
        ORDER BY c.charter_id DESC
        LIMIT 15
    """)
    sample = cur.fetchall()

    # Oldest and newest null examples
    cur.execute("""
        SELECT MIN(charter_date), MAX(charter_date)
        FROM charters WHERE client_display_name IS NULL
    """)
    date_range = cur.fetchone()

    print(f"Total NULL display names: {total_null}")
    print("Breakdown:")
    for bucket, cnt in by_client_id:
        print(f"  {bucket}: {cnt}")
    print(f"client_id present but missing clients row: {missing_client_row}")
    print(f"client row present but client_name blank: {blank_client_name}")
    print(f"Date range of NULLs: {date_range[0]} → {date_range[1]}")
    print("Sample charter_ids (charter_id, client_id):")
    for cid, clid in sample:
        print(f"  {cid} | {clid}")

    # Suggested remediation counts
    can_backfill_from_client_id = missing_client_row + blank_client_name
    print("\nRemediation Suggestions:")
    if total_null:
        print("  1. Set client_display_name = client_id::text where client_id IS NOT NULL and no name available.")
        print("  2. Investigate client_id NULL rows (likely placeholder / test / orphan charters).")
        print("  3. Optionally create placeholder client records for missing client rows.")
    else:
        print("  All charters have display names.")

    conn.close()

if __name__=='__main__':
    main()
