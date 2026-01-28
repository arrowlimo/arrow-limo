"""
Reconcile ROE insurable earnings/hours against PD7A and T4 aggregates (per year).
- Uses ROE_SUMMARY_REPORT.json (earnings/hours per year)
- Uses PD7A_SUMMARY_REPORT.json
- Uses T4_PDF_TOTALS_SUMMARY.json (PDF totals; closest proxy to T4 earnings)
- Outputs JSON/Markdown with deltas
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict

ROE_PATH = Path(r"L:\\limo\\reports\\ROE_SUMMARY_REPORT.json")
PD7A_PATH = Path(r"L:\\limo\\reports\\PD7A_SUMMARY_REPORT.json")
T4_PATH = Path(r"L:\\limo\\reports\\T4_PDF_TOTALS_SUMMARY.json")
OUTPUT_JSON = Path(r"L:\\limo\\reports\\ROE_PD7A_T4_RECON_SUMMARY.json")
OUTPUT_MD = Path(r"L:\\limo\\reports\\ROE_PD7A_T4_RECON_SUMMARY.md")


def to_decimal(val):
    if val is None:
        return Decimal("0")
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def load_roe() -> Dict[str, Dict[str, Decimal]]:
    if not ROE_PATH.exists():
        raise FileNotFoundError(f"Missing ROE report: {ROE_PATH}")
    with open(ROE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    per_year = data.get("per_year_totals", {})
    out = {}
    for year, vals in per_year.items():
        out[year] = {
            "earnings": to_decimal(vals.get("earnings")),
            "hours": to_decimal(vals.get("hours")),
        }
    return out


def load_pd7a() -> Dict[str, Dict[str, Decimal]]:
    if not PD7A_PATH.exists():
        raise FileNotFoundError(f"Missing PD7A summary: {PD7A_PATH}")
    with open(PD7A_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("by_year", {})
    parsed: Dict[str, Dict[str, Decimal]] = {}
    for year, vals in raw.items():
        parsed[year] = {k: to_decimal(v) for k, v in vals.items()}
    return parsed


def load_t4_pdf_totals() -> Dict[str, Dict[str, Decimal]]:
    if not T4_PATH.exists():
        raise FileNotFoundError(f"Missing T4 PDF totals: {T4_PATH}")
    with open(T4_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("totals_by_year", {})
    parsed: Dict[str, Dict[str, Decimal]] = {}
    for year, boxes in raw.items():
        parsed[year] = {k: to_decimal(v) for k, v in boxes.items()}
    return parsed


def pct_diff(a: Decimal, b: Decimal) -> Decimal:
    if b == 0:
        return Decimal("0")
    return (a - b) / b * Decimal("100")


def main() -> None:
    roe = load_roe()
    pd7a = load_pd7a()
    t4 = load_t4_pdf_totals()

    years = sorted(set(roe.keys()) | set(pd7a.keys()) | set(t4.keys()))
    recon = {}
    for year in years:
        roe_vals = roe.get(year, {"earnings": Decimal("0"), "hours": Decimal("0")})
        pd7a_vals = pd7a.get(year, {})
        t4_vals = t4.get(year, {})

        gross = pd7a_vals.get("gross_payroll", Decimal("0"))
        t4_income = t4_vals.get("box_14", Decimal("0"))
        roe_earn = roe_vals.get("earnings", Decimal("0"))
        roe_hours = roe_vals.get("hours", Decimal("0"))

        recon[year] = {
            "roe_earnings": str(roe_earn),
            "roe_hours": str(roe_hours),
            "pd7a_gross": str(gross),
            "t4_income": str(t4_income),
            "delta_roe_vs_pd7a_gross": str(roe_earn - gross),
            "pct_roe_vs_pd7a_gross": str(pct_diff(roe_earn, gross)),
            "delta_roe_vs_t4_income": str(roe_earn - t4_income),
            "pct_roe_vs_t4_income": str(pct_diff(roe_earn, t4_income)),
        }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated": datetime.now().isoformat(),
                "reconciliation": recon,
                "source": {
                    "roe": str(ROE_PATH),
                    "pd7a": str(PD7A_PATH),
                    "t4_pdf": str(T4_PATH),
                },
            },
            f,
            indent=2,
        )

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# ROE vs PD7A/T4 Reconciliation\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for year in years:
            entry = recon[year]
            f.write(f"## {year}\n")
            f.write(
                "- ROE earnings ${roe} | PD7A gross ${pd7a} | Δ ${d} | %Δ {p:.2f}%\n".format(
                    roe=entry["roe_earnings"],
                    pd7a=entry["pd7a_gross"],
                    d=entry["delta_roe_vs_pd7a_gross"],
                    p=Decimal(entry["pct_roe_vs_pd7a_gross"]),
                )
            )
            f.write(
                "- ROE earnings ${roe} | T4 box14 (PDF) ${t4} | Δ ${d} | %Δ {p:.2f}%\n".format(
                    roe=entry["roe_earnings"],
                    t4=entry["t4_income"],
                    d=entry["delta_roe_vs_t4_income"],
                    p=Decimal(entry["pct_roe_vs_t4_income"]),
                )
            )
            f.write("- ROE hours: {hrs}\n\n".format(hrs=entry["roe_hours"]))

    print("✅ ROE vs PD7A/T4 reconciliation saved.")


if __name__ == "__main__":
    main()
