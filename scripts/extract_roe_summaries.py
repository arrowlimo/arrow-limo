"""
Extract ROE (Record of Employment) summaries from inventory-listed PDFs (no DB writes).
- Reads PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json
- Scans documents tagged with category "ROE"
- Extracts SIN plus key totals: total insurable earnings, total insurable hours, pay period type,
  reason code, last day for which paid (raw text)
- Aggregates per year and outputs JSON/Markdown summaries
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

INVENTORY_PATH = Path(r"L:\\limo\\reports\\PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json")
OUTPUT_JSON = Path(r"L:\\limo\\reports\\ROE_SUMMARY_REPORT.json")
OUTPUT_MD = Path(r"L:\\limo\\reports\\ROE_SUMMARY_REPORT.md")

SIN_PATTERN = re.compile(r"\b(\d{9})\b")
EARNINGS_PATTERN = re.compile(r"total\s+insurable\s+earnings[^0-9]*([\d,]+(?:\.\d{2})?)", re.IGNORECASE | re.DOTALL)
HOURS_PATTERN = re.compile(r"total\s+insurable\s+hours[^0-9]*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE | re.DOTALL)
PAY_PERIOD_PATTERN = re.compile(r"pay\s+period\s+type[^A-Za-z]*([A-Za-z ]+)", re.IGNORECASE)
REASON_PATTERN = re.compile(r"reason\s+for\s+issuing\s+roe[^A-Za-z0-9]*([A-Z0-9]{1,3})", re.IGNORECASE)
LAST_DAY_PATTERN = re.compile(r"last\s+day\s+for\s+which\s+paid[^A-Za-z0-9]*([A-Za-z]{3}\.?\s?\d{1,2},?\s?\d{4}|\d{4}[-/ ]\d{2}[-/ ]\d{2})", re.IGNORECASE)


def parse_decimal(val: Optional[str]) -> Decimal:
    if not val:
        return Decimal("0")
    try:
        cleaned = val.replace(",", "")
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def extract_from_text(text: str) -> Dict[str, Optional[str]]:
    fields: Dict[str, Optional[str]] = {
        "sin": None,
        "total_insurable_earnings": None,
        "total_insurable_hours": None,
        "pay_period_type": None,
        "reason_code": None,
        "last_day_for_which_paid": None,
    }
    sin_match = SIN_PATTERN.search(text)
    if sin_match:
        fields["sin"] = sin_match.group(1)
    if m := EARNINGS_PATTERN.search(text):
        fields["total_insurable_earnings"] = m.group(1)
    if m := HOURS_PATTERN.search(text):
        fields["total_insurable_hours"] = m.group(1)
    if m := PAY_PERIOD_PATTERN.search(text):
        fields["pay_period_type"] = m.group(1).strip()
    if m := REASON_PATTERN.search(text):
        fields["reason_code"] = m.group(1).strip().upper()
    if m := LAST_DAY_PATTERN.search(text):
        fields["last_day_for_which_paid"] = m.group(1).strip()
    return fields


def extract_roe_pdf(path: Path, year: Optional[int]) -> List[dict]:
    rows: List[dict] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            fields = extract_from_text(text)
            # Keep entries with at least a SIN or earnings/hours value
            if fields["sin"] or fields["total_insurable_earnings"] or fields["total_insurable_hours"]:
                rows.append({
                    "year": year,
                    "sin": fields["sin"],
                    "total_insurable_earnings": parse_decimal(fields["total_insurable_earnings"] or "0"),
                    "total_insurable_hours": parse_decimal(fields["total_insurable_hours"] or "0"),
                    "pay_period_type": fields["pay_period_type"],
                    "reason_code": fields["reason_code"],
                    "last_day_for_which_paid": fields["last_day_for_which_paid"],
                    "source_file": str(path),
                })
    return rows


def load_inventory() -> dict:
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(f"Inventory not found: {INVENTORY_PATH}")
    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    inventory = load_inventory()
    documents = inventory.get("documents", [])
    roe_docs = [doc for doc in documents if "ROE" in doc.get("categories", [])]

    detail_rows: List[dict] = []
    per_year: Dict[int, Dict[str, Decimal]] = defaultdict(lambda: {"earnings": Decimal("0"), "hours": Decimal("0")})

    for doc in roe_docs:
        path = Path(doc["path"])
        year = doc.get("year")
        if not path.exists() or year is None:
            continue
        try:
            rows = extract_roe_pdf(path, year)
        except Exception:
            continue
        detail_rows.extend(rows)
        for r in rows:
            per_year[year]["earnings"] += r["total_insurable_earnings"]
            per_year[year]["hours"] += r["total_insurable_hours"]

    serializable_details = []
    for row in detail_rows:
        serializable_details.append({
            "year": row["year"],
            "sin": row["sin"],
            "total_insurable_earnings": float(row["total_insurable_earnings"]),
            "total_insurable_hours": float(row["total_insurable_hours"]),
            "pay_period_type": row["pay_period_type"],
            "reason_code": row["reason_code"],
            "last_day_for_which_paid": row["last_day_for_which_paid"],
            "source_file": row["source_file"],
        })

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated": datetime.now().isoformat(),
                "roe_documents": len(roe_docs),
                "per_year_totals": {str(y): {"earnings": str(v["earnings"]), "hours": str(v["hours"])} for y, v in per_year.items()},
                "detail_rows": serializable_details,
            },
            f,
            indent=2,
        )

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# ROE Summary Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for year in sorted(per_year.keys()):
            totals = per_year[year]
            f.write(f"## {year}\n")
            f.write(f"- Total insurable earnings: ${totals['earnings']:.2f}\n")
            f.write(f"- Total insurable hours: {totals['hours']:.2f}\n\n")
        f.write(f"Detail rows: {len(detail_rows)}\n")

    print("✅ ROE summary saved.")


if __name__ == "__main__":
    main()
