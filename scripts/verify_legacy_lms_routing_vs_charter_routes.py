#!/usr/bin/env python3
"""
Verify legacy LMS routing info against ALMS charter_routes.
- Loads routing-related fields from LMS Reserve
- Maps by reserve_number (business key) to ALMS charters
- Compares against existing charter_routes rows
- Reports missing routes and mismatches per field
"""

import os
import sys
import datetime as dt
from typing import Any, Dict, Optional, Tuple

import psycopg2
import pyodbc

DEFAULT_LMS_PATH = r"L:\limo\backups\lms.mdb"


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def extract_time(value: Any) -> Optional[dt.time]:
    """Access stores times as datetime with base date 1899-12-30."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.time()
    if isinstance(value, dt.time):
        return value
    # Attempt parse
    try:
        return dt.datetime.fromisoformat(str(value)).time()
    except Exception:
        return None


def get_lms_conn(path: str):
    return pyodbc.connect(rf"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};")


def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "***REMOVED***"),
    )


def fetch_lms_reserve(cur_lms):
    cur_lms.execute(
        """
        SELECT Reserve_No, PU_Date, PU_Time, Do_Time, Drop_Off,
               Line_1, Line_2, From_To, Trip_Notes
        FROM Reserve
        WHERE Reserve_No IS NOT NULL
        """
    )
    rows = []
    for row in cur_lms.fetchall():
        reserve_no = clean_text(row[0])
        if not reserve_no:
            continue
        rows.append(
            {
                "reserve_no": reserve_no,
                "pu_date": row[1],
                "pu_time": extract_time(row[2]),
                "do_time": extract_time(row[3]),
                "drop_off_time": extract_time(row[4]),
                "line_1": clean_text(row[5]),
                "line_2": clean_text(row[6]),
                "from_to": clean_text(row[7]),
                "trip_notes": clean_text(row[8]),
            }
        )
    return rows


def build_pickup_location(line1: Optional[str], line2: Optional[str]) -> Optional[str]:
    parts = [p for p in [line1, line2] if p]
    return "\n".join(parts) if parts else None


def normalize(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return "\n".join([p.strip() for p in str(s).splitlines() if p.strip()])


def fetch_charter_routes_for_reserve(cur_pg, reserve_number: str):
    cur_pg.execute(
        """
        SELECT cr.pickup_location, cr.pickup_time, cr.dropoff_location, cr.dropoff_time, cr.route_notes
        FROM charter_routes cr
        JOIN charters c ON c.charter_id = cr.charter_id
        WHERE c.reserve_number = %s
        ORDER BY cr.route_sequence
        """,
        (reserve_number,),
    )
    return cur_pg.fetchall()


def main() -> int:
    lms_path = os.getenv("LMS_PATH", DEFAULT_LMS_PATH)
    print(f"LMS: {lms_path}")
    try:
        lms = get_lms_conn(lms_path); lcur = lms.cursor()
    except Exception as e:
        print(f"❌ Could not open LMS.mdb: {e}")
        return 1
    pg = get_pg_conn(); pcur = pg.cursor()

    lms_rows = fetch_lms_reserve(lcur)
    print(f"Fetched {len(lms_rows)} LMS Reserve rows")

    stats = {
        "total_with_routing": 0,
        "matched_charters": 0,
        "missing_routes": 0,
        "mismatched_routes": 0,
        "exact_matches": 0,
    }

    mismatches = []
    missing = []

    for r in lms_rows:
        # Determine if LMS row has any routing info
        pickup_location = build_pickup_location(r["line_1"], r["line_2"])
        dropoff_location = r["from_to"]
        pickup_time = r["pu_time"]
        dropoff_time = r["do_time"] or r["drop_off_time"]
        route_notes = r["trip_notes"]
        has_routing = any([pickup_location, dropoff_location, pickup_time, dropoff_time, route_notes])
        if not has_routing:
            continue
        stats["total_with_routing"] += 1

        # Fetch charter_routes for this reserve
        rows = fetch_charter_routes_for_reserve(pcur, r["reserve_no"])
        if not rows:
            stats["missing_routes"] += 1
            missing.append({"reserve_no": r["reserve_no"], "pickup": pickup_location, "dropoff": dropoff_location})
            continue
        stats["matched_charters"] += 1

        # Compare first route line (sequence=1) against LMS synthesized values
        cr_pickup, cr_pu_time, cr_dropoff, cr_do_time, cr_notes = rows[0]

        def times_equal(a: Optional[dt.time], b: Optional[dt.time]) -> bool:
            if a is None and b is None:
                return True
            if a is None or b is None:
                return False
            return (a.hour, a.minute) == (b.hour, b.minute)

        ok = True
        expected_pickup = normalize(pickup_location)
        expected_dropoff = normalize(dropoff_location)
        if normalize(cr_pickup) != expected_pickup:
            ok = False
        if normalize(cr_dropoff) != expected_dropoff:
            ok = False
        if not times_equal(cr_pu_time, pickup_time):
            ok = False
        if not times_equal(cr_do_time, dropoff_time):
            ok = False
        # Notes: allow partial match
        if route_notes and cr_notes and route_notes.strip() not in cr_notes.strip():
            ok = False

        if ok:
            stats["exact_matches"] += 1
        else:
            stats["mismatched_routes"] += 1
            mismatches.append(
                {
                    "reserve_no": r["reserve_no"],
                    "lms_pickup": expected_pickup,
                    "lms_dropoff": expected_dropoff,
                    "lms_pu_time": pickup_time.isoformat() if pickup_time else None,
                    "lms_do_time": dropoff_time.isoformat() if dropoff_time else None,
                    "lms_notes": route_notes,
                    "cr_pickup": normalize(cr_pickup),
                    "cr_dropoff": normalize(cr_dropoff),
                    "cr_pu_time": cr_pu_time.isoformat() if cr_pu_time else None,
                    "cr_do_time": cr_do_time.isoformat() if cr_do_time else None,
                    "cr_notes": cr_notes,
                }
            )

    # Write report
    import json
    import csv
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"l:/limo/reports/LMS_ROUTING_AUDIT_{ts}"

    os.makedirs("l:/limo/reports", exist_ok=True)
    with open(base + "_mismatches.json", "w", encoding="utf-8") as f:
        json.dump(mismatches, f, ensure_ascii=False, indent=2)
    with open(base + "_missing.json", "w", encoding="utf-8") as f:
        json.dump(missing, f, ensure_ascii=False, indent=2)

    # CSV for quick viewing
    with open(base + "_mismatches.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "reserve_no", "lms_pickup", "lms_dropoff", "lms_pu_time", "lms_do_time", "lms_notes",
            "cr_pickup", "cr_dropoff", "cr_pu_time", "cr_do_time", "cr_notes",
        ])
        for m in mismatches:
            w.writerow([
                m["reserve_no"], m["lms_pickup"], m["lms_dropoff"], m["lms_pu_time"], m["lms_do_time"], m["lms_notes"],
                m["cr_pickup"], m["cr_dropoff"], m["cr_pu_time"], m["cr_do_time"], m["cr_notes"],
            ])

    # Markdown summary
    md = [
        "# LMS Routing Audit",
        f"Generated: {ts}",
        "",
        "## Summary",
        f"- LMS rows with routing: {stats['total_with_routing']}",
        f"- Charters matched: {stats['matched_charters']}",
        f"- Missing charter_routes: {stats['missing_routes']}",
        f"- Mismatched routes: {stats['mismatched_routes']}",
        f"- Exact matches: {stats['exact_matches']}",
        "",
        "## Files",
        f"- Mismatches JSON: {base + '_mismatches.json'}",
        f"- Missing JSON: {base + '_missing.json'}",
        f"- Mismatches CSV: {base + '_mismatches.csv'}",
    ]
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n✅ Audit complete")
    print(f"   Mismatches: {stats['mismatched_routes']}")
    print(f"   Missing routes: {stats['missing_routes']}")
    print(f"   Exact matches: {stats['exact_matches']}")

    pcur.close(); pg.close(); lcur.close(); lms.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
