#!/usr/bin/env python3
"""
Generate Tax Year Summary (GST/HST + GL + CRA payments)
=======================================================

Reads directly from PostgreSQL and produces a concise tax-year summary including:
- GST/HST net: collected vs ITCs from receipts (if available) or GL accounts with 'GST' in name
- P&L snapshot from unified_general_ledger (revenue vs expense aggregation)
- CRA-related payments from banking_transactions (Receiver General / CRA)

Outputs:
  exports/cra/<year>/tax_year_summary_<year>.md   (human summary)
  exports/cra/<year>/tax_year_summary_<year>.csv  (machine totals)

Safe: Read-only. Defensive: adapts to available schemas.
"""
from __future__ import annotations

import os
import csv
import sys
import argparse
from datetime import date
import psycopg2
from psycopg2.extras import DictCursor


DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)


def get_columns(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def find_date_col(cols: set[str]) -> str | None:
    for c in ("transaction_date", "date", "receipt_date", "posting_date", "created_at"):
        if c in cols:
            return c
    return None


def sum_gst_itc_from_receipts(conn, year: int) -> float:
    """Sum GST/HST on expenses (ITCs) from receipts table if available."""
    cols = get_columns(conn, "receipts")
    if not cols:
        return 0.0
    date_col = find_date_col(cols)
    if not date_col:
        return 0.0
    gst_col = next((c for c in ("gst_amount", "tax_amount", "gst") if c in cols), None)
    if not gst_col:
        return 0.0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COALESCE(SUM({gst_col}),0)
                FROM receipts
                WHERE EXTRACT(YEAR FROM {date_col}) = %s
                """,
                (year,),
            )
            row = cur.fetchone()
            v = row[0] if row and len(row) > 0 else 0
            return float(v or 0.0)
    except Exception:
        return 0.0


def gst_from_gl(conn, year: int) -> dict:
    """Try to derive GST collected and ITCs from unified_general_ledger by account name."""
    cols = get_columns(conn, "unified_general_ledger")
    if not cols:
        return {"collected": 0.0, "itc": 0.0}
    date_col = find_date_col(cols) or "transaction_date"
    acc_name = "account_name" if "account_name" in cols else None
    debit = "debit_amount" if "debit_amount" in cols else None
    credit = "credit_amount" if "credit_amount" in cols else None
    if not (acc_name and debit and credit and date_col):
        return {"collected": 0.0, "itc": 0.0}
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  SUM(CASE WHEN {acc_name} ILIKE '%GST%' AND {credit} > 0 THEN {credit} ELSE 0 END) AS gst_collected,
                  SUM(CASE WHEN {acc_name} ILIKE '%GST%' AND {debit}  > 0 THEN {debit}  ELSE 0 END) AS gst_itc
                FROM unified_general_ledger
                WHERE EXTRACT(YEAR FROM {date_col}) = %s
                """,
                (year,),
            )
            row = cur.fetchone()
            collected = float((row[0] if row and len(row) > 0 else 0) or 0.0)
            itc = float((row[1] if row and len(row) > 1 else 0) or 0.0)
            return {"collected": collected, "itc": itc}
    except Exception:
        return {"collected": 0.0, "itc": 0.0}


def gst_collected_from_income_ledger(conn, year: int) -> float:
    """Fallback: derive GST collected from income_ledger if available.
    Looks for columns fiscal_year and gst_collected.
    """
    cols = get_columns(conn, "income_ledger")
    if not cols:
        return 0.0
    if not ("fiscal_year" in cols and "gst_collected" in cols):
        return 0.0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(gst_collected),0)
                FROM income_ledger
                WHERE fiscal_year = %s
                """,
                (year,),
            )
            row = cur.fetchone()
            v = row[0] if row and len(row) > 0 else 0
            return float(v or 0.0)
    except Exception:
        return 0.0


def pnl_from_gl(conn, year: int) -> dict:
    """Very high-level revenue/expense from unified_general_ledger by sign semantics."""
    cols = get_columns(conn, "unified_general_ledger")
    if not cols:
        return {"revenue": 0.0, "expense": 0.0, "net_income": 0.0}
    date_col = find_date_col(cols) or "transaction_date"
    debit = "debit_amount" if "debit_amount" in cols else None
    credit = "credit_amount" if "credit_amount" in cols else None
    if not (debit and credit):
        return {"revenue": 0.0, "expense": 0.0, "net_income": 0.0}
    # Approximation: credits as revenue, debits as expense (ignoring balance sheet moves)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COALESCE(SUM({credit}),0) AS total_credit, COALESCE(SUM({debit}),0) AS total_debit
                FROM unified_general_ledger
                WHERE EXTRACT(YEAR FROM {date_col}) = %s
                """,
                (year,),
            )
            row = cur.fetchone()
            total_credit = row[0] if row and len(row) > 0 else 0
            total_debit = row[1] if row and len(row) > 1 else 0
            revenue = float(total_credit or 0.0)
            expense = float(total_debit or 0.0)
            net_income = revenue - expense
            return {"revenue": revenue, "expense": expense, "net_income": net_income}
    except Exception:
        return {"revenue": 0.0, "expense": 0.0, "net_income": 0.0}


