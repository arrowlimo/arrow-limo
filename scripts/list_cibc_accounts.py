import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from api import get_db_connection

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM information_schema.tables WHERE table_schema='public' AND table_name='cibc_accounts'")
        if not cur.fetchone():
            print("cibc_accounts table not found")
            return
        cur.execute("SELECT account_number, account_name FROM cibc_accounts ORDER BY account_number")
        rows = cur.fetchall()
        for r in rows:
            print(f"{r[0]}\t{r[1]}")
    finally:
        cur.close(); conn.close()

if __name__ == "__main__":
    main()
