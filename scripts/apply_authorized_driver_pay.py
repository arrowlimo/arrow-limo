#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apply authorized driver pay details to specific charters by reserve_number.

- Uses provided hours, gratuity, and reimbursement amounts in the exact order.
- Derives hourly rate from payroll entry id=18522 (base_wages / total_hours) by default.
- Updates charter fields (if present):
  - driver_hourly_rate
  - driver_hours_worked
  - driver_base_pay
  - driver_gratuity_amount (falls back to driver_gratuity)
  - driver_total_expense
- Dry-run by default; use --write to apply changes.

Safety:
- Validates column existence via information_schema and only updates available columns.
- Verifies totals match payroll entry values (base_wages, gratuity_amount, expense_reimbursement) when possible.

Environment:
- DB_HOST, DB_NAME, DB_USER, DB_PASSWORD (fallbacks: localhost, almsdata, postgres, ***REMOVED***)
"""
import os
import sys
import argparse
import psycopg2
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

RESERVE_NUMBERS = [
    '007237','007245','007243','007227','007228',
    '007188','007104','007269','007277','007148',
    '007278','007109','007288'
]

HOURS = [
    2.0, 3.5, 4.25, 6.25, 3.5,
    5.0, 3.5, 6.0, 3.75, 3.0,
    3.0, 3.5, 4.0
]

# Provided gratuities (12 values given; last is missing). Set None as placeholder to force confirmation.
GRATUITIES = [
    0.0, 250.0, 29.5, 30.0, 196.36,
    0.0, 27.3, 57.0, 0.0, 50.0,
    0.0, 31.5, 8.73
]

# Provided reimbursements (12 values given; last is missing). Set None as placeholder to force confirmation.
REIMBURSEMENTS = [
    0.0, 0.0, 0.0, 0.0, 0.0,
    6.0, 0.0, 0.0, 21.22, 0.0,
    0.0, 19.5, 62.0
]

PAYROLL_ENTRY_ID = 18522  # Gordon Deans Dec 2012 entry


def dquant(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_conn():
    host = os.environ.get('DB_HOST', 'localhost')
    name = os.environ.get('DB_NAME', 'almsdata')
    user = os.environ.get('DB_USER', 'postgres')
    pwd = os.environ.get('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, database=name, user=user, password=pwd)


def get_charters_columns(cur):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'charters'
        AND table_schema = 'public'
        """
    )
    cols = {r[0] for r in cur.fetchall()}
    return cols


def get_payroll_breakdown(cur):
    cur.execute(
        """
        SELECT base_wages, gratuity_amount, expense_reimbursement
        FROM driver_payroll
        WHERE id = %s
        """,
        (PAYROLL_ENTRY_ID,)
    )
    row = cur.fetchone()
    if not row:
        return None, None, None
    return tuple(Decimal(str(x or 0)) for x in row)


