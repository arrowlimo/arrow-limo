#!/usr/bin/env python3
"""
Extract data from staged PDF files
Processes PDFs by category with specialized extractors
"""
import os
import psycopg2
from pathlib import Path
import pypdf
import re
from datetime import datetime
import json

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF"""
    try:
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            text = ""
            for page in reader.pages:
                try:
                    text += page.extract_text() + "\n"
                except:
                    pass
            return text
    except Exception as e:
        return None

def extract_receipt_data(text, file_name):
    """Extract receipt/invoice data"""
    data = {}
    
    # Extract amounts
    amounts = re.findall(r'\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2})', text)
    if amounts:
        # Take the largest amount as total
        amounts_float = [float(a.replace(',', '')) for a in amounts]
        data['amount'] = max(amounts_float)
    
    # Extract vendor name (first few lines usually contain vendor)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if lines:
        data['vendor'] = lines[0][:100]
    
    # Extract dates
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{2}/\d{2}/\d{4})',
        r'(\w+ \d{1,2},? \d{4})'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            data['date'] = match.group(1)
            break
    
    # Extract invoice number
    inv_match = re.search(r'(?:invoice|inv|receipt)\s*#?\s*[:.]?\s*(\w+)', text, re.IGNORECASE)
    if inv_match:
        data['invoice_number'] = inv_match.group(1)
    
    return data

def extract_payroll_data(text, file_name):
    """Extract payroll data"""
    data = {}
    
    # Extract pay period
    period_match = re.search(r'(?:pay\s+period|period\s+ending)[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text, re.IGNORECASE)
    if period_match:
        data['pay_period'] = period_match.group(1)
    
    # Extract gross pay
    gross_match = re.search(r'gross\s+(?:pay|payroll)[:\s]+\$?(\d{1,3}(?:,\d{3})*\.\d{2})', text, re.IGNORECASE)
    if gross_match:
        data['gross_pay'] = float(gross_match.group(1).replace(',', ''))
    
    # Extract employee count
    emp_match = re.search(r'(?:no\.\s+of\s+employees|employee\s+count)[:\s]+(\d+)', text, re.IGNORECASE)
    if emp_match:
        data['employee_count'] = int(emp_match.group(1))
    
    # Extract employee names (common patterns)
    names = re.findall(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b', text)
    if names:
        data['employees'] = list(set(names))[:20]  # First 20 unique names
    
    return data

def extract_insurance_data(text, file_name):
    """Extract insurance policy data"""
    data = {}
    
    # Extract policy number
    policy_match = re.search(r'policy\s+(?:number|#)[:\s]+(\w+)', text, re.IGNORECASE)
    if policy_match:
        data['policy_number'] = policy_match.group(1)
    
    # Extract effective date
    eff_match = re.search(r'effective\s+date[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text, re.IGNORECASE)
    if eff_match:
        data['effective_date'] = eff_match.group(1)
    
    # Extract premium amount
    premium_match = re.search(r'(?:premium|total)[:\s]+\$?(\d{1,3}(?:,\d{3})*\.\d{2})', text, re.IGNORECASE)
    if premium_match:
        data['premium'] = float(premium_match.group(1).replace(',', ''))
    
    # Extract VIN numbers
    vins = re.findall(r'\b([A-HJ-NPR-Z0-9]{17})\b', text)
    if vins:
        data['vins'] = vins
    
    return data

def extract_banking_data(text, file_name):
    """Extract banking statement data"""
    data = {}
    
    # Extract account number
    account_match = re.search(r'account\s+(?:number|#)[:\s]+(\d+)', text, re.IGNORECASE)
    if account_match:
        data['account_number'] = account_match.group(1)
    
    # Extract statement period
    period_match = re.search(r'statement\s+period[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+to\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text, re.IGNORECASE)
    if period_match:
        data['statement_start'] = period_match.group(1)
        data['statement_end'] = period_match.group(2)
    
    # Extract opening/closing balance
    opening_match = re.search(r'opening\s+balance[:\s]+\$?(\d{1,3}(?:,\d{3})*\.\d{2})', text, re.IGNORECASE)
    if opening_match:
        data['opening_balance'] = float(opening_match.group(1).replace(',', ''))
    
    closing_match = re.search(r'closing\s+balance[:\s]+\$?(\d{1,3}(?:,\d{3})*\.\d{2})', text, re.IGNORECASE)
    if closing_match:
        data['closing_balance'] = float(closing_match.group(1).replace(',', ''))
    
    return data

def extract_vehicle_data(text, file_name):
    """Extract vehicle document data"""
    data = {}
    
    # Extract VIN
    vin_match = re.search(r'VIN[:\s]+([A-HJ-NPR-Z0-9]{17})', text, re.IGNORECASE)
    if vin_match:
        data['vin'] = vin_match.group(1)
    
    # Extract make/model/year
    year_match = re.search(r'\b(20\d{2}|19\d{2})\s+([A-Z][a-z]+)\s+([A-Z][a-z0-9-]+)', text)
    if year_match:
        data['year'] = int(year_match.group(1))
        data['make'] = year_match.group(2)
        data['model'] = year_match.group(3)
    
    # Extract lease/loan information
    lease_match = re.search(r'lease\s+(?:number|#|no\.?)[:\s]+(\w+)', text, re.IGNORECASE)
    if lease_match:
        data['lease_number'] = lease_match.group(1)
    
    return data

def process_pdf(pdf_id, pdf_path, category, conn):
    """Process a single PDF file"""
    try:
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        if not text:
            return False, "Failed to extract text"
        
        # Extract data based on category
        extractors = {
            'receipt': extract_receipt_data,
            'payroll': extract_payroll_data,
            'insurance': extract_insurance_data,
            'banking': extract_banking_data,
            'vehicle': extract_vehicle_data,
        }
        
        extractor = extractors.get(category)
        extracted_data = {}
        
        if extractor:
            extracted_data = extractor(text, Path(pdf_path).name)
        
        # Store extracted text and data
        cur = conn.cursor()
        cur.execute("""
            UPDATE pdf_staging 
            SET status = 'processed',
                processed_at = CURRENT_TIMESTAMP,
                extracted_data = %s,
                processing_notes = %s
            WHERE id = %s
        """, (
            json.dumps(extracted_data),
            f"Extracted {len(text)} chars, {len(extracted_data)} fields",
            pdf_id
        ))
        conn.commit()
        cur.close()
        
        return True, f"Extracted {len(extracted_data)} fields"
        
    except Exception as e:
        return False, str(e)

def main():
    print("="*70)
    print("PDF DATA EXTRACTION")
    print("="*70)
    
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()
    
    # Get pending PDFs
    cur.execute("""
        SELECT id, file_path, category, file_name
        FROM pdf_staging 
        WHERE status = 'pending'
        ORDER BY category, year_detected DESC
        LIMIT 100
    """)
    
    pdfs = cur.fetchall()
    print(f"\n📋 Processing {len(pdfs)} PDFs (batch of 100)...")
    
    if not pdfs:
        print("[OK] No pending PDFs to process")
        cur.close()
        conn.close()
        return
    
    # Process by category
    category_stats = {}
    processed = 0
    failed = 0
    
    for pdf_id, pdf_path, category, file_name in pdfs:
        success, message = process_pdf(pdf_id, pdf_path, category, conn)
        
        if success:
            processed += 1
            category_stats[category] = category_stats.get(category, 0) + 1
            if processed % 10 == 0:
                print(f"  [OK] Processed {processed}/{len(pdfs)}...")
        else:
            failed += 1
            # Update with error
            cur.execute("""
                UPDATE pdf_staging 
                SET status = 'error',
                    processing_notes = %s
                WHERE id = %s
            """, (message, pdf_id))
            conn.commit()
    
    # Summary
    print("\n" + "="*70)
    print("EXTRACTION SUMMARY")
    print("="*70)
    print(f"Total processed: {processed}")
    print(f"Failed: {failed}")
    
    if category_stats:
        print(f"\n📊 By category:")
        for category, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {category:15} {count:5} files")
    
    # Check remaining
    cur.execute("SELECT COUNT(*) FROM pdf_staging WHERE status = 'pending'")
    remaining = cur.fetchone()[0]
    print(f"\n📋 Remaining: {remaining} PDFs")
    
    if remaining > 0:
        print(f"\n🔄 Run again to process next batch:")
        print(f"   python scripts/extract_staged_pdfs.py")
    else:
        print(f"\n[OK] All PDFs processed!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
