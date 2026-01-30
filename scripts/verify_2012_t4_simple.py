"""
Simple 2012 T4 extractor - manually enter the CRA data and compare to database.
"""
import psycopg2
import os

# CRA T4 Data from "2012 CRA Copy of T4's_ocred.pdf" (SOURCE OF TRUTH)
CRA_T4_DATA = [
    {'name': 'Michael Blades', 'sin': '627754336', 'box_14': 4279.60, 'box_22': 709.93},
    {'name': 'Kevin Boulley', 'sin': '492717913', 'box_14': 4226.00, 'box_22': 309.46},
    {'name': 'Shawn Callin', 'sin': '637005133', 'box_14': 2509.15, 'box_22': 157.76},
    {'name': 'Wesley Charles', 'sin': '640881041', 'box_14': 3582.99, 'box_22': 271.56},
    {'name': 'Renita Christensen', 'sin': '662354950', 'box_14': 10.90, 'box_22': 0.00},
    {'name': 'Gordon Deans', 'sin': '621372804', 'box_14': 1705.39, 'box_22': 108.07},
    {'name': 'Daryl Derksen', 'sin': '638991356', 'box_14': 611.68, 'box_22': 0.00},
    # Need to add remaining employees from other pages
]

def connect_db():
    return psycopg2.connect(
        dbname=os.getenv('PGDATABASE', 'almsdata'),
        user=os.getenv('PGUSER', 'postgres'),
        host=os.getenv('PGHOST', 'localhost'),
        port=os.getenv('PGPORT', '5432'),
        password=os.getenv('PGPASSWORD', '***REDACTED***')
    )

def get_database_t4_data():
    """Get 2012 T4 data from driver_payroll table."""
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            e.full_name as name,
            SUM(COALESCE(dp.t4_box_14, 0)) as total_box_14,
            SUM(COALESCE(dp.t4_box_22, 0)) as total_box_22,
            COUNT(*) as record_count
        FROM driver_payroll dp
        LEFT JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        AND e.full_name IS NOT NULL
        GROUP BY e.full_name
        ORDER BY e.full_name
    """)
    
    db_records = []
    for row in cur.fetchall():
        db_records.append({
            'name': row[0],
            'box_14': float(row[1]) if row[1] else 0.0,
            'box_22': float(row[2]) if row[2] else 0.0,
            'record_count': row[3]
        })
    
    cur.close()
    conn.close()
    
    return db_records

def normalize_name(name):
    """Normalize name for comparison."""
    if not name:
        return ''
    # Remove punctuation, lowercase, remove spaces
    import re
    return re.sub(r'[^a-z]', '', name.lower())

def compare_t4_data():
    """Compare CRA T4 records against database records."""
    print("="*80)
    print("2012 T4 VERIFICATION - CRA Copy vs Database")
    print("="*80)
    
    db_records = get_database_t4_data()
    
    print(f"\nCRA T4 Records: {len(CRA_T4_DATA)}")
    print(f"Database Payroll Records: {len(db_records)}")
    
    # Create lookup dictionaries
    cra_by_name = {normalize_name(r['name']): r for r in CRA_T4_DATA}
    db_by_name = {normalize_name(r['name']): r for r in db_records if r['name']}
    
    matches = []
    mismatches = []
    missing_in_db = []
    missing_in_cra = []
    
    # Check CRA records against database
    for norm_name, cra_rec in cra_by_name.items():
        if norm_name in db_by_name:
            db_rec = db_by_name[norm_name]
            box_14_diff = abs(cra_rec['box_14'] - db_rec['box_14'])
            box_22_diff = abs(cra_rec['box_22'] - db_rec['box_22'])
            
            if box_14_diff > 0.01 or box_22_diff > 0.01:
                mismatches.append({
                    'name': cra_rec['name'],
                    'cra_box_14': cra_rec['box_14'],
                    'db_box_14': db_rec['box_14'],
                    'diff_box_14': cra_rec['box_14'] - db_rec['box_14'],
                    'cra_box_22': cra_rec['box_22'],
                    'db_box_22': db_rec['box_22'],
                    'diff_box_22': cra_rec['box_22'] - db_rec['box_22']
                })
            else:
                matches.append(cra_rec)
        else:
            missing_in_db.append(cra_rec)
    
    # Check for employees in database but not in CRA file
    for norm_name, db_rec in db_by_name.items():
        if norm_name not in cra_by_name:
            missing_in_cra.append(db_rec)
    
    # Print results
    print("\n" + "="*80)
    print("[OK] MATCHES (Database = CRA)")
    print("="*80)
    for match in matches:
        print(f"  {match['name']:<30} Box 14: ${match['box_14']:>10,.2f}  Box 22: ${match['box_22']:>10,.2f}")
    
    if mismatches:
        print("\n" + "="*80)
        print("[WARN]  MISMATCHES (Database ≠ CRA) - CRA IS SOURCE OF TRUTH")
        print("="*80)
        print(f"{'Name':<30} {'CRA Box 14':>12} {'DB Box 14':>12} {'Diff':>10}  {'CRA Box 22':>12} {'DB Box 22':>12} {'Diff':>10}")
        print("-"*80)
        for mm in mismatches:
            print(f"{mm['name']:<30} ${mm['cra_box_14']:>11,.2f} ${mm['db_box_14']:>11,.2f} ${mm['diff_box_14']:>9,.2f}  ${mm['cra_box_22']:>11,.2f} ${mm['db_box_22']:>11,.2f} ${mm['diff_box_22']:>9,.2f}")
    
    if missing_in_db:
        print("\n" + "="*80)
        print("[WARN]  IN CRA BUT NOT IN DATABASE")
        print("="*80)
        for rec in missing_in_db:
            print(f"  {rec['name']:<30} Box 14: ${rec['box_14']:>10,.2f}  Box 22: ${rec['box_22']:>10,.2f}")
    
    if missing_in_cra:
        print("\n" + "="*80)
        print("[WARN]  IN DATABASE BUT NOT IN CRA FILE (Incomplete CRA data extraction)")
        print("="*80)
        for rec in missing_in_cra:
            print(f"  {rec['name']:<30} Box 14: ${rec['box_14']:>10,.2f}  Box 22: ${rec['box_22']:>10,.2f}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total Matches:           {len(matches)}")
    print(f"Total Mismatches:        {len(mismatches)}")
    print(f"Missing in Database:     {len(missing_in_db)}")
    print(f"Missing in CRA File:     {len(missing_in_cra)} (need to extract from remaining PDF pages)")
    
    if mismatches:
        total_cra_14 = sum(mm['cra_box_14'] for mm in mismatches)
        total_db_14 = sum(mm['db_box_14'] for mm in mismatches)
        total_cra_22 = sum(mm['cra_box_22'] for mm in mismatches)
        total_db_22 = sum(mm['db_box_22'] for mm in mismatches)
        print(f"\nMismatch Totals:")
        print(f"  Box 14 (Income):  CRA ${total_cra_14:,.2f}  DB ${total_db_14:,.2f}  Diff ${total_cra_14 - total_db_14:,.2f}")
        print(f"  Box 22 (Tax):     CRA ${total_cra_22:,.2f}  DB ${total_db_22:,.2f}  Diff ${total_cra_22 - total_db_22:,.2f}")

if __name__ == '__main__':
    print("NOTE: Only 7 of 16 T4s have been manually extracted from PDF so far.")
    print("Need to extract remaining employees from pages 5-16.\n")
    compare_t4_data()
