#!/usr/bin/env python3
"""
Use email_financial_events to upsert vehicle_loans and vehicle_loan_payments.
Attempts to map VIN to vehicles.vehicle_id and create loans per lender.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Fetch events likely related to vehicle loans
    # Join to vehicles on full VIN OR last-8 VIN match (case-insensitive), tolerating nulls
    cur.execute(
        """
        SELECT e.*, v.vehicle_id, v.make as v_make, v.model as v_model, v.license_plate as v_plate
          FROM email_financial_events e
          LEFT JOIN vehicles v
                 ON (
                       e.vin IS NOT NULL
                   AND (
                         UPPER(v.vin_number) = UPPER(e.vin)
                      OR RIGHT(UPPER(v.vin_number), 8) = RIGHT(UPPER(e.vin), 8)
                   )
                 )
         WHERE e.entity IN ('Heffner','CMB Insurance')
        """
    )
    events = cur.fetchall()

    # Ensure basic vehicle_loans structure exists
    # vehicle_loans(id, vehicle_id, vehicle_name, lender, paid_by, opening_balance, closing_balance,
    #               total_paid,total_interest,total_fees,total_penalties,total_sold_for,loan_start_date,loan_end_date,notes)

    inserted_loans = 0
    inserted_payments = 0
    skipped_no_vehicle = 0

    for ev in events:
        # Determine lender/loan key
        lender = (ev.get('lender_name') or ev.get('entity') or 'Unknown').strip()
        vehicle_id = ev['vehicle_id']
        # Prefer event-provided name; otherwise derive from vehicles table info if available
        vehicle_name = (
            (ev.get('vehicle_name') or '').strip()
            or (
                f"{(ev.get('v_make') or '').strip()} {(ev.get('v_model') or '').strip()}".strip()
                + (f" ({ev.get('v_plate')})" if ev.get('v_plate') else "")
                if ev.get('v_make') or ev.get('v_model') or ev.get('v_plate') else None
            )
        )

        # If we couldn't map to a vehicle, skip (schema requires vehicle_id)
        if not vehicle_id:
            skipped_no_vehicle += 1
            continue

        # Upsert loan row per vehicle+lender
        loan_id = None
        cur.execute(
            """
            SELECT id FROM vehicle_loans
             WHERE COALESCE(vehicle_id, -1) = COALESCE(%s, -1)
               AND lender = %s
             LIMIT 1
            """,
            (vehicle_id, lender)
        )
        r = cur.fetchone()
        if r:
            loan_id = r['id']
        else:
            cur.execute(
                """
                INSERT INTO vehicle_loans(vehicle_id, vehicle_name, lender, paid_by, notes)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (vehicle_id, vehicle_name, lender, 'Arrow Limousine', 'Created from email_financial_events')
            )
            loan_id = cur.fetchone()['id']
            inserted_loans += 1

        # If event is a payment-like, insert into vehicle_loan_payments
        if ev['event_type'] in ('loan_payment','nsf_fee','extra_payment') and ev['amount']:
            interest = None
            fee = ev['amount'] if ev['event_type'] == 'nsf_fee' else None
            penalty = None
            # Idempotent insert: avoid duplicates by (loan_id, date, amount)
            cur.execute(
                """
                INSERT INTO vehicle_loan_payments(loan_id, payment_date, payment_amount, interest_amount, fee_amount, penalty_amount, paid_by, notes)
                SELECT %s, %s, %s, %s, %s, %s, %s, %s
                 WHERE NOT EXISTS (
                    SELECT 1 FROM vehicle_loan_payments
                     WHERE loan_id = %s AND payment_date = %s AND payment_amount = %s
                 )
                """,
                (loan_id, ev['email_date'], ev['amount'], interest, fee, penalty, 'bank', ev['subject'],
                 loan_id, ev['email_date'], ev['amount'])
            )
            inserted_payments += (cur.rowcount or 0)

    conn.commit()
    cur.close(); conn.close()
    print(f"Inserted {inserted_loans} vehicle_loans, {inserted_payments} vehicle_loan_payments; skipped {skipped_no_vehicle} events without a mapped vehicle")


if __name__ == '__main__':
    main()
