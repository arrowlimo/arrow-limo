"""
Export per-SIN T4 PDF details for all years (no DB writes).
- Reads PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json and scans T4 PDFs
- Extracts boxes 14, 16, 18, 22, 24, 26 per SIN per year
- Dedupes by (year, sin) keeping max value per box across duplicates
- Writes JSON and CSV for downstream DB loading or review
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

INVENTORY_PATH = Path(r"L:\\limo\\reports\\PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json")
OUTPUT_JSON = Path(r"L:\\limo\\reports\\T4_PDF_DETAIL_EXPORT.json")
OUTPUT_CSV = Path(r"L:\\limo\\reports\\T4_PDF_DETAIL_EXPORT.csv")

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
    rows: List[dict] = []
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
            if sin and boxes.get("box_14", Decimal("0")) > 0:
                rows.append({
                    "sin": sin,
                    "year": year,
                    "boxes": boxes,
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
    t4_docs = [doc for doc in documents if "T4" in doc.get("categories", [])]

    # year -> sin -> aggregated boxes
    per_year_sin: Dict[int, Dict[str, Dict[str, Decimal]]] = defaultdict(dict)
    # Detailed rows (per page match)
    detail_rows: List[dict] = []

    for doc in t4_docs:
        path = Path(doc["path"])
        year = doc.get("year")
        if year is None or not path.exists():
            continue
        try:
            rows = extract_t4_pdf(path, year)
        except Exception:
            continue
        detail_rows.extend(rows)
        for row in rows:
            sin = row["sin"]
            boxes = row["boxes"]
            existing = per_year_sin[year].get(sin, {})
            merged = existing.copy()
            for key, value in boxes.items():
                prev = merged.get(key, Decimal("0.00"))
                merged[key] = max(prev, value)
            per_year_sin[year][sin] = merged

    # Flatten deduped rows
    dedup_rows: List[dict] = []
    for year, sins in per_year_sin.items():
        for sin, boxes in sins.items():
            dedup_rows.append({
                "year": year,
                "sin": sin,
                **{k: float(v) for k, v in boxes.items()},
            })

    serializable_detail = []
    for row in detail_rows:
        serializable_detail.append({
            "sin": row["sin"],
            "year": row["year"],
            "source_file": row["source_file"],
            "boxes": {k: float(v) for k, v in row["boxes"].items()},
        })

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.now().isoformat(),
            "dedup_by_year_sin": dedup_rows,
            "detail_rows": serializable_detail,
        }, f, indent=2)

    fieldnames = ["year", "sin", "box_14", "box_16", "box_18", "box_22", "box_24", "box_26"]
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in dedup_rows:
            writer.writerow({fn: row.get(fn, "") for fn in fieldnames})

    print("✅ T4 PDF detail export saved.")


if __name__ == "__main__":
    main()
