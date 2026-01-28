#!/usr/bin/env python3
"""
Audit almsdata vs LMS for charters that should be zeroed out (cancelled or closed)
so we avoid taxing unpaid revenue. Gratuity GST is intentionally not flagged.

Finds:
- Cancelled with non-zero balance in almsdata
- Closed/complete with non-zero balance where LMS shows zero (write-off missing)
- Over-credit/refund cases

Outputs:
- reports/ALMS_LMS_BALANCE_AUDIT.csv
- reports/ALMS_LMS_BALANCE_AUDIT_SUMMARY.json
"""

import os
import csv
import json
from decimal import Decimal
import psycopg2
import pyodbc

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

LMS_PATH = r"L:\\limo\\backups\\lms.mdb"

ALLOWED_CLOSED_STATUSES = {"closed", "complete", "completed"}
CANCELLED_STATUSES = {"cancelled", "canceled"}

OUTPUT_CSV = r"L:\\limo\\reports\\ALMS_LMS_BALANCE_AUDIT.csv"
OUTPUT_JSON = r"L:\\limo\\reports\\ALMS_LMS_BALANCE_AUDIT_SUMMARY.json"


def get_alms_balances():
    """Aggregate almsdata balances by reserve."""
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            reserve_number,
            LOWER(COALESCE(status, '')) AS status,
            COALESCE(total_amount_due, 0) AS charter_total,
            COALESCE(paid_amount, 0) AS charter_paid,
            COALESCE(
                (SELECT SUM(amount) FROM charter_charges c WHERE c.reserve_number = ch.reserve_number), 0
            ) AS charges_total,
            COALESCE(
                (SELECT SUM(amount) FROM payments p WHERE p.reserve_number = ch.reserve_number), 0
            ) AS payments_total
        FROM charters ch
        WHERE reserve_number IS NOT NULL
        """
    )

    data = {}
    for row in cur.fetchall():
        reserve, status, charter_total, charter_paid, charges_total, payments_total = row
        balance = float(charges_total) - float(payments_total)
        data[reserve] = {
            "status": status,
            "charter_total": float(charter_total),
            "charter_paid": float(charter_paid),
            "charges_total": float(charges_total),
            "payments_total": float(payments_total),
            "balance": balance,
        }

    cur.close()
    conn.close()
    return data


def connect_lms():
    conn_str = r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_PATH + ";"
    return pyodbc.connect(conn_str)


def get_lms_state(reserve_number, conn):
    """Get LMS charge/payment totals using column introspection (robust to field names)."""
    cur = conn.cursor()

    # Charges
    charges_total = 0.0
    charge_count = 0
    try:
        cur.execute("SELECT TOP 1 * FROM Charge")
        cols = [d[0] for d in cur.description] if cur.description else []
        reserve_field = None
        amount_field = None
        for col in cols:
            cl = col.lower()
            if "reserve" in cl and ("no" in cl or "id" in cl):
                reserve_field = col
            if cl == "amount":
                amount_field = col
        if reserve_field and amount_field:
            cur.execute(f"SELECT SUM([{amount_field}]), COUNT(*) FROM Charge WHERE [{reserve_field}] = ?", (reserve_number,))
            row = cur.fetchone()
            charges_total = float(row[0] or 0)
            charge_count = row[1] or 0
    except Exception:
        pass

    # Payments
    payments_total = 0.0
    payment_count = 0
    try:
        cur.execute("SELECT TOP 1 * FROM Payment")
        cols = [d[0] for d in cur.description] if cur.description else []
        reserve_field = None
        amount_field = None
        for col in cols:
            cl = col.lower()
            if "reserve" in cl and ("no" in cl or "id" in cl):
                reserve_field = col
            if cl == "amount":
                amount_field = col
        if reserve_field and amount_field:
            cur.execute(f"SELECT SUM([{amount_field}]), COUNT(*) FROM Payment WHERE [{reserve_field}] = ?", (reserve_number,))
            row = cur.fetchone()
            payments_total = float(row[0] or 0)
            payment_count = row[1] or 0
    except Exception:
        pass

    cur.close()

    return {
        "charges_total": charges_total,
        "payments_total": payments_total,
        "balance": charges_total - payments_total,
        "charge_count": charge_count,
        "payment_count": payment_count,
    }


def categorize(reserve, alms, lms):
    status = alms["status"] or ""
    balance = alms["balance"]
    lms_balance = lms["balance"] if lms else None

    category = None
    action = None
    reason = None

    if status in CANCELLED_STATUSES:
        if abs(balance) > 0.01:
            category = "CANCELLED_NONZERO"
            action = "Remove charges / write off to zero in almsdata"
            reason = f"Cancelled but balance {balance:+.2f}"
        else:
            category = "CANCELLED_OK"
            action = "None"
            reason = "Cancelled and zeroed"
    elif status in ALLOWED_CLOSED_STATUSES:
        if abs(balance) > 0.01:
            if lms_balance is not None and abs(lms_balance) < 1.0:
                category = "WRITE_OFF_MISSING"
                action = "Write down charges in almsdata to match LMS zero"
                reason = f"Closed with balance {balance:+.2f}; LMS ~0"
            elif balance < -0.01:
                category = "OVER_CREDIT"
                action = "Review over-refund/credit"
                reason = f"Closed with negative balance {balance:+.2f}"
            else:
                category = "CLOSED_NONZERO"
                action = "Review unpaid/collect or write off"
                reason = f"Closed with balance {balance:+.2f}"
        else:
            category = "CLOSED_OK"
            action = "None"
            reason = "Closed and zeroed"
    else:
        category = "OTHER_STATUS"
        action = "Ignore for now"
        reason = f"Status {status}"

    return category, action, reason


def main():
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    alms = get_alms_balances()

    # Filter to candidates: cancelled or closed/complete with non-zero balance
    candidates = {
        r: v for r, v in alms.items()
        if (v["status"] in CANCELLED_STATUSES | ALLOWED_CLOSED_STATUSES) is None
    }
    # Python set union is better; fix logic below
    candidates = {}
    for r, v in alms.items():
        status = v["status"]
        if status in CANCELLED_STATUSES or status in ALLOWED_CLOSED_STATUSES:
            if abs(v["balance"]) > 0.01:
                candidates[r] = v

    if not candidates:
        print("No non-zero cancelled/closed balances found in almsdata.")
        return

    conn_lms = connect_lms()

    rows = []
    categories = {}

    for reserve, alms_state in candidates.items():
        lms_state = get_lms_state(reserve, conn_lms)
        cat, action, reason = categorize(reserve, alms_state, lms_state)

        row = {
            "reserve_number": reserve,
            "status": alms_state["status"],
            "alms_charges": alms_state["charges_total"],
            "alms_payments": alms_state["payments_total"],
            "alms_balance": alms_state["balance"],
            "lms_charges": lms_state["charges_total"] if lms_state else None,
            "lms_payments": lms_state["payments_total"] if lms_state else None,
            "lms_balance": lms_state["balance"] if lms_state else None,
            "category": cat,
            "action": action,
            "reason": reason,
        }
        rows.append(row)
        categories.setdefault(cat, []).append(row)

    conn_lms.close()

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "reserve_number", "status",
            "alms_charges", "alms_payments", "alms_balance",
            "lms_charges", "lms_payments", "lms_balance",
            "category", "action", "reason",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # Summary
    summary = {
        "total_candidates": len(rows),
        "categories": {
            cat: {
                "count": len(items),
                "sample": items[0]["reserve_number"],
            }
            for cat, items in categories.items()
        },
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 80)
    print("ALMS vs LMS Balance Audit")
    print("=" * 80)
    print()
    for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        print(f"{cat}: {len(items)} reserves")
        print(f"  Sample: {items[0]['reserve_number']} ({items[0]['reason']})")
        print()
    print(f"Details: {OUTPUT_CSV}")
    print(f"Summary: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
