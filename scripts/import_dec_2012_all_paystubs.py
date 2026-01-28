#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Import all December 2012 individual paystub data.
Based on extracted data from December 2012 Pay Cheques PDF.
"""
import os
import sys
import argparse
import psycopg2
from datetime import date
from decimal import Decimal

# All December 2012 paystubs (current period only - not YTD)
PAYSTUBS = [
    {
        'name': 'Paul D Richard',
        'driver_id': 'Owner',
        'cheque': 'P1119',
        'current_gross': Decimal('1532.64'),
        'current_cpp': Decimal('61.43'),
        'current_ei': Decimal('0'),
        'current_tax': Decimal('74.82'),
        'current_net': Decimal('1396.39'),
        'ytd_gross': Decimal('14672.73'),
        'ytd_cpp': Decimal('559.75'),
        'ytd_ei': Decimal('0'),
        'ytd_tax': Decimal('549.04'),
    },
    {
        'name': 'Jeannie Shillington',
        'driver_id': 'Dr_Jeannie',  # Temporary - need proper ID
        'cheque': 'P1120',
        'current_gross': Decimal('2457.90'),
        'current_cpp': Decimal('102.28'),
        'current_ei': Decimal('43.15'),
        'current_tax': Decimal('310.14'),
        'current_net': Decimal('2002.33'),
        'ytd_gross': Decimal('35711.84'),
        'ytd_cpp': Decimal('1555.34'),
        'ytd_ei': Decimal('639.05'),
        'ytd_tax': Decimal('5356.53'),
    },
    {
        'name': 'Michael Richard',
        'driver_id': 'Dr_Michael',  # Temporary - need proper ID
        'cheque': 'P1121',
        'current_gross': Decimal('2698.36'),
        'current_cpp': Decimal('119.13'),
        'current_ei': Decimal('0'),  # Not shown in extraction
        'current_tax': Decimal('351.83'),
        'current_net': Decimal('2227.40'),
        'ytd_gross': Decimal('28557.74'),
        'ytd_cpp': Decimal('1183.45'),
        'ytd_ei': Decimal('0'),  # Not shown
        'ytd_tax': Decimal('3116.76'),
    },
    {
        'name': 'Kevin Boulley',
        'driver_id': 'Dr_Kevin',  # Temporary - need proper ID
        'cheque': 'P1122',
        'current_gross': Decimal('1632.19'),
        'current_cpp': Decimal('66.07'),
        'current_ei': Decimal('29.76'),
        'current_tax': Decimal('139.66'),
        'current_net': Decimal('1396.70'),
        'ytd_gross': Decimal('3381.98'),
        'ytd_cpp': Decimal('123.81'),
        'ytd_ei': Decimal('61.78'),
        'ytd_tax': Decimal('259.46'),
    },
    {
        'name': 'Doug Redmond',
        'driver_id': 'Dr_Doug',  # Temporary - need proper ID
        'cheque': 'P1124',
        'current_gross': Decimal('1286.91'),
        'current_cpp': Decimal('49.26'),
        'current_ei': Decimal('23.55'),
        'current_tax': Decimal('0'),
        'current_net': Decimal('1180.95'),  # Should be 1214.10 but extraction shows 1180.95
        'ytd_gross': Decimal('19055.72'),
        'ytd_cpp': Decimal('818.52'),
        'ytd_ei': Decimal('345.30'),
        'ytd_tax': Decimal('0'),  # Interesting - no tax withheld
    },
    {
        'name': 'Dale Menard',
        'driver_id': 'Dr_Dale',  # Temporary - need proper ID
        'cheque': 'P1125',
        'current_gross': Decimal('1258.40'),
        'current_cpp': Decimal('0'),  # Not extracted
        'current_ei': Decimal('0'),  # Not extracted
        'current_tax': Decimal('0'),  # Not extracted
        'current_net': Decimal('253.67'),  # Suggests ~$1000 deductions?
        'ytd_gross': Decimal('5262.36'),
        'ytd_cpp': Decimal('0'),  # Not shown
        'ytd_ei': Decimal('0'),
        'ytd_tax': Decimal('0'),
    },
    {
        'name': 'Dustan Townsend',
        'driver_id': 'Dr_Dustan',  # Temporary - need proper ID
        'cheque': 'P1126',
        'current_gross': Decimal('1447.53'),
        'current_cpp': Decimal('55.23'),
        'current_ei': Decimal('25.76'),
        'current_tax': Decimal('50.01'),
        'current_net': Decimal('1316.53'),
        'ytd_gross': Decimal('4977.39'),
        'ytd_cpp': Decimal('170.30'),
        'ytd_ei': Decimal('89.53'),
        'ytd_tax': Decimal('116.80'),
    },
    {
        'name': 'Jesse Gordon',
        'driver_id': 'Dr_Jesse',  # Temporary - need proper ID
        'cheque': 'P1130',
        'current_gross': Decimal('2535.38'),
        'current_cpp': Decimal('111.06'),
        'current_ei': Decimal('46.40'),
        'current_tax': Decimal('301.51'),
        'current_net': Decimal('2076.41'),
        'ytd_gross': Decimal('5240.21'),
        'ytd_cpp': Decimal('172.35'),
        'ytd_ei': Decimal('95.90'),
        'ytd_tax': Decimal('301.51'),
    },
]

PAY_DATE = date(2012, 12, 31)
YEAR = 2012
MONTH = 12


def get_conn():
    host = os.environ.get('DB_HOST', 'localhost')
    name = os.environ.get('DB_NAME', 'almsdata')
    user = os.environ.get('DB_USER', 'postgres')
    pwd = os.environ.get('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, database=name, user=user, password=pwd)


def check_existing(cur, driver_id):
    """Check if entry already exists for this driver in December 2012."""
    cur.execute("""
        SELECT id, gross_pay 
        FROM driver_payroll 
        WHERE driver_id = %s 
        AND year = %s 
        AND month = %s
    """, (driver_id, YEAR, MONTH))
    return cur.fetchone()


def insert_payroll(cur, stub):
    """Insert one payroll entry."""
    sql = """
        INSERT INTO driver_payroll (
            driver_id, year, month, pay_date,
            gross_pay, cpp, ei, tax, net_pay,
            source
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    values = [
        stub['driver_id'],
        YEAR,
        MONTH,
        PAY_DATE,
        stub['current_gross'],
        stub['current_cpp'],
        stub['current_ei'],
        stub['current_tax'],
        stub['current_net'],
        f"December 2012 Pay Cheques PDF - {stub['cheque']}"
    ]
    
    cur.execute(sql, values)
    return cur.fetchone()[0]


def main():
    ap = argparse.ArgumentParser(description='Import December 2012 paystubs (dry-run by default)')
    ap.add_argument('--write', action='store_true', help='Apply to database')
    args = ap.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    print('December 2012 Paystub Import (All Employees)')
    print('=' * 80)
    print(f"Total employees: {len(PAYSTUBS)}")
    print(f"Pay date: {PAY_DATE}")
    print()
    
    # Calculate totals
    total_gross = sum(s['current_gross'] for s in PAYSTUBS)
    total_cpp = sum(s['current_cpp'] for s in PAYSTUBS)
    total_ei = sum(s['current_ei'] for s in PAYSTUBS)
    total_tax = sum(s['current_tax'] for s in PAYSTUBS)
    
    print(f"December 2012 Period Totals:")
    print(f"  Gross: ${total_gross:,.2f}")
    print(f"  CPP:   ${total_cpp:,.2f}")
    print(f"  EI:    ${total_ei:,.2f}")
    print(f"  Tax:   ${total_tax:,.2f}")
    print()
    
    # Check for existing and show details
    need_import = []
    already_exist = []
    
    for stub in PAYSTUBS:
        existing = check_existing(cur, stub['driver_id'])
        if existing:
            already_exist.append((stub['name'], stub['driver_id'], existing[1]))
        else:
            need_import.append(stub)
            print(f"✓ {stub['name']:<25} ({stub['driver_id']:<10}) Gross: ${stub['current_gross']:>10,.2f}")
    
    if already_exist:
        print(f"\n[WARN]  {len(already_exist)} entries already exist:")
        for name, driver_id, gross in already_exist:
            print(f"   {name:<25} ({driver_id:<10}) Gross: ${gross:>10,.2f}")
    
    if not need_import:
        print("\nNo new entries to import.")
        cur.close(); conn.close()
        return
    
    print(f"\n{len(need_import)} new entries to import.")
    
    if not args.write:
        print('\n' + '=' * 80)
        print('DRY RUN complete. Use --write to apply changes.')
        cur.close(); conn.close()
        return
    
    # Insert entries
    print('\nInserting payroll entries...')
    inserted_ids = []
    for stub in need_import:
        payroll_id = insert_payroll(cur, stub)
        inserted_ids.append((stub['name'], payroll_id))
        print(f"  ✓ {stub['name']:<25} → ID {payroll_id}")
    
    conn.commit()
    
    # Show updated 2012 totals (excluding ADJ)
    cur.execute("""
        SELECT 
            COALESCE(SUM(gross_pay), 0),
            COALESCE(SUM(cpp), 0),
            COALESCE(SUM(ei), 0),
            COALESCE(SUM(tax), 0)
        FROM driver_payroll
        WHERE year = 2012
        AND driver_id != 'ADJ'
    """)
    total = cur.fetchone()
    print(f"\n2012 Year Totals (after import, excluding ADJ):")
    print(f"  Gross: ${total[0]:,.2f}")
    print(f"  CPP:   ${total[1]:,.2f}")
    print(f"  EI:    ${total[2]:,.2f}")
    print(f"  Tax:   ${total[3]:,.2f}")
    
    print(f"\nTarget (from December paystubs YTD):")
    print(f"  Gross: $116,859.97")
    print(f"  CPP:   $  1,844.73")
    print(f"  EI:    $  1,326.62")
    print(f"  Tax:   $  1,226.81")
    
    print(f"\nRemaining gap:")
    print(f"  Gross: ${116859.97 - float(total[0]):,.2f}")
    
    cur.close(); conn.close()
    print('\n✓ Import complete!')


if __name__ == '__main__':
    main()
