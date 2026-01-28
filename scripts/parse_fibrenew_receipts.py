"""
Parse Fibrenew receipt PDFs and extract financial data.
"""
import pdfplumber
import re
from datetime import datetime
from pathlib import Path
import os

# Set environment for UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

def extract_receipt_data(pdf_path):
    """Extract data from a single Fibrenew receipt PDF."""
    data = {
        'filename': Path(pdf_path).name,
        'date': None,
        'invoice_number': None,
        'amount': None,
        'gst': None,
        'total': None,
        'description': None,
        'raw_text': []
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    data['raw_text'].append(text)
                    
                    # Extract date patterns
                    date_patterns = [
                        r'Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                        r'(\w+ \d{1,2},? \d{4})',
                    ]
                    for pattern in date_patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match and not data['date']:
                            data['date'] = match.group(1)
                    
                    # Extract invoice/receipt number
                    invoice_patterns = [
                        r'Invoice\s*#?\s*[:\s]*(\d+)',
                        r'Receipt\s*#?\s*[:\s]*(\d+)',
                        r'#\s*(\d{4,})',
                    ]
                    for pattern in invoice_patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match and not data['invoice_number']:
                            data['invoice_number'] = match.group(1)
                    
                    # Extract amounts (look for GST, subtotal, total)
                    amount_patterns = [
                        r'GST[:\s]+\$?\s*([\d,]+\.\d{2})',
                        r'Sub[\s-]*total[:\s]+\$?\s*([\d,]+\.\d{2})',
                        r'Total[:\s]+\$?\s*([\d,]+\.\d{2})',
                        r'\$\s*([\d,]+\.\d{2})',
                    ]
                    
                    # Try to find GST
                    gst_match = re.search(r'GST[:\s]+\$?\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
                    if gst_match:
                        data['gst'] = float(gst_match.group(1).replace(',', ''))
                    
                    # Try to find subtotal
                    subtotal_match = re.search(r'Sub[\s-]*total[:\s]+\$?\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
                    if subtotal_match:
                        data['amount'] = float(subtotal_match.group(1).replace(',', ''))
                    
                    # Try to find total
                    total_match = re.search(r'Total[:\s]+\$?\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
                    if total_match:
                        data['total'] = float(total_match.group(1).replace(',', ''))
                    
                    # Extract description (look for common patterns)
                    desc_patterns = [
                        r'Description[:\s]+(.+?)(?:\n|$)',
                        r'Services[:\s]+(.+?)(?:\n|$)',
                        r'For[:\s]+(.+?)(?:\n|$)',
                    ]
                    for pattern in desc_patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match and not data['description']:
                            data['description'] = match.group(1).strip()
    
    except Exception as e:
        data['error'] = str(e)
    
    return data

def main():
    # List of PDF files to parse
    pdf_files = [
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(20).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(21).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(22).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta.pdf",
        r"L:\limo\audit_records\fibrenew\shawns wedding .pdf",
        r"L:\limo\audit_records\fibrenew\Statement from Fibrenew Central Alberta.pdf",
        r"L:\limo\audit_records\fibrenew\Payment Receipt from Fibrenew Central Alberta.pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(1).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(2).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(3).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(4).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(5).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(6).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(7).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(8).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(9).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(10).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(11).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(12).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(13).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(14).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(15).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(16).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(17).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(18).pdf",
        r"L:\limo\audit_records\fibrenew\Receipt from Fibrenew Central Alberta(19).pdf",
    ]
    
    print("=" * 80)
    print("FIBRENEW RECEIPT PARSING")
    print("=" * 80)
    print()
    
    receipts = []
    total_amount = 0
    total_gst = 0
    
    for pdf_path in pdf_files:
        if not Path(pdf_path).exists():
            print(f"⚠️  File not found: {Path(pdf_path).name}")
            continue
        
        print(f"Parsing: {Path(pdf_path).name}")
        data = extract_receipt_data(pdf_path)
        receipts.append(data)
        
        # Print summary
        print(f"  Date: {data['date'] or 'NOT FOUND'}")
        print(f"  Invoice#: {data['invoice_number'] or 'NOT FOUND'}")
        print(f"  Amount: ${data['amount']:.2f}" if data['amount'] else "  Amount: NOT FOUND")
        print(f"  GST: ${data['gst']:.2f}" if data['gst'] else "  GST: NOT FOUND")
        print(f"  Total: ${data['total']:.2f}" if data['total'] else "  Total: NOT FOUND")
        if data['description']:
            print(f"  Description: {data['description'][:60]}...")
        
        if 'error' in data:
            print(f"  ❌ Error: {data['error']}")
        
        print()
        
        # Accumulate totals
        if data['total']:
            total_amount += data['total']
        if data['gst']:
            total_gst += data['gst']
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total receipts processed: {len(receipts)}")
    print(f"Total amount: ${total_amount:,.2f}")
    print(f"Total GST: ${total_gst:,.2f}")
    print()
    
    # Show raw text from first few receipts for inspection
    print("=" * 80)
    print("RAW TEXT SAMPLES (First 3 receipts)")
    print("=" * 80)
    for i, receipt in enumerate(receipts[:3], 1):
        print(f"\n--- Receipt {i}: {receipt['filename']} ---")
        if receipt['raw_text']:
            full_text = '\n'.join(receipt['raw_text'])
            print(full_text[:800])  # First 800 chars
            if len(full_text) > 800:
                print("... [truncated]")
        print()

if __name__ == '__main__':
    main()
