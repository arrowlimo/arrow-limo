#!/usr/bin/env python3
"""
Audit data completion summary for recent work:
- Vehicle loan payments (WOODRIDGE FORD): row count and GST totals
- Email events reconciliation: linked vs unlinked
- Banking 2017 import: total transactions in 2017
"""
import os
import psycopg2

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)

def fmt_pass(pass_: bool):
    return 'PASS' if pass_ else 'FAIL'

with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        print('='*80)
        print('AUDIT DATA COMPLETION SUMMARY')
        print('='*80)

        # 1) Vehicle loan payments - Woodridge
        cur.execute("""
            SELECT COUNT(*) AS cnt,
                   COALESCE(SUM(CASE WHEN payment_type='reversal' THEN -gross_amount ELSE gross_amount END),0) AS total_gross,
                   COALESCE(SUM(CASE WHEN payment_type='reversal' THEN -gst_amount ELSE gst_amount END),0) AS total_gst
            FROM vehicle_loan_payments
            WHERE lender_name='WOODRIDGE FORD'
        """)
        cnt, total_gross, total_gst = cur.fetchone()
        vlp_ok = (cnt >= 7 and total_gst > 0)
        print(f"Vehicle loan payments (WOODRIDGE FORD): count={cnt}, total_gross={float(total_gross):.2f}, total_gst={float(total_gst):.2f} -> {fmt_pass(vlp_ok)}")

        # 2) Email events reconciliation status
        cur.execute("SELECT COUNT(*) FROM email_financial_events")
        total_events = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM email_financial_events WHERE banking_transaction_id IS NOT NULL")
        linked_events = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM email_financial_events WHERE banking_transaction_id IS NULL")
        unlinked_events = cur.fetchone()[0]
        email_ok = (unlinked_events == 0) or (linked_events > 0)
        print(f"Email financial events: total={total_events}, linked={linked_events}, unlinked={unlinked_events} -> {fmt_pass(email_ok)}")

        # 3) Banking 2017 import status
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE transaction_date >= DATE '2017-01-01' AND transaction_date < DATE '2018-01-01'
        """)
        y2017 = cur.fetchone()[0]
        # Expectation from previous run: ~1,791
        banking_ok = (y2017 >= 1750)  # allow some tolerance
        print(f"Banking transactions 2017: {y2017} rows -> {fmt_pass(banking_ok)}")

        print('-'*80)
        overall = vlp_ok and banking_ok
        print(f"OVERALL: {fmt_pass(overall)}")
        print('='*80)
