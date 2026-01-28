#!/usr/bin/env python3
"""
Check Square matches and refund status for a specific reserve number.

Usage:
  python -X utf8 scripts/check_square_payments_for_reserve.py 017196 [--write-report]

Outputs a concise console summary and, if --write-report is given,
writes reports/SQUARE_MATCH_<reserve>.csv with details per payment.
"""
from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import psycopg2  # type: ignore
from psycopg2.extras import RealDictCursor  # type: ignore

# Prefer requests to the SDK for a small, targeted lookup
import requests  # type: ignore


# Load env from workspace root if present
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv("l:/limo/.env"); load_dotenv()
except Exception:
    pass


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REMOVED***")

SQUARE_TOKEN = (os.getenv("SQUARE_ACCESS_TOKEN", "").strip())
SQUARE_ENV = os.getenv("SQUARE_ENV", "production").strip().lower()
SQUARE_BASE = (
    "https://connect.squareup.com" if SQUARE_ENV == "production" else "https://connect.squareupsandbox.com"
)


@dataclass
class PaymentRow:
    payment_id: int
    reserve: str
    amount: float
    date: Optional[datetime]
    method: Optional[str]
    square_payment_id: str
    square_transaction_id: str
    square_status: str
    reference_number: str
    notes: str


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def fetch_payments(reserve: str) -> List[PaymentRow]:
    q = (
        """
        SELECT payment_id, reserve_number, amount, payment_date, payment_method,
               COALESCE(square_payment_id,''), COALESCE(square_transaction_id,''),
               COALESCE(square_status,''), COALESCE(reference_number,''), COALESCE(notes,'')
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date NULLS LAST, payment_id
        """
    )
    rows: List[PaymentRow] = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(q, (reserve,))
            for r in cur.fetchall():
                rows.append(
                    PaymentRow(
                        payment_id=r[0],
                        reserve=r[1],
                        amount=float(r[2] or 0.0),
                        date=r[3],
                        method=r[4],
                        square_payment_id=r[5],
                        square_transaction_id=r[6],
                        square_status=r[7],
                        reference_number=r[8],
                        notes=r[9],
                    )
                )
    return rows


def sq_headers() -> Dict[str, str]:
    if not SQUARE_TOKEN:
        raise RuntimeError("SQUARE_ACCESS_TOKEN not set. Add it to l:/limo/.env")
    return {
        "Square-Version": "2024-11-20",
        "Authorization": f"Bearer {SQUARE_TOKEN}",
        "Content-Type": "application/json",
    }


def get_square_payment(pid: str) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(f"{SQUARE_BASE}/v2/payments/{pid}", headers=sq_headers(), timeout=25)
        if resp.status_code == 200:
            return (resp.json() or {}).get("payment")
        return None
    except Exception:
        return None


def payment_refunded_dollars(square_payment: Dict[str, Any]) -> float:
    if not square_payment:
        return 0.0
    rm = (square_payment.get("refunded_money") or {}).get("amount")
    try:
        return round((int(rm) if rm is not None else 0) / 100.0, 2)
    except Exception:
        return 0.0


def list_square_payments(begin: datetime, end: datetime) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    # Square expects ISO8601 with Z
    def iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    while True:
        params = {
            "begin_time": iso(begin),
            "end_time": iso(end),
            "limit": "100",
            "sort_order": "ASC",
        }
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(f"{SQUARE_BASE}/v2/payments", headers=sq_headers(), params=params, timeout=25)
        if resp.status_code != 200:
            break
        body = resp.json() or {}
        out.extend(body.get("payments", []) or [])
        cursor = body.get("cursor")
        if not cursor:
            break
    return out


def write_report(reserve: str, rows: List[Dict[str, Any]]) -> str:
    out_path = f"l:/limo/reports/SQUARE_MATCH_{reserve}.csv"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if not rows:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return out_path
    keys = [
        "reserve","payment_id","alms_amount","alms_date","method",
        "square_payment_id","square_status","square_created","square_amount",
        "refund_count","refund_total","refund_ids","reference_number","notes",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(rows)
    return out_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -X utf8 scripts/check_square_payments_for_reserve.py <reserve> [--write-report]")
        sys.exit(2)
    reserve = sys.argv[1].strip()
    write_csv = any(a.strip().lower() == "--write-report" for a in sys.argv[2:])

    payments = fetch_payments(reserve)
    if not payments:
        print(f"No ALMS payments found for reserve {reserve}")
        sys.exit(0)

    print("=" * 100)
    print(f"Reserve {reserve} — ALMS payments and Square lookup")
    print("=" * 100)

    report_rows: List[Dict[str, Any]] = []
    for p in payments:
        sqpid = (p.square_payment_id or "").strip()
        square = get_square_payment(sqpid) if sqpid else None
        refund_total_d = payment_refunded_dollars(square) if sqpid and square else 0.0
        sq_amt = None
        sq_status = None
        sq_created = None
        if square:
            am = ((square.get("amount_money") or {}).get("amount") or 0) or 0
            sq_amt = round(am / 100.0, 2)
            sq_status = square.get("status")
            sq_created = square.get("created_at")

        candidates: List[Dict[str, Any]] = []
        if not sqpid and p.date:
            # Fuzzy search payments around the ALMS payment date by amount
            window_start = datetime.combine(p.date, datetime.min.time()).replace(tzinfo=timezone.utc) - timedelta(days=2)
            window_end = datetime.combine(p.date, datetime.max.time()).replace(tzinfo=timezone.utc) + timedelta(days=2)
            try:
                listed = list_square_payments(window_start, window_end)
                target_cents = int(round(p.amount * 100))
                for item in listed:
                    cents = ((item.get("amount_money") or {}).get("amount") or 0) or 0
                    if int(cents) == target_cents:
                        candidates.append(item)
            except Exception:
                pass

        print(f"- payment_id={p.payment_id} date={p.date} amt={p.amount:.2f} method={p.method} | sq_id={sqpid or '-'} | refunded_total={refund_total_d:.2f} | candidates={len(candidates)}")
        if not sqpid and candidates:
            for c in candidates[:5]:
                pid = c.get("id", "")
                created = c.get("created_at", "")
                status = c.get("status", "")
                brand = (((c.get("card_details") or {}).get("card") or {}).get("card_brand") or "")
                last4 = (((c.get("card_details") or {}).get("card") or {}).get("last_4") or "")
                print(f"  -> candidate payment {pid} {created} {status} {brand}••{last4}")
                # For each candidate, show refunded amount if available
                try:
                    sp = get_square_payment(pid)
                    if sp:
                        rtot = payment_refunded_dollars(sp)
                        if rtot > 0:
                            print(f"     refunded_total={rtot:.2f}")
                except Exception:
                    pass

        report_rows.append({
            "reserve": p.reserve,
            "payment_id": p.payment_id,
            "alms_amount": f"{p.amount:.2f}",
            "alms_date": p.date.isoformat() if p.date else "",
            "method": p.method or "",
            "square_payment_id": sqpid,
            "square_status": sq_status or p.square_status,
            "square_created": sq_created or "",
            "square_amount": f"{sq_amt:.2f}" if sq_amt is not None else "",
            "refund_count": 1 if refund_total_d > 0 else 0,
            "refund_total": f"{refund_total_d:.2f}",
            "refund_ids": "",
            "reference_number": p.reference_number or "",
            "notes": p.notes or "",
        })

    if write_csv:
        out = write_report(reserve, report_rows)
        print(f"\nReport written: {out}")


if __name__ == "__main__":
    main()
