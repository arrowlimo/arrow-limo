"""
Map UNKNOWN_PAGE entries back to their source PDF files using the inventory.
"""
from __future__ import annotations

import csv
import json
import pdfplumber
import re
from pathlib import Path
from decimal import Decimal

INVENTORY_PATH = Path(r"L:\limo\reports\PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json")
UNKNOWN_PAGE_LIST = Path(r"L:\limo\reports\T4_UNKNOWN_PAGE_LIST.csv")
OUT_CSV = Path(r"L:\limo\reports\T4_UNKNOWN_PAGE_WITH_SOURCE_FILES.csv")

T4_BOXES = {
    "14": r"14[\s\S]{0,100}?(\d{1,10}\.\d{2})",
    "16": r"16[\s\S]{0,100}?(\d{1,10}\.\d{2})",
    "22": r"22[\s\S]{0,100}?(\d{1,10}\.\d{2})",
}


def parse_amount(text: str) -> float:
    clean = text.replace(",", "").replace("$", "").strip()
    try:
        return float(clean)
    except:
        return 0.0


def scan_pdf_page(pdf_path: Path, page_num: int) -> dict | None:
    """Extract box values from specific PDF page."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num - 1 >= len(pdf.pages):
                return None
            page = pdf.pages[page_num - 1]
            page_text = page.extract_text() or ""

            boxes = {}
            for box_num, pattern in T4_BOXES.items():
                match = re.search(pattern, page_text)
                if match:
                    boxes[f"box_{box_num}"] = parse_amount(match.group(1))

            return boxes if boxes else None
    except Exception as e:
        print(f"Error reading {pdf_path} page {page_num}: {e}")
        return None


def main():
    # Load inventory
    with open(INVENTORY_PATH) as f:
        inventory = json.load(f)

    # Load UNKNOWN_PAGE list
    unknown_rows = []
    with open(UNKNOWN_PAGE_LIST) as f:
        reader = csv.DictReader(f)
        for row in reader:
            unknown_rows.append(row)

    # Build mapping: year → pdf_list
    pdf_by_year = {}
    for pdf_entry in inventory.get("documents", []):
        year = pdf_entry.get("year")
        if year not in [2013, 2014]:
            continue
        if "t4" not in pdf_entry.get("category", "").lower():
            continue

        if year not in pdf_by_year:
            pdf_by_year[year] = []
        pdf_by_year[year].append({
            "path": pdf_entry.get("file_path"),
            "status": pdf_entry.get("status"),
        })

    # For each UNKNOWN_PAGE, scan PDFs to find matching box values
    results = []
    for unknown_row in unknown_rows:
        year = int(unknown_row["year"])
        target_box_14 = float(unknown_row["box_14"])
        target_box_22 = float(unknown_row["box_22"])
        target_box_16 = float(unknown_row["box_16"])

        found = False
        if year in pdf_by_year:
            for pdf_info in pdf_by_year[year]:
                pdf_path = Path(pdf_info["path"])
                if not pdf_path.exists():
                    continue

                # Try all pages in this PDF
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        for page_idx, page in enumerate(pdf.pages, 1):
                            page_text = page.extract_text() or ""
                            boxes = {}
                            for box_num, pattern in T4_BOXES.items():
                                match = re.search(pattern, page_text)
                                if match:
                                    boxes[f"box_{box_num}"] = parse_amount(match.group(1))

                            # Check if box values match
                            if (boxes.get("box_14", 0) == target_box_14 and
                                boxes.get("box_22", 0) == target_box_22 and
                                boxes.get("box_16", 0) == target_box_16):
                                results.append({
                                    "year": year,
                                    "unknown_page": unknown_row["sin"],
                                    "box_14": target_box_14,
                                    "box_22": target_box_22,
                                    "box_16": target_box_16,
                                    "source_file": pdf_path.name,
                                    "source_path": str(pdf_path),
                                    "source_page": page_idx,
                                })
                                found = True
                                break
                        if found:
                            break
                except Exception as e:
                    print(f"Error scanning {pdf_path}: {e}")
                    continue

        if not found:
            results.append({
                "year": year,
                "unknown_page": unknown_row["sin"],
                "box_14": target_box_14,
                "box_22": target_box_22,
                "box_16": target_box_16,
                "source_file": "(not found)",
                "source_path": "(scanning required)",
                "source_page": "",
            })

    # Write results
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["year", "unknown_page", "box_14", "box_22", "box_16", "source_file", "source_path", "source_page"],
        )
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"✅ Mapped {len(results)} UNKNOWN_PAGE entries: {OUT_CSV}")
    found_count = sum(1 for r in results if r["source_file"] != "(not found)")
    print(f"   Found in PDFs: {found_count}/{len(results)}")


if __name__ == "__main__":
    main()
