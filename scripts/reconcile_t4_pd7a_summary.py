"""
Compare T4 PDF totals (per-year sums) against PD7A summaries.
- Reads reports/T4_PDF_TOTALS_SUMMARY.json and reports/PD7A_SUMMARY_REPORT.json
- Computes deltas and percent differences for income/gross_payroll, tax, CPP, EI
- Writes JSON and Markdown summaries; no DB writes
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Optional

T4_TOTALS_PATH = Path(r"L:\\limo\\reports\\T4_PDF_TOTALS_SUMMARY.json")
PD7A_PATH = Path(r"L:\\limo\\reports\\PD7A_SUMMARY_REPORT.json")
OUTPUT_JSON = Path(r"L:\\limo\\reports\\T4_PD7A_RECON_SUMMARY.json")
OUTPUT_MD = Path(r"L:\\limo\\reports\\T4_PD7A_RECON_SUMMARY.md")

FIELDS = {
    "income_vs_gross": ("box_14", "gross_payroll"),
    "tax": ("box_22", "tax_deductions"),
    "cpp": ("box_16", "cpp_employee"),
    "ei": ("box_18", "ei_employee"),
}


def to_decimal(val: Optional[str]) -> Decimal:
    if val is None:
        return Decimal("0")
    try:
        return Decimal(val)
    except (InvalidOperation, TypeError):
        return Decimal("0")


def load_t4_totals() -> Dict[str, Dict[str, Decimal]]:
    if not T4_TOTALS_PATH.exists():
        raise FileNotFoundError(f"Missing T4 totals: {T4_TOTALS_PATH}")
    with open(T4_TOTALS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("totals_by_year", {})
    parsed: Dict[str, Dict[str, Decimal]] = {}
    for year, boxes in raw.items():
        parsed[year] = {k: to_decimal(v) for k, v in boxes.items()}
    return parsed


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


def pct_diff(t4_val: Decimal, pd7a_val: Decimal) -> Decimal:
    if pd7a_val == 0:
        return Decimal("0")
    return (t4_val - pd7a_val) / pd7a_val * Decimal("100")


def main() -> None:
    t4 = load_t4_totals()
    pd7a = load_pd7a_totals()

    years = sorted(set(t4.keys()) | set(pd7a.keys()))
    recon = {}
    for year in years:
        t4_boxes = t4.get(year, {})
        pd7a_vals = pd7a.get(year, {})
        entry = {}
        for label, (t4_field, pd7a_field) in FIELDS.items():
            t4_val = t4_boxes.get(t4_field, Decimal("0"))
            pd7a_val = pd7a_vals.get(pd7a_field, Decimal("0"))
            entry[label] = {
                "t4": str(t4_val),
                "pd7a": str(pd7a_val),
                "delta": str(t4_val - pd7a_val),
                "pct_diff": str(pct_diff(t4_val, pd7a_val)),
            }
        recon[year] = entry

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated": datetime.now().isoformat(),
                "source": {
                    "t4": str(T4_TOTALS_PATH),
                    "pd7a": str(PD7A_PATH),
                },
                "reconciliation": recon,
            },
            f,
            indent=2,
        )

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# T4 vs PD7A Reconciliation\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for year in years:
            entry = recon[year]
            f.write(f"## {year}\n")
            f.write("- Income vs Gross: T4 box14 ${t4} | PD7A gross ${pd} | Δ ${d} | %Δ {p:.2f}%\n".format(
                t4=entry["income_vs_gross"]["t4"],
                pd=entry["income_vs_gross"]["pd7a"],
                d=entry["income_vs_gross"]["delta"],
                p=Decimal(entry["income_vs_gross"]["pct_diff"]),
            ))
            f.write("- Tax: T4 box22 ${t4} | PD7A tax ${pd} | Δ ${d} | %Δ {p:.2f}%\n".format(
                t4=entry["tax"]["t4"],
                pd=entry["tax"]["pd7a"],
                d=entry["tax"]["delta"],
                p=Decimal(entry["tax"]["pct_diff"]),
            ))
            f.write("- CPP: T4 box16 ${t4} | PD7A CPP ${pd} | Δ ${d} | %Δ {p:.2f}%\n".format(
                t4=entry["cpp"]["t4"],
                pd=entry["cpp"]["pd7a"],
                d=entry["cpp"]["delta"],
                p=Decimal(entry["cpp"]["pct_diff"]),
            ))
            f.write("- EI: T4 box18 ${t4} | PD7A EI ${pd} | Δ ${d} | %Δ {p:.2f}%\n\n".format(
                t4=entry["ei"]["t4"],
                pd=entry["ei"]["pd7a"],
                d=entry["ei"]["delta"],
                p=Decimal(entry["ei"]["pct_diff"]),
            ))

    print("✅ T4 vs PD7A reconciliation saved.")


if __name__ == "__main__":
    main()
