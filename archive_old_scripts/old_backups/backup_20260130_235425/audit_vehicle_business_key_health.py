import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_conn():
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_NAME = os.environ.get("DB_NAME", "almsdata")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

if __name__ == "__main__":
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            print("# Vehicle business key health audit (vehicle_number)\n")

            # Vehicles: empties / nulls
            cur.execute("""
                SELECT COUNT(*) AS cnt_empty
                FROM vehicles
                WHERE vehicle_number IS NULL OR TRIM(vehicle_number) = ''
            """)
            cnt_empty = cur.fetchone()["cnt_empty"]
            print(f"vehicles with empty vehicle_number: {cnt_empty}")

            # Vehicles: duplicates
            cur.execute("""
                SELECT vehicle_number, COUNT(*) AS dup_count
                FROM vehicles
                WHERE vehicle_number IS NOT NULL AND TRIM(vehicle_number) <> ''
                GROUP BY vehicle_number
                HAVING COUNT(*) > 1
                ORDER BY dup_count DESC, vehicle_number
            """)
            dups = cur.fetchall()
            print(f"duplicate vehicle_number values in vehicles: {len(dups)}")
            for d in dups[:25]:
                print(f"- {d['vehicle_number']}: {d['dup_count']} entries")
            if len(dups) > 25:
                print(f"... and {len(dups) - 25} more")

            # Receipts referencing vehicle_number not present in vehicles
            cur.execute("""
                SELECT COUNT(*) AS cnt_receipts_with_vehicle_number
                FROM receipts
                WHERE vehicle_number IS NOT NULL AND TRIM(vehicle_number) <> ''
            """)
            cnt_receipts_nonempty = cur.fetchone()["cnt_receipts_with_vehicle_number"]
            print(f"receipts with non-empty vehicle_number: {cnt_receipts_nonempty}")

            cur.execute("""
                SELECT COUNT(*) AS cnt_missing
                FROM receipts r
                WHERE r.vehicle_number IS NOT NULL AND TRIM(r.vehicle_number) <> ''
                  AND NOT EXISTS (
                    SELECT 1 FROM vehicles v
                    WHERE v.vehicle_number = r.vehicle_number
                  )
            """)
            cnt_missing_map = cur.fetchone()["cnt_missing"]
            print(f"receipts.vehicle_number not matching any vehicles.vehicle_number: {cnt_missing_map}")

            # Receipts where vehicle_id is set but vehicle_number mismatches the linked vehicle
            try:
                cur.execute("""
                    SELECT COUNT(*) AS cnt_mismatch
                    FROM receipts r
                    JOIN vehicles v ON r.vehicle_id = v.vehicle_id
                    WHERE r.vehicle_number IS NOT NULL AND TRIM(r.vehicle_number) <> ''
                      AND r.vehicle_number <> v.vehicle_number
                """)
                cnt_mismatch = cur.fetchone()["cnt_mismatch"]
                print(f"receipts linked by vehicle_id where vehicle_number mismatches: {cnt_mismatch}")
            except Exception as e:
                print(f"receipts vehicle_id mismatch check skipped: {e}")

            # Summary recommendation
            print("\nRecommendation:")
            if cnt_empty == 0 and len(dups) == 0:
                print("- Safe to enforce UNIQUE NOT NULL on vehicles.vehicle_number (business key).")
            else:
                print("- Clean up empties/duplicates before enforcing UNIQUE NOT NULL on vehicles.vehicle_number.")
            print("- Continue using vehicle_id for foreign keys, and vehicle_number for business logic and UI.")
