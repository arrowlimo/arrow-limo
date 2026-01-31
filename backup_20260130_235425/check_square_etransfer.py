#!/usr/bin/env python3
"""
Check whether Square and Interac e-Transfer transactions were added to the receipts table.
Print counts, total inflow, and a few sample rows for each.
"""
import os
import psycopg2

DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))


def summary(cur, label: str, where_sql: str, params: tuple = ()):  # type: ignore
    inflow_sql = f"""
        SELECT 
            COUNT(*) AS rows,
            COALESCE(SUM(CASE 
                WHEN COALESCE(revenue,0) > 0 THEN revenue
                WHEN expense < 0 THEN ABS(expense)
                ELSE 0 END), 0) AS inflow
        FROM receipts
        WHERE {where_sql}
    """
    cur.execute(inflow_sql)
    rows, inflow = cur.fetchone()
    print(f"\n=== {label} ===")
    print(f"Rows: {rows}")
    print(f"Total inflow: ${float(inflow or 0):,.2f}")

    sample_sql = f"""
        SELECT receipt_date, vendor_name, category, expense_account, 
               revenue, expense
        FROM receipts
        WHERE {where_sql}
        ORDER BY receipt_date DESC
        LIMIT 10
    """
    cur.execute(sample_sql)
    sample = cur.fetchall()
    if sample:
        print("Samples (latest 10):")
        for r in sample:
            rd, vn, cat, acct, rev, exp = r
            inflow = (rev or 0) if (rev or 0) > 0 else (abs(exp) if (exp or 0) < 0 else 0)
            print(f"  {rd} | {vn[:50]} | {cat or ''} | {acct or ''} | inflow=${inflow:,.2f}")
    else:
        print("No sample rows found.")


def main():
    with psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT) as conn:
        with conn.cursor() as cur:
            # Square indicators: vendor name contains SQUARE or SQ *
            square_where = "(vendor_name ILIKE '%SQUARE%' OR vendor_name ILIKE 'REVENUE - SQUARE%') AND (COALESCE(revenue,0) > 0 OR expense < 0)"
            summary(cur, 'SQUARE (Deposits)', square_where)

            # e-Transfer indicators: INTERAC, E-TRANSFER, ETRANSFER, EMT
            etrans_where = (
                "(vendor_name ILIKE '%INTERAC%' OR vendor_name ILIKE '%E-TRANSFER%' OR "
                " vendor_name ILIKE '%ETRANSFER%' OR vendor_name ILIKE '%E TRANSFER%' OR vendor_name ILIKE '%EMT%') "
                " AND (COALESCE(revenue,0) > 0 OR expense < 0)"
            )
            summary(cur, 'INTERAC e-Transfer (Deposits)', etrans_where)


if __name__ == '__main__':
    main()
