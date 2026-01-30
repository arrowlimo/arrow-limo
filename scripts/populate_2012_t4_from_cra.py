"""
Populate 2012 T4 data from CRA official filing.
1. Add missing employees to employees table
2. Update driver_payroll with official T4 box values
3. Generate detailed comparison reports
"""
import csv
import psycopg2
import os
from datetime import datetime

CRA_CSV = r"l:\limo\data\2012_cra_t4_complete_extraction.csv"
REPORT_DIR = r"l:\limo\reports"

def connect_db():
    return psycopg2.connect(
        dbname=os.getenv('PGDATABASE', 'almsdata'),
        user=os.getenv('PGUSER', 'postgres'),
        host=os.getenv('PGHOST', 'localhost'),
        port=os.getenv('PGPORT', '5432'),
        password=os.getenv('PGPASSWORD', '***REDACTED***')
    )

def load_cra_data():
    """Load CRA T4 data from CSV."""
    records = []
    with open(CRA_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {
                'last_name': row['last_name'],
                'first_name': row['first_name'],
                'initials': row['initials'],
                'sin': row['sin'],
                'address': row['address'],
                'postal_code': row['postal_code'],
            }
            # Add all T4 boxes
            for key in row.keys():
                if key.startswith('box_'):
                    # Box 10 is province (text), others are numeric
                    if key == 'box_10':
                        record[key] = row[key] if row[key] else None
                    else:
                        try:
                            record[key] = float(row[key]) if row[key] else None
                        except ValueError:
                            record[key] = None
            records.append(record)
    return records

def get_existing_employees(conn):
    """Get existing employees with their IDs."""
    cur = conn.cursor()
    cur.execute("SELECT employee_id, full_name, first_name, last_name FROM employees")
    employees = {}
    for row in cur.fetchall():
        emp_id, full_name, first, last = row
        # Create multiple lookup keys
        if full_name:
            employees[full_name.lower().strip()] = emp_id
        if first and last:
            employees[f"{last}, {first}".lower().strip()] = emp_id
            employees[f"{first} {last}".lower().strip()] = emp_id
    cur.close()
    return employees

def normalize_name(last, first, initials=''):
    """Create normalized name for matching."""
    import re
    last = re.sub(r'[^a-z]', '', last.lower()) if last else ''
    first = re.sub(r'[^a-z]', '', first.lower()) if first else ''
    return f"{last}{first}"

def add_missing_employees(conn, cra_records, dry_run=True):
    """Add employees that exist in CRA but not in database."""
    cur = conn.cursor()
    
    existing = get_existing_employees(conn)
    
    added = []
    skipped = []
    
    for rec in cra_records:
        # Try multiple name formats
        full_name = f"{rec['last_name']}, {rec['first_name']}"
        if rec['initials'] and rec['initials'] not in ['RPP']:
            full_name += f" {rec['initials']}"
        
        name_variations = [
            full_name.lower(),
            f"{rec['first_name']} {rec['last_name']}".lower(),
            f"{rec['last_name']}, {rec['first_name']}".lower(),
        ]
        
        found = False
        for name_var in name_variations:
            if name_var in existing:
                found = True
                skipped.append((full_name, existing[name_var]))
                break
        
        if not found:
            # Add new employee
            if not dry_run:
                # Generate employee_number (use next available number)
                # employee_number is TEXT, so cast to integer for math, then back to text
                cur.execute("SELECT COALESCE(MAX(employee_number::integer), 0) + 1 FROM employees WHERE employee_number IS NOT NULL AND employee_number ~ '^[0-9]+$'")
                emp_number = str(cur.fetchone()[0])
                cur.execute("""
                    INSERT INTO employees 
                    (employee_number, full_name, first_name, last_name, position, status, is_chauffeur, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING employee_id
                """, (
                    emp_number,
                    full_name,
                    rec['first_name'],
                    rec['last_name'],
                    'Chauffeur',
                    'terminated',  # All 2012 employees are historical
                    False,  # Set to false to avoid auto driver_code assignment trigger
                    datetime.now()
                ))
                emp_id = cur.fetchone()[0]
                added.append((full_name, emp_id, rec['sin']))
                print(f"  [OK] Added: {full_name} (ID: {emp_id}, #: {emp_number}, SIN: {rec['sin']})")
            else:
                added.append((full_name, None, rec['sin']))
                print(f"  [DRY-RUN] Would add: {full_name} (SIN: {rec['sin']})")
    
    if not dry_run:
        conn.commit()
    
    return added, skipped

def get_payroll_data_by_employee(conn):
    """Get 2012 payroll data grouped by employee."""
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            e.employee_id,
            e.full_name,
            SUM(COALESCE(dp.gross_pay, 0)) as total_gross,
            SUM(COALESCE(dp.cpp, 0)) as total_cpp,
            SUM(COALESCE(dp.ei, 0)) as total_ei,
            SUM(COALESCE(dp.tax, 0)) as total_tax,
            SUM(COALESCE(dp.net_pay, 0)) as total_net,
            SUM(COALESCE(dp.t4_box_14, 0)) as t4_box_14,
            SUM(COALESCE(dp.t4_box_16, 0)) as t4_box_16,
            SUM(COALESCE(dp.t4_box_18, 0)) as t4_box_18,
            SUM(COALESCE(dp.t4_box_22, 0)) as t4_box_22,
            SUM(COALESCE(dp.t4_box_24, 0)) as t4_box_24,
            SUM(COALESCE(dp.t4_box_26, 0)) as t4_box_26,
            COUNT(*) as record_count
        FROM driver_payroll dp
        LEFT JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        AND e.employee_id IS NOT NULL
        GROUP BY e.employee_id, e.full_name
        ORDER BY e.full_name
    """)
    
    payroll = {}
    for row in cur.fetchall():
        payroll[row[0]] = {  # Key by employee_id
            'employee_id': row[0],
            'full_name': row[1],
            'gross_pay': float(row[2]),
            'cpp': float(row[3]),
            'ei': float(row[4]),
            'tax': float(row[5]),
            'net_pay': float(row[6]),
            't4_box_14': float(row[7]),
            't4_box_16': float(row[8]),
            't4_box_18': float(row[9]),
            't4_box_22': float(row[10]),
            't4_box_24': float(row[11]),
            't4_box_26': float(row[12]),
            'record_count': row[13]
        }
    cur.close()
    return payroll

def update_t4_boxes(conn, cra_records, dry_run=True):
    """Update T4 box values in driver_payroll to match CRA filing."""
    cur = conn.cursor()
    
    # Get employee lookup
    existing = get_existing_employees(conn)
    
    updates = []
    not_found = []
    
    for rec in cra_records:
        # Find employee ID
        full_name = f"{rec['last_name']}, {rec['first_name']}"
        if rec['initials'] and rec['initials'] not in ['RPP']:
            full_name += f" {rec['initials']}"
        
        name_variations = [
            full_name.lower(),
            f"{rec['first_name']} {rec['last_name']}".lower(),
            f"{rec['last_name']}, {rec['first_name']}".lower(),
        ]
        
        emp_id = None
        for name_var in name_variations:
            if name_var in existing:
                emp_id = existing[name_var]
                break
        
        if emp_id:
            # Update all T4 boxes for this employee's 2012 records
            if not dry_run:
                cur.execute("""
                    UPDATE driver_payroll
                    SET 
                        t4_box_10 = %s,
                        t4_box_14 = %s,
                        t4_box_16 = %s,
                        t4_box_18 = %s,
                        t4_box_22 = %s,
                        t4_box_24 = %s,
                        t4_box_26 = %s
                    WHERE employee_id = %s
                    AND year = 2012
                """, (
                    rec['box_10'],  # Province of employment
                    rec['box_14'],  # Employment income
                    rec['box_16'],  # CPP contributions
                    rec['box_18'],  # EI premiums
                    rec['box_22'],  # Income tax deducted
                    rec['box_24'],  # EI insurable earnings
                    rec['box_26'],  # CPP pensionable earnings
                    emp_id
                ))
                updated_rows = cur.rowcount
                updates.append((full_name, emp_id, updated_rows))
                print(f"  [OK] Updated {updated_rows} records for {full_name} (ID: {emp_id})")
            else:
                updates.append((full_name, emp_id, 0))
                print(f"  [DRY-RUN] Would update records for {full_name} (ID: {emp_id})")
        else:
            not_found.append((full_name, rec['sin']))
            print(f"  [WARN]  Employee not found: {full_name} (SIN: {rec['sin']})")
    
    if not dry_run:
        conn.commit()
    
    return updates, not_found

def generate_detailed_reports(cra_records):
    """Generate detailed comparison reports."""
    conn = connect_db()
    
    # Get current employee and payroll data
    existing = get_existing_employees(conn)
    payroll = get_payroll_data_by_employee(conn)
    
    # Create employee ID to payroll lookup
    payroll_by_name = {}
    for emp_id, data in payroll.items():
        name_lower = data['full_name'].lower() if data['full_name'] else ''
        payroll_by_name[name_lower] = data
    
    matched = []
    mismatched = []
    not_in_db = []
    
    for rec in cra_records:
        full_name = f"{rec['last_name']}, {rec['first_name']}"
        if rec['initials'] and rec['initials'] not in ['RPP']:
            full_name += f" {rec['initials']}"
        
        name_variations = [
            full_name.lower(),
            f"{rec['first_name']} {rec['last_name']}".lower(),
            f"{rec['last_name']}, {rec['first_name']}".lower(),
        ]
        
        db_data = None
        for name_var in name_variations:
            if name_var in payroll_by_name:
                db_data = payroll_by_name[name_var]
                break
        
        if db_data:
            # Compare all boxes
            diff_14 = abs((rec['box_14'] or 0) - db_data['gross_pay'])
            diff_16 = abs((rec['box_16'] or 0) - db_data['cpp'])
            diff_18 = abs((rec['box_18'] or 0) - db_data['ei'])
            diff_22 = abs((rec['box_22'] or 0) - db_data['tax'])
            diff_24 = abs((rec['box_24'] or 0) - db_data['t4_box_24'])
            diff_26 = abs((rec['box_26'] or 0) - db_data['t4_box_26'])
            
            comparison = {
                'name': full_name,
                'sin': rec['sin'],
                'address': rec['address'],
                'postal_code': rec['postal_code'],
                'cra': rec,
                'db': db_data,
                'differences': {
                    'box_14': diff_14,
                    'box_16': diff_16,
                    'box_18': diff_18,
                    'box_22': diff_22,
                    'box_24': diff_24,
                    'box_26': diff_26,
                }
            }
            
            # Check if match (all differences < 0.01)
            if all(d < 0.01 for d in comparison['differences'].values()):
                matched.append(comparison)
            else:
                mismatched.append(comparison)
        else:
            not_in_db.append({
                'name': full_name,
                'sin': rec['sin'],
                'address': rec['address'],
                'postal_code': rec['postal_code'],
                'cra': rec
            })
    
    conn.close()
    
    # Generate reports
    generate_matched_report(matched)
    generate_mismatched_report(mismatched)
    generate_not_in_db_report(not_in_db)
    
    return matched, mismatched, not_in_db

def generate_matched_report(matched):
    """Generate report of perfectly matched T4 slips."""
    report_path = os.path.join(REPORT_DIR, '2012_T4_MATCHED_SLIPS.md')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 2012 T4 Matched Slips Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total Matched Slips: {len(matched)}\n\n")
        f.write("These employees have T4 slips where CRA filing matches database records exactly (within $0.01).\n\n")
        
        if not matched:
            f.write("**No perfectly matched slips found.**\n\n")
            f.write("All 2012 T4 slips show discrepancies between CRA filing and database records.\n")
        else:
            f.write("| Employee | SIN | Box 14 (Income) | Box 16 (CPP) | Box 18 (EI) | Box 22 (Tax) |\n")
            f.write("|----------|-----|-----------------|--------------|-------------|---------------|\n")
            
            for m in matched:
                f.write(f"| {m['name']} | {m['sin']} | ${m['cra']['box_14']:,.2f} | ${m['cra']['box_16']:,.2f} | ${m['cra']['box_18']:,.2f} | ${m['cra']['box_22']:,.2f} |\n")
            
            # Totals
            total_14 = sum(m['cra']['box_14'] or 0 for m in matched)
            total_16 = sum(m['cra']['box_16'] or 0 for m in matched)
            total_18 = sum(m['cra']['box_18'] or 0 for m in matched)
            total_22 = sum(m['cra']['box_22'] or 0 for m in matched)
            
            f.write(f"\n**Totals:** ${total_14:,.2f} income, ${total_16:,.2f} CPP, ${total_18:,.2f} EI, ${total_22:,.2f} tax\n")
    
    print(f"\n[OK] Generated: {report_path}")

def generate_mismatched_report(mismatched):
    """Generate detailed report of mismatched T4 slips."""
    report_path = os.path.join(REPORT_DIR, '2012_T4_MISMATCHED_SLIPS_DETAIL.md')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 2012 T4 Mismatched Slips - Detailed Analysis\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total Mismatched Slips: {len(mismatched)}\n\n")
        f.write("## Summary\n\n")
        f.write("These T4 slips show discrepancies between CRA official filing and database records.\n")
        f.write("**CRA values are the source of truth** - these represent what was actually filed with the government.\n\n")
        
        # Calculate totals
        total_cra_14 = sum(m['cra']['box_14'] or 0 for m in mismatched)
        total_db_14 = sum(m['db']['gross_pay'] for m in mismatched)
        total_cra_16 = sum(m['cra']['box_16'] or 0 for m in mismatched)
        total_db_16 = sum(m['db']['cpp'] for m in mismatched)
        total_cra_18 = sum(m['cra']['box_18'] or 0 for m in mismatched)
        total_db_18 = sum(m['db']['ei'] for m in mismatched)
        total_cra_22 = sum(m['cra']['box_22'] or 0 for m in mismatched)
        total_db_22 = sum(m['db']['tax'] for m in mismatched)
        
        f.write("### Aggregate Totals\n\n")
        f.write("| Box | Description | CRA Filed | Database | Difference | % of CRA |\n")
        f.write("|-----|-------------|-----------|----------|------------|----------|\n")
        f.write(f"| 14 | Employment Income | ${total_cra_14:,.2f} | ${total_db_14:,.2f} | ${total_cra_14-total_db_14:,.2f} | {(total_db_14/total_cra_14*100) if total_cra_14 else 0:.1f}% |\n")
        f.write(f"| 16 | CPP Contributions | ${total_cra_16:,.2f} | ${total_db_16:,.2f} | ${total_cra_16-total_db_16:,.2f} | {(total_db_16/total_cra_16*100) if total_cra_16 else 0:.1f}% |\n")
        f.write(f"| 18 | EI Premiums | ${total_cra_18:,.2f} | ${total_db_18:,.2f} | ${total_cra_18-total_db_18:,.2f} | {(total_db_18/total_cra_18*100) if total_cra_18 else 0:.1f}% |\n")
        f.write(f"| 22 | Income Tax Deducted | ${total_cra_22:,.2f} | ${total_db_22:,.2f} | ${total_cra_22-total_db_22:,.2f} | {(total_db_22/total_cra_22*100) if total_cra_22 else 0:.1f}% |\n")
        
        f.write("\n## Individual Employee Details\n\n")
        
        # Sort by largest discrepancy in Box 14
        mismatched_sorted = sorted(mismatched, key=lambda x: x['differences']['box_14'], reverse=True)
        
        for m in mismatched_sorted:
            f.write(f"### {m['name']}\n\n")
            f.write(f"**SIN:** {m['sin']}  \n")
            f.write(f"**Address:** {m['address']}, {m['postal_code']}  \n")
            f.write(f"**Database Records:** {m['db']['record_count']} payroll entries  \n\n")
            
            f.write("| Box | Description | CRA Filed | Database | Difference | Status |\n")
            f.write("|-----|-------------|-----------|----------|------------|--------|\n")
            
            # Box 10 - Province
            f.write(f"| 10 | Province | {m['cra']['box_10']} | - | - | ℹ️ |\n")
            
            # Box 14 - Employment income
            box_14_cra = m['cra']['box_14'] or 0
            box_14_db = m['db']['gross_pay']
            box_14_diff = box_14_cra - box_14_db
            box_14_status = "[OK]" if abs(box_14_diff) < 0.01 else "[FAIL]"
            f.write(f"| 14 | Employment Income | ${box_14_cra:,.2f} | ${box_14_db:,.2f} | ${box_14_diff:,.2f} | {box_14_status} |\n")
            
            # Box 16 - CPP contributions
            box_16_cra = m['cra']['box_16'] or 0
            box_16_db = m['db']['cpp']
            box_16_diff = box_16_cra - box_16_db
            box_16_status = "[OK]" if abs(box_16_diff) < 0.01 else "[FAIL]"
            f.write(f"| 16 | CPP Contributions | ${box_16_cra:,.2f} | ${box_16_db:,.2f} | ${box_16_diff:,.2f} | {box_16_status} |\n")
            
            # Box 18 - EI premiums
            box_18_cra = m['cra']['box_18'] or 0
            box_18_db = m['db']['ei']
            box_18_diff = box_18_cra - box_18_db
            box_18_status = "[OK]" if abs(box_18_diff) < 0.01 else "[FAIL]"
            f.write(f"| 18 | EI Premiums | ${box_18_cra:,.2f} | ${box_18_db:,.2f} | ${box_18_diff:,.2f} | {box_18_status} |\n")
            
            # Box 22 - Income tax deducted
            box_22_cra = m['cra']['box_22'] or 0
            box_22_db = m['db']['tax']
            box_22_diff = box_22_cra - box_22_db
            box_22_status = "[OK]" if abs(box_22_diff) < 0.01 else "[FAIL]"
            f.write(f"| 22 | Income Tax Deducted | ${box_22_cra:,.2f} | ${box_22_db:,.2f} | ${box_22_diff:,.2f} | {box_22_status} |\n")
            
            # Box 24 - EI insurable earnings
            box_24_cra = m['cra']['box_24'] or 0
            box_24_db = m['db']['t4_box_24']
            box_24_diff = box_24_cra - box_24_db
            box_24_status = "[OK]" if abs(box_24_diff) < 0.01 else "[FAIL]"
            f.write(f"| 24 | EI Insurable Earnings | ${box_24_cra:,.2f} | ${box_24_db:,.2f} | ${box_24_diff:,.2f} | {box_24_status} |\n")
            
            # Box 26 - CPP pensionable earnings
            box_26_cra = m['cra']['box_26'] or 0
            box_26_db = m['db']['t4_box_26']
            box_26_diff = box_26_cra - box_26_db
            box_26_status = "[OK]" if abs(box_26_diff) < 0.01 else "[FAIL]"
            f.write(f"| 26 | CPP Pensionable Earnings | ${box_26_cra:,.2f} | ${box_26_db:,.2f} | ${box_26_diff:,.2f} | {box_26_status} |\n")
            
            f.write("\n")
            
            # Analysis
            if box_14_diff > 100:
                f.write(f"**[WARN] Significant income discrepancy:** CRA shows ${box_14_diff:,.2f} more income than database.\n\n")
            elif box_14_diff < -100:
                f.write(f"**[WARN] Database shows more income:** Database has ${-box_14_diff:,.2f} more than CRA filing.\n\n")
            
            f.write("---\n\n")
    
    print(f"[OK] Generated: {report_path}")

def generate_not_in_db_report(not_in_db):
    """Generate report of employees in CRA but not in database."""
    report_path = os.path.join(REPORT_DIR, '2012_T4_NOT_IN_DATABASE.md')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 2012 T4 Slips Not Found in Database\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total Missing: {len(not_in_db)}\n\n")
        f.write("These employees have T4 slips filed with CRA but no corresponding payroll records in the database.\n")
        f.write("This indicates employee_id linkage issues or missing payroll imports.\n\n")
        
        if not_in_db:
            total_income = sum(emp['cra']['box_14'] or 0 for emp in not_in_db)
            total_tax = sum(emp['cra']['box_22'] or 0 for emp in not_in_db)
            
            f.write(f"**Total Income Not in Database:** ${total_income:,.2f}  \n")
            f.write(f"**Total Tax Not in Database:** ${total_tax:,.2f}  \n\n")
            
            f.write("## Individual Details\n\n")
            
            for emp in sorted(not_in_db, key=lambda x: x['cra']['box_14'] or 0, reverse=True):
                f.write(f"### {emp['name']}\n\n")
                f.write(f"**SIN:** {emp['sin']}  \n")
                f.write(f"**Address:** {emp['address']}, {emp['postal_code']}  \n\n")
                
                f.write("| Box | Description | CRA Filed |\n")
                f.write("|-----|-------------|----------|\n")
                f.write(f"| 10 | Province | {emp['cra']['box_10']} |\n")
                f.write(f"| 14 | Employment Income | ${emp['cra']['box_14'] or 0:,.2f} |\n")
                f.write(f"| 16 | CPP Contributions | ${emp['cra']['box_16'] or 0:,.2f} |\n")
                f.write(f"| 18 | EI Premiums | ${emp['cra']['box_18'] or 0:,.2f} |\n")
                f.write(f"| 22 | Income Tax Deducted | ${emp['cra']['box_22'] or 0:,.2f} |\n")
                f.write(f"| 24 | EI Insurable Earnings | ${emp['cra']['box_24'] or 0:,.2f} |\n")
                f.write(f"| 26 | CPP Pensionable Earnings | ${emp['cra']['box_26'] or 0:,.2f} |\n")
                
                f.write("\n**Action Required:** Link to existing employee or import missing payroll data.\n\n")
                f.write("---\n\n")
    
    print(f"[OK] Generated: {report_path}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate 2012 T4 data from CRA filing')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    print("="*100)
    print("2012 T4 DATA POPULATION FROM CRA FILING")
    print("="*100)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print()
    
    # Load CRA data
    print("Loading CRA T4 data...")
    cra_records = load_cra_data()
    print(f"  Loaded {len(cra_records)} T4 slips from CRA filing\n")
    
    # Connect to database
    conn = connect_db()
    
    # Step 1: Add missing employees
    print("="*100)
    print("STEP 1: ADD MISSING EMPLOYEES")
    print("="*100)
    added, skipped = add_missing_employees(conn, cra_records, dry_run=not args.write)
    print(f"\n  Added: {len(added)}")
    print(f"  Already existed: {len(skipped)}\n")
    
    # Step 2: Update T4 boxes
    print("="*100)
    print("STEP 2: UPDATE T4 BOX VALUES")
    print("="*100)
    updates, not_found = update_t4_boxes(conn, cra_records, dry_run=not args.write)
    print(f"\n  Updated: {len(updates)}")
    print(f"  Not found: {len(not_found)}\n")
    
    conn.close()
    
    # Step 3: Generate detailed reports
    print("="*100)
    print("STEP 3: GENERATE DETAILED REPORTS")
    print("="*100)
    matched, mismatched, not_in_db = generate_detailed_reports(cra_records)
    
    print(f"\n  Matched slips: {len(matched)}")
    print(f"  Mismatched slips: {len(mismatched)}")
    print(f"  Not in database: {len(not_in_db)}")
    
    print("\n" + "="*100)
    print("COMPLETE")
    print("="*100)
    
    if not args.write:
        print("\n[WARN]  DRY-RUN MODE - No changes were made to the database.")
        print("Run with --write to apply changes.")
