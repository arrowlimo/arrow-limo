"""
Generate a verification worksheet for UNKNOWN_PAGE entries.
Shows unique T4 signatures and guidance for cross-reference against CRA submission.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import defaultdict

DEDUP_JSON = Path(r"L:\limo\reports\T4_DEDUPLICATION_ANALYSIS.json")
OUT_CSV = Path(r"L:\limo\reports\T4_VERIFICATION_WORKSHEET.csv")


def main():
    with open(DEDUP_JSON) as f:
        analysis = json.load(f)

    # Extract unique safe + suspicious entries (not the dups)
    unique_entries = []
    seen = set()

    # Add safe-to-load entries first
    for entry in analysis["recommended_keep"]:
        key = (entry["year"], entry["box_14"], entry["box_22"], entry["box_16"])
        if key not in seen:
            unique_entries.append({
                "year": entry["year"],
                "box_14": entry["box_14"],
                "box_16": entry["box_16"],
                "box_22": entry["box_22"],
                "status": "SAFE - Load this",
                "action": "ADD to mapping",
                "notes": "Verified unique, not a duplicate",
            })
            seen.add(key)

    # Add suspicious entries with guidance
    for entry in analysis["suspicious"]:
        key = (entry["year"], entry["box_14"], entry["box_22"], entry["box_16"])
        if key not in seen:
            unique_entries.append({
                "year": entry["year"],
                "box_14": entry["box_14"],
                "box_16": entry["box_16"],
                "box_22": entry["box_22"],
                "status": "SUSPICIOUS - Review",
                "action": "Check CRA submission or emails",
                "notes": entry["reason"],
            })
            seen.add(key)

    # Sort by year, then by box_14
    unique_entries.sort(key=lambda e: (e["year"], float(e["box_14"])))

    # Write worksheet
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "year",
                "box_14_income",
                "box_22_tax",
                "box_16_cpp",
                "status",
                "action",
                "notes",
                "cra_submission_match",
                "employee_name_inferred",
                "decision",
            ],
        )
        writer.writeheader()
        for entry in unique_entries:
            writer.writerow({
                "year": entry["year"],
                "box_14_income": entry["box_14"],
                "box_22_tax": entry["box_22"],
                "box_16_cpp": entry["box_16"],
                "status": entry["status"],
                "action": entry["action"],
                "notes": entry["notes"],
                "cra_submission_match": "(to be filled)",
                "employee_name_inferred": "(to be filled)",
                "decision": "(KEEP / DISCARD)",
            })

    print(f"✅ Verification worksheet created: {OUT_CSV}")
    print(f"\nUnique T4 signatures found after deduplication: {len(unique_entries)}")
    print("\nInstructions:")
    print("1. Open the CSV file")
    print("2. For each row, check your CRA T4 submission records or emails")
    print("3. Fill in 'cra_submission_match' (YES/NO)")
    print("4. Fill in 'employee_name_inferred' (if you can identify from context)")
    print("5. Mark 'decision' as KEEP or DISCARD")
    print("6. Use the populated file to update T4_NAME_SIN_MAPPING.csv")


if __name__ == "__main__":
    main()
