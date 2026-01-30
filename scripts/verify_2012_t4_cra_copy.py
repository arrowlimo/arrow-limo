"""
Verify 2012 CRA Copy of T4's against database records.
Extract T4 data from the official CRA copy and compare to driver_payroll records.
"""
import os
import re
import pdfplumber
import psycopg2
from decimal import Decimal

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def extract_2012_t4_data(pdf_path):
    """
    Extract T4 data from 2012 CRA Copy PDF.
    Returns list of T4 records with employee name, SIN, and box amounts.
    """
    t4_records = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Processing PDF with {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    print(f"  Page {page_num}: No text extracted")
                    continue
                
                print(f"\n=== Page {page_num} ===")
                print(text)  # Print full text to see all structure
                
                # Look for T4 slip patterns
                # Common patterns: employee names (all caps), SIN (xxx xxx xxx), box amounts
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                
                for i, line in enumerate(lines):
                    # Look for employee names (usually all caps, 2-3 words)
                    if re.match(r'^[A-Z][A-Z\s\-\.]+$', line) and 5 < len(line) < 50:
                        # Skip company names and common headers
                        if any(skip in line for skip in ['ARROW', 'LIMOUSINE', 'SERVICES', 'CANADA REVENUE']):
                            continue
                        
                        # Look for SIN in nearby lines
                        sin = None
                        for offset in range(-3, 4):
                            if 0 <= i + offset < len(lines):
                                sin_match = re.search(r'(\d{3})\s+(\d{3})\s+(\d{3})', lines[i + offset])
                                if sin_match:
                                    sin = ''.join(sin_match.groups())
                                    break
                        
                        if sin:
                            # Look for box 14 (employment income) - usually largest amount
                            box_14 = None
                            for offset in range(-5, 6):
                                if 0 <= i + offset < len(lines):
                                    amounts = re.findall(r'\b(\d{1,3}(?:,?\d{3})*\.\d{2})\b', lines[i + offset])
                                    for amt in amounts:
                                        val = float(amt.replace(',', ''))
                                        if 100 <= val <= 999999:
                                            box_14 = amt.replace(',', '')
                                            break
                                    if box_14:
                                        break
                            
                            if box_14:
                                t4_records.append({
                                    'name': line.strip(),
                                    'sin': sin,
                                    'box_14_employment_income': box_14,
                                    'page': page_num
                                })
                                print(f"  Found T4: {line.strip()} - SIN: {sin} - Box 14: ${box_14}")
    
    except Exception as e:
        print(f"Error processing PDF: {e}")
        import traceback
        traceback.print_exc()
    
    return t4_records

def get_database_t4_data():
    """
    Get 2012 T4 data from driver_payroll table.
    Sum up box 14 (employment income) by employee.
    """
    conn = connect_db()
    cur = conn.cursor()
    
    # Get 2012 payroll totals by employee
    cur.execute("""
        SELECT 
            e.full_name,
            SUM(dp.t4_box_14) as total_box_14,
            COUNT(*) as record_count
        FROM driver_payroll dp
        LEFT JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        AND dp.t4_box_14 IS NOT NULL
        GROUP BY e.full_name
        ORDER BY e.full_name
    """)
    
    db_records = []
    for row in cur.fetchall():
        db_records.append({
            'name': row[0],
            'sin': None,
            'box_14': float(row[1]) if row[1] else 0.0,
            'record_count': row[2]
        })
    
    cur.close()
    conn.close()
    
    return db_records

def normalize_name(name):
    """Normalize name for comparison (remove spaces, lowercase, remove punctuation)."""
    if not name:
        return ''
    return re.sub(r'[^a-z]', '', name.lower())

def compare_t4_data(cra_records, db_records):
    """Compare CRA T4 records against database records."""
    print("\n" + "="*80)
    print("2012 T4 VERIFICATION - CRA Copy vs Database")
    print("="*80)
    
    print(f"\nCRA T4 Records Found: {len(cra_records)}")
    print(f"Database Records Found: {len(db_records)}")
    
    # Create lookup dictionaries
    cra_by_name = {normalize_name(r['name']): r for r in cra_records}
    db_by_name = {normalize_name(r['name']): r for r in db_records if r['name']}
    
    mismatches = []
    matches = []
    missing_in_db = []
    missing_in_cra = []
    
    # Check CRA records against database
    for norm_name, cra_rec in cra_by_name.items():
        if norm_name in db_by_name:
            db_rec = db_by_name[norm_name]
            cra_amount = float(cra_rec['box_14_employment_income'])
            db_amount = db_rec['box_14']
            
            diff = abs(cra_amount - db_amount)
            if diff > 0.01:  # More than 1 cent difference
                mismatches.append({
                    'name': cra_rec['name'],
                    'sin': cra_rec['sin'],
                    'cra_amount': cra_amount,
                    'db_amount': db_amount,
                    'difference': cra_amount - db_amount
                })
            else:
                matches.append({
                    'name': cra_rec['name'],
                    'amount': cra_amount
                })
        else:
            missing_in_db.append(cra_rec)
    
    # Check for employees in database but not in CRA file
    for norm_name, db_rec in db_by_name.items():
        if norm_name not in cra_by_name:
            missing_in_cra.append(db_rec)
    
    # Print results
    print("\n" + "="*80)
    print("MATCHES (Database = CRA)")
    print("="*80)
    for match in matches:
        print(f"[OK] {match['name']:<30} ${match['amount']:>10,.2f}")
    
    if mismatches:
        print("\n" + "="*80)
        print("[WARN]  MISMATCHES (Database ≠ CRA) - CRA IS SOURCE OF TRUTH")
        print("="*80)
        print(f"{'Name':<30} {'CRA Amount':>12} {'DB Amount':>12} {'Difference':>12}")
        print("-"*80)
        for mm in mismatches:
            print(f"{mm['name']:<30} ${mm['cra_amount']:>11,.2f} ${mm['db_amount']:>11,.2f} ${mm['difference']:>11,.2f}")
    
    if missing_in_db:
        print("\n" + "="*80)
        print("[WARN]  IN CRA BUT NOT IN DATABASE")
        print("="*80)
        for rec in missing_in_db:
            print(f"  {rec['name']:<30} SIN: {rec['sin']} - ${rec['box_14_employment_income']}")
    
    if missing_in_cra:
        print("\n" + "="*80)
        print("[WARN]  IN DATABASE BUT NOT IN CRA FILE")
        print("="*80)
        for rec in missing_in_cra:
            print(f"  {rec['name']:<30} ${rec['box_14']:>10,.2f}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total Matches:           {len(matches)}")
    print(f"Total Mismatches:        {len(mismatches)}")
    print(f"Missing in Database:     {len(missing_in_db)}")
    print(f"Missing in CRA File:     {len(missing_in_cra)}")
    
    if mismatches:
        total_cra = sum(mm['cra_amount'] for mm in mismatches)
        total_db = sum(mm['db_amount'] for mm in mismatches)
        print(f"\nMismatch Totals:")
        print(f"  CRA Total:     ${total_cra:,.2f}")
        print(f"  DB Total:      ${total_db:,.2f}")
        print(f"  Difference:    ${total_cra - total_db:,.2f}")
    
    return {
        'matches': matches,
        'mismatches': mismatches,
        'missing_in_db': missing_in_db,
        'missing_in_cra': missing_in_cra
    }

if __name__ == '__main__':
    pdf_path = r"L:\limo\pdf\2012\2012 CRA Copy of T4's_ocred.pdf"
    
    print("="*80)
    print("2012 T4 VERIFICATION SCRIPT")
    print("="*80)
    print(f"PDF: {pdf_path}")
    
    # Extract CRA T4 data
    print("\nExtracting T4 data from CRA Copy PDF...")
    cra_records = extract_2012_t4_data(pdf_path)
    
    # Get database T4 data
    print("\nQuerying database for 2012 T4 data...")
    db_records = get_database_t4_data()
    
    # Compare
    results = compare_t4_data(cra_records, db_records)
    
    print("\n" + "="*80)
    print("VERIFICATION COMPLETE")
    print("="*80)
