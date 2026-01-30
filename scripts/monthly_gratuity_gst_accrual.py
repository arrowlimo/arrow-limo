import os
import sys
from decimal import Decimal, ROUND_HALF_UP
import psycopg2
from psycopg2.extras import DictCursor


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def money(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.01'), ROUND_HALF_UP):,.2f}"


def fetch_monthly_controlled_gst(cur, year_filter=None):
    # Sum gst_amount by month for controlled gratuity lines
    sql = (
        """
        SELECT EXTRACT(YEAR FROM c.charter_date)::int AS y,
               EXTRACT(MONTH FROM c.charter_date)::int AS m,
               ROUND(SUM(COALESCE(cc.gst_amount, 0))::numeric, 2) AS gst_total
        FROM charter_charges cc
        JOIN charters c ON c.charter_id = cc.charter_id
        WHERE cc.gratuity_type = 'controlled'
          AND cc.gst_amount IS NOT NULL
          AND cc.gst_amount > 0
          AND c.charter_date IS NOT NULL
        {year_clause}
        GROUP BY y, m
        ORDER BY y, m
        """
    )
    year_clause = ""
    params = []
    if year_filter:
        year_clause = "AND EXTRACT(YEAR FROM c.charter_date) = %s"
        params.append(year_filter)
    cur.execute(sql.format(year_clause=year_clause), params)
    return cur.fetchall()


def existing_entry(cur, marker: str) -> bool:
    cur.execute("""
        SELECT 1 FROM unified_general_ledger
        WHERE description = %s
        LIMIT 1
    """, (marker,))
    return cur.fetchone() is not None


def post_month(cur, year: int, month: int, amount: Decimal, gst_account: str, revenue_account: str, apply: bool):
    marker = f"GST accrual controlled gratuity {year}-{month:02d}"
    if existing_entry(cur, marker):
        return False
    if apply:
        # Use first day of next month as accrual date or last day of current month; choose last day of month for clarity
        # Construct date string safely via SQL
        date_sql = "SELECT (DATE %s + INTERVAL '1 month') - INTERVAL '1 day'"
        cur.execute(date_sql, (f"{year}-{month:02d}-01",))
        txn_date = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO unified_general_ledger (transaction_date, account_code, account_name, description, debit_amount, credit_amount, source_system)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (txn_date, revenue_account, 'Gratuity Revenue', marker, str(amount), '0', 'system')
        )
        cur.execute(
            """
            INSERT INTO unified_general_ledger (transaction_date, account_code, account_name, description, debit_amount, credit_amount, source_system)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (txn_date, gst_account, 'GST Payable', marker, '0', str(amount), 'system')
        )
    return True


def main():
    apply = '--apply' in sys.argv
    # Optional filters: --year 2025
    year_filter = None
    for i, a in enumerate(sys.argv):
        if a == '--year' and i + 1 < len(sys.argv):
            try:
                year_filter = int(sys.argv[i + 1])
            except ValueError:
                pass

    gst_account = os.getenv('GST_PAYABLE_ACCOUNT', '2100')
    revenue_account = os.getenv('GRATUITY_REVENUE_ACCOUNT', '4150')

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        rows = fetch_monthly_controlled_gst(cur, year_filter)
        print("=== Monthly GST Accrual (Controlled Gratuity) ===")
        total = Decimal('0.00')
        for r in rows:
            y, m, amt = r['y'], r['m'], Decimal(str(r['gst_total']))
            total += amt
            status = 'posted' if False else 'pending'
            print(f"{y}-{m:02d}: GST {money(amt)} [{status}]")

        if apply:
            posted = 0
            for r in rows:
                y, m, amt = r['y'], r['m'], Decimal(str(r['gst_total']))
                if amt <= 0:
                    continue
                ok = post_month(cur, y, m, amt, gst_account, revenue_account, True)
                if ok:
                    posted += 1
            conn.commit()
            print(f"Applied {posted} monthly accrual entries. Total GST: {money(total)}")
        else:
            print(f"Dry-run: Total GST to accrue: {money(total)}")
            print("Use --apply to post monthly entries. Optional filter: --year 2025")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
