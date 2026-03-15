"""
Analyze T4 reconciliation data to identify unmapped patterns and generate a summary.
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

RECON_PATH = Path(r"L:\limo\reports\T4_RECONCILIATION_REPORT.json")
OUT_PATH = Path(r"L:\limo\reports\T4_ANALYSIS_UNMAPPED_ENTRIES.json")


def main():
    with open(RECON_PATH) as f:
        recon = json.load(f)

    analysis = {
        "generated": str(Path(RECON_PATH).stat().st_mtime),
        "by_year": {},
    }

    for year_str in ["2013", "2014"]:
        year_data = recon.get("results_by_year", {}).get(year_str, {})
        pdf_only = year_data.get("pdf_only", [])
        discrepancies = year_data.get("discrepancies", [])

        # Categorize unmapped entries
        unmapped_patterns = defaultdict(list)
        mapped_count = 0
        unmapped_count = 0

        for entry in pdf_only + discrepancies:
            sin = entry.get("sin", "")
            emp_name = entry.get("employee_name", "")
            
            if sin.startswith("UNKNOWN_PAGE"):
                unmapped_patterns["UNKNOWN_PAGE (OCR-locked PDF)"].append({
                    "sin": sin,
                    "employee_name": emp_name or "(blank)",
                })
                unmapped_count += 1
            elif sin and not emp_name:
                unmapped_patterns["SIN found but no employee_name"].append({
                    "sin": sin,
                    "employee_name": "(blank)",
                })
                unmapped_count += 1
            elif emp_name and sin not in ["UNKNOWN_PAGE1", "UNKNOWN_PAGE2", "UNKNOWN_PAGE3", "UNKNOWN_PAGE5", "UNKNOWN_PAGE8", "UNKNOWN_PAGE10", "UNKNOWN_PAGE12", "UNKNOWN_PAGE16", "UNKNOWN_PAGE23", "UNKNOWN_PAGE24"]:
                # This would be a valid employee name + SIN combo
                mapped_count += 1
            else:
                unmapped_patterns[f"Other unmapped ({sin[:20]})"].append({
                    "sin": sin,
                    "employee_name": emp_name or "(blank)",
                })
                unmapped_count += 1

        analysis["by_year"][year_str] = {
            "pdf_only_count": len(pdf_only),
            "discrepancies_count": len(discrepancies),
            "total_entries": len(pdf_only) + len(discrepancies),
            "mapped_count": mapped_count,
            "unmapped_count": unmapped_count,
            "unmapped_patterns": {k: len(v) for k, v in unmapped_patterns.items()},
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"✅ Analysis saved: {OUT_PATH}")
    for year_str, stats in analysis["by_year"].items():
        print(f"\n{year_str}:")
        print(f"  Total entries: {stats['total_entries']}")
        print(f"  Mapped: {stats['mapped_count']}")
        print(f"  Unmapped: {stats['unmapped_count']}")
        print(f"  Patterns:")
        for pattern, count in stats["unmapped_patterns"].items():
            print(f"    - {pattern}: {count}")


if __name__ == "__main__":
    main()
