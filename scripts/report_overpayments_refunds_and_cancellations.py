#!/usr/bin/env python
"""
Report:
- Overpaid charters (expected_balance < 0) and whether refunds exist
- Cancelled charters with deposits/retainers to classify as non-refundable retainers

Outputs CSVs under reports/:
- overpaid_charters_with_refunds.csv
- cancelled_charters_with_deposits.csv
"""
import os
import csv
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def table_exists(cur, name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema='public' AND table_name=%s
        )
        """,
        (name,)
    )
    return cur.fetchone()[0]


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s AND column_name=%s
        )
        """,
        (table, column)
    )
    return cur.fetchone()[0]


def main():
    conn = get_conn()
    cur = conn.cursor()

    os.makedirs("reports", exist_ok=True)

    # 1) Overpaid charters with refund check (robust mapping by reserve_number or charter_id)
    has_refunds = table_exists(cur, "charter_refunds")
    refunds_has_reserve = False
    if has_refunds:
        refunds_has_reserve = column_exists(cur, "charter_refunds", "reserve_number")

        # Compose SQL with flexible refunds aggregation
    if has_refunds:
        refunds_sql_parts = []
        if refunds_has_reserve:
            refunds_sql_parts.append(
                """
                SELECT r.reserve_number::text AS reserve_number, COALESCE(SUM(r.amount),0) AS refunds_sum
                FROM charter_refunds r
                WHERE r.reserve_number IS NOT NULL AND r.reserve_number <> ''
                GROUP BY r.reserve_number
                """
            )
        refunds_sql_parts.append(
            """
            SELECT c.reserve_number::text AS reserve_number, COALESCE(SUM(r.amount),0) AS refunds_sum
            FROM charter_refunds r
            JOIN charters c ON c.charter_id = r.charter_id
            GROUP BY c.reserve_number
            """
        )
        refunds_union = " UNION ALL ".join(refunds_sql_parts)
        refunds_cte = f"""
            refunds AS (
              SELECT reserve_number, SUM(refunds_sum) AS refunds_sum
              FROM (
                {refunds_union}
              ) uu
              GROUP BY reserve_number
            )
        """
    else:
        refunds_cte = """refunds AS (
            SELECT NULL::text AS reserve_number, 0::numeric AS refunds_sum
        )"""

    cur.execute(
        f"""
        WITH payments AS (
          SELECT charter_id::text AS reserve_number, COALESCE(SUM(amount),0) AS payments_sum
          FROM charter_payments
          GROUP BY charter_id
        ),
        {refunds_cte},
        totals AS (
          SELECT c.charter_id, c.reserve_number,
                 COALESCE(c.total_amount_due,0) AS total_due,
                 COALESCE(p.payments_sum,0) AS payments_sum,
                 COALESCE(r.refunds_sum,0) AS refunds_sum,
                 COALESCE(c.paid_amount,0) AS paid_amount,
                 COALESCE(c.balance,0) AS balance
          FROM charters c
          LEFT JOIN payments p ON p.reserve_number = c.reserve_number::text
          LEFT JOIN refunds  r ON r.reserve_number = c.reserve_number::text
        )
        SELECT charter_id, reserve_number, total_due, payments_sum, refunds_sum,
               (payments_sum - refunds_sum) AS net_paid,
               (COALESCE(total_due,0) - (payments_sum - refunds_sum)) AS expected_balance
        FROM totals
        WHERE (COALESCE(total_due,0) - (payments_sum - refunds_sum)) < 0
        ORDER BY (payments_sum - refunds_sum) - COALESCE(total_due,0) DESC
        """
    )
    overpaid = cur.fetchall()

    overpaid_path = os.path.join("reports", "overpaid_charters_with_refunds.csv")
    with open(overpaid_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["charter_id","reserve_number","total_due","payments_sum","refunds_sum","net_paid","expected_balance","refunds_present"])
        for cid, res, total_due, pay_sum, ref_sum, net_paid, expected in overpaid:
            refunds_present = (ref_sum or 0) > 0
            w.writerow([cid, res, float(total_due or 0), float(pay_sum or 0), float(ref_sum or 0), float(net_paid or 0), float(expected or 0), refunds_present])

    # 2) Cancelled charters with deposits/retainers (broadened detection)
    has_booking_status = column_exists(cur, "charters", "booking_status")
    has_status = column_exists(cur, "charters", "status")

    cancelled_predicates = ["(cancelled = TRUE)"]
    if has_booking_status:
        cancelled_predicates.append("(LOWER(COALESCE(booking_status,'')) IN ('cancelled','canceled'))")
    if has_status:
        cancelled_predicates.append("(LOWER(COALESCE(status,'')) IN ('cancelled','canceled'))")

    cancelled_where = "(" + " OR ".join(cancelled_predicates) + ")"

    cur.execute(
        f"""
        SELECT charter_id, reserve_number, client_id, charter_date,
               COALESCE(retainer_amount,0) AS retainer_amount,
               COALESCE(deposit,0) AS deposit,
               COALESCE(total_amount_due,0) AS total_due,
               COALESCE(paid_amount,0) AS paid_amount
        FROM charters
        WHERE {cancelled_where}
          AND (
                COALESCE(retainer_amount,0) > 0 OR COALESCE(deposit,0) > 0
                OR (COALESCE(paid_amount,0) > 0 AND COALESCE(total_amount_due,0) = 0)
              )
        ORDER BY charter_date NULLS LAST
        """
    )
    cancelled_with_deposits = cur.fetchall()

    cancelled_path = os.path.join("reports", "cancelled_charters_with_deposits.csv")
    with open(cancelled_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["charter_id","reserve_number","client_id","charter_date","retainer_amount","deposit","total_due","paid_amount","candidate_nonrefundable_retainer"])
        for row in cancelled_with_deposits:
            cid, res, client_id, date, ret_amt, deposit, total_due, paid_amount = row
            candidate = (ret_amt or 0) > 0 or (deposit or 0) > 0 or ((paid_amount or 0) > 0 and (total_due or 0) == 0)
            w.writerow([cid, res, client_id, date, float(ret_amt or 0), float(deposit or 0), float(total_due or 0), float(paid_amount or 0), candidate])

    print("Reports written:")
    print(f"- {overpaid_path}")
    print(f"- {cancelled_path}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
