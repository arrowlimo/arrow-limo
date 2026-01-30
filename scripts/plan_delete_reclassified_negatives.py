"""
Plan the safe deletion of reclassified negative payments (pre-2025).

Reads the plan CSV produced by reclassify_negative_payments_pre2025.py and:
- Verifies a corresponding receipts row exists for each payment via source_hash
- Enumerates FK dependencies referencing payments.payment_id and counts rows
- Emits a Markdown and CSV report detailing what would be deleted and impacted

Dry-run only. No database writes performed.
"""
import os
import sys
import csv
from datetime import date, datetime
import psycopg2


REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
DEFAULT_PLAN = os.path.join(REPORTS_DIR, 'reclassify_negative_payments_plan_pre2025.csv')


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def table_exists(cur, name: str) -> bool:
    cur.execute(
        """SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)""",
        (name,)
    )
    return cur.fetchone()[0]


def get_fk_references(cur, schema: str, table: str):
    """Return a list of (fk_table, fk_column) that reference schema.table's primary key.
    We specifically look for FKs referencing payments.payment_id.
    """
    cur.execute(
        """
        SELECT
            tc.table_name AS fk_table,
            kcu.column_name AS fk_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_schema = %s
          AND ccu.table_name = %s
          AND ccu.column_name = 'payment_id'
        ORDER BY fk_table
        """,
        (schema, table)
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


def main(plan_path: str = DEFAULT_PLAN):
    if not os.path.exists(plan_path):
        print(f"Plan CSV not found: {plan_path}")
        sys.exit(2)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_md = os.path.join(REPORTS_DIR, f'delete_reclassified_negatives_plan_{ts}.md')
    out_csv = os.path.join(REPORTS_DIR, f'delete_reclassified_negatives_targets_{ts}.csv')

    # Load plan rows
    targets = []
    with open(plan_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                targets.append({
                    'payment_id': int(row['payment_id']),
                    'source_hash': row.get('source_hash') or '',
                    'reserve_number': row.get('reserve_number'),
                    'receipt_date': row.get('receipt_date'),
                    'gross_amount': float(row.get('gross_amount') or 0),
                })
            except Exception:
                continue

    if not targets:
        print('No targets found in plan CSV.')
        sys.exit(0)

    conn = connect()
    cur = conn.cursor()

    if not table_exists(cur, 'payments') or not table_exists(cur, 'receipts'):
        print('Required tables not found (payments/receipts).')
        sys.exit(2)

    # Verify receipts exist for each source_hash
    with_receipt = 0
    missing_receipt = []
    for t in targets:
        cur.execute("SELECT 1 FROM receipts WHERE source_hash = %s LIMIT 1", (t['source_hash'],))
        if cur.fetchone():
            with_receipt += 1
        else:
            missing_receipt.append(t)

    # FK references to payments.payment_id
    fk_refs = get_fk_references(cur, 'public', 'payments')
    fk_counts = []
    id_list = tuple(t['payment_id'] for t in targets)
    for fk_table, fk_col in fk_refs:
        # Count rows in each dependent table
        cur.execute(f"SELECT COUNT(*) FROM {fk_table} WHERE {fk_col} = ANY(%s)", (list(id_list),))
        cnt = cur.fetchone()[0]
        fk_counts.append((fk_table, fk_col, cnt))

    # Emit CSV of payment_ids to delete
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['payment_id'])
        for t in targets:
            w.writerow([t['payment_id']])

    # Emit Markdown summary
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write(f"# Deletion Plan: Reclassified Negative Payments\n\n")
        f.write(f"Generated: {ts}\n\n")
        f.write(f"Plan CSV input: {plan_path}\n\n")
        f.write(f"Total targets in plan: {len(targets)}\n\n")
        f.write(f"Receipts verified (by source_hash): {with_receipt}\n\n")
        f.write(f"Missing receipts: {len(missing_receipt)}\n\n")
        if missing_receipt:
            f.write("## Missing Receipts (first 20)\n")
            f.write("payment_id | reserve_number | gross_amount | receipt_date\n")
            f.write("---|---|---|---\n")
            for m in missing_receipt[:20]:
                f.write(f"{m['payment_id']}|{m['reserve_number']}|{m['gross_amount']}|{m['receipt_date']}\n")
            f.write("\n")

        f.write("## FK Dependencies referencing payments.payment_id\n")
        f.write("table | column | rows_referencing_targets\n")
        f.write("---|---|---\n")
        for fk_table, fk_col, cnt in fk_counts:
            f.write(f"{fk_table}|{fk_col}|{cnt}\n")
        f.write("\n")

        f.write(f"Targets CSV: {out_csv}\n")

    print(f"Plan written:\n - {out_md}\n - {out_csv}")
    print(f"Receipts verified: {with_receipt} / {len(targets)}")
    if missing_receipt:
        print(f"WARNING: {len(missing_receipt)} plan rows have no matching receipts by source_hash")

    cur.close(); conn.close()


if __name__ == '__main__':
    plan = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAN
    main(plan)
