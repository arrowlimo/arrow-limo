"""
Create missing journal entries for 2012 write-offs.

- Uses GST-included model (AB 5%): gst = total * 0.05 / 1.05; net = total - gst
- For each write-off amount, inserts three journal lines (double-entry):
  1) DR Bad Debt Expense      = net
  2) DR GST Recoverable       = gst
  3) CR Accounts Receivable   = total

Safety:
- Dry-run by default. Use --write to apply.
- Skips reserves that already have a write-off journal (Memo/Description ILIKE '%write%off%' AND reserve in memo)
- Requires a target date (default 2012-12-31) since write-offs occurred in 2012 period

Columns (journal table):
  "Date" (text YYYY-MM-DD), "Transaction Type", "#", "Name", "Memo/Description",
  "Account", "Debit" (float), "Credit" (float), merchant, transaction_type,
  reference_number, "Reference", journal_id
"""
import argparse
import os
from decimal import Decimal, ROUND_HALF_UP
import psycopg2

WRITEOFFS = [
    ('002359', 312.00), ('002947', 29.25), ('002994', 682.50), ('003261', 353.15),
    ('003406', 19.50), ('003429', 236.25), ('003897', 240.00), ('003959', 1808.09),
    ('004035', 220.50), ('004125', 200.00), ('004138', 0.50), ('004173', 68.25),
    ('004200', 156.00), ('004211', 60.00), ('004251', 675.00), ('004273', 149.50),
    ('004279', 857.75), ('004301', 58.50), ('004315', 68.24), ('004322', 244.76),
    ('004326', 509.00), ('004343', 307.12), ('004483', 10.50), ('004502', 204.50),
    ('004522', 24.75), ('004564', 653.00), ('004572', 262.00), ('004584', 220.50),
    ('004596', 365.00), ('004626', 243.00), ('004647', 10.50), ('004697', 234.00),
    ('004713', 120.00), ('004872', 416.50), ('004932', 124.50), ('004941', 207.52),
    ('004947', 363.00), ('004963', 240.00), ('004981', 189.75), ('004982', 161.50),
    ('004997', 438.50), ('005020', 573.25), ('005026', 247.50), ('005034', 30.02),
    ('005042', 536.26), ('005069', 230.00), ('005138', 1121.98), ('005159', 300.00),
    ('005162', 235.00), ('005217', 198.00), ('005280', 74.75), ('005359', 140.00),
    ('005428', 0.01), ('005527', 371.26), ('005535', 300.00), ('005672', 45.01)
]

BAD_DEBT_ACCOUNT_DEFAULT = 'Bad Debt Expense'
GST_ACCOUNT_DEFAULT = 'GST Recoverable'
AR_ACCOUNT_DEFAULT = 'Accounts Receivable'


def get_db():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )


def dec(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def gst_breakdown(total):
    total = dec(total)
    gst = (total * dec('0.05') / dec('1.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    net = total - gst
    return net, gst


def next_journal_id(cur):
    cur.execute('SELECT COALESCE(MAX(journal_id), 0) FROM journal')
    return (cur.fetchone()[0] or 0) + 1


def get_client_name(cur, reserve):
    cur.execute(
        '''SELECT c.client_name
           FROM charters ch LEFT JOIN clients c ON ch.client_id = c.client_id
           WHERE ch.reserve_number = %s''', (reserve,)
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else 'Unknown Client'


def already_recorded(cur, reserve):
    # Consider either reference_number exact match or memo containing the reserve
    cur.execute(
        'SELECT 1 FROM journal WHERE reference_number = %s OR "Memo/Description" ILIKE %s LIMIT 1',
        (reserve, f'%{reserve}%')
    )
    return cur.fetchone() is not None


def insert_line(cur, date_str, txn_type, number, name, memo, account, debit, credit, ref, refnum, journal_id, merchant=None):
    cur.execute(
        'INSERT INTO journal ("Date", "Transaction Type", "#", "Name", "Memo/Description", "Account", "Debit", "Credit", merchant, transaction_type, reference_number, "Reference", journal_id) '
        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        (
            date_str, txn_type, number, name, memo, account,
            float(debit or 0), float(credit or 0), merchant, 'writeoff',
            refnum, ref, journal_id
        )
    )


def main():
    p = argparse.ArgumentParser(description='Create 2012 write-off journal entries')
    p.add_argument('--date', default='2012-12-31', help='Journal date to use (YYYY-MM-DD)')
    p.add_argument('--bad-debt', default=BAD_DEBT_ACCOUNT_DEFAULT)
    p.add_argument('--gst', default=GST_ACCOUNT_DEFAULT)
    p.add_argument('--ar', default=AR_ACCOUNT_DEFAULT)
    p.add_argument('--write', action='store_true', help='Apply changes')
    p.add_argument('--limit', type=int, default=None, help='Limit number of reserves processed')
    args = p.parse_args()

    conn = get_db()
    cur = conn.cursor()

    date_str = args.date
    print('=' * 100)
    print(f'CREATING 2012 WRITE-OFF JOURNAL ENTRIES (date={date_str})')
    print('=' * 100)

    start_id = next_journal_id(cur)
    to_process = WRITEOFFS[: args.limit] if args.limit else WRITEOFFS

    created = 0
    skipped = 0

    for i, (reserve, total) in enumerate(to_process, start=1):
        if already_recorded(cur, reserve):
            skipped += 1
            print(f'- SKIP reserve {reserve}: already has a write-off journal')
            continue

        net, gst = gst_breakdown(total)
        name = get_client_name(cur, reserve)
        memo = f'Write-off of uncollectible charter balance | Reserve {reserve}'
        number = reserve
        ref = f'Reserve {reserve}'
        refnum = reserve

        # Three lines: DR expense, DR GST, CR A/R
        jid = start_id + (created * 3)
        print(f'+ ADD reserve {reserve}: total={total:.2f} net={net:.2f} gst={gst:.2f} | client={name}')

        if args.write:
            insert_line(cur, date_str, 'Journal', number, name, memo, args.bad_debt, net, 0, ref, refnum, jid)
            insert_line(cur, date_str, 'Journal', number, name, memo, args.gst, gst, 0, ref, refnum, jid + 1)
            insert_line(cur, date_str, 'Journal', number, name, memo, args.ar, 0, net + gst, ref, refnum, jid + 2)
        created += 1

    print('\n' + '-' * 100)
    print(f'Reserves processed: {len(to_process)}')
    print(f'Would create: {created * 3} journal lines for {created} write-offs')
    print(f'Skipped (already recorded): {skipped}')

    if args.write:
        conn.commit()
        print('Changes committed.')
    else:
        print('Dry-run only. Re-run with --write to apply.')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
