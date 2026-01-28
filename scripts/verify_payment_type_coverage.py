#!/usr/bin/env python3
"""
Summarize linkage coverage by payment type for revenue receipts, and orphan status for payments.
Reports counts, sums, and linkage percentages.
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    print("="*80)
    print("REVENUE RECEIPTS COVERAGE BY TYPE")
    print("="*80)

    cur.execute(
        """
        WITH categorized AS (
            SELECT 
                CASE 
                    WHEN vendor_name ILIKE '%square%' THEN 'SQUARE'
                    WHEN vendor_name ILIKE '%email%transfer%' OR vendor_name ILIKE '%e-transfer%' OR vendor_name ILIKE '%etransfer%' OR description ILIKE 'Internet Banking E-TRANSFER%' THEN 'E-TRANSFER'
                    WHEN vendor_name ILIKE '%customer%deposit%' THEN 'CUSTOMER_DEPOSIT'
                    WHEN vendor_name ILIKE '%cash%deposit%' OR vendor_name ILIKE '%owner%cash%' THEN 'CASH'
                    WHEN vendor_name ILIKE '%check%' OR vendor_name ILIKE '%cheque%' THEN 'CHECK'
                    WHEN vendor_name ILIKE '%refund%' OR vendor_name ILIKE '%reversal%' THEN 'REFUND'
                    ELSE 'OTHER'
                END AS payment_type,
                revenue,
                (CASE WHEN charter_id IS NOT NULL OR reserve_number IS NOT NULL THEN 1 ELSE 0 END) AS linked
            FROM receipts
            WHERE revenue > 0
        )
        SELECT payment_type,
               COUNT(*) AS cnt,
               COALESCE(SUM(revenue), 0) AS total_revenue,
               SUM(linked) AS linked_cnt,
               COUNT(*) - SUM(linked) AS unlinked_cnt
        FROM categorized
        GROUP BY payment_type
        ORDER BY total_revenue DESC
        """
    )
    rows = cur.fetchall()
    for payment_type, cnt, total_rev, linked_cnt, unlinked_cnt in rows:
        pct_linked = (linked_cnt / cnt * 100.0) if cnt else 0.0
        print(f"{payment_type:18} | Count: {cnt:5} | Revenue: ${total_rev:12,.2f} | Linked: {linked_cnt:5} ({pct_linked:5.1f}%) | Missing: {unlinked_cnt:5}")

    print("\n" + "="*80)
    print("PAYMENTS ORPHAN STATUS")
    print("="*80)

    # Total payments
    cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payments")
    total_payments, total_amount = cur.fetchone()
    print(f"Total payments: {total_payments:,} | ${total_amount:,.2f}")

    # With reserve_number
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
    """)
    rn_cnt, rn_sum = cur.fetchone()
    print(f"With reserve_number: {rn_cnt:,} | ${rn_sum:,.2f} ({rn_cnt/total_payments*100:.1f}%)")

    # Orphans (no reserve_number and no charter_id)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments
        WHERE (reserve_number IS NULL OR reserve_number='') AND charter_id IS NULL
    """)
    orphan_cnt, orphan_sum = cur.fetchone()
    print(f"Orphan payments: {orphan_cnt:,} | ${orphan_sum:,.2f} ({orphan_cnt/total_payments*100:.1f}%)")

    # Square orphan
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments
        WHERE square_payment_id IS NOT NULL AND (reserve_number IS NULL OR reserve_number='')
    """)
    sq_orphan_cnt, sq_orphan_sum = cur.fetchone()
    print(f"Orphan Square: {sq_orphan_cnt:,} | ${sq_orphan_sum:,.2f}")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    cur.execute("""
        SELECT 
            COUNT(*) as total_revenue_receipts,
            COALESCE(SUM(revenue),0) as total_revenue,
            SUM(CASE WHEN charter_id IS NOT NULL OR reserve_number IS NOT NULL THEN 1 ELSE 0 END) as linked,
            SUM(CASE WHEN charter_id IS NULL AND reserve_number IS NULL THEN 1 ELSE 0 END) as not_linked
        FROM receipts
        WHERE revenue > 0
    """)
    tr, rev, linked, not_linked = cur.fetchone()
    print(f"Revenue receipts: {tr:,} | Revenue: ${rev:,.2f} | Linked: {linked:,} ({linked/tr*100:.1f}%) | Missing: {not_linked:,} ({not_linked/tr*100:.1f}%)")

    cur.close(); conn.close()


if __name__ == "__main__":
    main()
