import os, sys, csv, hashlib, datetime
from pathlib import Path
import psycopg2

ACCOUNT_DEFAULT = os.environ.get('DEFAULT_BANK_ACCOUNT','0228362')

INSERT_SQL = """
INSERT INTO banking_transactions (account_number, transaction_date, description, debit_amount, credit_amount)
VALUES (%s, %s, %s, %s, %s)
"""

CHECK_SQL = """
SELECT 1 FROM banking_transactions
WHERE account_number=%s AND transaction_date=%s AND COALESCE(description,'')=%s AND COALESCE(debit_amount,0)=%s AND COALESCE(credit_amount,0)=%s
LIMIT 1
"""

def parse_date(s: str):
    if not s:
        return None
    s = s.strip()
    # expect YYYY-MM-DD from our staged exports
    try:
        return datetime.date.fromisoformat(s)
    except Exception:
        # try other common formats
        for fmt in ("%d/%m/%Y","%m/%d/%Y","%Y/%m/%d"):
            try:
                return datetime.datetime.strptime(s, fmt).date()
            except Exception:
                pass
    return None

def to_float(s):
    if s is None or s == '':
        return 0.0
    try:
        return float(str(s).replace(',',''))
    except Exception:
        return 0.0

def main():
    src_dir = Path('exports/banking/imported_csv')
    if len(sys.argv) > 1:
        src_dir = Path(sys.argv[1])
    account = ACCOUNT_DEFAULT
    if len(sys.argv) > 2:
        account = sys.argv[2]

    paths = list(src_dir.glob('*.csv'))
    if not paths:
        print({'inserted':0,'skipped':0,'reason':'no files'})
        return

    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '5432')),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    for p in paths:
        with p.open('r', encoding='utf-8', newline='') as f:
            r = csv.DictReader(f)
            for row in r:
                dt = parse_date(row.get('date') or row.get('transaction_date'))
                desc = (row.get('description') or row.get('memo') or '').strip()[:400]
                debit = to_float(row.get('debit'))
                credit = to_float(row.get('credit'))
                if not dt:
                    continue
                # idempotency check
                cur.execute(CHECK_SQL, (account, dt, desc, debit, credit))
                if cur.fetchone():
                    skipped += 1
                    continue
                cur.execute(INSERT_SQL, (account, dt, desc, debit, credit))
                inserted += 1
    conn.commit()
    cur.close(); conn.close()
    print({'inserted':inserted,'skipped':skipped,'account':account,'files':len(paths)})

if __name__ == '__main__':
    main()