def cra_payments_from_banking(conn, year: int) -> float:
    cols = get_columns(conn, "banking_transactions")
    if not cols:
        return 0.0
    date_col = find_date_col(cols) or "transaction_date"
    desc_col = next((c for c in ("description", "vendor_name", "memo") if c in cols), None)
    debit = next((c for c in ("debit_amount", "amount") if c in cols), None)
    if not (desc_col and debit and date_col):
        return 0.0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COALESCE(SUM({debit}),0)
                FROM banking_transactions
                WHERE EXTRACT(YEAR FROM {date_col}) = %s
                  AND (
                      {desc_col} ILIKE %s
                      OR {desc_col} ILIKE %s
                      OR {desc_col} ILIKE %s
                      OR {desc_col} ILIKE %s
                      OR {desc_col} ILIKE %s
                  )
                """,
                (year, "%receiver general%", "%canada revenue%", "%revenue canada%", "%cra%", "%gst%"),
            )
            row = cur.fetchone()
            v = row[0] if row and len(row) > 0 else 0
            return float(v or 0.0)
    except Exception:
        return 0.0


def write_outputs(year: int, outdir: str, data: dict):
    os.makedirs(outdir, exist_ok=True)
    # CSV totals
    csv_path = os.path.join(outdir, f"tax_year_summary_{year}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        for k, v in data.items():
            if isinstance(v, (int, float)):
                w.writerow([k, f"{v:.2f}"])
    # Markdown summary
    md_path = os.path.join(outdir, f"tax_year_summary_{year}.md")
    gst_net = float(data.get("gst_collected") or 0.0) - float(data.get("gst_itc") or 0.0)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Tax Year Summary {year}\n\n")
        f.write("## GST/HST\n")
        f.write(f"- GST/HST collected: ${float(data.get('gst_collected') or 0.0):,.2f}\n")
        f.write(f"- ITCs (from receipts/GL): ${float(data.get('gst_itc') or 0.0):,.2f}\n")
        f.write(f"- Net GST/HST: ${gst_net:,.2f} ({'owing' if gst_net>0 else 'refund due' if gst_net<0 else 'even'})\n\n")
        f.write("## P&L Snapshot (from GL, approximate)\n")
        f.write(f"- Revenue (credits): ${float(data.get('revenue') or 0.0):,.2f}\n")
        f.write(f"- Expenses (debits): ${float(data.get('expense') or 0.0):,.2f}\n")
        f.write(f"- Net income (approx): ${float(data.get('net_income') or 0.0):,.2f}\n\n")
        f.write("## CRA Payments (banking)\n")
        f.write(f"- Payments found to CRA/Receiver General: ${float(data.get('cra_payments') or 0.0):,.2f}\n\n")
        f.write("## Next Steps\n")
        f.write("- If Net GST/HST > 0: remit GST/HST by filing the 2012 return; if < 0: claim refund.\n")
        f.write("- Review P&L and prepare 2012 T2; tax computation depends on small business rates (consult accountant).\n")
        f.write("- Cross-check CRA payments against return balances; reconcile any differences.\n")
    return csv_path, md_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--outdir", type=str, default="exports/cra")
    args = ap.parse_args()

    year = args.year
    year_dir = os.path.join(args.outdir, str(year))

    try:
        with psycopg2.connect(**DSN) as conn:
            # GST from receipts (ITC)
            itc = sum_gst_itc_from_receipts(conn, year)
            # GST from GL (collected & itc)
            gl_gst = gst_from_gl(conn, year)
            collected = gl_gst.get("collected", 0.0)
            if not collected:
                # Fallback to income_ledger if GL doesn't carry GST accounts
                collected = gst_collected_from_income_ledger(conn, year)
            # Prefer GL ITC if non-zero; else receipts ITC
            gst_itc = gl_gst.get("itc", 0.0) or itc

            # P&L
            pnl = pnl_from_gl(conn, year)
            # CRA payments
            cra_paid = cra_payments_from_banking(conn, year)

            data = {
                "gst_collected": collected,
                "gst_itc": gst_itc,
                "revenue": pnl.get("revenue", 0.0),
                "expense": pnl.get("expense", 0.0),
                "net_income": pnl.get("net_income", 0.0),
                "cra_payments": cra_paid,
            }
            csv_path, md_path = write_outputs(year, year_dir, data)
            print("[OK] Tax year summary generated:")
            print("  ", csv_path)
            print("  ", md_path)
    except Exception as e:
        print("[FAIL] Error:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
