"""
Parse fibrenew invoices2.pdf completely and verify against database receipts.
"""
import PyPDF2
import re
import psycopg2
from datetime import datetime

pdf_path = r'L:\limo\pdf\2012\fibrenew invoices2.pdf'

# Extract all text from PDF
with open(pdf_path, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    print(f"\nPDF has {len(pdf.pages)} pages\n")
    
    all_text = ""
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        all_text += text + "\n"

# Parse invoice data
invoice_pattern = re.compile(r'Invoice\s+#(\d+)', re.IGNORECASE)
date_pattern = re.compile(r'(\d{2}/\d{2}/\d{4})')
amount_pattern = re.compile(r'\$?([\d,]+\.\d{2})')

invoices = []
lines = all_text.split('\n')

current_invoice = None
for i, line in enumerate(lines):
    # Look for invoice number
    inv_match = invoice_pattern.search(line)
    if inv_match:
        if current_invoice:
            invoices.append(current_invoice)
        
        invoice_num = inv_match.group(1)
        current_invoice = {
            'invoice_number': invoice_num,
            'date': None,
            'amount': None,
            'description': line
        }
    
    # Look for dates
    if current_invoice and not current_invoice['date']:
        date_match = date_pattern.search(line)
        if date_match:
            date_str = date_match.group(1)
            try:
                current_invoice['date'] = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
            except:
                pass
    
    # Look for total amounts (lines with "Total" or amounts after GST)
    if current_invoice and 'Total' in line:
        amounts = amount_pattern.findall(line)
        if amounts:
            # Last amount on "Total" line is usually the total
            amount_str = amounts[-1].replace(',', '')
            try:
                current_invoice['amount'] = float(amount_str)
            except:
                pass

# Add last invoice
if current_invoice:
    invoices.append(current_invoice)

print(f"=== Parsed {len(invoices)} invoices from PDF ===\n")

for inv in invoices:
    print(f"Invoice #{inv['invoice_number']} | {inv['date']} | ${inv['amount']:,.2f if inv['amount'] else 0:.2f}")
    print(f"  {inv['description'][:80]}")
    print()

# Now check against database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\n=== Verifying against database ===\n")

for inv in invoices:
    invoice_num = inv['invoice_number']
    date = inv['date']
    amount = inv['amount']
    
    # Search for this invoice in database
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, description, category
        FROM receipts
        WHERE vendor_name ILIKE '%fibrenew%'
        AND (description ILIKE %s OR description ILIKE %s)
    """, (f'%{invoice_num}%', f'%Invoice #{invoice_num}%'))
    
    matches = cur.fetchall()
    
    if matches:
        print(f"✅ Invoice #{invoice_num} - FOUND in database:")
        for m in matches:
            print(f"   Receipt {m[0]} | {m[1]} | ${m[2]:,.2f} | {m[4]}")
            print(f"   {m[3][:70]}")
    else:
        print(f"❌ Invoice #{invoice_num} - NOT FOUND in database")
        print(f"   PDF shows: {date} | ${amount:,.2f if amount else 0}")
        
        # Check if we have a receipt for that date/amount
        if date and amount:
            cur.execute("""
                SELECT receipt_id, receipt_date, gross_amount, description
                FROM receipts
                WHERE vendor_name ILIKE '%fibrenew%'
                AND receipt_date = %s
                AND ABS(gross_amount - %s) < 0.01
            """, (date, amount))
            
            date_amount_matches = cur.fetchall()
            if date_amount_matches:
                print(f"   ⚠️  Found receipt with matching date/amount but no invoice# in description:")
                for m in date_amount_matches:
                    print(f"      Receipt {m[0]} | {m[3][:60]}")
    print()

cur.close()
conn.close()

print("\n=== Summary ===")
print(f"Total invoices in PDF: {len(invoices)}")
print(f"\nInvoice numbers found: {', '.join([inv['invoice_number'] for inv in invoices])}")
