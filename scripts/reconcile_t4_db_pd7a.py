"""
Reconcile T4 DB totals against PD7A summaries.
- Reads employee_t4_summary from DB (aggregated per year)
- Reads PD7A_SUMMARY_REPORT.json
- Computes deltas and percent differences
- Outputs JSON and Markdown
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

PD7A_PATH = Path(r"L:\\limo\\reports\\PD7A_SUMMARY_REPORT.json")
OUTPUT_JSON = Path(r"L:\\limo\\reports\\T4_DB_PD7A_RECON_SUMMARY.json")
OUTPUT_MD = Path(r"L:\\limo\\reports\\T4_DB_PD7A_RECON_SUMMARY.md")

FIELDS = {
    "income_vs_gross": ("t4_employment_income", "gross_payroll"),
    "tax": ("t4_federal_tax", "tax_deductions"),
    "cpp": ("t4_cpp_contributions", "cpp_employee"),
    "ei": ("t4_ei_contributions", "ei_employee"),
}


def to_decimal(val: str | float | Decimal | None) -> Decimal:
    if val is None:
        return Decimal("0")
    try:
        if isinstance(val, Decimal):
            return val
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def load_pd7a_totals() -> Dict[str, Dict[str, Decimal]]:
    if not PD7A_PATH.exists():
        raise FileNotFoundError(f"Missing PD7A summary: {PD7A_PATH}")
    with open(PD7A_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("by_year", {})
    parsed: Dict[str, Dict[str, Decimal]] = {}
    for year, vals in raw.items():
        parsed[year] = {k: to_decimal(v) for k, v in vals.items()}
    return parsed


def load_t4_from_db() -> Dict[int, Dict[str, Decimal]]:
    conn = connect_db()
    cur = conn.cursor()
    try:
        query = """
            SELECT fiscal_year,
                   COALESCE(SUM(t4_employment_income), 0) as employment_income,
                   COALESCE(SUM(t4_cpp_contributions), 0) as cpp,
                   COALESCE(SUM(t4_ei_contributions), 0) as ei,
                   COALESCE(SUM(t4_federal_tax), 0) as tax
            FROM employee_t4_summary
            GROUP BY fiscal_year
            ORDER BY fiscal_year
        """
        cur.execute(query)
        result = {}
        for row in cur.fetchall():
            year = row[0]
            result[year] = {
                "t4_employment_income": to_decimal(row[1]),
                "t4_cpp_contributions": to_decimal(row[2]),
                "t4_ei_contributions": to_decimal(row[3]),
                "t4_federal_tax": to_decimal(row[4]),
            }
        return result
    finally:
        cur.close()
        conn.close()


def pct_diff(t4_val: Decimal, pd7a_val: Decimal) -> Decimal:
    if pd7a_val == 0:
        return Decimal("0")
    return (t4_val - pd7a_val) / pd7a_val * Decimal("100")


def main() -> None:
    t4_db = load_t4_from_db()
    pd7a = load_pd7a_totals()

    years = sorted(set(str(k) for k in t4_db.keys()) | set(pd7a.keys()))
    recon = {}
    for year_str in years:
        try:
            year_int = int(year_str)
        except ValueError:
            year_int = 0
        
        t4_boxes = t4_db.get(year_int, {})
        pd7a_vals = pd7a.get(year_str, {})
        entry = {}
        for label, (t4_field, pd7a_field) in FIELDS.items():
            t4_val = t4_boxes.get(t4_field, Decimal("0"))
            pd7a_val = pd7a_vals.get(pd7a_field, Decimal("0"))
            entry[label] = {
                "t4_db": str(t4_val),
                "pd7a": str(pd7a_val),
                "delta": str(t4_val - pd7a_val),
                "pct_diff": str(pct_diff(t4_val, pd7a_val)),
            }
        recon[year_str] = entry

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated": datetime.now().isoformat(),
                "source": {
                    "t4": "employee_t4_records (DB aggregate)",
                    "pd7a": str(PD7A_PATH),
                },
                "reconciliation": recon,
            },
            f,
            indent=2,
        )

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# T4 DB vs PD7A Reconciliation\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for year_str in years:
            entry = recon[year_str]
            f.write(f"## {year_str}\n")
            f.write("- Income vs Gross: T4 DB ${t4} | PD7A gross ${pd} | Δ ${d} | %Δ {p:.2f}%\n".format(
                t4=entry["income_vs_gross"]["t4_db"],
                pd=entry["income_vs_gross"]["pd7a"],
                d=entry["income_vs_gross"]["delta"],
                p=Decimal(entry["income_vs_gross"]["pct_diff"]),
            ))
            f.write("- Tax: T4 DB ${t4} | PD7A tax ${pd} | Δ ${d} | %Δ {p:.2f}%\n".format(
                t4=entry["tax"]["t4_db"],
                pd=entry["tax"]["pd7a"],
                d=entry["tax"]["delta"],
                p=Decimal(entry["tax"]["pct_diff"]),
            ))
            f.write("- CPP: T4 DB ${t4} | PD7A CPP ${pd} | Δ ${d} | %Δ {p:.2f}%\n".format(
                t4=entry["cpp"]["t4_db"],
                pd=entry["cpp"]["pd7a"],
                d=entry["cpp"]["delta"],
                p=Decimal(entry["cpp"]["pct_diff"]),
            ))
            f.write("- EI: T4 DB ${t4} | PD7A EI ${pd} | Δ ${d} | %Δ {p:.2f}%\n\n".format(
                t4=entry["ei"]["t4_db"],
                pd=entry["ei"]["pd7a"],
                d=entry["ei"]["delta"],
                p=Decimal(entry["ei"]["pct_diff"]),
            ))

    print("✅ T4 DB vs PD7A reconciliation saved.")


if __name__ == "__main__":
    main()
