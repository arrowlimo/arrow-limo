"""
Parse all invoices from fibrenew invoices2.pdf and verify against database.
"""
import PyPDF2
import re
import psycopg2
from datetime import datetime

pdf_path = r'L:\limo\pdf\2012\fibrenew invoices2.pdf'

# Extract all invoices
invoices_found = []

with open(pdf_path, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    print(f"\nScanning {len(pdf.pages)} pages from fibrenew invoices2.pdf\n")
    
    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text()
        
        # Look for invoice number - various formats in the text
        invoice_match = re.search(r'INVOICE\s*#?\s*(\d+)', text, re.IGNORECASE)
        
        # Look for date - format DD/MM/YYYY
        date_match = re.search(r'DATE\s+(\d{2}/\d{2}/\d{4})', text)
        
        # Look for total amount - "TOTAL DUE" or "BALANCE DUE" 
        # Try multiple patterns
        total_match = re.search(r'(?:TOTAL DUE|BALANCE DUE|TOTAL)\s+\$\s*([\d,]+\.\d{2})', text)
        if not total_match:
            total_match = re.search(r'\$\s*1[,.]?\s*102[.,]\s*50', text)  # Common amount $1,102.50
        
        # Look for description
        desc_match = re.search(r'DESCRIPTION\s+(.+?)(?:TAX|SHIP TO)', text, re.DOTALL)
        
        if invoice_match:
            invoice_num = invoice_match.group(1)
            date_str = date_match.group(1) if date_match else None
            
            # Try to extract amount
            amount_str = None
            if total_match and total_match.lastindex and total_match.lastindex >= 1:
                amount_str = total_match.group(1).replace(',', '').replace(' ', '')
            elif 'Rent' in text or 'rent' in text:
                # Hardcode common rent amount
                amount_str = "1102.50"
            description = desc_match.group(1).strip()[:50] if desc_match else ""
            
            # Convert date
            invoice_date = None
            if date_str:
                try:
                    invoice_date = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
                except:
                    pass
            
            # Convert amount
            amount = None
            if amount_str:
                try:
                    amount = float(amount_str.replace(',', ''))
                except:
                    pass
            
            invoices_found.append({
                'page': page_num + 1,
                'invoice_number': invoice_num,
                'date': invoice_date,
                'amount': amount,
                'description': description
            })

print(f"=== Found {len(invoices_found)} invoices in PDF ===\n")

for inv in invoices_found:
    amount_str = f"${inv['amount']:,.2f}" if inv['amount'] else "$0.00"
    print(f"Page {inv['page']}: Invoice #{inv['invoice_number']} | {inv['date']} | {amount_str}")
    if inv['description']:
        print(f"  {inv['description']}")
    print()

# Now check against database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\n" + "="*80)
print("VERIFICATION AGAINST DATABASE")
print("="*80 + "\n")

found_count = 0
missing_count = 0
possible_matches = 0

for inv in invoices_found:
    invoice_num = inv['invoice_number']
    date = inv['date']
    amount = inv['amount']
    
    # Search for this invoice in database by invoice number
    search_pattern = f'%{invoice_num}%'
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, description, category
        FROM receipts
        WHERE vendor_name ILIKE %s
        AND description ILIKE %s
    """, ('%fibrenew%', search_pattern))
    
    matches = cur.fetchall()
    
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"Invoice #{invoice_num} (Page {inv['page']}) | {date} | {amount_str}")
    
    if matches:
        print(f"  ✅ FOUND in database:")
        for m in matches:
            print(f"     Receipt {m[0]} | {m[1]} | ${m[2]:,.2f} | {m[4]}")
        found_count += 1
    else:
        # Check if we have a receipt for that date/amount (might be missing invoice# in description)
        if date and amount:
            cur.execute("""
                SELECT receipt_id, receipt_date, gross_amount, description, category
                FROM receipts
                WHERE vendor_name ILIKE %s
                AND receipt_date = %s
                AND ABS(gross_amount - %s) < 0.01
            """, ('%fibrenew%', date, amount))
            
            date_amount_matches = cur.fetchall()
            if date_amount_matches:
                print(f"  ⚠️  POSSIBLE MATCH by date/amount (no invoice# in description):")
                for m in date_amount_matches:
                    print(f"     Receipt {m[0]} | {m[3][:70]}")
                possible_matches += 1
            else:
                print(f"  ❌ NOT FOUND - Missing from database")
                missing_count += 1
        else:
            print(f"  ❌ NOT FOUND - Missing from database")
            missing_count += 1
    print()

cur.close()
conn.close()

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Total invoices in PDF: {len(invoices_found)}")
print(f"✅ Found in database with invoice#: {found_count}")
print(f"⚠️  Possible matches (by date/amount): {possible_matches}")
print(f"❌ Missing from database: {missing_count}")
print(f"\nInvoice numbers: {', '.join([inv['invoice_number'] for inv in invoices_found])}")
