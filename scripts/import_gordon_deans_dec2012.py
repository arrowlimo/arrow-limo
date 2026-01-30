#!/usr/bin/env python3
"""Import Gordon Deans payroll entry for December 2012."""
import os, psycopg2, argparse
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def table_has_column(cur, table, column):
    cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (table, column))
    return cur.fetchone() is not None

# Gordon Deans December 2012 payroll
PAYROLL_DATA = {
    'driver_id': '69',  # From charter assignments
    'pay_period_start': '2012-12-01',
    'pay_period_end': '2012-12-31',
    'pay_date': '2012-12-31',  # End of pay period
    'wages': 1025.00,
    'gratuities_taxable': 680.39,
    'expense_reimbursed': 108.72,
    'gross_pay': 1814.11,
    'cpp': 69.98,
    'ei': 31.21,
    'tax': 108.07,
    'total_deductions': 209.26,
    'net_pay': 1604.85,
    'vacation_available': 41.00,
    'reservations': ['007237', '007245', '007243', '007227', '007228', '007188',
                     '007104', '007269', '007277', '007148', '007278', '007109', '007288'],
    'source': 'Manual_PayStub_Import_Dec2012'
}

def insert_payroll(cur, conn, dry_run=True):
    """Insert the payroll entry"""
    
    # Check if entry already exists
    cur.execute("""
        SELECT id FROM driver_payroll 
        WHERE driver_id = %s 
          AND pay_date = %s 
          AND ABS(gross_pay - %s) < 0.01
    """, (PAYROLL_DATA['driver_id'], PAYROLL_DATA['pay_date'], PAYROLL_DATA['gross_pay']))
    
    existing = cur.fetchone()
    if existing:
        print(f"\n[WARN]  Entry already exists with ID {existing[0]}")
        return None
    
    # Build insert statement
    has_net_pay = table_has_column(cur, 'driver_payroll', 'net_pay')
    has_source = table_has_column(cur, 'driver_payroll', 'source')
    has_year = table_has_column(cur, 'driver_payroll', 'year')
    has_month = table_has_column(cur, 'driver_payroll', 'month')
    
    columns = ['driver_id', 'pay_date', 'gross_pay', 'cpp', 'ei', 'tax']
    values = [
        PAYROLL_DATA['driver_id'],
        PAYROLL_DATA['pay_date'],
        PAYROLL_DATA['gross_pay'],
        PAYROLL_DATA['cpp'],
        PAYROLL_DATA['ei'],
        PAYROLL_DATA['tax']
    ]
    
    if has_net_pay:
        columns.append('net_pay')
        values.append(PAYROLL_DATA['net_pay'])
    
    if has_source:
        columns.append('source')
        values.append(PAYROLL_DATA['source'])
    
    if has_year:
        columns.append('year')
        values.append(2012)
    
    if has_month:
        columns.append('month')
        values.append(12)
    
    # Only add created_at if column exists
    if table_has_column(cur, 'driver_payroll', 'created_at'):
        columns.append('created_at')
        values.append(datetime.now())
    
    print(f"\n{'='*100}")
    print(f"GORDON DEANS PAYROLL IMPORT {'(DRY RUN)' if dry_run else '(APPLYING)'}")
    print(f"{'='*100}\n")
    
    print(f"Driver ID: {PAYROLL_DATA['driver_id']}")
    print(f"Pay Period: {PAYROLL_DATA['pay_period_start']} to {PAYROLL_DATA['pay_period_end']}")
    print(f"Pay Date: {PAYROLL_DATA['pay_date']}")
    print(f"\nCompensation:")
    print(f"  Wages:                ${PAYROLL_DATA['wages']:>10,.2f}")
    print(f"  Gratuities (taxable): ${PAYROLL_DATA['gratuities_taxable']:>10,.2f}")
    print(f"  Expense Reimbursed:   ${PAYROLL_DATA['expense_reimbursed']:>10,.2f}")
    print(f"  {'─'*35}")
    print(f"  Gross Pay:            ${PAYROLL_DATA['gross_pay']:>10,.2f}")
    print(f"\nDeductions:")
    print(f"  CPP:                  ${PAYROLL_DATA['cpp']:>10,.2f}")
    print(f"  EI:                   ${PAYROLL_DATA['ei']:>10,.2f}")
    print(f"  Federal Income Tax:   ${PAYROLL_DATA['tax']:>10,.2f}")
    print(f"  {'─'*35}")
    print(f"  Total Deductions:     ${PAYROLL_DATA['total_deductions']:>10,.2f}")
    print(f"\nNet Pay:                ${PAYROLL_DATA['net_pay']:>10,.2f}")
    print(f"Vacation Available:     ${PAYROLL_DATA['vacation_available']:>10,.2f}")
    
    print(f"\nReservations ({len(PAYROLL_DATA['reservations'])}):")
    print(f"  {', '.join(PAYROLL_DATA['reservations'])}")
    
    if dry_run:
        print(f"\n[WARN]  DRY RUN - No changes made")
        print(f"Use --apply to insert this payroll entry")
        return None
    
    # Insert
    placeholders = ', '.join(['%s'] * len(values))
    col_names = ', '.join(columns)
    
    query = f"INSERT INTO driver_payroll ({col_names}) VALUES ({placeholders}) RETURNING id"
    cur.execute(query, values)
    new_id = cur.fetchone()[0]
    conn.commit()
    
    print(f"\n✓ Inserted payroll entry with ID: {new_id}")
    
    return new_id

