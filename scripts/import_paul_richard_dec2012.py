#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Import Paul Richard (owner) December 2012 payroll entry and link to charters.

Pay Stub Breakdown:
- Salary: $3,990.07
- Gratuity: $442.92
- Vacation Pay Paid: $159.61
- Wages: $1,265.00
- Vacation Pay Accrued Paid Out: $50.60
- Total Gross: $5,908.20
- CPP: $226.96
- Federal Tax: $306.32
- Net Pay: $5,374.92

Charters: 006179, 006196, 006197, 006199, 005934, 006232
Hours: 7, 3, 5, 2, 12, 7 (total 36 hours)
Gratuities: 0, 0, 0, 17.5, 90, 0 (total $107.50)

Note: Pay stub shows $442.92 total gratuity but charter breakdown only accounts for $107.50.
Remaining $335.42 may be from other sources or additional charters not listed.
"""
import os
import sys
import argparse
import psycopg2
from datetime import date
from decimal import Decimal

# Pay stub values
SALARY = Decimal('3990.07')
GRATUITY_TOTAL = Decimal('442.92')
VAC_PAY_PAID = Decimal('159.61')
WAGES = Decimal('1265.00')
VAC_ACCRUED_PAID = Decimal('50.60')
GROSS_PAY = SALARY + GRATUITY_TOTAL + VAC_PAY_PAID + WAGES + VAC_ACCRUED_PAID  # 5908.20
CPP = Decimal('226.96')
FED_TAX = Decimal('306.32')
NET_PAY = GROSS_PAY - CPP - FED_TAX  # 5374.92

# Charter details
RESERVE_NUMBERS = ['006179', '006196', '006197', '006199', '005934', '006232']
HOURS = [7, 3, 5, 2, 12, 7]  # Total 36 hours
CHARTER_GRATUITIES = [0.0, 0.0, 0.0, 17.5, 90.0, 0.0]  # Total $107.50

# Payroll entry details
DRIVER_NAME = 'Paul Richard'
DRIVER_ID = 'Owner'  # Or appropriate driver code
PAY_DATE = date(2012, 12, 31)
YEAR = 2012
MONTH = 12


def get_conn():
    host = os.environ.get('DB_HOST', 'localhost')
    name = os.environ.get('DB_NAME', 'almsdata')
    user = os.environ.get('DB_USER', 'postgres')
    pwd = os.environ.get('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, database=name, user=user, password=pwd)


def check_existing(cur):
    """Check if entry already exists."""
    cur.execute("""
        SELECT id, gross_pay, net_pay 
        FROM driver_payroll 
        WHERE driver_id = %s 
        AND year = %s 
        AND month = %s
        AND pay_date = %s
    """, (DRIVER_ID, YEAR, MONTH, PAY_DATE))
    return cur.fetchone()


def verify_charters(cur):
    """Verify all charters exist."""
    cur.execute("""
        SELECT reserve_number, charter_date, driver_name
        FROM charters 
        WHERE reserve_number = ANY(%s)
        ORDER BY charter_date
    """, (RESERVE_NUMBERS,))
    rows = cur.fetchall()
    print(f"\nFound {len(rows)} of {len(RESERVE_NUMBERS)} charters:")
    for rn, dt, driver in rows:
        print(f"  {rn}: {dt}, driver: {driver or '(none)'}")
    return len(rows) == len(RESERVE_NUMBERS)


def insert_payroll(cur):
    """Insert payroll entry with detailed breakdown."""
    # Check if columns exist
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'driver_payroll' 
        AND column_name IN ('base_wages', 'gratuity_amount', 'expense_reimbursement', 
                            'hours_worked', 'vacation_pay')
    """)
    available_cols = {r[0] for r in cur.fetchall()}
    
    # Base insert (note: driver_payroll has driver_id only, not driver_name)
    sql = """
        INSERT INTO driver_payroll (
            driver_id, year, month, pay_date,
            gross_pay, cpp, ei, tax, net_pay
    """
    values = [DRIVER_ID, YEAR, MONTH, PAY_DATE,
              GROSS_PAY, CPP, 0, FED_TAX, NET_PAY]
    
    # Add optional columns if they exist
    if 'base_wages' in available_cols:
        sql += ", base_wages"
        values.append(SALARY + WAGES)  # Combined salary + wages = $5,255.07
    if 'gratuity_amount' in available_cols:
        sql += ", gratuity_amount"
        values.append(GRATUITY_TOTAL)
    if 'vacation_pay' in available_cols:
        sql += ", vacation_pay"
        values.append(VAC_PAY_PAID + VAC_ACCRUED_PAID)  # Combined vacation = $210.21
    if 'hours_worked' in available_cols:
        sql += ", hours_worked"
        values.append(sum(HOURS))  # 36 hours
    
    sql += ") VALUES (" + ", ".join(["%s"] * len(values)) + ") RETURNING id"
    
    cur.execute(sql, values)
    payroll_id = cur.fetchone()[0]
    return payroll_id


