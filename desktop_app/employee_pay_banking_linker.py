"""Auto-link pending employee pay transactions to banking transactions."""

from __future__ import annotations

import logging
from datetime import timedelta

from db_error_handling import DatabaseContext

logger = logging.getLogger(__name__)


def _method_predicate(method: str) -> tuple[str, list[str]]:
    method_up = (method or "").upper().strip()
    if method_up == "E-TRANSFER":
        sql = (
            "(LOWER(COALESCE(bt.description, '')) LIKE %s "
            "OR LOWER(COALESCE(bt.description, '')) LIKE %s "
            "OR LOWER(COALESCE(bt.description, '')) LIKE %s "
            "OR LOWER(COALESCE(bt.description, '')) LIKE %s)"
        )
        return sql, ["%transfer%", "%e-transfer%", "%etransfer%", "%interac%"]

    if method_up == "DIRECT_DEPOSIT":
        sql = (
            "(LOWER(COALESCE(bt.description, '')) LIKE %s "
            "OR LOWER(COALESCE(bt.description, '')) LIKE %s "
            "OR LOWER(COALESCE(bt.description, '')) LIKE %s)"
        )
        return sql, ["%direct deposit%", "%payroll%", "%deposit%"]

    return "1=1", []


def auto_link_pending_employee_pay_transactions(
    db_or_conn,
    employee_id: int | None = None,
    pay_period_id: int | None = None,
    fiscal_year: int | None = None,
    max_rows: int = 200,
) -> int:
    """Link pending employee pay rows to banking transactions by method + amount.

    Intended behavior:
    - Rows with bank_link_status='PENDING_BANK_MATCH' are candidates.
    - A candidate banking row must have matching amount and an expected method hint
      in description (for e-transfer/direct deposit).
    - Rows are linked one-to-one (a banking transaction can be used once).
    """
    if max_rows <= 0:
        return 0

    linked_count = 0
    conn = db_or_conn.conn if hasattr(db_or_conn, "conn") else db_or_conn

    try:
        with DatabaseContext(conn, auto_commit=False) as cur:
            sql = [
                "SELECT transaction_id, employee_id, fiscal_year, pay_period_id,",
                "       transaction_date, amount, payment_method",
                "FROM employee_pay_transactions",
                "WHERE COALESCE(bank_link_status, '') = 'PENDING_BANK_MATCH'",
                "  AND banking_transaction_id IS NULL",
            ]
            params: list[object] = []

            if employee_id:
                sql.append("AND employee_id = %s")
                params.append(int(employee_id))
            if pay_period_id:
                sql.append("AND pay_period_id = %s")
                params.append(int(pay_period_id))
            if fiscal_year:
                sql.append("AND fiscal_year = %s")
                params.append(int(fiscal_year))

            sql.append("ORDER BY transaction_date NULLS LAST, transaction_id")
            sql.append("LIMIT %s")
            params.append(int(max_rows))

            cur.execute("\n".join(sql), params)
            pending_rows = cur.fetchall()

        if not pending_rows:
            return 0

        with DatabaseContext(conn, auto_commit=True) as cur:
            for (
                pay_tx_id,
                _emp_id,
                _fy,
                _ppid,
                pay_date,
                amount,
                method,
            ) in pending_rows:
                if pay_date is None:
                    continue

                amount_val = float(amount or 0)
                if amount_val <= 0:
                    continue

                method_sql, method_params = _method_predicate(method)
                window_start = pay_date - timedelta(days=3)
                window_end = pay_date + timedelta(days=120)

                candidate_sql = [
                    "SELECT bt.transaction_id, bt.transaction_date,",
                    "       LOWER(COALESCE(bt.description, '')) AS desc_lc,",
                    "       COALESCE(bt.debit_amount, 0) AS debit_amount,",
                    "       COALESCE(bt.credit_amount, 0) AS credit_amount",
                    "FROM banking_transactions bt",
                    "WHERE bt.transaction_date BETWEEN %s AND %s",
                    "  AND (ABS(COALESCE(bt.debit_amount, 0) - %s) <= 0.01",
                    "       OR ABS(COALESCE(bt.credit_amount, 0) - %s) <= 0.01)",
                    "  AND NOT EXISTS (",
                    "      SELECT 1 FROM employee_pay_transactions ept",
                    "      WHERE ept.banking_transaction_id = bt.transaction_id",
                    "  )",
                    f"  AND {method_sql}",
                    "ORDER BY ABS(bt.transaction_date - %s), bt.transaction_id",
                    "LIMIT 1",
                ]

                candidate_params: list[object] = [
                    window_start,
                    window_end,
                    amount_val,
                    amount_val,
                ]
                candidate_params.extend(method_params)
                candidate_params.append(pay_date)

                cur.execute("\n".join(candidate_sql), candidate_params)
                candidate = cur.fetchone()
                if not candidate:
                    continue

                bank_tx_id = int(candidate[0])
                cur.execute(
                    """
                    UPDATE employee_pay_transactions
                    SET banking_transaction_id = %s,
                        bank_link_status = 'LINKED',
                        bank_matched_at = NOW()
                    WHERE transaction_id = %s
                    """,
                    (bank_tx_id, int(pay_tx_id)),
                )
                linked_count += 1

    except Exception as exc:
        logger.warning("Employee-pay auto-link skipped due to error: %s", exc)
        return linked_count

    return linked_count
