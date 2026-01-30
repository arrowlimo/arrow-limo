import os
import re
import pdfplumber
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def extract_t4_data(pdf_path):
    """
    Extract T4 data: name, SIN, year, and box amounts (especially box 14 - employment income)
    
    Format observed:
    Arrow Limousine & Sedan Services Ltd.
    2013
    70 Rupert Crescent
    Red Deer, AB, AB T4P 2Z1
    6227.90 410.65
    AB 207.22 6227.90
    492 717 913
    6227.90
    117.09
    BOULLEY Kevin
    276 Wiley Crescent
    """
    t4_records = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            
            if not full_text:
                return t4_records
            
            # Split by "Arrow Limousine" to separate individual T4s
            t4_sections = re.split(r'Arrow Limousine & Sedan Services Ltd\.', full_text)
            
            for section in t4_sections:
                if not section.strip():
                    continue
                
                lines = [l.strip() for l in section.split('\n') if l.strip()]
                if len(lines) < 5:
                    continue
                
                year = None
                sin = None
                name = None
                box_14 = None
                
                # Parse each section
                for i, line in enumerate(lines):
                    # Year
                    if not year and re.match(r'^20\d{2}$', line):
                        year = line
                    
                    # SIN: line with 3 groups of 3 digits
                    if not sin:
                        sin_match = re.search(r'\b(\d{3})\s+(\d{3})\s+(\d{3})\b', line)
                        if sin_match:
                            sin = ''.join(sin_match.groups())
                    
                    # Name: all caps, contains letters and spaces, not an address
                    if not name and re.match(r'^[A-Z][A-Z\s\-\.]+$', line) and len(line) > 5:
                        # Skip company name, city names, provinces
                        if ('ARROW' not in line and 'SERVICES' not in line and 
                            'RED DEER' not in line and 'CRESCENT' not in line and
                            'AVENUE' not in line and line not in ['AB', 'BC', 'ON']):
                            name = line.strip()
                    
                    # Box 14: first large dollar amount (after SIN, before name usually)
                    # Look for amounts > 100 and < 999999
                    if not box_14:
                        amount_matches = re.findall(r'\b(\d{1,3}(?:,?\d{3})*\.\d{2})\b', line)
                        for amount_str in amount_matches:
                            amount_val = float(amount_str.replace(',', ''))
                            if 100.0 <= amount_val <= 999999.0:
                                box_14 = amount_str.replace(',', '')
                                break
                
                # If we found all required fields, add record
                if year and sin and name and box_14:
                    t4_records.append({
                        'year': year,
                        'sin': sin,
                        'name': name,
                        'box_14_employment_income': box_14
                    })
                    print(f"Found: {year} - {name} (SIN: {sin}) - Box 14: ${box_14}")
    
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        import traceback
        traceback.print_exc()
    
    return t4_records

def create_t4_table():
    """Create a table to store T4 validation data"""
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staging_t4_validation (
            id SERIAL PRIMARY KEY,
            year INTEGER,
            sin VARCHAR(20),
            employee_name VARCHAR(255),
            box_14_employment_income NUMERIC(10, 2),
            source_file VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Created staging_t4_validation table")

def insert_t4_records(records, source_file):
    """Insert T4 records into the staging table"""
    if not records:
        print(f"No records extracted from {source_file}")
        return
    
    conn = connect_db()
    cur = conn.cursor()
    
    for rec in records:
        cur.execute("""
            INSERT INTO staging_t4_validation 
            (year, sin, employee_name, box_14_employment_income, source_file)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            rec['year'],
            rec['sin'],
            rec['name'],
            float(rec['box_14_employment_income']),
            source_file
        ))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(records)} T4 records from {source_file}")

def main():
    # T4 files to process
    t4_files = [
        r"L:\limo\quickbooks\New folder\2013 Arrow Limousine & Sedan Ltd. T4 Slips-CRA Copy.pdf",
        r"L:\limo\quickbooks\New folder\2013 T4 Slips - Arrow Employees.pdf",
        r"L:\limo\quickbooks\New folder\2013 T4 Slips Arrow Office File Copy.pdf",
    ]
    
    # Create table
    create_t4_table()
    
    # Process each file
    all_records = []
    for t4_file in t4_files:
        if os.path.exists(t4_file):
            print(f"\n{'='*80}")
            print(f"Processing: {t4_file}")
            print('='*80)
            records = extract_t4_data(t4_file)
            if records:
                insert_t4_records(records, t4_file)
                all_records.extend(records)
        else:
            print(f"File not found: {t4_file}")
    
    print(f"\n{'='*80}")
    print(f"Total T4 records extracted: {len(all_records)}")
    print('='*80)

if __name__ == '__main__':
    main()
