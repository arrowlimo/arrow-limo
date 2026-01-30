"""
Import Jan-Mar 2012 hourly payroll data from Excel workbooks.

These are gratuity/expense payments to drivers (not full payroll with taxes).
Based on extracted data from MASTER COPY 2012 YTD Hourly Payroll Workbook.xls
"""

import psycopg2
import os
import sys
from decimal import Decimal
from datetime import date
import argparse

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

# Extracted payroll data for Jan-Mar 2012
# This data comes from extract_2012_excel_payroll.py output
# Note: First two workbooks are identical, so taking unique entries
PAYROLL_DATA = [
    # January 2012
    {'month': 1, 'year': 2012, 'emp_num': '100', 'name': 'Paul Richard', 'grat_tax': 156.37, 'grat_misc': 0, 'expense': 0},
    {'month': 1, 'year': 2012, 'emp_num': '03', 'name': 'Jeannie Shillington', 'grat_tax': 53.00, 'grat_misc': 0, 'expense': 60.63},
    {'month': 1, 'year': 2012, 'emp_num': '03', 'name': 'Office-Jeannie Shillington', 'grat_tax': 0, 'grat_misc': 0, 'expense': 0},  # Office entry
    {'month': 1, 'year': 2012, 'emp_num': '09', 'name': 'Michael Richard', 'grat_tax': 271.25, 'grat_misc': 0, 'expense': 266.43},
    {'month': 1, 'year': 2012, 'emp_num': '09', 'name': 'Office-Michael Richard', 'grat_tax': 0, 'grat_misc': 0, 'expense': 0},  # Office entry
    {'month': 1, 'year': 2012, 'emp_num': '22', 'name': 'Mark Linton', 'grat_tax': 54.37, 'grat_misc': 0, 'expense': 64.88},
    {'month': 1, 'year': 2012, 'emp_num': '26', 'name': 'Paul Mansell', 'grat_tax': 40.00, 'grat_misc': 0, 'expense': 0},
    {'month': 1, 'year': 2012, 'emp_num': '27', 'name': 'Carla Metivier', 'grat_tax': 2.50, 'grat_misc': 0, 'expense': 0},
    
    # February 2012
    {'month': 2, 'year': 2012, 'emp_num': '100', 'name': 'Paul Richard', 'grat_tax': 30.00, 'grat_misc': 0, 'expense': 0},
    {'month': 2, 'year': 2012, 'emp_num': '01', 'name': 'Erik J Richard', 'grat_tax': 193.50, 'grat_misc': 0, 'expense': 0},
    {'month': 2, 'year': 2012, 'emp_num': '03', 'name': 'Jeannie Shillington', 'grat_tax': 170.00, 'grat_misc': 0, 'expense': 88.55},
    {'month': 2, 'year': 2012, 'emp_num': '09', 'name': 'Michael Richard', 'grat_tax': 195.50, 'grat_misc': 0, 'expense': 30.89},
    {'month': 2, 'year': 2012, 'emp_num': '22', 'name': 'Mark Linton', 'grat_tax': 40.00, 'grat_misc': 0, 'expense': 0},
    {'month': 2, 'year': 2012, 'emp_num': '26', 'name': 'Paul Mansell', 'grat_tax': 205.00, 'grat_misc': 0, 'expense': 160.50},
    {'month': 2, 'year': 2012, 'emp_num': '32', 'name': 'Michael Blades', 'grat_tax': 0, 'grat_misc': 0, 'expense': 0},
    {'month': 2, 'year': 2012, 'emp_num': '33', 'name': 'Andrew Lafont', 'grat_tax': 0, 'grat_misc': 0, 'expense': 0},
    {'month': 2, 'year': 2012, 'emp_num': '35', 'name': 'Barney Forsberg', 'grat_tax': 0, 'grat_misc': 0, 'expense': 0},
    
    # March 2012
    {'month': 3, 'year': 2012, 'emp_num': '100', 'name': 'Paul Richard', 'grat_tax': 54.00, 'grat_misc': 0, 'expense': 0},
    {'month': 3, 'year': 2012, 'emp_num': '01', 'name': 'Erik J Richard', 'grat_tax': 180.00, 'grat_misc': 0, 'expense': 0},
    {'month': 3, 'year': 2012, 'emp_num': '03', 'name': 'Jeannie Shillington', 'grat_tax': 38.50, 'grat_misc': 0, 'expense': 89.31},
    {'month': 3, 'year': 2012, 'emp_num': '09', 'name': 'Michael Richard', 'grat_tax': 167.75, 'grat_misc': 0, 'expense': 78.80},
    {'month': 3, 'year': 2012, 'emp_num': '20', 'name': 'Flinn Winston', 'grat_tax': 58.50, 'grat_misc': 0, 'expense': 0},
    {'month': 3, 'year': 2012, 'emp_num': '26', 'name': 'Paul Mansell', 'grat_tax': 0, 'grat_misc': 0, 'expense': 0},  # Two entries; this is first
    {'month': 3, 'year': 2012, 'emp_num': '26', 'name': 'Paul Mansell', 'grat_tax': 30.00, 'grat_misc': 0, 'expense': 0},  # Second entry
    {'month': 3, 'year': 2012, 'emp_num': '38', 'name': 'Angel Escobar', 'grat_tax': 0, 'grat_misc': 0, 'expense': 163.82},
]

