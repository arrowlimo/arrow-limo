"""
Charter Sheet API Router - LMS-style detailed charter printout

Endpoint: GET /charter-sheet/{reserve_number}
Returns complete charter sheet with:
- Reservation details
- Customer/billing info
- Charge breakdown (line items)
- Payment breakdown (with labels: NRD, Deposit, E-Transfer, etc.)
- Driver trip log
- Balance calculation
"""
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from ..db import get_connection

router = APIRouter(prefix="/api", tags=["charter-sheet"])


@router.get("/charter-sheet/{reserve_number}")
def get_charter_sheet(reserve_number: str):
    """
    Get complete charter sheet for driver/customer printout.
    Matches LMS reservation sheet format.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Get charter details
        cur.execute(
            """
            SELECT
                c.charter_id, c.reserve_number, c.charter_date, c.pickup_time,
                c.pickup_address, c.dropoff_address, c.passenger_load,
                c.vehicle_type_requested, c.vehicle_booked_id, c.driver_name,
                c.total_amount_due, c.status, c.charter_type, c.quoted_hours,
                c.separate_customer_printout,
                c.actual_pickup_time, c.actual_dropoff_time, c.actual_hours,
                c.odometer_start, c.odometer_end, c.total_miles,
                c.fuel_gallons, c.fuel_price_per_gallon, c.fuel_total_cost,
                cl.client_name, cl.phone, cl.email, cl.address_line1,
                cl.city, cl.province, cl.zip_code, cl.gst_exempt,
                cl.account_number
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE c.reserve_number = %s
        """,
            (reserve_number,),
        )

        charter_row = cur.fetchone()
        if not charter_row:
            raise HTTPException(
                status_code=404, detail=f"Charter {reserve_number} not found"
            )

        charter_data = {
            "charter_id": charter_row[0],
            "reserve_number": charter_row[1],
            "charter_date": charter_row[2].isoformat() if charter_row[2] else None,
            "pickup_time": charter_row[3].isoformat() if charter_row[3] else None,
            "pickup_address": charter_row[4],
            "dropoff_address": charter_row[5],
            "passenger_load": charter_row[6],
            "vehicle_type": charter_row[7],
            "vehicle_id": charter_row[8],
            "driver_name": charter_row[9],
            "total_amount_due": float(charter_row[10]) if charter_row[10] else 0.0,
            "status": charter_row[11],
            "charter_type": charter_row[12],
            "quoted_hours": float(charter_row[13]) if charter_row[13] else 0.0,
            "separate_customer_printout": charter_row[14],
            "driver_trip_log": {
                "actual_pickup_time": charter_row[15].isoformat()
                if charter_row[15]
                else None,
                "actual_dropoff_time": charter_row[16].isoformat()
                if charter_row[16]
                else None,
                "actual_hours": float(charter_row[17]) if charter_row[17] else 0.0,
                "odometer_start": charter_row[18],
                "odometer_end": charter_row[19],
                "total_miles": charter_row[20],
                "fuel_gallons": float(charter_row[21]) if charter_row[21] else 0.0,
                "fuel_price_per_gallon": float(charter_row[22])
                if charter_row[22]
                else 0.0,
                "fuel_total_cost": float(charter_row[23]) if charter_row[23] else 0.0,
            },
            "customer": {
                "client_name": charter_row[24],
                "phone": charter_row[25],
                "email": charter_row[26],
                "street_address": charter_row[27],
                "city": charter_row[28],
                "province": charter_row[29],
                "postal_code": charter_row[30],
                "gst_exempt": charter_row[31],
                "account_number": charter_row[32],
            },
        }

        # Get charge breakdown (line items)
        cur.execute(
            """
            SELECT charge_id, charge_type, amount, description, created_at
            FROM charges
            WHERE reserve_number = %s
            ORDER BY
                CASE charge_type
                    WHEN 'base_rate' THEN 1
                    WHEN 'airport_fee' THEN 2
                    WHEN 'additional' THEN 3
                    WHEN 'gst' THEN 4
                    ELSE 5
                END,
                charge_id
        """,
            (reserve_number,),
        )

        charges = []
        total_charges = 0.0
        for row in cur.fetchall():
            amt = float(row[2]) if row[2] else 0.0
            charges.append(
                {
                    "charge_id": row[0],
                    "charge_type": row[1],
                    "amount": amt,
                    "description": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                }
            )
            if row[1] != "gst":  # Don't double-count GST in subtotal
                total_charges += amt

        # Get payment breakdown (with labels: NRD, Deposit, E-Transfer, etc.)
        cur.execute(
            """
            SELECT
                payment_id, payment_label, payment_method, amount,
                payment_date, status, notes, reference_number
            FROM payments
            WHERE reserve_number = %s
            ORDER BY payment_date, payment_id
        """,
            (reserve_number,),
        )

        payments = []
        total_paid = 0.0
        for row in cur.fetchall():
            amt = float(row[3]) if row[3] else 0.0
            payments.append(
                {
                    "payment_id": row[0],
                    "payment_label": row[1] or "Payment",
                    "payment_method": row[2],
                    "amount": amt,
                    "payment_date": row[4].isoformat() if row[4] else None,
                    "status": row[5],
                    "notes": row[6],
                    "reference_number": row[7],
                }
            )
            total_paid += amt

        # Calculate balance
        total_due = charter_data["total_amount_due"]
        balance = round(total_due - total_paid, 2)

        # Get trip notes (beverage orders, etc.)
        trip_notes = []

        return {
            "charter": charter_data,
            "charges": charges,
            "charge_summary": {
                "subtotal": round(total_charges, 2),
                "total_with_gst": round(total_due, 2),
            },
            "payments": payments,
            "payment_summary": {
                "total_paid": round(total_paid, 2),
                "balance_due": balance,
                "is_paid_in_full": balance <= 0.01,
                "has_overpayment": balance < -0.01,
            },
            "trip_notes": trip_notes,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load charter sheet: {e}"
        )
    finally:
        cur.close()
        conn.close()