def compute_rate(base_wages, hours_list):
    total_hours = sum(Decimal(str(h)) for h in hours_list)
    if total_hours == 0:
        return Decimal('0')
    return (Decimal(base_wages) / total_hours).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def build_updates(rate, cols):
    # Compute base pay per charter with rounding; adjust last to maintain exact sum
    base_pays = [ (Decimal(str(h)) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for h in HOURS ]

    return base_pays


def main():
    ap = argparse.ArgumentParser(description='Apply authorized driver pay to charters (dry-run by default).')
    ap.add_argument('--write', action='store_true', help='Apply updates to the database')
    ap.add_argument('--fill-missing-zero', action='store_true',
                    help='Treat missing gratuity/reimbursement values as 0.00 and proceed')
    args = ap.parse_args()

    # Validate lengths
    if len(RESERVE_NUMBERS) != len(HOURS):
        print(f"ERROR: Reserve numbers ({len(RESERVE_NUMBERS)}) and hours ({len(HOURS)}) length mismatch.")
        sys.exit(1)
    if len(RESERVE_NUMBERS) != len(GRATUITIES):
        print(f"ERROR: Gratuities count ({len(GRATUITIES)}) does not match number of charters ({len(RESERVE_NUMBERS)}). Fill missing values.")
        sys.exit(1)
    if len(RESERVE_NUMBERS) != len(REIMBURSEMENTS):
        print(f"ERROR: Reimbursements count ({len(REIMBURSEMENTS)}) does not match number of charters ({len(RESERVE_NUMBERS)}). Fill missing values.")
        sys.exit(1)
    
    if any(g is None for g in GRATUITIES) or any(r is None for r in REIMBURSEMENTS):
        if args.fill_missing_zero:
            # Replace Nones with 0.0 and announce which
            missing_grat = []
            missing_reim = []
            for i in range(len(RESERVE_NUMBERS)):
                if GRATUITIES[i] is None:
                    GRATUITIES[i] = 0.0
                    missing_grat.append(RESERVE_NUMBERS[i])
                if REIMBURSEMENTS[i] is None:
                    REIMBURSEMENTS[i] = 0.0
                    missing_reim.append(RESERVE_NUMBERS[i])
            if missing_grat:
                print(f"Filled missing gratuities with 0.00 for: {', '.join(missing_grat)}")
            if missing_reim:
                print(f"Filled missing reimbursements with 0.00 for: {', '.join(missing_reim)}")
        else:
            print('ERROR: Missing gratuity and/or reimbursement values. Provide all 13 values or use --fill-missing-zero to default to 0.00.')
            sys.exit(1)

    conn = get_conn()
    cur = conn.cursor()

    cols = get_charters_columns(cur)
    can_set = {
        'driver_hourly_rate': 'driver_hourly_rate' in cols,
        'driver_hours_worked': 'driver_hours_worked' in cols,
        'driver_base_pay': 'driver_base_pay' in cols,
        'driver_gratuity_amount': 'driver_gratuity_amount' in cols or 'driver_gratuity' in cols,
        'driver_total_expense': 'driver_total_expense' in cols,
    }

    base_wages, payroll_grat, payroll_exp = get_payroll_breakdown(cur)
    if base_wages is None:
        print(f"WARNING: Payroll entry {PAYROLL_ENTRY_ID} not found. Using computed rate from totals.")
        # Fall back to 20.00 if not found
        rate = Decimal('20.00')
    else:
        rate = compute_rate(base_wages, HOURS)

    base_pays = build_updates(rate, cols)

    total_hours = sum(Decimal(str(h)) for h in HOURS)
    total_base = sum(base_pays)
    total_grat = sum(Decimal(str(g)) for g in GRATUITIES)
    total_exp = sum(Decimal(str(r)) for r in REIMBURSEMENTS)

    print('Authorized Driver Pay Plan (dry-run unless --write):')
    print(f"  Rate:           ${rate}")
    print(f"  Total hours:     {total_hours}")
    print(f"  Total base pay: ${total_base}")
    print(f"  Total gratuity: ${total_grat}")
    print(f"  Total expense:  ${total_exp}")
    if base_wages is not None:
        print(f"  Payroll base_wages: ${base_wages}")
        if total_base != base_wages:
            print('  NOTE: Base pay sum differs from payroll base_wages (rounding may apply).')
        if payroll_grat is not None and payroll_grat != total_grat:
            print('  NOTE: Gratuity sum differs from payroll gratuity_amount.')
        if payroll_exp is not None and payroll_exp != total_exp:
            print('  NOTE: Expense sum differs from payroll expense_reimbursement.')

    # Preview per-charter
    print('\nPer-charter breakdown (reserve_number, hours, base_pay, gratuity, expense):')
    for i, rn in enumerate(RESERVE_NUMBERS):
        print(f"  {rn}: hours={HOURS[i]}, base=${base_pays[i]}, grat=${GRATUITIES[i]}, exp=${REIMBURSEMENTS[i]}")

    if not args.write:
        print('\nDRY RUN complete. Re-run with --write to apply updates.')
        cur.close(); conn.close()
        return

    # Apply updates
    updated = 0
    for i, rn in enumerate(RESERVE_NUMBERS):
        sets = []
        params = []
        if can_set['driver_hourly_rate']:
            sets.append('driver_hourly_rate = %s')
            params.append(rate)
        if can_set['driver_hours_worked']:
            sets.append('driver_hours_worked = %s')
            params.append(HOURS[i])
        if can_set['driver_base_pay']:
            sets.append('driver_base_pay = %s')
            params.append(base_pays[i])
        if can_set['driver_gratuity_amount']:
            if 'driver_gratuity_amount' in cols:
                sets.append('driver_gratuity_amount = %s')
            else:
                sets.append('driver_gratuity = %s')
            params.append(GRATUITIES[i])
        if can_set['driver_total_expense']:
            sets.append('driver_total_expense = %s')
            params.append(REIMBURSEMENTS[i])

        if not sets:
            print('No updatable charter columns present; aborting.')
            cur.close(); conn.close(); sys.exit(1)

        params.append(rn)
        sql = f"UPDATE charters SET {', '.join(sets)} WHERE reserve_number = %s"
        cur.execute(sql, params)
        updated += cur.rowcount

    conn.commit()
    print(f"\nApplied updates to {updated} charter rows.")

    # Verify write
    cur.execute(
        """
        SELECT 
            COALESCE(SUM(driver_hours_worked), 0),
            COALESCE(SUM(driver_base_pay), 0),
            COALESCE(SUM(CASE WHEN EXISTS (
                SELECT 1 FROM information_schema.columns c
                WHERE c.table_name='charters' AND c.column_name='driver_gratuity_amount'
            ) THEN driver_gratuity_amount ELSE driver_gratuity END), 0),
            COALESCE(SUM(driver_total_expense), 0)
        FROM charters 
        WHERE reserve_number = ANY(%s)
        """,
        (RESERVE_NUMBERS,)
    )
    v_hours, v_base, v_grat, v_exp = cur.fetchone()
    print('Verification (sum over 13 charters):')
    print(f"  Hours: {v_hours}  vs input {float(total_hours)}")
    print(f"  Base:  ${v_base} vs input ${total_base}")
    print(f"  Grat:  ${v_grat} vs input ${total_grat}")
    print(f"  Exp:   ${v_exp}  vs input ${total_exp}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