def main():
    parser = argparse.ArgumentParser(description='Import Jan-Mar 2012 Excel payroll data')
    parser.add_argument('--write', action='store_true', help='Actually write to database (default is dry-run)')
    args = parser.parse_args()
    
    if not args.write:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("    Run with --write to actually import data\n")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check for existing entries in these months
        print("Checking for existing Jan-Mar 2012 payroll entries...")
        cur.execute("""
            SELECT COUNT(*), SUM(gross_pay)
            FROM driver_payroll
            WHERE year = 2012 AND month IN (1, 2, 3)
        """)
        existing_count, existing_gross = cur.fetchone()
        print(f"  Existing entries: {existing_count}, Gross: ${existing_gross or 0:.2f}\n")
        
        # Calculate totals
        total_grat_tax = sum(Decimal(str(e['grat_tax'])) for e in PAYROLL_DATA)
        total_grat_misc = sum(Decimal(str(e['grat_misc'])) for e in PAYROLL_DATA)
        total_expense = sum(Decimal(str(e['expense'])) for e in PAYROLL_DATA)
        total_gross = total_grat_tax + total_grat_misc + total_expense
        
        print(f"Jan-Mar 2012 Excel Data to Import:")
        print(f"  Entries: {len(PAYROLL_DATA)}")
        print(f"  Gratuities (taxable): ${total_grat_tax:.2f}")
        print(f"  Gratuities (misc): ${total_grat_misc:.2f}")
        print(f"  Expenses: ${total_expense:.2f}")
        print(f"  Total: ${total_gross:.2f}\n")
        
        if not args.write:
            print("Sample entries to import:")
            for i, entry in enumerate(PAYROLL_DATA[:5]):
                print(f"  {entry['year']}-{entry['month']:02d} {entry['emp_num']:>5} {entry['name']:<30} "
                      f"Grat: ${entry['grat_tax']:>8.2f}  Exp: ${entry['expense']:>8.2f}")
            if len(PAYROLL_DATA) > 5:
                print(f"  ... and {len(PAYROLL_DATA) - 5} more entries")
            print("\n[OK] Dry run complete. Run with --write to import.")
            return
        
        # Import entries
        print("Importing entries...")
        imported_count = 0
        
        for entry in PAYROLL_DATA:
            # Map emp_num to driver_id format
            emp_num = entry['emp_num']
            if emp_num == '100':
                driver_id = 'Owner'
            elif emp_num.startswith('Of'):
                # Office entries - use base emp_num
                driver_id = f"Dr{emp_num.replace('Of', '')}"
            else:
                driver_id = f"Dr{emp_num.zfill(2)}"
            
            # Calculate gross pay
            gross_pay = Decimal(str(entry['grat_tax'])) + Decimal(str(entry['grat_misc'])) + Decimal(str(entry['expense']))
            
            # Skip zero entries
            if gross_pay == 0:
                continue
            
            # Last day of month
            if entry['month'] == 2:
                pay_date = date(entry['year'], 2, 29 if entry['year'] % 4 == 0 else 28)
            elif entry['month'] in [4, 6, 9, 11]:
                pay_date = date(entry['year'], entry['month'], 30)
            else:
                pay_date = date(entry['year'], entry['month'], 31)
            
            cur.execute("""
                INSERT INTO driver_payroll (
                    driver_id, year, month, pay_date,
                    gross_pay, gratuity_amount, expense_reimbursement,
                    net_pay,
                    cpp, ei, tax, total_deductions,
                    source, imported_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    0, 0, 0, 0,
                    'Excel Jan-Mar 2012 Hourly Payroll', CURRENT_TIMESTAMP
                )
                RETURNING id
            """, (
                driver_id, entry['year'], entry['month'], pay_date,
                gross_pay, entry['grat_tax'], entry['expense'],
                gross_pay  # No taxes on these gratuity/expense payments
            ))
            
            new_id = cur.fetchone()[0]
            print(f"  ✓ {entry['name']:30} → ID {new_id}  "
                  f"(${gross_pay:.2f})")
            imported_count += 1
        
        if args.write:
            conn.commit()
            print(f"\n[OK] Imported {imported_count} entries")
            
            # Show updated totals
            cur.execute("""
                SELECT COUNT(*), SUM(gross_pay)
                FROM driver_payroll
                WHERE year = 2012 AND month IN (1, 2, 3)
            """)
            new_count, new_gross = cur.fetchone()
            print(f"\nJan-Mar 2012 totals after import:")
            print(f"  Entries: {new_count}")
            print(f"  Gross: ${new_gross:.2f}")
            
            # Show full year 2012 status
            cur.execute("""
                SELECT 
                    SUM(gross_pay) as total_gross,
                    SUM(cpp) as total_cpp,
                    SUM(ei) as total_ei,
                    SUM(tax) as total_tax
                FROM driver_payroll
                WHERE year = 2012
                    AND (driver_id != 'ADJ' OR driver_id IS NULL)
            """)
            row = cur.fetchone()
            print(f"\n2012 Year Totals (after Jan-Mar import, excluding ADJ):")
            print(f"  Gross: ${row[0]:.2f}")
            print(f"  CPP: ${row[1]:.2f}")
            print(f"  EI: ${row[2]:.2f}")
            print(f"  Tax: ${row[3]:.2f}")
            
            # Compare to target
            target_gross = Decimal('116859.97')
            remaining = target_gross - row[0]
            print(f"\nTarget (from December paystubs YTD): ${target_gross:.2f}")
            print(f"Remaining gap: ${remaining:.2f}")
    
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
