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
    """
    t4_records = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                # Split into lines
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                
                # Look for patterns:
                # - Year (2013, 2014, etc.)
                # - SIN (9 digits, may have spaces)
                # - Name (uppercase, after SIN)
                # - Address
                # - Box 14 (employment income)
                
                i = 0
                while i < len(lines):
                    line = lines[i]
                    
                    # Look for year
                    year_match = re.search(r'\b(20\d{2})\b', line)
                    if year_match:
                        year = year_match.group(1)
                        
                        # Look ahead for SIN (3 digits, 3 digits, 3 digits pattern)
                        sin = None
                        name = None
                        box_14 = None
                        
                        for j in range(i, min(i+20, len(lines))):
                            check_line = lines[j]
                            
                            # SIN pattern: 3 groups of 3 digits
                            sin_match = re.search(r'\b(\d{3})\s*(\d{3})\s*(\d{3})\b', check_line)
                            if sin_match and not sin:
                                sin = ''.join(sin_match.groups())
                            
                            # Name: all caps line after SIN
                            if sin and not name and re.match(r'^[A-Z\s\-\.]+$', check_line) and len(check_line) > 3:
                                # Skip if it's an address or company name
                                if 'ARROW' not in check_line and 'CRESCENT' not in check_line and 'RED DEER' not in check_line:
                                    name = check_line.strip()
                            
                            # Box 14 (employment income): look for pattern like "14" followed by amount
                            # Or just a dollar amount after name
                            amount_match = re.search(r'(\d{1,3}(?:,?\d{3})*\.\d{2})', check_line)
                            if amount_match and name and not box_14:
                                box_14 = amount_match.group(1).replace(',', '')
                        
                        if sin and name and box_14:
                            t4_records.append({
                                'year': year,
                                'sin': sin,
                                'name': name,
                                'box_14_employment_income': box_14
                            })
                            print(f"Found: {year} - {name} (SIN: {sin}) - Box 14: ${box_14}")
                    
                    i += 1
    
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
    
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
    for t4_file in t4_files:
        if os.path.exists(t4_file):
            print(f"\nProcessing: {t4_file}")
            records = extract_t4_data(t4_file)
            insert_t4_records(records, t4_file)
        else:
            print(f"File not found: {t4_file}")

if __name__ == '__main__':
    main()
