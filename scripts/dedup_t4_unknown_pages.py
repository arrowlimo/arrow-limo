"""
Deduplication analysis for UNKNOWN_PAGE entries.
Identifies exact duplicates, potential corrected versions, and suspicious entries.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import defaultdict

UNKNOWN_PAGE_LIST = Path(r"L:\limo\reports\T4_UNKNOWN_PAGE_LIST.csv")
OUT_JSON = Path(r"L:\limo\reports\T4_DEDUPLICATION_ANALYSIS.json")


def main():
    # Load UNKNOWN_PAGE entries
    rows = []
    with open(UNKNOWN_PAGE_LIST) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    analysis = {
        "total_entries": len(rows),
        "by_year": {},
        "duplicates": [],
        "suspicious": [],
        "recommended_keep": [],
    }

    # Group by year
    by_year = defaultdict(list)
    for row in rows:
        year = int(row["year"])
        by_year[year].append(row)

    # Analyze by year
    for year in sorted(by_year.keys()):
        entries = by_year[year]
        
        # Group by exact box values (exact duplicates)
        by_signature = defaultdict(list)
        for i, entry in enumerate(entries):
            sig = (
                entry["box_14"],
                entry["box_16"],
                entry["box_18"],
                entry["box_22"],
                entry["box_24"],
                entry["box_26"],
            )
            by_signature[sig].append(i)

        exact_dups = {sig: indices for sig, indices in by_signature.items() if len(indices) > 1}
        
        analysis["by_year"][year] = {
            "total": len(entries),
            "exact_duplicate_sets": len(exact_dups),
            "exact_duplicate_entries": sum(len(idx) - 1 for idx in exact_dups.values()),
        }

        # Mark exact duplicates
        for sig, indices in exact_dups.items():
            # Keep first, mark rest as duplicates
            keep_idx = indices[0]
            for dup_idx in indices[1:]:
                entry = entries[dup_idx]
                analysis["duplicates"].append({
                    "year": year,
                    "sin": entry["sin"],
                    "box_14": entry["box_14"],
                    "box_22": entry["box_22"],
                    "box_16": entry["box_16"],
                    "reason": f"Exact duplicate of entry at index {keep_idx}",
                    "action": "REMOVE",
                })

        # Flag suspicious entries (very small amounts, missing critical boxes)
        for i, entry in enumerate(entries):
            box_14 = float(entry["box_14"])
            box_22 = float(entry["box_22"])
            box_16 = float(entry["box_16"])

            reason = None
            if box_14 < 1:
                reason = "Income < $1.00 (suspicious)"
            elif box_14 < 10 and box_22 < 1 and box_16 < 1:
                reason = "Very low income with no tax/CPP (suspicious)"

            if reason:
                analysis["suspicious"].append({
                    "year": year,
                    "index": i,
                    "sin": entry["sin"],
                    "box_14": entry["box_14"],
                    "box_22": entry["box_22"],
                    "box_16": entry["box_16"],
                    "reason": reason,
                    "action": "REVIEW",
                })

    # Recommended keep: entries that are NOT exact duplicates or suspicious
    dup_indices = set()
    for dup in analysis["duplicates"]:
        # Find the original row index
        year = dup["year"]
        year_entries = by_year[year]
        for i, entry in enumerate(year_entries):
            if (
                entry["sin"] == dup["sin"]
                and entry["box_14"] == dup["box_14"]
                and entry["box_22"] == dup["box_22"]
            ):
                dup_indices.add((year, i))

    sus_indices = set()
    for sus in analysis["suspicious"]:
        sus_indices.add((sus["year"], sus["index"]))

    for year in sorted(by_year.keys()):
        year_entries = by_year[year]
        for i, entry in enumerate(year_entries):
            if (year, i) not in dup_indices and (year, i) not in sus_indices:
                analysis["recommended_keep"].append({
                    "year": year,
                    "sin": entry["sin"],
                    "box_14": entry["box_14"],
                    "box_22": entry["box_22"],
                    "box_16": entry["box_16"],
                })

    # Save results
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        # Convert to serializable format
        result = {
            "total_entries": analysis["total_entries"],
            "by_year": analysis["by_year"],
            "summary": {
                "exact_duplicates_to_remove": len(analysis["duplicates"]),
                "suspicious_entries_to_review": len(analysis["suspicious"]),
                "safe_to_load": len(analysis["recommended_keep"]),
            },
            "duplicates": analysis["duplicates"],
            "suspicious": analysis["suspicious"],
            "recommended_keep": analysis["recommended_keep"],
        }
        json.dump(result, f, indent=2)

    # Print summary
    print(f"✅ Deduplication analysis saved: {OUT_JSON}\n")
    print(f"Total entries: {analysis['total_entries']}")
    print(f"Exact duplicates to REMOVE: {len(analysis['duplicates'])}")
    print(f"Suspicious entries to REVIEW: {len(analysis['suspicious'])}")
    print(f"Safe to load: {len(analysis['recommended_keep'])}\n")
    
    for year in sorted(by_year.keys()):
        print(f"{year}:")
        print(f"  Total: {analysis['by_year'][year]['total']}")
        print(f"  Exact dups: {analysis['by_year'][year]['exact_duplicate_entries']}")

    print(f"\n📋 Duplicates to remove:")
    for dup in analysis["duplicates"]:
        print(f"  {dup['year']} {dup['sin']}: ${dup['box_14']} income (dup of earlier entry)")

    print(f"\n⚠️  Suspicious entries to review:")
    for sus in analysis["suspicious"]:
        print(f"  {sus['year']} {sus['sin']}: ${sus['box_14']} income - {sus['reason']}")


if __name__ == "__main__":
    main()
