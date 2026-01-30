import os
import sys
from decimal import Decimal, ROUND_HALF_UP
import psycopg2
from psycopg2.extras import DictCursor
from datetime import date

GST_RATE = Decimal('0.05')


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def fetch_controlled_totals(cur):
    cur.execute("""
        SELECT SUM(amount) AS gross, SUM(gst_amount) AS gst
        FROM charter_charges
        WHERE gratuity_type = 'controlled'
          AND gst_amount IS NOT NULL
          AND gst_amount > 0
    """)
    row = cur.fetchone()
    gross = row[0] or 0
    gst = row[1] or 0
    return Decimal(str(gross)), Decimal(str(gst))


def existing_entry(cur, marker: str) -> bool:
    cur.execute("""
        SELECT 1 FROM unified_general_ledger
        WHERE description = %s
        LIMIT 1
    """, (marker,))
    return cur.fetchone() is not None


def create_journal_entries(cur, gst_amount: Decimal, marker: str, gst_account: str, revenue_account: str, apply: bool):
    # Debit gratuity revenue (reduce revenue), Credit GST payable
    today = date.today()
    if apply:
        # Insert two rows to unified_general_ledger maintaining double-entry
        cur.execute("""
            INSERT INTO unified_general_ledger (transaction_date, account_code, account_name, description, debit_amount, credit_amount, source_system)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (today, revenue_account, 'Gratuity Revenue', marker, str(gst_amount), '0', 'system'))
        cur.execute("""
            INSERT INTO unified_general_ledger (transaction_date, account_code, account_name, description, debit_amount, credit_amount, source_system)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (today, gst_account, 'GST Payable', marker, '0', str(gst_amount), 'system'))


def main():
    apply = '--apply' in sys.argv
    gst_account = '2100'  # Placeholder; adjust to actual GST payable account code
    revenue_account = '4150'  # Gratuity revenue
    marker = 'GST reclass controlled gratuity (one-time)'

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        gross, gst = fetch_controlled_totals(cur)
        print(f"Controlled Gross: {gross:.2f}")
        print(f"Controlled GST Portion: {gst:.2f}")
        if existing_entry(cur, marker):
            print("Journal entry already exists with this marker. No action taken.")
            return
        if apply:
            create_journal_entries(cur, gst, marker, gst_account, revenue_account, True)
            conn.commit()
            print(f"Applied journal reclass: Debit {revenue_account} / Credit {gst_account} {gst:.2f}")
        else:
            print(f"Dry-run: Would create Debit {revenue_account} {gst:.2f} / Credit {gst_account} {gst:.2f} with marker '{marker}'")
            print("Use --apply to commit.")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