def update_charters(cur):
    """Update charters with driver details."""
    # Calculate hourly rate from wages portion: $1,265 / 36 hours = $35.14/hr
    hourly_rate = (WAGES / Decimal(str(sum(HOURS)))).quantize(Decimal('0.01'))
    
    for i, rn in enumerate(RESERVE_NUMBERS):
        hours = HOURS[i]
        base_pay = (hourly_rate * Decimal(str(hours))).quantize(Decimal('0.01'))
        gratuity = Decimal(str(CHARTER_GRATUITIES[i]))
        
        # Update charter with available columns
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'charters' 
            AND column_name IN ('driver_hourly_rate', 'driver_hours_worked', 
                                'driver_base_pay', 'driver_gratuity_amount', 'driver_gratuity')
        """)
        cols = {r[0] for r in cur.fetchall()}
        
        sets = ["driver_name = %s"]
        params = [f"{DRIVER_NAME} ({DRIVER_ID})"]
        
        if 'driver_hourly_rate' in cols:
            sets.append("driver_hourly_rate = %s")
            params.append(hourly_rate)
        if 'driver_hours_worked' in cols:
            sets.append("driver_hours_worked = %s")
            params.append(hours)
        if 'driver_base_pay' in cols:
            sets.append("driver_base_pay = %s")
            params.append(base_pay)
        if 'driver_gratuity_amount' in cols:
            sets.append("driver_gratuity_amount = %s")
            params.append(gratuity)
        elif 'driver_gratuity' in cols:
            sets.append("driver_gratuity = %s")
            params.append(gratuity)
        
        params.append(rn)
        sql = f"UPDATE charters SET {', '.join(sets)} WHERE reserve_number = %s"
        cur.execute(sql, params)


def main():
    ap = argparse.ArgumentParser(description='Import Paul Richard Dec 2012 payroll (dry-run by default)')
    ap.add_argument('--write', action='store_true', help='Apply to database')
    args = ap.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    print('Paul Richard December 2012 Payroll Import')
    print('=' * 60)
    print(f"Salary:                    ${SALARY}")
    print(f"Gratuity (total):          ${GRATUITY_TOTAL}")
    print(f"Vacation Pay Paid:         ${VAC_PAY_PAID}")
    print(f"Wages:                     ${WAGES}")
    print(f"Vac Pay Accrued Paid Out:  ${VAC_ACCRUED_PAID}")
    print(f"{'─' * 60}")
    print(f"Gross Pay:                 ${GROSS_PAY}")
    print(f"CPP:                       ${CPP}")
    print(f"Federal Tax:               ${FED_TAX}")
    print(f"{'─' * 60}")
    print(f"Net Pay:                   ${NET_PAY}")
    print()
    
    # Check existing
    existing = check_existing(cur)
    if existing:
        print(f"[WARN]  Entry already exists: ID {existing[0]}, Gross ${existing[1]}, Net ${existing[2]}")
        print("No action taken.")
        cur.close(); conn.close()
        return
    
    # Verify charters
    if not verify_charters(cur):
        print("\n[WARN]  Not all charters found. Aborting.")
        cur.close(); conn.close()
        sys.exit(1)
    
    # Show charter breakdown
    print(f"\nCharter breakdown (6 charters, {sum(HOURS)} total hours):")
    for i, rn in enumerate(RESERVE_NUMBERS):
        print(f"  {rn}: hours={HOURS[i]}, gratuity=${CHARTER_GRATUITIES[i]}")
    
    charter_grat_sum = sum(Decimal(str(g)) for g in CHARTER_GRATUITIES)
    print(f"\nNote: Charter gratuities sum to ${charter_grat_sum}, but pay stub shows ${GRATUITY_TOTAL}")
    print(f"      Difference of ${GRATUITY_TOTAL - charter_grat_sum} may be from other sources.")
    
    if not args.write:
        print('\n' + '=' * 60)
        print('DRY RUN complete. Use --write to apply changes.')
        cur.close(); conn.close()
        return
    
    # Insert payroll
    print('\nInserting payroll entry...')
    payroll_id = insert_payroll(cur)
    print(f"✓ Created payroll entry ID: {payroll_id}")
    
    # Update charters
    print('Updating charters...')
    update_charters(cur)
    print(f"✓ Updated {len(RESERVE_NUMBERS)} charters")
    
    conn.commit()
    
    # Verify
    cur.execute("SELECT gross_pay, cpp, tax, net_pay FROM driver_payroll WHERE id = %s", (payroll_id,))
    row = cur.fetchone()
    print(f"\nVerification:")
    print(f"  Entry {payroll_id}: Gross ${row[0]}, CPP ${row[1]}, Tax ${row[2]}, Net ${row[3]}")
    
    # Show updated 2012 totals
    cur.execute("""
        SELECT 
            COALESCE(SUM(gross_pay), 0),
            COALESCE(SUM(cpp), 0),
            COALESCE(SUM(ei), 0),
            COALESCE(SUM(tax), 0)
        FROM driver_payroll
        WHERE year = 2012
    """)
    total = cur.fetchone()
    print(f"\n2012 Year Totals (after this entry):")
    print(f"  Gross: ${total[0]}")
    print(f"  CPP:   ${total[1]}")
    print(f"  EI:    ${total[2]}")
    print(f"  Tax:   ${total[3]}")
    
    cur.close(); conn.close()
    print('\n✓ Import complete!')


if __name__ == '__main__':
    main()
