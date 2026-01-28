import os
import re
import pdfplumber
import psycopg2
from datetime import datetime

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def parse_clean_payroll_contact_list(pdf_path):
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.split('\n'):
                # Expect rows like: Active ???  Dr05  Name   03/01/2007   01/31/2012   609 046 735   #346  5344  76 Street   Red Deer  AB  T4P 2A6
                m = re.match(r'^(Active.*?|Inactive.*?)\s+([A-Za-z]{1,3}\d{1,3})\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\d{3}\s\d{3}\s\d{3})\s+(.+?)\s+([A-Za-z\s]+?)\s+AB\s+([A-Z]\d[A-Z]\s?\d[A-Z]\d)\s*$', line)
                if m:
                    status = m.group(1)
                    emp_no = m.group(2)
                    name = m.group(3).strip()
                    hire_date = m.group(4)
                    last_cheque = m.group(5)
                    sin = m.group(6)
                    street1 = m.group(7).strip()
                    city = m.group(8).strip()
                    postal = m.group(9).replace(' ', '')
                    records.append({
                        'status': status,
                        'emp_no': emp_no,
                        'name': name,
                        'hire_date': hire_date,
                        'last_cheque': last_cheque,
                        'sin': sin,
                        'street1': street1,
                        'city': city,
                        'postal': postal
                    })
    return records

def upsert_employee_reference(records, source_file):
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
            status VARCHAR(50),
            last_cheque_date DATE,
            source_file VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    for r in records:
        cur.execute("""
            INSERT INTO staging_employee_reference_data (
                employee_id, employee_name, hire_date, sin, street1, city, postal_code, status, last_cheque_date, source_file
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            r['emp_no'], r['name'], datetime.strptime(r['hire_date'], '%m/%d/%Y'), r['sin'], r['street1'], r['city'], r['postal'], r['status'], datetime.strptime(r['last_cheque'], '%m/%d/%Y'), source_file
        ))
    conn.commit()
    cur.close()
    conn.close()


def main():
    pdf_path = r"L:\limo\quickbooks\New folder\Clean%20Payroll%20UP.pdf".replace('%20', ' ')
    records = parse_clean_payroll_contact_list(pdf_path)
    print(f"Parsed {len(records)} employee rows from contact list")
    upsert_employee_reference(records, pdf_path)
    
    # Exclude from pay ingestion
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE staging_driver_pay_files
        SET status = 'excluded', error_message = 'Reference data: Employee Contact List (hire date, last cheque, SIN, address) extracted.'
        WHERE file_path = %s
    """, (pdf_path,))
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
