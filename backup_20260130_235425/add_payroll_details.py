#!/usr/bin/env python3
"""Add gratuity/hours columns to driver_payroll and link to charters."""
import os, psycopg2, argparse

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

def add_columns_if_needed(cur, conn, dry_run=True):
    """Add columns for wages, gratuities, hours, expenses if they don't exist"""
    
    columns_to_add = [
        ('base_wages', 'DECIMAL(12,2)', 'Base wages/hourly pay'),
        ('gratuity_amount', 'DECIMAL(12,2)', 'Gratuities/tips (taxable)'),
        ('expense_reimbursement', 'DECIMAL(12,2)', 'Expense reimbursements'),
        ('hours_worked', 'DECIMAL(8,2)', 'Total hours worked'),
    ]
    
    print(f"\n{'='*100}")
    print(f"ADD PAYROLL DETAIL COLUMNS {'(DRY RUN)' if dry_run else '(APPLYING)'}")
    print(f"{'='*100}\n")
    
    existing = []
    to_add = []
    
    for col_name, col_type, description in columns_to_add:
        if table_has_column(cur, 'driver_payroll', col_name):
            existing.append(col_name)
            print(f"✓ Column '{col_name}' already exists")
        else:
            to_add.append((col_name, col_type, description))
            print(f"  Column '{col_name}' needs to be added - {description}")
    
    if not to_add:
        print(f"\n✓ All required columns already exist")
        return True
    
    if dry_run:
        print(f"\n[WARN]  DRY RUN - Would add {len(to_add)} columns")
        print(f"Use --apply to add these columns")
        return False
    
    print(f"\nAdding {len(to_add)} columns...")
    for col_name, col_type, description in to_add:
        query = f"ALTER TABLE driver_payroll ADD COLUMN {col_name} {col_type}"
        print(f"  Adding {col_name}...")
        cur.execute(query)
    
    conn.commit()
    print(f"✓ Columns added successfully")
    return True

def update_gordon_deans_entry(cur, conn, dry_run=True):
    """Update Gordon Deans entry with breakdown and link to charters"""
    
    # Check columns exist
    required = ['base_wages', 'gratuity_amount', 'expense_reimbursement', 'hours_worked']
    missing = [col for col in required if not table_has_column(cur, 'driver_payroll', col)]
    
    if missing:
        print(f"\n[FAIL] Missing columns: {', '.join(missing)}")
        print(f"Run with --apply first to add columns")
        return
    
    # Gordon Deans data
    entry_id = 18522
    breakdown = {
        'base_wages': 1025.00,
        'gratuity_amount': 680.39,
        'expense_reimbursement': 108.72,
        'hours_worked': None  # Not provided in pay stub
    }
    
    reservations = ['007237', '007245', '007243', '007227', '007228', '007188',
                    '007104', '007269', '007277', '007148', '007278', '007109', '007288']
    
    print(f"\n{'='*100}")
    print(f"UPDATE GORDON DEANS ENTRY {'(DRY RUN)' if dry_run else '(APPLYING)'}")
    print(f"{'='*100}\n")
    
    print(f"Entry ID: {entry_id}")
    print(f"\nPay Breakdown:")
    print(f"  Base Wages:           ${breakdown['base_wages']:>10,.2f}")
    print(f"  Gratuity (taxable):   ${breakdown['gratuity_amount']:>10,.2f}")
    print(f"  Expense Reimbursed:   ${breakdown['expense_reimbursement']:>10,.2f}")
    print(f"  {'─'*40}")
    print(f"  Total (should be):    ${sum(v for v in breakdown.values() if v):>10,.2f}")
    
    print(f"\nReservations to link: {len(reservations)}")
    
    # Check which charters exist
    reserve_list = ', '.join(f"'{r}'" for r in reservations)
    cur.execute(f"""
        SELECT reserve_number, charter_id, assigned_driver_id
        FROM charters 
        WHERE reserve_number IN ({reserve_list})
        ORDER BY reserve_number
    """)
    
    charters = cur.fetchall()
    print(f"  Found {len(charters)}/{len(reservations)} charters in database")
    
    if len(charters) < len(reservations):
        missing = set(reservations) - set([c[0] for c in charters])
        print(f"  [WARN]  Missing: {', '.join(sorted(missing))}")
    
    if dry_run:
        print(f"\n[WARN]  DRY RUN - No changes made")
        print(f"Use --apply to update payroll entry and link charters")
        return
    
    # Update payroll entry with breakdown
    update_query = """
        UPDATE driver_payroll 
        SET base_wages = %s,
            gratuity_amount = %s,
            expense_reimbursement = %s
        WHERE id = %s
    """
    
    cur.execute(update_query, (
        breakdown['base_wages'],
        breakdown['gratuity_amount'],
        breakdown['expense_reimbursement'],
        entry_id
    ))
    
    print(f"\n✓ Updated payroll entry {entry_id} with pay breakdown")
    
    # Link charters to this payroll entry
    # Just update driver_name field (assigned_driver_id is integer, keep existing value)
    
    # Update charters driver_name to match
    for charter in charters:
        reserve_num, charter_id, current_driver = charter
        cur.execute("""
            UPDATE charters 
            SET driver_name = %s
            WHERE charter_id = %s
        """, ('Gordon Deans (Dr46)', charter_id))
        print(f"  Updated charter {reserve_num} driver name")
    
    conn.commit()
    
    print(f"\n✓ All charters linked to driver Dr46")
    
    # Verify
    cur.execute("""
        SELECT base_wages, gratuity_amount, expense_reimbursement, gross_pay
        FROM driver_payroll 
        WHERE id = %s
    """, (entry_id,))
    
    row = cur.fetchone()
    calculated_gross = sum(float(v) for v in row[:3] if v)
    
    print(f"\n{'='*100}")
    print(f"VERIFICATION")
    print(f"{'='*100}")
    print(f"Base Wages:           ${float(row[0] or 0):>10,.2f}")
    print(f"Gratuity:             ${float(row[1] or 0):>10,.2f}")
    print(f"Expense Reimburse:    ${float(row[2] or 0):>10,.2f}")
    print(f"{'─'*40}")
    print(f"Calculated Gross:     ${calculated_gross:>10,.2f}")
    print(f"Stored Gross:         ${float(row[3]):>10,.2f}")
    
    if abs(calculated_gross - float(row[3])) < 0.01:
        print(f"✓ Breakdown matches gross pay")
    else:
        print(f"[WARN]  Mismatch: ${abs(calculated_gross - float(row[3])):.2f} difference")

def main():
    parser = argparse.ArgumentParser(description='Add payroll detail columns and update Gordon Deans entry')
    parser.add_argument('--apply', action='store_true', help='Apply changes')
    args = parser.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Step 1: Add columns
    columns_ready = add_columns_if_needed(cur, conn, dry_run=not args.apply)
    
    if columns_ready or args.apply:
        # Step 2: Update entry
        update_gordon_deans_entry(cur, conn, dry_run=not args.apply)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
