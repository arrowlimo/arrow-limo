"""
Extract UNKNOWN_PAGE entries from T4 reconciliation for manual inspection.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

RECON_PATH = Path(r"L:\limo\reports\T4_RECONCILIATION_REPORT.json")
OUT_CSV = Path(r"L:\limo\reports\T4_UNKNOWN_PAGE_LIST.csv")


def main():
    with open(RECON_PATH) as f:
        recon = json.load(f)

    rows = []
    for year_str, year_data in recon.get("results_by_year", {}).items():
        year = int(year_str)
        for entry in year_data.get("pdf_only", []) + year_data.get("discrepancies", []):
            sin = entry.get("sin", "")
            if not sin.startswith("UNKNOWN_PAGE"):
                continue

            emp_name = entry.get("employee_name", "")
            boxes = entry.get("boxes", {})
            if not boxes:
                issues = entry.get("issues", [])
                boxes = {i.get("box"): i.get("pdf_value", 0) for i in issues if i.get("box")}

            rows.append({
                "year": year,
                "sin": sin,
                "employee_name": emp_name or "(blank)",
                "box_14": boxes.get("box_14", 0) or 0,
                "box_16": boxes.get("box_16", 0) or 0,
                "box_18": boxes.get("box_18", 0) or 0,
                "box_22": boxes.get("box_22", 0) or 0,
                "box_24": boxes.get("box_24", 0) or 0,
                "box_26": boxes.get("box_26", 0) or 0,
            })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["year", "sin", "employee_name", "box_14", "box_16", "box_18", "box_22", "box_24", "box_26"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"✅ Extracted {len(rows)} UNKNOWN_PAGE entries: {OUT_CSV}")
    
    # Print summary
    by_year = {}
    for row in rows:
        year = row["year"]
        by_year.setdefault(year, []).append(row)
    
    for year in sorted(by_year.keys()):
        print(f"\n{year}: {len(by_year[year])} entries")
        for row in by_year[year]:
            print(f"  {row['sin']}: {row['employee_name']} | box_14={row['box_14']}, box_22={row['box_22']}, box_16={row['box_16']}")


if __name__ == "__main__":
    main()
