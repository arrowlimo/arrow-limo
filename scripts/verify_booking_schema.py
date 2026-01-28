import sys
import os

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from modern_backend.app.db import get_connection

CHECKS = []

def add_check(name, ok, details=""):
    CHECKS.append({"name": name, "ok": bool(ok), "details": details})


def main():
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1) Sequence exists
        cur.execute(
            """
            SELECT sequence_name FROM information_schema.sequences
            WHERE sequence_name = 'reserve_number_seq'
            """
        )
        seq = cur.fetchone()
        add_check("reserve_number_seq exists", bool(seq), f"found={seq[0] if seq else None}")

        # 2) charter_routes columns
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'charter_routes'
            ORDER BY ordinal_position
            """
        )
        route_cols = [r[0] for r in cur.fetchall()]
        add_check("charter_routes columns retrieved", bool(route_cols), 
                  f"columns={','.join(route_cols)}")
        add_check("charter_routes has address or directions",
                  any(c in route_cols for c in ("address", "directions", "pickup_location", "dropoff_location")),
                  f"columns={','.join(route_cols)}")

        # 3) charters columns
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'charters'
            ORDER BY ordinal_position
            """
        )
        charter_cols = [r[0] for r in cur.fetchall()]
        add_check("charters columns retrieved", bool(charter_cols), f"columns={','.join(charter_cols)}")
        # Ensure required fields exist
        required = [
            "charter_id", "client_id", "reserve_number", "charter_date", "passenger_load",
            "vehicle_booked_id", "vehicle_type_requested", "driver_name", "pickup_address", "dropoff_address", "status"
        ]
        missing = [c for c in required if c not in charter_cols]
        add_check("charters required fields present", len(missing) == 0, f"missing={','.join(missing)}")

        # 4) charges table
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'charges'
            ORDER BY ordinal_position
            """
        )
        charges_cols = [r[0] for r in cur.fetchall()]
        add_check("charges table present", bool(charges_cols), f"columns={','.join(charges_cols)}")
        # Expect reserve_number, charge_type, amount
        expected_charges = ["charge_id", "reserve_number", "charge_type", "amount"]
        missing_charges = [c for c in expected_charges if c not in charges_cols]
        add_check("charges required fields present", len(missing_charges) == 0, f"missing={','.join(missing_charges)}")

        # 5) payments table and reserve_number presence
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'payments'
            ORDER BY ordinal_position
            """
        )
        payments_cols = [r[0] for r in cur.fetchall()]
        add_check("payments table present", bool(payments_cols), f"columns={','.join(payments_cols)}")
        add_check("payments has reserve_number", "reserve_number" in payments_cols, f"columns={','.join(payments_cols)}")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    # Print summary
    ok = True
    for c in CHECKS:
        status = "OK" if c["ok"] else "FAIL"
        print(f"[ {status} ] {c['name']} :: {c['details']}")
        ok = ok and c["ok"]
    sys.exit(0 if ok else 2)

if __name__ == "__main__":
    main()
