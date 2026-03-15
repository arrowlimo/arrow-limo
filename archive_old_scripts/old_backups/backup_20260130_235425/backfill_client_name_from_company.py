import psycopg2, os
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REDACTED***')
    )

def main(write=False):
    conn = get_conn(); cur = conn.cursor()
    print(f"== Backfill client_name from company_name ({'WRITE' if write else 'DRY-RUN'}) {datetime.now():%Y-%m-%d %H:%M:%S} ==")

    # Count candidates
    cur.execute("""
        SELECT COUNT(*) FROM clients
        WHERE (client_name IS NULL OR TRIM(client_name)='')
          AND company_name IS NOT NULL AND TRIM(company_name)<>''
    """)
    cand = cur.fetchone()[0]
    print(f"Candidates to backfill: {cand}")

    # Show sample
    cur.execute("""
        SELECT client_id, company_name FROM clients
        WHERE (client_name IS NULL OR TRIM(client_name)='') AND TRIM(company_name)<>''
        ORDER BY client_id DESC LIMIT 10
    """)
    for cid, cname in cur.fetchall():
        print(f"  sample client_id={cid} company_name='{cname}'")

    if write and cand>0:
        backup = f"clients_company_name_backup_{datetime.now():%Y%m%d_%H%M%S}"
        cur.execute(f"""
            CREATE TABLE {backup} AS
            SELECT * FROM clients
            WHERE (client_name IS NULL OR TRIM(client_name)='')
              AND company_name IS NOT NULL AND TRIM(company_name)<>''
        """)
        print(f"Backup table created: {backup}")
        cur.execute("""
            UPDATE clients
            SET client_name = company_name
            WHERE (client_name IS NULL OR TRIM(client_name)='')
              AND company_name IS NOT NULL AND TRIM(company_name)<>''
        """)
        updated = cur.rowcount
        print(f"Rows updated: {updated}")
        # Trigger should propagate to charters; verify
        cur.execute("SELECT COUNT(*) FROM charters WHERE client_display_name IS NULL")
        null_after = cur.fetchone()[0]
        conn.commit()
        print(f"Remaining NULL client_display_name in charters after update: {null_after}")
    elif not write:
        print("DRY-RUN: no changes applied.")

    cur.close(); conn.close()

if __name__=='__main__':
    import sys
    main(write='--write' in sys.argv)
