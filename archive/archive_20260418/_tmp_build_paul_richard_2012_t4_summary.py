from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import csv

import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}

YEAR = 2012
OUT_DIR = Path(r"l:\limo\data\audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def d(v) -> Decimal:
    return Decimal(str(v or 0))


def get_payroll_rollup(cur, employee_id: int) -> dict:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'employee_pay_entries'
        ORDER BY ordinal_position
        """
    )
    cols = {r["column_name"] for r in cur.fetchall()}
    if not cols:
        return {"available": False, "reason": "employee_pay_entries columns not found"}

    date_col = "pay_date" if "pay_date" in cols else None
    if date_col is None:
        return {"available": False, "reason": "No pay_date column in employee_pay_entries"}

    metric_cols = [
        "gross_pay",
        "net_pay",
        "gross_amount",
        "net_amount",
        "income_tax",
        "income_tax_deduction",
        "cpp",
        "cpp_deduction",
        "ei",
        "ei_deduction",
    ]
    metric_cols = [c for c in metric_cols if c in cols]

    select_bits = ["COUNT(*) AS row_count"]
    for c in metric_cols:
        select_bits.append(f"COALESCE(SUM({c}),0) AS {c}")

    sql = f"""
        SELECT {', '.join(select_bits)}
        FROM employee_pay_entries
        WHERE employee_id = %s
          AND {date_col} >= %s
          AND {date_col} < %s
    """
    cur.execute(sql, (employee_id, f"{YEAR}-01-01", f"{YEAR+1}-01-01"))
    row = cur.fetchone()

    out = {"available": True, "row_count": int(row["row_count"]), "metrics": {}}
    for c in metric_cols:
        out["metrics"][c] = d(row[c])
    return out


def main() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_out = OUT_DIR / f"paul_richard_t4_summary_{YEAR}_{ts}.txt"
    bank_csv = OUT_DIR / f"paul_richard_banking_support_{YEAR}_{ts}.csv"

    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT employee_id, first_name, last_name, full_name, t4_sin, street_address, city, province, postal_code
        FROM employees
        WHERE employee_id = 10
        """
    )
    emp = cur.fetchone()
    if not emp:
        raise RuntimeError("Employee 10 (Paul Richard) not found")

    cur.execute(
        """
        SELECT t4_id, tax_year,
               COALESCE(box_14_employment_income,0) AS box14,
               COALESCE(box_16_cpp_contributions,0) AS box16,
               COALESCE(box_18_ei_premiums,0) AS box18,
               COALESCE(box_22_income_tax,0) AS box22,
               COALESCE(box_24_ei_insurable_earnings,0) AS box24,
               COALESCE(box_26_cpp_pensionable_earnings,0) AS box26,
               COALESCE(notes,'') AS notes
        FROM employee_t4_records
        WHERE employee_id = %s
          AND tax_year = %s
        """,
        (emp["employee_id"], YEAR),
    )
    t4 = cur.fetchone()

    cur.execute(
        """
        SELECT transaction_id, transaction_date, debit_amount, description, check_number
        FROM banking_transactions
        WHERE transaction_date >= %s
          AND transaction_date < %s
          AND debit_amount > 0
          AND (
                                description ILIKE '%%chq%%'
                                OR description ILIKE '%%cheque%%'
                                OR description ILIKE '%%etransfer%%'
                                OR description ILIKE '%%e-transfer%%'
                                OR description ILIKE '%%email transfer%%'
                                OR description ILIKE '%%payroll%%'
              )
                    AND description ILIKE '%%paul richard%%'
        ORDER BY transaction_date, transaction_id
        """,
        (f"{YEAR}-01-01", f"{YEAR+1}-01-01"),
    )
    bank_rows = cur.fetchall()

    with bank_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["transaction_id", "transaction_date", "debit_amount", "check_number", "description"])
        for r in bank_rows:
            w.writerow([r["transaction_id"], r["transaction_date"], float(d(r["debit_amount"])), r["check_number"], r["description"]])

    bank_total = sum(d(r["debit_amount"]) for r in bank_rows)

    payroll_rollup = get_payroll_rollup(cur, int(emp["employee_id"]))

    lines = []
    lines.append(f"PAUL RICHARD T4 SUMMARY - {YEAR}")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("Employee")
    lines.append(f"- Employee ID: {emp['employee_id']}")
    lines.append(f"- Name: {emp['full_name'] or (str(emp['first_name']) + ' ' + str(emp['last_name']))}")
    lines.append(f"- SIN: {emp['t4_sin'] or '(missing)'}")
    lines.append(f"- Address: {emp['street_address'] or ''}, {emp['city'] or ''}, {emp['province'] or ''}, {emp['postal_code'] or ''}")
    lines.append("")

    if t4:
        lines.append("T4 Record (employee_t4_records)")
        lines.append(f"- t4_id: {t4['t4_id']}")
        lines.append(f"- Box 14 Employment Income: ${d(t4['box14']):,.2f}")
        lines.append(f"- Box 16 CPP Contributions: ${d(t4['box16']):,.2f}")
        lines.append(f"- Box 18 EI Premiums: ${d(t4['box18']):,.2f}")
        lines.append(f"- Box 22 Income Tax: ${d(t4['box22']):,.2f}")
        lines.append(f"- Box 24 EI Insurable Earnings: ${d(t4['box24']):,.2f}")
        lines.append(f"- Box 26 CPP Pensionable Earnings: ${d(t4['box26']):,.2f}")
        lines.append(f"- Notes: {t4['notes']}")
        lines.append("")
    else:
        lines.append("T4 Record (employee_t4_records)")
        lines.append("- No 2012 T4 row found for Paul Richard")
        lines.append("")

    lines.append("Banking Support (cheques/e-transfers mentioning Paul Richard)")
    lines.append(f"- Matching rows: {len(bank_rows)}")
    lines.append(f"- Total debits: ${bank_total:,.2f}")
    lines.append(f"- Detail CSV: {bank_csv}")
    if bank_rows:
        lines.append("- Entries:")
        for r in bank_rows:
            lines.append(
                f"  - {r['transaction_date']} | ${d(r['debit_amount']):,.2f} | "
                f"CHQ={r['check_number'] or ''} | {r['description']}"
            )
    lines.append("")

    lines.append("Driver Pay Management Rollup (policy source for payroll numbers)")
    if payroll_rollup.get("available"):
        lines.append(f"- Row count ({YEAR}): {payroll_rollup['row_count']}")
        metrics = payroll_rollup.get("metrics", {})
        if metrics:
            for k in sorted(metrics.keys()):
                lines.append(f"- {k}: ${d(metrics[k]):,.2f}")
        else:
            lines.append("- No numeric payroll metric columns found in schema")
    else:
        lines.append(f"- Unavailable: {payroll_rollup.get('reason')}")
    lines.append("")

    lines.append("Interpretation")
    lines.append("- T4 filing values should come from employee_t4_records / driver pay management (PD7/T4 flow).")
    lines.append("- Banking entries are supporting evidence only and should not overwrite T4 box values directly.")
    lines.append("- Owner/family EI exemption note present in T4 row should be preserved in filing package.")

    txt_out.write_text("\n".join(lines), encoding="utf-8")

    cur.close()
    conn.close()

    print(f"SUMMARY_TXT={txt_out}")
    print(f"BANKING_CSV={bank_csv}")


if __name__ == "__main__":
    main()
