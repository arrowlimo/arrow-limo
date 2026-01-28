"""
Record Payday Loan Agreement and Match Payments to Banking Logs

Loan:
- Principal: $1,000.00
- Fee: $150.00 (15 per $100)
- APR: 160.32%
- Term: 52 days
- Total repay: $1,150.00
- Installments: 4 x $287.50 on 2019-12-20, 2020-01-13, 2020-01-27, 2020-02-10

Usage:
  python -X utf8 scripts/record_payday_loan_and_match.py --write   # apply changes
  python -X utf8 scripts/record_payday_loan_and_match.py           # dry-run only
"""
import argparse
import psycopg2
from datetime import date, timedelta
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# Defaults; can be overridden by CLI args
LOAN = {
    'lender_name': 'Unknown Payday Lender',
    'agreement_date': date(2019, 12, 1),  # approximate if exact not provided
    'principal': Decimal('1000.00'),
    'fee_total': Decimal('150.00'),
    'apr_percent': Decimal('160.32'),
    'term_days': 52,
    'total_repay': Decimal('1150.00'),
    'notes': '4 payments of 287.50 due on 2019-12-20, 2020-01-13, 2020-01-27, 2020-02-10; agreement Dec 2019.'
}

SCHEDULE = [
    (date(2019, 12, 20), Decimal('287.50')),
    (date(2020, 1, 13), Decimal('287.50')),
    (date(2020, 1, 27), Decimal('287.50')),
    (date(2020, 2, 10), Decimal('287.50')),
]

def parse_date(s: str) -> date:
    parts = s.strip().split('-')
    if len(parts) == 3:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    # Support M/D/YYYY too
    parts = s.strip().replace('/', '-').split('-')
    if len(parts) == 3:
        y = int(parts[2]) if len(parts[2]) == 4 else int(parts[0])
        # Guess format MM-DD-YYYY
        if len(parts[2]) == 4:
            return date(int(parts[2]), int(parts[0]), int(parts[1]))
    raise ValueError(f"Unrecognized date format: {s}")

def build_from_args(args):
    global LOAN, SCHEDULE
    if any([args.principal, args.fee_total, args.total_repay, args.agreement_date, args.lender]):
        LOAN = {
            'lender_name': args.lender or 'Unknown Payday Lender',
            'agreement_date': parse_date(args.agreement_date) if args.agreement_date else LOAN['agreement_date'],
            'principal': Decimal(args.principal) if args.principal else LOAN['principal'],
            'fee_total': Decimal(args.fee_total) if args.fee_total else LOAN['fee_total'],
            'apr_percent': Decimal(args.apr) if args.apr else LOAN.get('apr_percent'),
            'term_days': args.term_days if args.term_days else LOAN.get('term_days'),
            'total_repay': Decimal(args.total_repay) if args.total_repay else LOAN['total_repay'],
            'notes': args.notes or LOAN['notes']
        }

    if args.due or args.due_dates:
        due_list = []
        if args.due:
            for d in args.due:
                due_list.append(parse_date(d))
        if args.due_dates:
            for d in args.due_dates.split(','):
                if d.strip():
                    due_list.append(parse_date(d.strip()))
        due_list = sorted(due_list)
        # Determine amounts
        if args.installment_amount:
            amt = Decimal(args.installment_amount)
            SCHEDULE = [(d, amt) for d in due_list]
        else:
            # Split total_repay evenly across due dates; adjust last for rounding
            n = len(due_list)
            if n == 0:
                raise ValueError('No due dates provided')
            per = (LOAN['total_repay'] / n).quantize(Decimal('0.01'))
            schedule = [(d, per) for d in due_list]
            total = sum(a for _, a in schedule)
            diff = (LOAN['total_repay'] - total).quantize(Decimal('0.01'))
            if diff != 0:
                # adjust last payment
                last_d, last_a = schedule[-1]
                schedule[-1] = (last_d, (last_a + diff).quantize(Decimal('0.01')))
            SCHEDULE = schedule
    return LOAN, SCHEDULE

DDL_LOANS = """
CREATE TABLE IF NOT EXISTS payday_loans (
  id SERIAL PRIMARY KEY,
  lender_name VARCHAR(200),
  agreement_date DATE NOT NULL,
  principal NUMERIC(12,2) NOT NULL,
  fee_total NUMERIC(12,2) NOT NULL,
  apr_percent NUMERIC(7,2),
  term_days INTEGER,
  total_repay NUMERIC(12,2) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  notes TEXT,
  source_hash TEXT UNIQUE
);
"""

