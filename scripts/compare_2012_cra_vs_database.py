"""
Compare 2012 CRA T4 official data against database driver_payroll records.
Show mismatches with proper T4-compliant names (LASTNAME, Firstname).
"""
import csv
import psycopg2
import os

CRA_CSV = r"l:\limo\data\2012_cra_t4_complete_extraction.csv"

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
            records.append({
                'last_name': row['last_name'],
                'first_name': row['first_name'],
                'initials': row['initials'],
                'sin': row['sin'],
                'address': row['address'],
                'postal_code': row['postal_code'],
                'box_10': row['box_10'],  # Province
                'box_14': float(row['box_14']) if row['box_14'] else 0.0,  # Employment income
                'box_16': float(row['box_16']) if row['box_16'] else 0.0,  # CPP contributions
                'box_18': float(row['box_18']) if row['box_18'] else 0.0,  # EI premiums
                'box_22': float(row['box_22']) if row['box_22'] else 0.0,  # Income tax deducted
                'box_24': float(row['box_24']) if row['box_24'] else 0.0,  # EI insurable earnings
                'box_26': float(row['box_26']) if row['box_26'] else 0.0,  # CPP pensionable earnings
            })
    return records

def get_database_data():
    """Get 2012 payroll data from database grouped by employee."""
    conn = connect_db()
    cur = conn.cursor()
    
    # Get all 2012 payroll records with employee names
    cur.execute("""
        SELECT 
            e.full_name,
            SUM(COALESCE(dp.gross_pay, 0)) as total_gross,
            SUM(COALESCE(dp.cpp, 0)) as total_cpp,
            SUM(COALESCE(dp.ei, 0)) as total_ei,
            SUM(COALESCE(dp.tax, 0)) as total_tax,
            SUM(COALESCE(dp.t4_box_14, 0)) as total_t4_box_14,
            SUM(COALESCE(dp.t4_box_22, 0)) as total_t4_box_22,
            COUNT(*) as record_count
        FROM driver_payroll dp
        LEFT JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        AND e.full_name IS NOT NULL
        GROUP BY e.full_name
        ORDER BY e.full_name
    """)
    
    records = {}
    for row in cur.fetchall():
        records[row[0]] = {
            'name': row[0],
            'gross_pay': float(row[1]),
            'cpp': float(row[2]),
            'ei': float(row[3]),
            'tax': float(row[4]),
            't4_box_14': float(row[5]),
            't4_box_22': float(row[6]),
            'record_count': row[7]
        }
    
    cur.close()
    conn.close()
    
    return records

def normalize_name(last, first, initials=''):
    """Create normalized name for matching."""
    # Remove special chars, lowercase
    import re
    last = re.sub(r'[^a-z]', '', last.lower()) if last else ''
    first = re.sub(r'[^a-z]', '', first.lower()) if first else ''
    return f"{last}{first}"

