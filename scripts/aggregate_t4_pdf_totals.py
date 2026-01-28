"""
Aggregate T4 PDF totals by year (no DB writes).
- Reads T4 PDFs listed in PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json
- Extracts boxes 14, 16, 18, 22, 24, 26 by SIN
- Dedupes per SIN by keeping the max value per box
- Outputs per-year sums to JSON and Markdown
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
OUTPUT_JSON = Path(r"L:\\limo\\reports\\T4_PDF_TOTALS_SUMMARY.json")
OUTPUT_MD = Path(r"L:\\limo\\reports\\T4_PDF_TOTALS_SUMMARY.md")

# Allow up to 100 characters between box number and numeric amount to accommodate wrapped layouts.
T4_BOX_PATTERNS: Dict[str, re.Pattern[str]] = {
    "box_14": re.compile(r"14[\s\S]{0,100}?(\d{1,10}\.\d{2})"),
    "box_16": re.compile(r"16[\s\S]{0,100}?(\d{1,10}\.\d{2})"),
    "box_18": re.compile(r"18[\s\S]{0,100}?(\d{1,10}\.\d{2})"),
    "box_22": re.compile(r"22[\s\S]{0,100}?(\d{1,10}\.\d{2})"),
    "box_24": re.compile(r"24[\s\S]{0,100}?(\d{1,10}\.\d{2})"),
    "box_26": re.compile(r"26[\s\S]{0,100}?(\d{1,10}\.\d{2})"),
}

SIN_PATTERN = re.compile(r"(\d{9})")


def parse_decimal(text: str) -> Decimal:
    try:
        return Decimal(text)
    except Exception:
        return Decimal("0.00")


def extract_t4_pdf(path: Path, year: Optional[int]) -> List[dict]:
    employees: List[dict] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            sin_match = SIN_PATTERN.search(text)
            sin = sin_match.group(1) if sin_match else None
            boxes: Dict[str, Decimal] = {}
            for key, pattern in T4_BOX_PATTERNS.items():
                match = pattern.search(text)
                if match:
                    boxes[key] = parse_decimal(match.group(1))
            # Keep entries that have a SIN and at least box 14
            if sin and boxes.get("box_14", Decimal("0")) > 0:
                employees.append({"sin": sin, "boxes": boxes, "year": year})
    return employees


def load_inventory() -> dict:
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(f"Inventory not found: {INVENTORY_PATH}")
    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    inventory = load_inventory()
    documents = inventory.get("documents", [])
    t4_docs = [doc for doc in documents if "T4" in doc.get("categories", [])]

    # year -> sin -> box dict
    per_year_sin: Dict[int, Dict[str, Dict[str, Decimal]]] = defaultdict(dict)

    for doc in t4_docs:
        path = Path(doc["path"])
        year = doc.get("year")
        if year is None:
            # Skip entries without a year; keep behavior explicit.
            continue
        if not path.exists():
            # Skip missing files quietly.
            continue
        try:
            employees = extract_t4_pdf(path, year)
        except Exception:
            # Skip unreadable PDFs quietly; upstream reports already capture lock issues.
            continue
        for emp in employees:
            sin = emp["sin"]
            boxes = emp["boxes"]
            existing = per_year_sin[year].get(sin, {})
            merged = existing.copy()
            for key, value in boxes.items():
                prev = merged.get(key, Decimal("0.00"))
                merged[key] = max(prev, value)
            per_year_sin[year][sin] = merged

    by_year_totals: Dict[int, Dict[str, Decimal]] = {}
    for year, sin_map in per_year_sin.items():
        agg = {k: Decimal("0.00") for k in T4_BOX_PATTERNS.keys()}
        for boxes in sin_map.values():
            for key, value in boxes.items():
                agg[key] += value
        by_year_totals[year] = agg

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_date": datetime.now().isoformat(),
                "totals_by_year": {
                    str(year): {key: str(value) for key, value in agg.items()}
                    for year, agg in by_year_totals.items()
                },
                "sins_per_year": {
                    str(year): list(sins.keys()) for year, sins in per_year_sin.items()
                },
            },
            f,
            indent=2,
        )

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# T4 PDF Totals Summary\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for year in sorted(by_year_totals.keys()):
            agg = by_year_totals[year]
            f.write(f"## {year}\n")
            f.write("- Sums (PDF, dedup by SIN max):\n")
            f.write(f"  - Box 14 (income): ${agg['box_14']:.2f}\n")
            f.write(f"  - Box 16 (CPP): ${agg['box_16']:.2f}\n")
            f.write(f"  - Box 18 (EI): ${agg['box_18']:.2f}\n")
            f.write(f"  - Box 22 (Tax): ${agg['box_22']:.2f}\n")
            f.write(f"  - Box 24 (EI earnings): ${agg['box_24']:.2f}\n")
            f.write(f"  - Box 26 (CPP earnings): ${agg['box_26']:.2f}\n\n")

    print("✅ T4 PDF totals summary saved.")


if __name__ == "__main__":
    main()
