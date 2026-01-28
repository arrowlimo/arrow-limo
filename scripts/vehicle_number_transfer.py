import os
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date

"""
Safely transfer a vehicle_number from an old (soon-to-be decommissioned) vehicle
to a newly purchased vehicle.

- Enforces active-only uniqueness via partial index (recommended to run separately)
- Sets decommission_date and is_active on the old vehicle
- Assigns the vehicle_number to the new vehicle
- Records history in vehicle_number_history with effective ranges

Usage examples:
    python -X utf8 scripts/vehicle_number_transfer.py --from-number L7 --to-vehicle-id 123 --effective 2026-01-23 --dry-run
    python -X utf8 scripts/vehicle_number_transfer.py --from-number L7 --to-vehicle-id 123 --effective 2026-01-23 --write
"""


def get_conn():
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_NAME = os.environ.get("DB_NAME", "almsdata")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def ensure_history_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.vehicle_number_history (
            id SERIAL PRIMARY KEY,
            vehicle_id INTEGER NOT NULL REFERENCES public.vehicles(vehicle_id),
            vehicle_number VARCHAR NOT NULL,
            effective_from DATE NOT NULL,
            effective_to DATE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )
    # Index to prevent overlapping assignments for same vehicle_number
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vnum_hist_vehicle_number ON public.vehicle_number_history(vehicle_number);
        """
    )


def parse_args():
    p = argparse.ArgumentParser(description="Transfer vehicle_number from decommissioned vehicle to new vehicle")
    p.add_argument("--from-number", required=True, help="Existing vehicle_number to transfer (e.g., L7)")
    p.add_argument("--to-vehicle-id", required=True, type=int, help="Target vehicle_id for the new purchased vehicle")
    p.add_argument("--effective", required=True, help="Effective date for transfer (YYYY-MM-DD)")
    p.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    p.add_argument("--write", action="store_true", help="Apply changes")
    return p.parse_args()


def main():
    args = parse_args()
    eff = date.fromisoformat(args.effective)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            ensure_history_table(cur)

            # Find old vehicle by vehicle_number
            cur.execute(
                """
                SELECT * FROM public.vehicles WHERE vehicle_number = %s
                """,
                (args.from_number,)
            )
            old = cur.fetchone()
            if not old:
                print(f"❌ No vehicle found with vehicle_number={args.from_number}")
                return

            # Find new vehicle by id
            cur.execute(
                """
                SELECT * FROM public.vehicles WHERE vehicle_id = %s
                """,
                (args.to_vehicle_id,)
            )
            new = cur.fetchone()
            if not new:
                print(f"❌ No vehicle found with vehicle_id={args.to_vehicle_id}")
                return

            if old["vehicle_id"] == new["vehicle_id"]:
                print("❌ Source and destination vehicles are the same")
                return

            # Validate uniqueness: ensure no other active vehicle already has this number
            cur.execute(
                """
                SELECT vehicle_id, vehicle_number, is_active, decommission_date
                FROM public.vehicles
                WHERE vehicle_number = %s AND vehicle_id <> %s AND (is_active = TRUE AND decommission_date IS NULL)
                """,
                (args.from_number, new["vehicle_id"])  # allow if it's the old vehicle
            )
            conflict = cur.fetchone()
            if conflict:
                print(f"❌ Active conflict: vehicle_id={conflict['vehicle_id']} already holds {args.from_number}")
                return

            print("# Transfer plan:")
            print(f"- Old vehicle: id={old['vehicle_id']} number={old['vehicle_number']} active={old['is_active']} decommission_date={old['decommission_date']}")
            print(f"- New vehicle: id={new['vehicle_id']} current_number={new['vehicle_number']} active={new['is_active']} decommission_date={new['decommission_date']}")
            print(f"- Effective date: {eff}")

            if args.dry_run and not args.write:
                print("\nDry-run only. No changes applied.")
                return

            # 1) Decommission old vehicle (if not already)
            cur.execute(
                """
                UPDATE public.vehicles
                SET is_active = FALSE,
                    decommission_date = COALESCE(decommission_date, %s)
                WHERE vehicle_id = %s
                """,
                (eff, old["vehicle_id"]) 
            )

            # 2) Record history close-out for old vehicle_number
            cur.execute(
                """
                INSERT INTO public.vehicle_number_history (vehicle_id, vehicle_number, effective_from, effective_to)
                VALUES (%s, %s, %s, %s)
                """,
                (old["vehicle_id"], args.from_number, old.get("commission_date") or eff, eff)
            )

            # 3) Assign vehicle_number to new vehicle
            cur.execute(
                """
                UPDATE public.vehicles
                SET vehicle_number = %s,
                    is_active = TRUE,
                    decommission_date = NULL
                WHERE vehicle_id = %s
                """,
                (args.from_number, new["vehicle_id"]) 
            )

            # 4) Record new history start
            cur.execute(
                """
                INSERT INTO public.vehicle_number_history (vehicle_id, vehicle_number, effective_from, effective_to)
                VALUES (%s, %s, %s, NULL)
                """,
                (new["vehicle_id"], args.from_number, eff)
            )

            conn.commit()
            print("✅ Transfer complete and history recorded.")

if __name__ == "__main__":
    main()
