#!/usr/bin/env python3
"""Backfill charter_routes and optional charter fields from LMS Reserve.

Default mode is dry-run. Use --apply to write changes.

Mappings (Reserve -> charter_routes):
- pickup_location: Line_1 (+ Line_2 if present)
- pickup_time: PU_Time (time-only)
- dropoff_location: From_To (if present)
- dropoff_time: Do_Time else Drop_Off (time-only)
- route_notes: Trip_Notes
- route_sequence: 1; route_status default

Optional charter updates (when --update-charters):
- pickup_address, dropoff_address, pickup_time, dropoff_time filled from the same sources
- Only fills nulls unless --force-overwrite is provided

Keying: reserve_number is the business key.
"""

import argparse
import datetime as dt
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

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


def fetch_lms_reserve(conn) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            Reserve_No,
            PU_Date,
            PU_Time,
            Do_Time,
            Drop_Off,
            Line_1,
            Line_2,
            From_To,
            Trip_Notes
        FROM Reserve
        WHERE Reserve_No IS NOT NULL
        """
    )
    rows = []
    for row in cur.fetchall():
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


def load_charters(pg_cur) -> Dict[str, Dict[str, Any]]:
    pg_cur.execute(
        """
        SELECT charter_id, reserve_number, pickup_address, dropoff_address,
               pickup_time
        FROM charters
        WHERE reserve_number IS NOT NULL
        """
    )
    mapping: Dict[str, Dict[str, Any]] = {}
    for charter_id, reserve_number, pu_addr, do_addr, pu_time in pg_cur.fetchall():
        if reserve_number is None:
            continue
        mapping[str(reserve_number).strip()] = {
            "charter_id": charter_id,
            "pickup_address": pu_addr,
            "dropoff_address": do_addr,
            "pickup_time": pu_time,
        }
    return mapping


def existing_route_counts(pg_cur) -> Dict[int, int]:
    pg_cur.execute("SELECT charter_id, COUNT(*) FROM charter_routes GROUP BY charter_id")
    return {row[0]: row[1] for row in pg_cur.fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill charter_routes from LMS Reserve")
    parser.add_argument("--apply", action="store_true", help="Execute writes (default is dry-run)")
    parser.add_argument("--lms-path", default=DEFAULT_LMS_PATH, help="Path to lms.mdb")
    parser.add_argument("--update-charters", action="store_true", help="Also fill top-level charter pickup/dropoff fields")
    parser.add_argument("--force-overwrite", action="store_true", help="When updating charters, overwrite non-null fields")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of LMS rows processed (for testing)")
    args = parser.parse_args()

    print("Mode: {}".format("APPLY" if args.apply else "DRY-RUN"))
    print(f"LMS: {args.lms_path}")

    if not os.path.exists(args.lms_path):
        print("LMS file not found")
        return 1

    lms_conn = pyodbc.connect(rf"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={args.lms_path};")
    pg_conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "***REMOVED***"),
    )
    pg_cur = pg_conn.cursor()

    reserve_rows = fetch_lms_reserve(lms_conn)
    if args.limit:
        reserve_rows = reserve_rows[: args.limit]
    print(f"Fetched {len(reserve_rows)} reserve rows from LMS")

    charters = load_charters(pg_cur)
    route_counts = existing_route_counts(pg_cur)

    to_insert: List[Tuple] = []
    charter_updates: List[Tuple] = []

    stats = {
        "matched": 0,
        "missing_charter": 0,
        "skipped_existing_routes": 0,
        "insert_candidates": 0,
        "update_candidates": 0,
    }

    for row in reserve_rows:
        reserve_no = row["reserve_no"]
        charter = charters.get(reserve_no)
        if not charter:
            stats["missing_charter"] += 1
            continue

        charter_id = charter["charter_id"]
        stats["matched"] += 1

        if route_counts.get(charter_id, 0) > 0:
            stats["skipped_existing_routes"] += 1
            continue

        pickup_location_parts = [p for p in [row["line_1"], row["line_2"]] if p]
        pickup_location = "\n".join(pickup_location_parts) if pickup_location_parts else None
        dropoff_location = row["from_to"]
        pickup_time = row["pu_time"]
        dropoff_time = row["do_time"] or row["drop_off_time"]
        route_notes = row["trip_notes"]

        if not any([pickup_location, dropoff_location, pickup_time, dropoff_time, route_notes]):
            continue  # nothing to insert

        to_insert.append(
            (
                charter_id,
                1,  # route_sequence
                pickup_location,
                pickup_time,
                dropoff_location,
                dropoff_time,
                None,  # estimated_duration_minutes
                None,  # actual_duration_minutes
                None,  # estimated_distance_km
                None,  # actual_distance_km
                None,  # route_price
                route_notes,
                "pending",
            )
        )
        stats["insert_candidates"] += 1

        if args.update_charters:
            updates: Dict[str, Any] = {}
            if pickup_location and (args.force_overwrite or charter.get("pickup_address") is None):
                updates["pickup_address"] = pickup_location
            if dropoff_location and (args.force_overwrite or charter.get("dropoff_address") is None):
                updates["dropoff_address"] = dropoff_location
            if pickup_time and (args.force_overwrite or charter.get("pickup_time") is None):
                updates["pickup_time"] = pickup_time
            if updates:
                charter_updates.append((updates, charter_id))
                stats["update_candidates"] += 1

    print("\nSummary:")
    for k, v in stats.items():
        print(f"  {k.replace('_', ' ').title()}: {v}")
    print(f"  Insert rows prepared: {len(to_insert)}")
    print(f"  Charter updates prepared: {len(charter_updates)}")

    if not args.apply:
        print("Dry-run complete. Re-run with --apply to write changes.")
        pg_conn.close()
        lms_conn.close()
        return 0

    # Apply inserts
    insert_sql = """
        INSERT INTO charter_routes (
            charter_id, route_sequence, pickup_location, pickup_time,
            dropoff_location, dropoff_time, estimated_duration_minutes,
            actual_duration_minutes, estimated_distance_km, actual_distance_km,
            route_price, route_notes, route_status
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """
    for params in to_insert:
        pg_cur.execute(insert_sql, params)

    if args.update_charters and charter_updates:
        for updates, charter_id in charter_updates:
            sets = []
            values = []
            for col, val in updates.items():
                sets.append(f"{col} = %s")
                values.append(val)
            values.append(charter_id)
            sql = f"UPDATE charters SET {', '.join(sets)} WHERE charter_id = %s"
            pg_cur.execute(sql, values)

    pg_conn.commit()
    print(f"Applied {len(to_insert)} inserts and {len(charter_updates)} charter updates.")

    pg_conn.close()
    lms_conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
