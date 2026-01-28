#!/usr/bin/env python3
"""
Insert a single `charter_routes` row for a given reserve from Routing.xlsx.
- Reads L:\limo\data\Routing.xlsx directly
- Filters rows for --reserve and constructs a simple route entry
- Uses earliest row with a time and a location for pickup; notes included

Usage:
  python insert_one_route_from_excel.py --reserve 006717 --dry-run
  python insert_one_route_from_excel.py --reserve 006717 --apply
"""
import os
import sys
from datetime import time
from typing import Optional, List, Dict

import psycopg2
from openpyxl import load_workbook

DATA_PATH = r"L:\limo\data\Routing.xlsx"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def parse_hhmm(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    try:
        parts = str(s).strip().split(":")
        h = int(parts[0]); m = int(parts[1])
        return time(hour=h, minute=m)
    except Exception:
        return None


def header_map(headers):
    mapping = {}
    for idx, h in enumerate(headers):
        key = str(h).strip().lower()
        if key in ("reserve", "reserve_no", "reserve number", "reserve_no", "reserve_no."):
            mapping[idx] = "reserve_no"
        elif key in ("line1", "line_1", "pickup address", "street"):
            mapping[idx] = "line_1"
        elif key in ("line2", "line_2", "pickup address 2", "suite"):
            mapping[idx] = "line_2"
        elif key in ("city",):
            mapping[idx] = "city"
        elif key in ("phone", "telephone"):
            mapping[idx] = "phone"
        elif key in ("notes", "directions", "trip_notes"):
            mapping[idx] = "notes"
        elif key in ("time", "pu_time", "pickup_time"):
            mapping[idx] = "pu_time"
        elif key in ("type", "route_type"):
            mapping[idx] = "type"
    return mapping


def read_routing_for_reserve(path: str, reserve_filter: str) -> List[Dict[str, Optional[str]]]:
    wb = load_workbook(filename=path, data_only=True)
    ws = wb.active
    rows = list(ws.values)
    if not rows:
        return []
    headers = rows[0]
    map_idx = header_map(headers)
    out = []
    for r in rows[1:]:
        rec = {k: None for k in ("reserve_no", "line_1", "line_2", "city", "phone", "notes", "pu_time", "type")}
        for idx, col in map_idx.items():
            val = r[idx] if idx < len(r) else None
            if col in ("line_1", "line_2", "city", "phone", "notes", "type"):
                rec[col] = str(val).strip() if val is not None else None
            elif col == "pu_time":
                if val is None:
                    rec[col] = None
                else:
                    if hasattr(val, 'hour') and hasattr(val, 'minute'):
                        rec[col] = f"{val.hour:02d}:{val.minute:02d}"
                    else:
                        txt = str(val).strip()
                        parts = txt.split(":")
                        if len(parts) >= 2:
                            try:
                                h = int(parts[0]); m = int(parts[1])
                                rec[col] = f"{h:02d}:{m:02d}"
                            except Exception:
                                rec[col] = None
                        else:
                            rec[col] = None
            elif col == "reserve_no":
                rec[col] = str(val).strip() if val is not None else None
        if rec["reserve_no"] == reserve_filter:
            out.append(rec)
    return out


def main() -> int:
    if "--reserve" not in sys.argv:
        print("❌ Provide --reserve <Reserve_No>")
        return 1
    reserve = sys.argv[sys.argv.index("--reserve")+1]
    apply = "--apply" in sys.argv

    if not os.path.exists(DATA_PATH):
        print(f"❌ Routing.xlsx not found: {DATA_PATH}")
        return 1

    rows = read_routing_for_reserve(DATA_PATH, reserve)
    if not rows:
        print(f"❌ No rows found in Routing.xlsx for reserve {reserve}")
        return 1

    # Pick earliest row with a time and some location detail for pickup
    candidate = None
    for r in rows:
        has_loc = any([r.get("line_1"), r.get("city"), r.get("phone")])
        if r.get("pu_time") and has_loc:
            candidate = r
            break
    if not candidate:
        # Fallback: any row with location detail
        for r in rows:
            has_loc = any([r.get("line_1"), r.get("city"), r.get("phone")])
            if has_loc:
                candidate = r
                break
    if not candidate:
        print("❌ Could not find a suitable row with location info")
        return 1

    # Compose pickup_location string
    parts = []
    for key in ("line_1", "line_2", "city", "phone"):
        if candidate.get(key):
            parts.append(candidate[key])
    pickup_location = "\n".join(parts) if parts else None
    pu_time_str = candidate.get("pu_time")
    pu_time = parse_hhmm(pu_time_str)
    notes = candidate.get("notes")

    print(f"Candidate for reserve {reserve}:")
    print(f"  Pickup location:\n{pickup_location}")
    print(f"  Pickup time: {pu_time_str}")
    print(f"  Notes: {notes}")

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    # Find charter_id (try exact, then trim leading zeros)
    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1", (reserve,))
    row = cur.fetchone()
    if not row:
        cur.execute("SELECT charter_id FROM charters WHERE ltrim(reserve_number,'0') = ltrim(%s,'0') LIMIT 1", (reserve,))
        row = cur.fetchone()
    if not row:
        print(f"❌ Charter not found for reserve {reserve}")
        cur.close(); conn.close()
        return 1
    charter_id = row[0]

    # Determine next route_sequence for this charter
    cur.execute("SELECT COALESCE(MAX(route_sequence), 0) FROM charter_routes WHERE charter_id = %s", (charter_id,))
    next_seq = (cur.fetchone()[0] or 0) + 1

    if not apply:
        print("\nDRY-RUN: Would insert one route with above values.")
        cur.close(); conn.close()
        return 0

    cur.execute(
        """
        INSERT INTO charter_routes (
            charter_id, route_sequence, pickup_location, pickup_time,
            dropoff_location, dropoff_time, route_notes, route_status
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            charter_id,
            next_seq,
            pickup_location,
            pu_time,
            None,
            None,
            notes,
            "pending",
        ),
    )
    conn.commit()
    print("\n✅ Inserted one route from Routing.xlsx for testing")
    cur.close(); conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