DDL_PAYMENTS = """
CREATE TABLE IF NOT EXISTS payday_loan_payments (
  id SERIAL PRIMARY KEY,
  loan_id INTEGER NOT NULL REFERENCES payday_loans(id) ON DELETE CASCADE,
  due_date DATE NOT NULL,
  amount_due NUMERIC(12,2) NOT NULL,
  status VARCHAR(20) DEFAULT 'scheduled', -- scheduled|matched|paid|missed
  paid_date DATE,
  matched_amount NUMERIC(12,2),
  match_confidence NUMERIC(5,2),
  banking_transaction_id BIGINT,
  receipt_id BIGINT,
    match_method TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(loan_id, due_date, amount_due)
);
"""

def connect():
    return psycopg2.connect(**DB)


def ensure_schema(cur):
    cur.execute(DDL_LOANS)
    cur.execute(DDL_PAYMENTS)
    # Ensure match_method exists if table created previously
    cur.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payday_loan_payments' AND column_name = 'match_method'
            ) THEN
                ALTER TABLE payday_loan_payments ADD COLUMN match_method TEXT;
            END IF;
        END $$;
        """
    )


def upsert_loan(cur):
    # Create deterministic source hash to avoid duplicates
    src = f"PAYDAY_LOAN_{LOAN['lender_name']}_{LOAN['agreement_date']}_{LOAN['principal']}_{LOAN['total_repay']}"
    # Hash in SQL for simplicity
    cur.execute("""
        WITH s AS (
          SELECT md5(%s)::text AS h
        )
        INSERT INTO payday_loans (lender_name, agreement_date, principal, fee_total, apr_percent, term_days, total_repay, notes, source_hash)
        SELECT %s, %s, %s, %s, %s, %s, %s, %s, s.h FROM s
        ON CONFLICT (source_hash) DO UPDATE SET notes = EXCLUDED.notes
        RETURNING id, source_hash
    """, (
        src,
        LOAN['lender_name'], LOAN['agreement_date'], LOAN['principal'], LOAN['fee_total'],
        LOAN['apr_percent'], LOAN['term_days'], LOAN['total_repay'], LOAN['notes']
    ))
    row = cur.fetchone()
    return row[0]


def ensure_schedule(cur, loan_id):
    for due, amt in SCHEDULE:
        cur.execute(
            """
            INSERT INTO payday_loan_payments (loan_id, due_date, amount_due)
            VALUES (%s, %s, %s)
            ON CONFLICT (loan_id, due_date, amount_due) DO NOTHING
            RETURNING id
            """,
            (loan_id, due, amt)
        )


def find_bank_match(cur, due_date, amount, days_window=3, after_only=False, vendor_filter=None):
    if after_only:
        start = due_date
        end = due_date + timedelta(days=days_window)
    else:
        start = due_date - timedelta(days=days_window)
        end = due_date + timedelta(days=days_window)
    # Exact amount match on debit side with optional vendor filter
    # Parameters must align with SQL placeholder order; vendor (if any) precedes ORDER BY params
    params = [start, end, amount]
    vendor_clause = ""
    if vendor_filter:
        vendor_clause = " AND LOWER(description) LIKE %s"
        params.append(f"%{vendor_filter.lower()}%")
    # ORDER BY placeholders come last
    params.extend([due_date, amount])
    sql = f"""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND debit_amount IS NOT NULL AND ABS(debit_amount - %s) < 0.01
          {vendor_clause}
        ORDER BY ABS(transaction_date - %s), ABS(debit_amount - %s)
        LIMIT 5
    """
    cur.execute(sql, tuple(params))
    return cur.fetchall()


def match_payments(cur, loan_id, apply=False, vendor_filter_default='money mart'):
    cur.execute(
        "SELECT id, due_date, amount_due, status FROM payday_loan_payments WHERE loan_id=%s ORDER BY due_date",
        (loan_id,)
    )
    payments = cur.fetchall()
    print("\nPayment schedule:")
    for pid, due, amt, status in payments:
        print(f"  - {due}  ${amt:,.2f}  [{status}]")

    print("\nMatching to banking_transactions (exact amount, escalating windows)...")
    for pid, due, amt, status in payments:
        strategies = [
            {"window": 3,  "after_only": False, "vendor": None,          "conf": Decimal('1.00'), "label": "+/-3d"},
            {"window": 7,  "after_only": False, "vendor": None,          "conf": Decimal('0.98'), "label": "+/-7d"},
            {"window": 14, "after_only": True,  "vendor": vendor_filter_default, "conf": Decimal('0.95'), "label": "+14d after, vendor"},
        ]

        matched_here = False
        for strat in strategies:
            rows = find_bank_match(cur, due, amt, days_window=strat["window"], after_only=strat["after_only"], vendor_filter=strat["vendor"]) 
            if rows:
                print(f"\nDue {due} ${amt:,.2f} candidates ({strat['label']}):")
                for (txid, tdate, desc, debit, credit) in rows:
                    print(f"  • TX {txid}  {tdate}  ${debit or 0:,.2f}  {desc}")
                txid, tdate, desc, debit, credit = rows[0]
                if apply:
                    cur.execute(
                        "UPDATE payday_loan_payments SET status='matched', paid_date=%s, matched_amount=%s, match_confidence=%s, banking_transaction_id=%s, match_method=%s WHERE id=%s",
                        (tdate, debit, strat["conf"], txid, strat["label"], pid)
                    )
                matched_here = True
                break

        if matched_here:
            continue

        # Final fallback: between this due date and next scheduled due date-1, vendor filtered
        cur.execute(
            "SELECT MIN(due_date) FROM payday_loan_payments WHERE loan_id=%s AND due_date > %s",
            (loan_id, due)
        )
        next_due = cur.fetchone()[0]
        if next_due:
            cur.execute(
                """
                SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
                FROM banking_transactions
                WHERE transaction_date >= %s AND transaction_date < %s
                  AND debit_amount IS NOT NULL AND ABS(debit_amount - %s) < 0.01
                  AND LOWER(description) LIKE %s
                ORDER BY transaction_date ASC
                LIMIT 5
                """,
                (due, next_due, amt, f"%{vendor_filter_default.lower()}%")
            )
            rows = cur.fetchall()
            if rows:
                print(f"\nDue {due} ${amt:,.2f} candidates (between due and next due):")
                for (txid, tdate, desc, debit, credit) in rows:
                    print(f"  • TX {txid}  {tdate}  ${debit or 0:,.2f}  {desc}")
                txid, tdate, desc, debit, credit = rows[0]
                if apply:
                    cur.execute(
                        "UPDATE payday_loan_payments SET status='matched', paid_date=%s, matched_amount=%s, match_confidence=%s, banking_transaction_id=%s, match_method=%s WHERE id=%s",
                        (tdate, debit, Decimal('0.92'), txid, 'between due->next, vendor', pid)
                    )
                continue

        print(f"\nDue {due} ${amt:,.2f}: no candidates found in banking_transactions within escalated windows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes (create loan, schedule, and persist matches)')
    # Loan details overrides
    ap.add_argument('--lender', help='Lender name (e.g., National Money Mart)')
    ap.add_argument('--agreement-date', dest='agreement_date', help='Agreement date (YYYY-MM-DD or M/D/YYYY)')
    ap.add_argument('--principal', help='Principal amount (e.g., 1420.00)')
    ap.add_argument('--fee-total', dest='fee_total', help='Total borrowing cost/fees (e.g., 213.00)')
    ap.add_argument('--apr', help='APR percent (e.g., 160.32)')
    ap.add_argument('--term-days', dest='term_days', type=int, help='Loan term in days')
    ap.add_argument('--total-repay', dest='total_repay', help='Total to be repaid (e.g., 1633.00)')
    ap.add_argument('--notes', help='Notes to store with the loan record')
    # Schedule
    ap.add_argument('--due', action='append', help='Due date (repeat for each due date), accepts YYYY-MM-DD or M/D/YYYY')
    ap.add_argument('--due-dates', dest='due_dates', help='Comma-separated due dates')
    ap.add_argument('--installment-amount', dest='installment_amount', help='Installment amount for each due (e.g., 408.25); if omitted, split total_repay evenly')
    # Matching options
    ap.add_argument('--vendor', default='money mart', help='Vendor keyword to filter descriptions (default: money mart)')
    args = ap.parse_args()

    conn = connect()
    try:
        cur = conn.cursor()
        ensure_schema(cur)
        # Override defaults if args provided
        build_from_args(args)
        loan_id = upsert_loan(cur)
        ensure_schedule(cur, loan_id)
        if args.write:
            conn.commit()
        match_payments(cur, loan_id, apply=args.write, vendor_filter_default=args.vendor)
        if args.write:
            conn.commit()
            print("\nSaved matches.")
        else:
            print("\nDry-run only. Re-run with --write to persist matches.")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
