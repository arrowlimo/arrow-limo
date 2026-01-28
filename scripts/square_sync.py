#!/usr/bin/env python3
"""
Square Sync and Reconciliation

What it does:
- Reads SQUARE_ACCESS_TOKEN and SQUARE_ENV (sandbox|production) from environment
- Fetches recent Payments and Payouts from Square
- Upserts Payments into existing `payments` table (payment_key = Square payment id)
- Creates/Upserts `square_payouts` table for payout records
- Generates CSV reconciliation reports by matching Square payouts to banking/receipts deposits

Outputs:
- reports/square_banking_reconciliation.csv
- reports/square_payout_breakdown.csv
- prints a short summary to stdout

Safe to run multiple times (idempotent upserts by keys).
"""
from __future__ import annotations

import os
import sys
import csv
from datetime import datetime, timedelta, UTC
from typing import Iterable, Tuple

import psycopg2  # type: ignore
from psycopg2.extras import RealDictCursor  # type: ignore
from dotenv import load_dotenv  # type: ignore

try:
    from square.client import Square, SquareEnvironment  # type: ignore
except Exception:  # pragma: no cover
    Square = None  # type: ignore
    SquareEnvironment = None  # type: ignore


# Load .env from workspace root if present
load_dotenv("l:/limo/.env")
load_dotenv()

# Environment configuration
SQUARE_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "").strip()
SQUARE_ENV = os.getenv("SQUARE_ENV", "production").strip().lower()
LOOKBACK_DAYS = int(os.getenv("SQUARE_LOOKBACK_DAYS", "120"))
RECON_TOLERANCE = float(os.getenv("SQUARE_RECON_TOLERANCE", "2.00"))
DATE_WINDOW_DAYS = int(os.getenv("SQUARE_RECON_DATE_WINDOW_DAYS", "5"))

_vendor_env = os.getenv("SQUARE_RECON_VENDOR_HINTS", "")
if _vendor_env:
    VENDOR_HINTS = [v.strip() for v in _vendor_env.split(",") if v.strip()]
else:
    VENDOR_HINTS = ["SQUARE", "SQ ", "SQUARE CANADA", "SQC"]

CREATE_PLACEHOLDER_RECEIPTS = os.getenv("SQUARE_CREATE_PLACEHOLDER_RECEIPTS", "false").lower() in {"1", "true", "yes"}

CSV_OUT = "l:/limo/reports/square_banking_reconciliation.csv"
CSV_OUT_PAYOUTS = "l:/limo/reports/square_payout_breakdown.csv"

# Database env
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def ensure_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS square_payouts (
            id TEXT PRIMARY KEY,
            status TEXT,
            location_id TEXT,
            arrival_date DATE,
            amount NUMERIC(12,2),
            currency TEXT,
            created_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ
        )
        """
    )


def cents_to_dollars(cents) -> float:
    if cents is None:
        return 0.0
    try:
        return round(int(cents) / 100.0, 2)
    except Exception:
        return 0.0


def upsert_payment(cur, p: dict) -> None:
    pid = p.get("id")
    if not pid:
        return
    amount = cents_to_dollars(((p.get("amount_money") or {}).get("amount")))
    created_at = p.get("created_at")  # ISO8601
    payment_date = None
    if created_at:
        try:
            payment_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
        except Exception:
            pass
    notes_src = (p.get("note") or "").strip()
    notes = f"[Square] {notes_src}".strip()
    
    # Extract Square-specific fields
    square_transaction_id = p.get("receipt_number")  # Square receipt number
    square_customer_name = None
    square_customer_email = None
    
    # Try to get customer info from customer_details or receipt_url
    customer_details = p.get("customer_details") or {}
    if customer_details:
        square_customer_name = customer_details.get("given_name", "")
        if customer_details.get("family_name"):
            if square_customer_name:
                square_customer_name += " " + customer_details.get("family_name")
            else:
                square_customer_name = customer_details.get("family_name")
        square_customer_email = customer_details.get("email_address")

    # payments table: amount, payment_date, charter_id, payment_key, payment_method, notes, last_updated, created_at
    cur.execute("SELECT 1 FROM payments WHERE payment_key = %s", (pid,))
    if cur.fetchone():
        cur.execute(
            """
            UPDATE payments
               SET amount = %s,
                   payment_date = %s,
                   notes = %s,
                   last_updated = NOW()
             WHERE payment_key = %s
            """,
            (amount, payment_date, notes, pid),
        )
    else:
        cur.execute(
            """
            INSERT INTO payments (amount, payment_date, charter_id, payment_key, payment_method, notes, last_updated, created_at, reserve_number)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)
            """,
            (amount, payment_date, None, pid, "credit_card", notes, None),
        )


def upsert_payout(cur, po: dict) -> None:
    poid = po.get("id")
    if not poid:
        return
    amount = cents_to_dollars(((po.get("amount_money") or {}).get("amount")))
    currency = ((po.get("amount_money") or {}).get("currency")) or "CAD"
    status = po.get("status")
    arrival_date = po.get("arrival_date")
    location_id = po.get("location_id")
    created_at = po.get("created_at")
    updated_at = po.get("updated_at")

    cur.execute("SELECT 1 FROM square_payouts WHERE id = %s", (poid,))
    if cur.fetchone():
        cur.execute(
            """
            UPDATE square_payouts
               SET status = %s,
                   location_id = %s,
                   arrival_date = %s,
                   amount = %s,
                   currency = %s,
                   created_at = COALESCE(%s, created_at),
                   updated_at = COALESCE(%s, updated_at)
             WHERE id = %s
            """,
            (status, location_id, arrival_date, amount, currency, created_at, updated_at, poid),
        )
    else:
        cur.execute(
            """
            INSERT INTO square_payouts (id, status, location_id, arrival_date, amount, currency, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (poid, status, location_id, arrival_date, amount, currency, created_at, updated_at),
        )


