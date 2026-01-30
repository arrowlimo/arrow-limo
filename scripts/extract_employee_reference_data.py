import os
import re
import pdfplumber
import psycopg2
from datetime import datetime

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def create_employee_info_table():
    """Create staging table for employee reference data"""
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staging_employee_reference_data (
            id SERIAL PRIMARY KEY,
            employee_id VARCHAR(20),
            employee_name VARCHAR(255),
            hire_date DATE,
            sin VARCHAR(20),
            birth_date DATE,
            additional_amount NUMERIC(10, 2),
            main_phone VARCHAR(50),
            street1 VARCHAR(255),
            city VARCHAR(100),
            postal_code VARCHAR(20),
            source_file VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Created staging_employee_reference_data table")

def parse_employee_info(pdf_path):
    """Extract employee reference data from PDF"""
    employees = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                for line in lines:
                    # Look for lines starting with employee ID pattern (e.g., AD100, Dr03, H02, Of03)
                    match = re.match(r'^([A-Z][a-z]\d+|[A-Z]+\d+)\s+(.+)', line)
                    if match:
                        emp_id = match.group(1)
                        rest = match.group(2).strip()
                        
                        # Parse the rest of the line
                        # Format: Name HireDate SIN BirthDate Amount Phone Address City PostalCode
                        parts = rest.split()
                        
                        if len(parts) < 5:
                            continue
                        
                        # Extract name (first 2-3 parts before date)
                        name_parts = []
                        i = 0
                        while i < len(parts) and not re.match(r'^\d{2}/\d{2}/\d{4}$', parts[i]):
                            name_parts.append(parts[i])
                            i += 1
                        
                        if i >= len(parts):
                            continue
                        
                        name = ' '.join(name_parts)
                        
                        # Hire date
                        hire_date = parts[i] if i < len(parts) else None
                        i += 1
                        
                        # SIN (3 groups of digits)
                        sin = None
                        if i + 2 < len(parts) and parts[i].isdigit() and parts[i+1].isdigit() and parts[i+2].isdigit():
                            sin = f"{parts[i]} {parts[i+1]} {parts[i+2]}"
                            i += 3
                        
                        # Birth date
                        birth_date = parts[i] if i < len(parts) and re.match(r'^\d{2}/\d{2}/\d{4}$', parts[i]) else None
                        if birth_date:
                            i += 1
                        
                        # Additional amount
                        additional_amount = None
                        if i < len(parts) and re.match(r'^\d+\.\d{2}$', parts[i]):
                            additional_amount = parts[i]
                            i += 1
                        
                        # Phone
                        phone = None
                        if i < len(parts) and re.match(r'^\d{3}-\d{3}-\d{4}$', parts[i]):
                            phone = parts[i]
                            i += 1
                        
                        # Address (rest of parts before City and Postal)
                        address_parts = []
                        city = None
                        postal = None
                        
                        # Last part is postal code (format: T4P 2Z1)
                        if len(parts) >= i + 2:
                            postal = f"{parts[-2]} {parts[-1]}"
                            city_idx = len(parts) - 2
                            
                            # Second to last is city (Red Deer, Lacombe, etc.)
                            if city_idx > i:
                                # City might be 2 words (Red Deer)
                                if parts[city_idx - 1] in ['Red', 'Red']:
                                    city = f"{parts[city_idx - 2]} {parts[city_idx - 1]}"
                                    address_parts = parts[i:city_idx - 2]
                                else:
                                    city = parts[city_idx - 1]
                                    address_parts = parts[i:city_idx - 1]
                        
                        address = ' '.join(address_parts) if address_parts else None
                        
                        employees.append({
                            'employee_id': emp_id,
                            'name': name,
                            'hire_date': hire_date,
                            'sin': sin,
                            'birth_date': birth_date,
                            'additional_amount': additional_amount,
                            'phone': phone,
                            'address': address,
                            'city': city,
                            'postal': postal
                        })
                        
                        print(f"Parsed: {emp_id} - {name} - SIN: {sin} - DOB: {birth_date}")
    
    except Exception as e:
        print(f"Error parsing {pdf_path}: {e}")
        import traceback
        traceback.print_exc()
    
    return employees

def insert_employee_info(employees, source_file):
    """Insert employee reference data into staging table"""
    if not employees:
        print("No employees parsed")
        return
    
    conn = connect_db()
    cur = conn.cursor()
    
    for emp in employees:
        # Convert dates
        hire_date = None
        if emp['hire_date']:
            try:
                hire_date = datetime.strptime(emp['hire_date'], '%m/%d/%Y').date()
            except:
                pass
        
        birth_date = None
        if emp['birth_date']:
            try:
                birth_date = datetime.strptime(emp['birth_date'], '%m/%d/%Y').date()
            except:
                pass
        
        additional_amount = float(emp['additional_amount']) if emp['additional_amount'] else None
        
        cur.execute("""
            INSERT INTO staging_employee_reference_data 
            (employee_id, employee_name, hire_date, sin, birth_date, additional_amount, 
             main_phone, street1, city, postal_code, source_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            emp['employee_id'],
            emp['name'],
            hire_date,
            emp['sin'],
            birth_date,
            additional_amount,
            emp['phone'],
            emp['address'],
            emp['city'],
            emp['postal'],
            source_file
        ))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(employees)} employee records")

def main():
    pdf_path = r"L:\limo\quickbooks\New folder\Arror Current Employee Info 01-02-14.pdf"
    
    # Create table
    create_employee_info_table()
    
    # Parse and insert
    employees = parse_employee_info(pdf_path)
    insert_employee_info(employees, pdf_path)
    
    # Mark as excluded in driver pay files
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE staging_driver_pay_files
        SET status = 'excluded', 
            error_message = 'Reference data: employee information (SIN, DOB, contact info) - extracted to staging_employee_reference_data'
        WHERE file_path = %s
    """, (pdf_path,))
    conn.commit()
    cur.close()
    conn.close()
    print(f"\nMarked file as excluded in staging_driver_pay_files")

if __name__ == '__main__':
    main()