def compare_data():
    """Compare CRA T4 data against database."""
    print("="*100)
    print("2012 T4 VERIFICATION - CRA vs Database")
    print("="*100)
    
    cra_records = load_cra_data()
    db_records = get_database_data()
    
    print(f"\nCRA T4 Slips: {len(cra_records)}")
    print(f"Database Employees with 2012 payroll: {len(db_records)}")
    
    # Create lookup by normalized name
    cra_by_norm = {}
    for r in cra_records:
        norm = normalize_name(r['last_name'], r['first_name'], r['initials'])
        cra_by_norm[norm] = r
    
    db_by_norm = {}
    for name, data in db_records.items():
        # Database uses "Last, First" or "Last, First Middle" format
        parts = name.split(',')
        if len(parts) >= 2:
            last = parts[0].strip()
            first_middle = parts[1].strip().split()
            first = first_middle[0] if first_middle else ''
            norm = normalize_name(last, first)
            db_by_norm[norm] = data
    
    # Compare
    matches = []
    mismatches = []
    in_cra_not_db = []
    in_db_not_cra = []
    
    for norm, cra_rec in cra_by_norm.items():
        cra_name = f"{cra_rec['last_name']}, {cra_rec['first_name']}"
        if cra_rec['initials'] and cra_rec['initials'] not in ['RPP']:
            cra_name += f" {cra_rec['initials']}"
        
        if norm in db_by_norm:
            db_rec = db_by_norm[norm]
            
            # Compare values
            # CRA Box 14 should match gross_pay (or t4_box_14 if populated)
            # CRA Box 22 should match tax (or t4_box_22 if populated)
            # CRA Box 16 should match cpp
            # CRA Box 18 should match ei
            
            box_14_diff = abs(cra_rec['box_14'] - db_rec['gross_pay'])
            box_22_diff = abs(cra_rec['box_22'] - db_rec['tax'])
            box_16_diff = abs(cra_rec['box_16'] - db_rec['cpp'])
            box_18_diff = abs(cra_rec['box_18'] - db_rec['ei'])
            
            if box_14_diff > 0.01 or box_22_diff > 0.01 or box_16_diff > 0.01 or box_18_diff > 0.01:
                mismatches.append({
                    'cra_name': cra_name,
                    'db_name': db_rec['name'],
                    'sin': cra_rec['sin'],
                    'cra_box_14': cra_rec['box_14'],
                    'db_gross': db_rec['gross_pay'],
                    'diff_14': cra_rec['box_14'] - db_rec['gross_pay'],
                    'cra_box_22': cra_rec['box_22'],
                    'db_tax': db_rec['tax'],
                    'diff_22': cra_rec['box_22'] - db_rec['tax'],
                    'cra_box_16': cra_rec['box_16'],
                    'db_cpp': db_rec['cpp'],
                    'diff_16': cra_rec['box_16'] - db_rec['cpp'],
                    'cra_box_18': cra_rec['box_18'],
                    'db_ei': db_rec['ei'],
                    'diff_18': cra_rec['box_18'] - db_rec['ei'],
                })
            else:
                matches.append({'cra_name': cra_name, 'db_name': db_rec['name'], 'box_14': cra_rec['box_14']})
        else:
            in_cra_not_db.append({
                'cra_name': cra_name,
                'sin': cra_rec['sin'],
                'box_14': cra_rec['box_14'],
                'box_22': cra_rec['box_22']
            })
    
    # Check for DB employees not in CRA
    for norm, db_rec in db_by_norm.items():
        if norm not in cra_by_norm:
            in_db_not_cra.append({
                'db_name': db_rec['name'],
                'gross': db_rec['gross_pay'],
                'tax': db_rec['tax']
            })
    
    # Print results
    print("\n" + "="*100)
    print("[OK] MATCHES (CRA = Database)")
    print("="*100)
    for m in matches:
        print(f"  {m['cra_name']:<40s} Box 14: ${m['box_14']:>10,.2f}")
    
    if mismatches:
        print("\n" + "="*100)
        print("[WARN]  MISMATCHES (CRA ≠ Database) - CRA IS SOURCE OF TRUTH")
        print("="*100)
        print(f"{'Name':<40s} {'Field':<10s} {'CRA Value':>12s} {'DB Value':>12s} {'Difference':>12s}")
        print("-"*100)
        for mm in mismatches:
            print(f"{mm['cra_name']:<40s} Box 14     ${mm['cra_box_14']:>11,.2f} ${mm['db_gross']:>11,.2f} ${mm['diff_14']:>11,.2f}")
            if abs(mm['diff_22']) > 0.01:
                print(f"{'':40s} Box 22     ${mm['cra_box_22']:>11,.2f} ${mm['db_tax']:>11,.2f} ${mm['diff_22']:>11,.2f}")
            if abs(mm['diff_16']) > 0.01:
                print(f"{'':40s} Box 16     ${mm['cra_box_16']:>11,.2f} ${mm['db_cpp']:>11,.2f} ${mm['diff_16']:>11,.2f}")
            if abs(mm['diff_18']) > 0.01:
                print(f"{'':40s} Box 18     ${mm['cra_box_18']:>11,.2f} ${mm['db_ei']:>11,.2f} ${mm['diff_18']:>11,.2f}")
    
    if in_cra_not_db:
        print("\n" + "="*100)
        print("[WARN]  IN CRA BUT NOT IN DATABASE (Employee_id linkage issue)")
        print("="*100)
        for rec in in_cra_not_db:
            print(f"  {rec['cra_name']:<40s} SIN: {rec['sin']} Box 14: ${rec['box_14']:>10,.2f}")
    
    if in_db_not_cra:
        print("\n" + "="*100)
        print("ℹ️  IN DATABASE BUT NOT IN CRA (Below T4 threshold or contractors)")
        print("="*100)
        for rec in in_db_not_cra:
            print(f"  {rec['db_name']:<40s} Gross: ${rec['gross']:>10,.2f}")
    
    # Totals
    print("\n" + "="*100)
    print("TOTALS COMPARISON")
    print("="*100)
    
    cra_total_14 = sum(r['box_14'] for r in cra_records)
    cra_total_22 = sum(r['box_22'] for r in cra_records)
    cra_total_16 = sum(r['box_16'] for r in cra_records)
    cra_total_18 = sum(r['box_18'] for r in cra_records)
    
    db_total_gross = sum(r['gross_pay'] for r in db_records.values())
    db_total_tax = sum(r['tax'] for r in db_records.values())
    db_total_cpp = sum(r['cpp'] for r in db_records.values())
    db_total_ei = sum(r['ei'] for r in db_records.values())
    
    print(f"{'Metric':<40s} {'CRA Total':>15s} {'DB Total':>15s} {'Difference':>15s}")
    print("-"*100)
    print(f"{'Box 14 (Employment Income)':<40s} ${cra_total_14:>14,.2f} ${db_total_gross:>14,.2f} ${cra_total_14-db_total_gross:>14,.2f}")
    print(f"{'Box 22 (Income Tax Deducted)':<40s} ${cra_total_22:>14,.2f} ${db_total_tax:>14,.2f} ${cra_total_22-db_total_tax:>14,.2f}")
    print(f"{'Box 16 (CPP Contributions)':<40s} ${cra_total_16:>14,.2f} ${db_total_cpp:>14,.2f} ${cra_total_16-db_total_cpp:>14,.2f}")
    print(f"{'Box 18 (EI Premiums)':<40s} ${cra_total_18:>14,.2f} ${db_total_ei:>14,.2f} ${cra_total_18-db_total_ei:>14,.2f}")
    
    # Summary
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    print(f"Total Matches:                           {len(matches)}")
    print(f"Total Mismatches:                        {len(mismatches)}")
    print(f"In CRA but not in Database:              {len(in_cra_not_db)}")
    print(f"In Database but not in CRA:              {len(in_db_not_cra)}")

if __name__ == '__main__':
    compare_data()
