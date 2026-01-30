import psycopg2, os
from datetime import datetime

TARGET_COLUMNS = ['business_name','company_name','organization_name','legal_name','account_name']

def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REDACTED***')
    )

def main():
    print(f"== Scan Client Business Name Columns {datetime.now():%Y-%m-%d %H:%M:%S} ==")
    conn = get_conn(); cur = conn.cursor()

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='clients' ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    present = [c for c in TARGET_COLUMNS if c in cols]
    print("Columns present:", present or '(none)')

    if not present:
        print("No business/company style name columns found.")
        conn.close(); return

    select_list = ', '.join(['client_id','client_name'] + present)
    cur.execute(f"""
        SELECT {select_list} FROM clients
        WHERE (client_name IS NULL OR TRIM(client_name)='')
          AND (
            { ' OR '.join([f"TRIM({c})<>''" for c in present]) }
          )
        LIMIT 100
    """)
    rows = cur.fetchall()
    print(f"Rows with blank client_name but business-style name populated: {len(rows)}")
    for row in rows[:10]:
        data = dict(zip(['client_id','client_name']+present,row))
        print("  client_id=", data['client_id'], " | business candidates: ", {c:data.get(c) for c in present if data.get(c)})

    # Backfill proposal
    # Priority order: business_name > company_name > organization_name > legal_name > account_name
    priority_expr = 'COALESCE(' + ','.join([c for c in present]) + ', client_id::text)'
    print("\nProposed UPDATE (review before running):")
    print("UPDATE clients SET client_name = " + priority_expr + " WHERE (client_name IS NULL OR TRIM(client_name)='') AND (" + ' OR '.join([f"TRIM({c})<>''" for c in present]) + ");")

    conn.close()

if __name__=='__main__':
    main()
