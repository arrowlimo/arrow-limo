import psycopg2, os, sys
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REMOVED***')
    )

def main(write=False):
    conn = get_conn(); cur = conn.cursor()
    print(f"== Client Display Name Migration ({'WRITE' if write else 'DRY-RUN'}) {datetime.now():%Y-%m-%d %H:%M:%S} ==")
    # Preview counts
    # Check if column exists first
    cur.execute("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='charters' AND column_name='client_display_name'
    """)
    has_col = cur.fetchone() is not None
    before_null = None
    if has_col:
        cur.execute("SELECT COUNT(*) FROM charters WHERE client_display_name IS NULL")
        before_null = cur.fetchone()[0]
        print(f"Charters missing client_display_name before: {before_null}")
    else:
        print("client_display_name column does not exist yet.")
    if write:
        sql_path = os.path.join(os.getcwd(),'migrations','2025-12-01_add_client_display_name_to_charters.sql')
        with open(sql_path,'r',encoding='utf-8') as f:
            sql = f.read()
        cur.execute(sql)
        conn.commit()
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='charters' AND column_name='client_display_name'
        """)
        has_col2 = cur.fetchone() is not None
        if has_col2:
            cur.execute("SELECT COUNT(*) FROM charters WHERE client_display_name IS NULL")
            after_null = cur.fetchone()[0]
            print(f"Charters missing client_display_name after: {after_null}")
        else:
            print("Column still missing after migration execution (check errors).")
    else:
        print("DRY-RUN only; passing on execution.")
    cur.close(); conn.close()

if __name__=='__main__':
    write = '--write' in sys.argv
    main(write)