def main():
    parser = argparse.ArgumentParser(description='Import Gordon Deans December 2012 payroll')
    parser.add_argument('--apply', action='store_true', help='Apply the import')
    args = parser.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    new_id = insert_payroll(cur, conn, dry_run=not args.apply)
    
    if args.apply and new_id:
        # Verify
        cur.execute("""
            SELECT driver_id, pay_date, gross_pay, cpp, ei, tax, net_pay
            FROM driver_payroll
            WHERE id = %s
        """, (new_id,))
        
        row = cur.fetchone()
        print(f"\n{'='*100}")
        print(f"VERIFICATION")
        print(f"{'='*100}")
        print(f"Retrieved entry ID {new_id}:")
        print(f"  Driver: {row[0]}, Date: {row[1]}")
        print(f"  Gross: ${row[2]:.2f}, CPP: ${row[3]:.2f}, EI: ${row[4]:.2f}, Tax: ${row[5]:.2f}")
        net_val = float(row[6]) if row[6] else 0.0
        print(f"  Net: ${net_val:.2f}")
        
        # Check 2012 totals
        cur.execute("""
            SELECT 
                COUNT(*) as entries,
                ROUND(SUM(gross_pay)::numeric, 2) as total_gross,
                ROUND(SUM(cpp)::numeric, 2) as total_cpp,
                ROUND(SUM(ei)::numeric, 2) as total_ei,
                ROUND(SUM(tax)::numeric, 2) as total_tax
            FROM driver_payroll
            WHERE pay_date >= '2012-01-01' AND pay_date < '2013-01-01'
              AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)
        """) if table_has_column(cur, 'driver_payroll', 'payroll_class') else cur.execute("""
            SELECT 
                COUNT(*) as entries,
                ROUND(SUM(gross_pay)::numeric, 2) as total_gross,
                ROUND(SUM(cpp)::numeric, 2) as total_cpp,
                ROUND(SUM(ei)::numeric, 2) as total_ei,
                ROUND(SUM(tax)::numeric, 2) as total_tax
            FROM driver_payroll
            WHERE pay_date >= '2012-01-01' AND pay_date < '2013-01-01'
        """)
        
        row = cur.fetchone()
        print(f"\n2012 Totals (after import):")
        print(f"  Entries:  {row[0]:>8,}")
        print(f"  Gross:    ${float(row[1]):>14,.2f}")
        print(f"  CPP:      ${float(row[2]):>14,.2f}")
        print(f"  EI:       ${float(row[3]):>14,.2f}")
        print(f"  Tax:      ${float(row[4]):>14,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
