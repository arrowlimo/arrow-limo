"""
Read-only verification to ensure no data was doubled.

Checks performed:
- payments: duplicate logical rows by (reserve_number, amount, payment_date[date])
- payments: residual 2025-07-24 duplicates (batch import) count
- receipts: duplicate source_hash if present
- external_documents: duplicate sha256 if table present

This script makes NO WRITES.
"""
import os
import sys
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        )
        """,
        (table_name,)
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


def check_payments(cur):
    print("\n== payments checks ==")
    if not table_exists(cur, 'payments'):
        print("payments table not found; skipping")
        return
    cols = set(columns(cur, 'payments'))

    date_col = None
    for cand in ('payment_date', 'created_at', 'updated_at', 'last_updated'):
        if cand in cols:
            date_col = cand
            break
    if not {'reserve_number', 'amount'}.issubset(cols) or not date_col:
        print("payments lacks required columns for duplicate check; skipping logical dup check")
    else:
        # Duplicate logical rows by reserve_number + amount + date (date-only)
        cur.execute(
            f"""
            SELECT reserve_number, amount, CAST({date_col} AS DATE) AS d, COUNT(*)
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number, amount, CAST({date_col} AS DATE)
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, d DESC
            LIMIT 50
            """
        )
        dups = cur.fetchall()
        print(f"Logical duplicates (reserve_number, amount, {date_col}[date]) -> {len(dups)}")
        if dups:
            for r in dups[:10]:
                print("  ", r)

    # Residual 2025-07-24 batch import duplicates
    if 'payment_date' in cols:
        cur.execute("SELECT COUNT(*) FROM payments WHERE payment_date = DATE '2025-07-24'")
    elif 'created_at' in cols:
        cur.execute("SELECT COUNT(*) FROM payments WHERE CAST(created_at AS DATE) = DATE '2025-07-24'")
    else:
        cur.execute("SELECT 0")
    july_cnt = cur.fetchone()[0]
    print(f"Rows on 2025-07-24: {july_cnt}")


def check_receipts(cur):
    print("\n== receipts checks ==")
    if not table_exists(cur, 'receipts'):
        print("receipts table not found; skipping")
        return
    cols = set(columns(cur, 'receipts'))
    if 'source_hash' in cols:
        cur.execute(
            """
            SELECT source_hash, COUNT(*)
            FROM receipts
            WHERE source_hash IS NOT NULL
            GROUP BY source_hash
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 50
            """
        )
        dups = cur.fetchall()
        print(f"Duplicate receipts by source_hash -> {len(dups)}")
        if dups:
            for r in dups[:10]:
                print("  ", r)
    else:
        print("receipts.source_hash not present; skipping strict dup check (business rules avoid naive dedupe)")


def check_external_documents(cur):
    print("\n== external_documents checks ==")
    if not table_exists(cur, 'external_documents'):
        print("external_documents table not found; skipping")
        return
    cols = set(columns(cur, 'external_documents'))
    if 'sha256' in cols:
        cur.execute(
            """
            SELECT sha256, COUNT(*)
            FROM external_documents
            WHERE sha256 IS NOT NULL
            GROUP BY sha256
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 50
            """
        )
        dups = cur.fetchall()
        print(f"Duplicate documents by sha256 -> {len(dups)}")
        if dups:
            for r in dups[:10]:
                print("  ", r)
    else:
        print("external_documents.sha256 not present; skipping hash dup check")


def main():
    conn = connect()
    try:
        cur = conn.cursor()
        check_payments(cur)
        check_receipts(cur)
        check_external_documents(cur)
        cur.close()
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Verification failed: {e}", file=sys.stderr)
        sys.exit(2)
