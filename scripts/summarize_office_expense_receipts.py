#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Summarize receipts created for office rent (Fibrenew/lease) and office utilities.

Outputs counts and totals overall and for the current year.
"""
import os
import psycopg2


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    db = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    pwd = os.getenv('DB_PASSWORD', '')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=db, user=user, password=pwd, port=port)


def summarize(cur, prefix: str):
    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(gross_amount),0)
        FROM receipts
        WHERE source_reference LIKE %s
        """,
        (prefix + '%',),
    )
    c_all, s_all = cur.fetchone()

    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(gross_amount),0)
        FROM receipts
        WHERE source_reference LIKE %s AND receipt_date >= date_trunc('year', CURRENT_DATE)
        """,
        (prefix + '%',),
    )
    c_y, s_y = cur.fetchone()

    return c_all, s_all, c_y, s_y


def main():
    conn = get_db_connection(); conn.autocommit = True
    cur = conn.cursor()
    rent_all, rent_sum, rent_y, rent_sum_y = summarize(cur, 'OFFICE_RENT_')
    util_all, util_sum, util_y, util_sum_y = summarize(cur, 'OFFICE_UTIL_')

    print('Office Rent Receipts:')
    print(f"  Total: {rent_all} | Sum: ${rent_sum:,.2f}")
    print(f"  {os.getenv('YEAR','current year')}: {rent_y} | Sum: ${rent_sum_y:,.2f}")
    print('Office Utilities Receipts:')
    print(f"  Total: {util_all} | Sum: ${util_sum:,.2f}")
    print(f"  {os.getenv('YEAR','current year')}: {util_y} | Sum: ${util_sum_y:,.2f}")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
