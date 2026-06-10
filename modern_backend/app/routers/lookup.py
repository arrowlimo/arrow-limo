"""
Lookup / Reference Data API Router
====================================
Serves read-only reference tables so the frontend never hard-codes dropdown
options.  All endpoints require an authenticated session but no elevated role.

Endpoints
---------
GET /api/lookup/vehicle-types   – active vehicle types + pricing (vehicle_pricing_defaults)
GET /api/lookup/run-types       – active run types ordered by display_order (charter_run_types)
GET /api/lookup/gst-rate        – current AB GST rate (gst_rates_lookup)
GET /api/lookup/airport-fees    – airport pickup fees per vehicle type
GET /api/lookup/system-config   – public key/value config rows (system_config)
"""

from fastapi import APIRouter

from ..db import get_connection, return_connection

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


# ---------------------------------------------------------------------------
# Vehicle Types
# ---------------------------------------------------------------------------
@router.get("/vehicle-types")
def get_vehicle_types():
    """Return active vehicle types ordered for display.

    Each entry includes the pricing fields needed for quote calculations so
    the frontend doesn't have to make a second request.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT ON (vehicle_type)
                vehicle_type,
                hourly_rate,
                daily_rate,
                hourly_package,
                standby_rate,
                airport_pickup_calgary,
                airport_pickup_edmonton,
                vehicle_type_display_order
            FROM vehicle_pricing_defaults
            WHERE is_active = true
            ORDER BY vehicle_type, vehicle_type_display_order NULLS LAST
        """)
        rows = cur.fetchall()
        results = []
        for row in rows:
            results.append({
                "vehicle_type": row[0],
                "hourly_rate": float(row[1]) if row[1] is not None else None,
                "daily_rate": float(row[2]) if row[2] is not None else None,
                "hourly_package": float(row[3]) if row[3] is not None else None,
                "standby_rate": float(row[4]) if row[4] is not None else None,
                "airport_pickup_calgary": float(row[5]) if row[5] is not None else None,
                "airport_pickup_edmonton": float(row[6]) if row[6] is not None else None,
            })
        # Sort by display_order, keeping unique vehicle_type names
        return sorted(results, key=lambda x: (
            rows[[r[0] for r in rows].index(x["vehicle_type"])][7] or 999
        ))
    finally:
        cur.close()
        return_connection(conn)


# ---------------------------------------------------------------------------
# Run Types
# ---------------------------------------------------------------------------
@router.get("/run-types")
def get_run_types():
    """Return active run types ordered for display from charter_run_types."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT run_type_id, run_type_name, description, display_order
            FROM charter_run_types
            WHERE is_active = true
            ORDER BY display_order, run_type_name
        """)
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "display_order": row[3],
            }
            for row in cur.fetchall()
        ]
    finally:
        cur.close()
        return_connection(conn)


# ---------------------------------------------------------------------------
# GST Rate
# ---------------------------------------------------------------------------
@router.get("/gst-rate")
def get_gst_rate(province: str = "AB"):
    """Return GST/tax rates for the given province (default Alberta)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT province_code, province_name, gst_rate, pst_rate, hst_rate,
                   total_rate, notes
            FROM gst_rates_lookup
            WHERE province_code = %s
            LIMIT 1
        """, (province.upper(),))
        row = cur.fetchone()
        if not row:
            return {"province_code": "AB", "gst_rate": 0.05, "total_rate": 0.05}
        return {
            "province_code": row[0],
            "province_name": row[1],
            "gst_rate": float(row[2]),
            "pst_rate": float(row[3]),
            "hst_rate": float(row[4]),
            "total_rate": float(row[5]),
            "notes": row[6],
        }
    finally:
        cur.close()
        return_connection(conn)


# ---------------------------------------------------------------------------
# Airport Fees
# ---------------------------------------------------------------------------
@router.get("/airport-fees")
def get_airport_fees():
    """Return airport pickup fees sourced from vehicle_pricing_defaults.

    Also returns the static airport list so the frontend dropdown never
    hard-codes airport names or fees.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Get fees by vehicle type
        cur.execute("""
            SELECT DISTINCT ON (vehicle_type)
                vehicle_type,
                airport_pickup_calgary,
                airport_pickup_edmonton
            FROM vehicle_pricing_defaults
            WHERE is_active = true
              AND (airport_pickup_calgary IS NOT NULL
                   OR airport_pickup_edmonton IS NOT NULL)
            ORDER BY vehicle_type, vehicle_type_display_order NULLS LAST
        """)
        by_vehicle = {
            row[0]: {
                "calgary": float(row[1]) if row[1] else 0.0,
                "edmonton": float(row[2]) if row[2] else 0.0,
            }
            for row in cur.fetchall()
        }

        # Aggregate default fees across all vehicle types (simple average of
        # non-zero values, or fallback to the stored system_config values)
        cur.execute("""
            SELECT
                AVG(NULLIF(airport_pickup_calgary, 0)),
                AVG(NULLIF(airport_pickup_edmonton, 0))
            FROM vehicle_pricing_defaults
            WHERE is_active = true
        """)
        avg = cur.fetchone()
        default_calgary = round(float(avg[0]), 2) if avg[0] else 65.0
        default_edmonton = round(float(avg[1]), 2) if avg[1] else 45.0

        return {
            "airports": [
                {
                    "value": "edmonton",
                    "label": f"Edmonton International (${default_edmonton:.0f} pickup fee)",
                    "fee": default_edmonton,
                },
                {
                    "value": "calgary",
                    "label": f"Calgary International (${default_calgary:.0f} pickup fee)",
                    "fee": default_calgary,
                },
                {
                    "value": "red_deer",
                    "label": "Red Deer Regional (no pickup fee)",
                    "fee": 0.0,
                },
            ],
            "by_vehicle_type": by_vehicle,
            "default_calgary_fee": default_calgary,
            "default_edmonton_fee": default_edmonton,
        }
    finally:
        cur.close()
        return_connection(conn)


# ---------------------------------------------------------------------------
# System Config (public keys only – no secrets)
# ---------------------------------------------------------------------------
_PUBLIC_CONFIG_KEYS = {
    "company_name", "default_currency", "timezone",
    "gst_rate", "advance_booking_days", "minimum_booking_notice",
    "payment_terms_days",
}


@router.get("/system-config")
def get_system_config():
    """Return public system config key/value pairs."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT config_key, config_value FROM system_config"
        )
        return {
            row[0]: row[1]
            for row in cur.fetchall()
            if row[0] in _PUBLIC_CONFIG_KEYS
        }
    finally:
        cur.close()
        return_connection(conn)
