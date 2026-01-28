"""
Reclassify negative payments (pre-2025) into receipts (dry-run by default).

Safety & Rules:
- No duplication: build unique source_hash per payment; skip if already in receipts.
- GST included (AB 5%): gst = gross * 0.05 / 1.05; net = gross - gst.
- Read-only unless --write. On write, inserts into receipts; deletion from payments is deferred unless explicitly enabled later.

Outputs a CSV plan and a markdown summary in reports/.
"""
import os
import sys
import csv
import hashlib
import argparse
from datetime import date
import psycopg2

CUTOFF = date(2025, 1, 1)


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def table_exists(cur, name: str) -> bool:
    cur.execute(
        """SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)""",
        (name,)
    )
    return cur.fetchone()[0]


def columns(cur, table: str):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [r[0] for r in cur.fetchall()]


def gst_included(amount: float, rate=0.05):
    gross = abs(float(amount))
    gst = round(gross * rate / (1 + rate), 2)
    net = round(gross - gst, 2)
    return gst, net


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply inserts into receipts')
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()

    if not table_exists(cur, 'payments') or not table_exists(cur, 'receipts'):
        print('payments/receipts tables not found.')
        sys.exit(2)

    pcols = columns(cur, 'payments')
    rcols = columns(cur, 'receipts')

    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    date_col = None
    for c in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if c in pcols:
            date_col = c
            break
    if not amount_col or not date_col:
        print('payments missing amount/date columns.')
        sys.exit(2)

    # Pull negative payments pre-2025
    cur.execute(
        f"""
        SELECT payment_id, reserve_number, COALESCE({amount_col},0) AS amount,
               CAST({date_col} AS DATE) AS pdate,
               COALESCE(payment_key,'') AS payment_key,
               COALESCE(payment_method,'') AS payment_method
        FROM payments
        WHERE COALESCE({amount_col},0) < 0
          AND CAST({date_col} AS DATE) < %s
        ORDER BY pdate ASC
        """,
        (CUTOFF,)
    )
    rows = cur.fetchall()

    # Build plan and check if target receipt already exists by source_hash
    plan = []
    skipped_existing = 0
    for pid, rn, amt, pdate, pkey, pmethod in rows:
        h = hashlib.sha256(f'payments:{pid}:{amt}:{pdate}'.encode('utf-8')).hexdigest()
        # Does receipt with this hash already exist?
        exists = False
        if 'source_hash' in rcols:
            cur.execute("SELECT 1 FROM receipts WHERE source_hash = %s LIMIT 1", (h,))
            exists = cur.fetchone() is not None
        if exists:
            skipped_existing += 1
            continue
        gst, net = gst_included(amt, 0.05)
        plan.append({
            'payment_id': pid,
            'reserve_number': rn,
            'gross_amount': abs(float(amt)),
            'gst_amount': gst,
            'net_amount': net,
            'receipt_date': pdate,
            'source_hash': h,
            'category': 'expense_reclass',
            'vendor_name': pmethod or 'Unknown',
            'tax_rate': 0.05,
        })

    report_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(report_dir, exist_ok=True)
    ts = os.path.basename(report_dir)
    csv_path = os.path.join(report_dir, f'reclassify_negative_payments_plan_pre2025.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'payment_id','reserve_number','gross_amount','gst_amount','net_amount','receipt_date','source_hash','category','vendor_name','tax_rate'
        ])
        w.writeheader()
        w.writerows(plan)

    print(f"Candidates: {len(plan)} (skipped existing in receipts: {skipped_existing})")
    print('Plan CSV:', csv_path)

    if not args.write or not plan:
        conn.rollback()
        print('Dry-run complete. No inserts performed.')
        return

    # Build dynamic INSERT for receipts
    insert_cols = []
    mapping = {
        'gross_amount': 'gross_amount',
        'gst_amount': 'gst_amount',
        'net_amount': 'net_amount',
        'receipt_date': 'receipt_date',
        'vendor_name': 'vendor_name',
        'category': 'category',
        'tax_rate': 'tax_rate',
        'source_hash': 'source_hash',
        'is_taxable': 'is_taxable',
    }
    for k, col in mapping.items():
        if col in rcols:
            insert_cols.append(col)

    inserted = 0
    for item in plan:
        vals = []
        cols = []
        for k, col in mapping.items():
            if col in insert_cols:
                cols.append(col)
                if col == 'is_taxable':
                    vals.append(True)
                else:
                    vals.append(item.get(k))
        placeholders = ', '.join(['%s'] * len(cols))
        cur.execute(
            f"INSERT INTO receipts ({', '.join(cols)}) VALUES ({placeholders})",
            vals
        )
        inserted += 1

    conn.commit()
    print(f"Inserted into receipts: {inserted}")
    print("Deletion from payments is deferred (safeguard).")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