def fetch_and_store(client) -> Tuple[int, int]:
    total_payments = 0
    total_payouts = 0
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            ensure_tables(cur)
            conn.commit()

            # Payments: use begin_time for lookback
            begin_time = (datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)).isoformat()
            try:
                pager = client.payments.list(begin_time=begin_time, limit=100, sort_order="DESC")
                for p in pager:
                    d = getattr(p, "model_dump", lambda: {})()
                    upsert_payment(cur, d)
                    total_payments += 1
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Square payments error: {e}")

            # Payouts
            try:
                pager = client.payouts.list(limit=100, sort_order="DESC")
                for po in pager:
                    d = getattr(po, "model_dump", lambda: {})()
                    arr = d.get("arrival_date")
                    if arr:
                        try:
                            arr_dt = datetime.fromisoformat(arr)
                            if arr_dt.date() < (datetime.now(UTC).date() - timedelta(days=LOOKBACK_DAYS)):
                                break
                        except Exception:
                            pass
                    upsert_payout(cur, d)
                    total_payouts += 1
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Square payouts error: {e}")

    return total_payments, total_payouts


def generate_payout_breakdown_csv(client) -> None:
    """For each recent payout, fetch payout entries from Square and compute gross, fees, and net,
    then compare to the deposited amount stored in DB. Writes CSV for auditing.
    """
    rows = []
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, arrival_date, amount, location_id, status
                  FROM square_payouts
                 WHERE arrival_date >= CURRENT_DATE - INTERVAL '%s days'
                 ORDER BY arrival_date DESC
                """ % LOOKBACK_DAYS
            )
            payouts = cur.fetchall()

    for poid, arr_date, amt, loc_id, status in payouts:
        gross = 0.0
        fees = 0.0
        entry_count = 0
        api_ok = False
        err = ""
        try:
            pager = None
            try:
                pager = client.payouts.list_payout_entries(payout_id=poid, limit=100)
            except Exception:
                try:
                    pager = client.payouts.list_entries(payout_id=poid, limit=100)
                except Exception as e2:
                    err = f"No entries API available: {e2}"
                    pager = None

            if pager is not None:
                for entry in pager:
                    d = getattr(entry, "model_dump", lambda: {})()
                    m = (d.get("amount_money") or {})
                    cents = m.get("amount") or 0
                    amount = cents_to_dollars(cents)
                    # Positive entries => gross; negative => fees/adjustments
                    if amount >= 0:
                        gross += amount
                    else:
                        fees += amount
                    entry_count += 1
                api_ok = True
        except Exception as e:
            err = str(e)

        net_calc = round(gross + fees, 2)
        diff = round(net_calc - float(amt), 2)
        rows.append({
            "payout_id": poid,
            "arrival_date": arr_date,
            "payout_amount": float(amt),
            "gross_payments": round(gross, 2),
            "total_fees": round(fees, 2),
            "net_calc": net_calc,
            "delta_vs_payout": diff,
            "entries_count": entry_count,
            "api_ok": api_ok,
            "error": err,
        })

    os.makedirs(os.path.dirname(CSV_OUT_PAYOUTS), exist_ok=True)
    with open(CSV_OUT_PAYOUTS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "payout_id",
                "arrival_date",
                "payout_amount",
                "gross_payments",
                "total_fees",
                "net_calc",
                "delta_vs_payout",
                "entries_count",
                "api_ok",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Payout breakdown CSV: {CSV_OUT_PAYOUTS}")


def reconcile_and_csv() -> None:
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM receipts_finance_view
                 WHERE receipt_date >= CURRENT_DATE - INTERVAL '%s days'
                   AND inflow_amount > 0
                """ % LOOKBACK_DAYS
            )
            dep_count = cur.fetchone()[0]
            print(f"Bank deposits in window (inflow_amount>0): {dep_count}")

            cur.execute("SELECT to_regclass('public.banking_transactions')")
            has_banking = cur.fetchone()[0] is not None

            cur.execute(
                """
                SELECT id, arrival_date, amount
                  FROM square_payouts
                 WHERE arrival_date >= CURRENT_DATE - INTERVAL '%s days'
                 ORDER BY arrival_date DESC
                """ % LOOKBACK_DAYS
            )
            payouts = cur.fetchall()

            rows = []
            matched_count = 0
            total_diff = 0.0
            for poid, arr_date, amt in payouts:
                # Build vendor hint filters
                vendor_like = []
                vendor_params = []
                for h in VENDOR_HINTS:
                    vendor_like.append("UPPER(COALESCE(v.vendor_name,'')) LIKE UPPER('%%' || %s || '%%')")
                    vendor_like.append("UPPER(COALESCE(r.description,'')) LIKE UPPER('%%' || %s || '%%')")
                    vendor_params.extend([h, h])
                vendor_or = (" OR ".join(vendor_like)) or "FALSE"

                sql = f"""
                    SELECT v.receipt_id AS id,
                           v.receipt_date,
                           v.vendor_name,
                           COALESCE(r.description,''),
                           v.inflow_amount AS deposit_amount,
                           v.outflow_amount,
                           v.category,
                           ABS(v.inflow_amount - %s) AS diff
                      FROM receipts_finance_view v
                 LEFT JOIN receipts r ON r.id = v.receipt_id
                     WHERE v.receipt_date BETWEEN %s::date - %s AND %s::date + %s
                       AND v.inflow_amount > 0
                       AND (
                            v.category IN ('DEPOSITS','TRANSFERS')
                         OR {vendor_or}
                       )
                     ORDER BY (
                        CASE WHEN {vendor_or} THEN 0 ELSE 1 END
                     ), diff ASC, v.receipt_date ASC
                     LIMIT 10
                """
                params = [amt, arr_date, DATE_WINDOW_DAYS, arr_date, DATE_WINDOW_DAYS] + vendor_params + vendor_params
                try:
                    cur.execute(sql, params)
                    candidates = cur.fetchall()
                except Exception as e:
                    print(f"Receipts match query error: {e}")
                    conn.rollback()
                    cur = conn.cursor()
                    candidates = []

                best = None
                for c in candidates:
                    # id, date, vendor, desc, deposit_amount, outflow_amount, category, diff
                    if abs(float(c[4]) - float(amt)) <= RECON_TOLERANCE:
                        best = c
                        break

                if best:
                    matched_count += 1
                    diff = float(best[4]) - float(amt)
                    total_diff += diff
                    rows.append({
                        "payout_id": poid,
                        "payout_date": arr_date,
                        "payout_amount": float(amt),
                        "receipt_id": best[0],
                        "receipt_date": best[1],
                        "vendor_name": best[2],
                        "description": best[3],
                        "receipt_amount": float(best[4]),
                        "category": best[6],
                        "source_type": "receipts",
                        "account_number": "",
                        "diff": round(diff, 2),
                        "status": "MATCH",
                    })
                    continue

                # Second pass: exact inflow match by amount within window (ignoring vendor/category hints)
                try:
                    cur.execute(
                        """
                        SELECT v.receipt_id, v.receipt_date, v.vendor_name, COALESCE(r.description,''), v.inflow_amount, v.category,
                               ABS(v.inflow_amount - %s) AS diff
                          FROM receipts_finance_view v
                     LEFT JOIN receipts r ON r.id = v.receipt_id
                         WHERE v.receipt_date BETWEEN %s::date - %s AND %s::date + %s
                           AND v.inflow_amount > 0
                           AND ABS(v.inflow_amount - %s) <= %s
                         ORDER BY diff ASC, v.receipt_date ASC
                         LIMIT 1
                        """,
                        (amt, arr_date, DATE_WINDOW_DAYS, arr_date, DATE_WINDOW_DAYS, amt, RECON_TOLERANCE),
                    )
                    exact = cur.fetchone()
                except Exception as e:
                    conn.rollback()
                    cur = conn.cursor()
                    exact = None

                if exact:
                    matched_count += 1
                    diff = float(exact[4]) - float(amt)
                    total_diff += diff
                    rows.append({
                        "payout_id": poid,
                        "payout_date": arr_date,
                        "payout_amount": float(amt),
                        "receipt_id": exact[0],
                        "receipt_date": exact[1],
                        "vendor_name": exact[2],
                        "description": exact[3],
                        "receipt_amount": float(exact[4]),
                        "category": exact[5],
                        "source_type": "receipts_exact",
                        "account_number": "",
                        "diff": round(diff, 2),
                        "status": "MATCH",
                    })
                    continue

                # Third pass: banking_transactions fallback
                bt_candidates = []
                bt_best = None
                if has_banking:
                    vendor_like_bt = []
                    vendor_params_bt = []
                    for h in VENDOR_HINTS:
                        vendor_like_bt.append("description ILIKE %s")
                        vendor_params_bt.append(f"%{h}%")
                    vendor_or_bt = (" OR ".join(vendor_like_bt)) or "FALSE"
                    sql_bt = f"""
                        SELECT transaction_id, transaction_date, account_number, credit_amount, description,
                               ABS(credit_amount - %s) AS diff
                          FROM banking_transactions
                         WHERE transaction_date BETWEEN %s::date - %s AND %s::date + %s
                           AND credit_amount IS NOT NULL AND credit_amount > 0
                           AND ({vendor_or_bt})
                         ORDER BY diff ASC, transaction_date ASC
                         LIMIT 10
                    """
                    params_bt = [amt, arr_date, DATE_WINDOW_DAYS, arr_date, DATE_WINDOW_DAYS] + vendor_params_bt
                    try:
                        cur.execute(sql_bt, params_bt)
                        bt_candidates = cur.fetchall()
                    except Exception as e:
                        print(f"Banking fallback query error: {e}")
                        conn.rollback()
                        cur = conn.cursor()
                        bt_candidates = []
                    for b in bt_candidates:
                        if abs(float(b[3]) - float(amt)) <= RECON_TOLERANCE:
                            bt_best = b
                            break

                if bt_best:
                    matched_count += 1
                    diff = float(bt_best[3]) - float(amt)
                    total_diff += diff
                    rows.append({
                        "payout_id": poid,
                        "payout_date": arr_date,
                        "payout_amount": float(amt),
                        "receipt_id": bt_best[0],
                        "receipt_date": bt_best[1],
                        "vendor_name": "",
                        "description": bt_best[4],
                        "receipt_amount": float(bt_best[3]),
                        "category": "BANKING_CREDIT",
                        "source_type": "banking_transactions",
                        "account_number": bt_best[2] or "",
                        "diff": round(diff, 2),
                        "status": "MATCH_BANK",
                    })
                else:
                    # No strict match; prefer closest receipts candidate, else closest banking candidate, else unmatched/placeholder
                    if candidates:
                        c0 = candidates[0]
                        rows.append({
                            "payout_id": poid,
                            "payout_date": arr_date,
                            "payout_amount": float(amt),
                            "receipt_id": c0[0],
                            "receipt_date": c0[1],
                            "vendor_name": c0[2],
                            "description": c0[3],
                            "receipt_amount": float(c0[4]),
                            "category": c0[6],
                            "source_type": "receipts",
                            "account_number": "",
                            "diff": round(float(c0[7]), 2),
                            "status": "CANDIDATE",
                        })
                    elif bt_candidates:
                        b0 = bt_candidates[0]
                        rows.append({
                            "payout_id": poid,
                            "payout_date": arr_date,
                            "payout_amount": float(amt),
                            "receipt_id": b0[0],
                            "receipt_date": b0[1],
                            "vendor_name": "",
                            "description": b0[4],
                            "receipt_amount": float(b0[3]),
                            "category": "BANKING_CREDIT",
                            "source_type": "banking_transactions",
                            "account_number": b0[2] or "",
                            "diff": round(float(b0[5]), 2),
                            "status": "CANDIDATE_BANK",
                        })
                    else:
                        if CREATE_PLACEHOLDER_RECEIPTS:
                            # Create a provisional receipt so books can reflect this deposit
                            try:
                                cur.execute(
                                    "SELECT id FROM receipts WHERE source_system='SQUARE_SYNC' AND source_reference=%s",
                                    (f"payout:{poid}",),
                                )
                                row = cur.fetchone()
                                if row:
                                    rid = row[0]
                                else:
                                    cur.execute(
                                        """
                                        INSERT INTO receipts (
                                            receipt_date, vendor_name, category, expense_account,
                                            expense, revenue, gross_amount, net_amount,
                                            description, created_from_banking, source_system, source_reference
                                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                        RETURNING id
                                        """,
                                        (
                                            arr_date,
                                            "Square Payout",
                                            "DEPOSITS",
                                            "DEPOSITS - Square",
                                            0.0,
                                            float(amt),
                                            float(amt),
                                            float(amt),
                                            f"Provisional: Square Payout {poid}",
                                            False,
                                            "SQUARE_SYNC",
                                            f"payout:{poid}",
                                        ),
                                    )
                                    rid = cur.fetchone()[0]
                                rows.append({
                                    "payout_id": poid,
                                    "payout_date": arr_date,
                                    "payout_amount": float(amt),
                                    "receipt_id": rid,
                                    "receipt_date": arr_date,
                                    "vendor_name": "Square Payout",
                                    "description": f"Provisional: Square Payout {poid}",
                                    "receipt_amount": float(amt),
                                    "category": "DEPOSITS",
                                    "source_type": "receipts_provisional",
                                    "account_number": "",
                                    "diff": 0.0,
                                    "status": "MATCH_PLACEHOLDER",
                                })
                                matched_count += 1
                            except Exception as e:
                                print(f"Placeholder receipt insert error: {e}")
                                conn.rollback()
                                cur = conn.cursor()
                                rows.append({
                                    "payout_id": poid,
                                    "payout_date": arr_date,
                                    "payout_amount": float(amt),
                                    "receipt_id": "",
                                    "receipt_date": "",
                                    "vendor_name": "",
                                    "description": "",
                                    "receipt_amount": "",
                                    "category": "",
                                    "source_type": "",
                                    "account_number": "",
                                    "diff": "",
                                    "status": "UNMATCHED",
                                })
                        else:
                            rows.append({
                                "payout_id": poid,
                                "payout_date": arr_date,
                                "payout_amount": float(amt),
                                "receipt_id": "",
                                "receipt_date": "",
                                "vendor_name": "",
                                "description": "",
                                "receipt_amount": "",
                                "category": "",
                                "source_type": "",
                                "account_number": "",
                                "diff": "",
                                "status": "UNMATCHED",
                            })

            # Write CSV
            os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
            with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "payout_id",
                        "payout_date",
                        "payout_amount",
                        "receipt_id",
                        "receipt_date",
                        "vendor_name",
                        "description",
                        "receipt_amount",
                        "category",
                        "source_type",
                        "account_number",
                        "diff",
                        "status",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)

            print(f"Reconciliation CSV: {CSV_OUT}")
            print(
                f"Payouts: {len(payouts)} | Matched: {matched_count} | Unmatched: {len(payouts) - matched_count} | Sum diff (matched): {total_diff:.2f}"
            )


def main() -> None:
    if not SQUARE_TOKEN or Square is None:
        print("SQUARE_ACCESS_TOKEN not set or Square SDK not available. Set it in your shell OR add it to l:/limo/.env and re-run.")
        print("PowerShell example:")
        print("  $env:SQUARE_ACCESS_TOKEN = 'YOUR_PRODUCTION_TOKEN'")
        print("  $env:SQUARE_ENV = 'production'")
        print("")
        print(".env example (file: l:/limo/.env):")
        print("  SQUARE_ENV=production")
        print("  SQUARE_ACCESS_TOKEN=EAAA...YOUR_TOKEN...")
        sys.exit(1)

    env_enum = SquareEnvironment.SANDBOX if SQUARE_ENV == "sandbox" else SquareEnvironment.PRODUCTION
    client = Square(token=SQUARE_TOKEN, environment=env_enum)
    print(f"Square sync starting | env={SQUARE_ENV} | lookback_days={LOOKBACK_DAYS}")
    total_payments, total_payouts = fetch_and_store(client)
    print(f"Fetched payments: {total_payments}, payouts: {total_payouts}")
    reconcile_and_csv()
    generate_payout_breakdown_csv(client)


if __name__ == "__main__":
    main()
