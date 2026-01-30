#!/usr/bin/env python3
"""
Verify Routing.xlsx against ALMS charter_routes.
- Reads L:\limo\data\Routing.xlsx
- Normalizes headers, supports common LMS-style field names
- Maps by reserve_number (business key) to ALMS charters
- Compares first route line with Excel values
- Outputs summary Markdown + detailed JSON/CSV
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import psycopg2
from openpyxl import load_workbook

DATA_PATH = r"L:\limo\data\Routing.xlsx"


def norm(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    return s or None


def normalize_multiline(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    lines = [ln.strip() for ln in str(s).splitlines() if ln and ln.strip()]
    return "\n".join(lines) if lines else None


def parse_time(val: Any) -> Optional[str]:
    # Return HH:MM string for comparison
    from datetime import time, datetime
    if val is None:
        return None
    if isinstance(val, time):
        return f"{val.hour:02d}:{val.minute:02d}"
    if isinstance(val, datetime):
        return f"{val.hour:02d}:{val.minute:02d}"
    # Try simple string parse like '08:30' or '8:30'
    try:
        txt = str(val).strip()
        parts = txt.split(":")
        if len(parts) >= 2:
            h = int(parts[0]); m = int(parts[1])
            return f"{h:02d}:{m:02d}"
    except Exception:
        return None
    return None


def header_map(headers):
    mapping = {}
    for idx, h in enumerate(headers):
        key = str(h).strip().lower()
        if key in ("reserve", "reserve_no", "reserve number", "reserve_number"):
            mapping[idx] = "reserve_no"
        elif key in ("line_1", "pickup_line1", "pickup address", "pickup_location_1"):
            mapping[idx] = "line_1"
        elif key in ("line_2", "pickup_line2", "pickup address 2", "pickup_location_2"):
            mapping[idx] = "line_2"
        elif key in ("from_to", "dropoff", "dropoff address", "dropoff_location"):
            mapping[idx] = "from_to"
        elif key in ("pu_time", "pickup_time"):
            mapping[idx] = "pu_time"
        elif key in ("do_time", "dropoff_time"):
            mapping[idx] = "do_time"
        elif key in ("trip_notes", "notes", "route_notes"):
            mapping[idx] = "trip_notes"
        # ignore other headers
    return mapping


def read_routing_excel(path: str):
    wb = load_workbook(filename=path, data_only=True)
    ws = wb.active
    rows = list(ws.values)
    if not rows:
        return []
    headers = rows[0]
    map_idx = header_map(headers)
    result = []
    for r in rows[1:]:
        rec = {k: None for k in ("reserve_no", "line_1", "line_2", "from_to", "pu_time", "do_time", "trip_notes")}
        for idx, col in map_idx.items():
            val = r[idx] if idx < len(r) else None
            if col in ("line_1", "line_2", "from_to", "trip_notes"):
                rec[col] = norm(val)
            elif col in ("pu_time", "do_time"):
                rec[col] = parse_time(val)
            elif col == "reserve_no":
                rec[col] = norm(val)
        if rec["reserve_no"] and any(rec[k] for k in ("line_1", "line_2", "from_to", "pu_time", "do_time", "trip_notes")):
            result.append(rec)
    return result


def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "***REDACTED***"),
    )


def fetch_charter_routes_for_reserve(cur, reserve_number: str):
    cur.execute(
        """
        SELECT cr.pickup_location, cr.pickup_time, cr.dropoff_location, cr.dropoff_time, cr.route_notes
        FROM charter_routes cr
        JOIN charters c ON c.charter_id = cr.charter_id
        WHERE c.reserve_number = %s
        ORDER BY cr.route_sequence
        """,
        (reserve_number,),
    )
    return cur.fetchall()


def main() -> int:
    if not os.path.exists(DATA_PATH):
        print(f"❌ Routing.xlsx not found: {DATA_PATH}")
        return 1
    print(f"Reading: {DATA_PATH}")
    excel_rows = read_routing_excel(DATA_PATH)
    print(f"Excel routing rows with data: {len(excel_rows)}")

    pg = get_pg_conn(); cur = pg.cursor()

    stats = {"missing_routes": 0, "mismatches": 0, "exact": 0}
    mismatches = []
    missing = []

    for rec in excel_rows:
        reserve = rec["reserve_no"]
        rows = fetch_charter_routes_for_reserve(cur, reserve)
        pickup_location = normalize_multiline("\n".join([p for p in [rec.get("line_1"), rec.get("line_2")] if p]))
        dropoff_location = normalize_multiline(rec.get("from_to"))
        pu_time = rec.get("pu_time")
        do_time = rec.get("do_time")
        notes = rec.get("trip_notes")

        if not rows:
            stats["missing_routes"] += 1
            missing.append({"reserve_no": reserve, "pickup": pickup_location, "dropoff": dropoff_location, "pu_time": pu_time, "do_time": do_time, "notes": notes})
            continue

        cr_pickup, cr_pu_time, cr_dropoff, cr_do_time, cr_notes = rows[0]

        def time_str(t) -> Optional[str]:
            if t is None:
                return None
            return f"{t.hour:02d}:{t.minute:02d}"

        ok = True
        if normalize_multiline(cr_pickup) != pickup_location:
            ok = False
        if normalize_multiline(cr_dropoff) != dropoff_location:
            ok = False
        if time_str(cr_pu_time) != pu_time:
            ok = False
        if time_str(cr_do_time) != do_time:
            ok = False
        if notes and cr_notes and notes.strip() not in cr_notes.strip():
            ok = False

        if ok:
            stats["exact"] += 1
        else:
            stats["mismatches"] += 1
            mismatches.append({
                "reserve_no": reserve,
                "excel_pickup": pickup_location,
                "excel_dropoff": dropoff_location,
                "excel_pu_time": pu_time,
                "excel_do_time": do_time,
                "excel_notes": notes,
                "cr_pickup": normalize_multiline(cr_pickup),
                "cr_dropoff": normalize_multiline(cr_dropoff),
                "cr_pu_time": time_str(cr_pu_time),
                "cr_do_time": time_str(cr_do_time),
                "cr_notes": cr_notes,
            })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"l:/limo/reports/ROUTING_XLSX_AUDIT_{ts}"
    os.makedirs("l:/limo/reports", exist_ok=True)

    import json, csv
    with open(base + "_missing.json", "w", encoding="utf-8") as f:
        json.dump(missing, f, ensure_ascii=False, indent=2)
    with open(base + "_mismatches.json", "w", encoding="utf-8") as f:
        json.dump(mismatches, f, ensure_ascii=False, indent=2)

    with open(base + "_mismatches.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["reserve_no", "excel_pickup", "excel_dropoff", "excel_pu_time", "excel_do_time", "excel_notes", "cr_pickup", "cr_dropoff", "cr_pu_time", "cr_do_time", "cr_notes"])
        for m in mismatches:
            w.writerow([m[k] for k in ("reserve_no", "excel_pickup", "excel_dropoff", "excel_pu_time", "excel_do_time", "excel_notes", "cr_pickup", "cr_dropoff", "cr_pu_time", "cr_do_time", "cr_notes")])

    md = [
        "# Routing.xlsx Audit",
        f"Generated: {ts}",
        "",
        "## Summary",
        f"- Excel rows with routing: {len(excel_rows)}",
        f"- Missing charter_routes: {stats['missing_routes']}",
        f"- Mismatches: {stats['mismatches']}",
        f"- Exact matches: {stats['exact']}",
        "",
        "## Files",
        f"- Missing JSON: {base + '_missing.json'}",
        f"- Mismatches JSON: {base + '_mismatches.json'}",
        f"- Mismatches CSV: {base + '_mismatches.csv'}",
    ]
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n✅ Excel routing audit complete")
    print(f"   Missing routes: {stats['missing_routes']}")
    print(f"   Mismatches: {stats['mismatches']}")
    print(f"   Exact matches: {stats['exact']}")

    cur.close(); pg.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
