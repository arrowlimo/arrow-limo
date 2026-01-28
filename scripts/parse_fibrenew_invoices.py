#!/usr/bin/env python3
"""
Parse Fibrenew invoice data from Excel/CSV attachment.

Data structure from attachment:
- Column 1: Invoice number (4318, 4401, 4436, etc.)
- Column 2: Date (24/01/2012, 01/04/2012, etc.)
- Column 3: Amount ($1,050.00, $1,207.50, etc.) - some with notes in same column
- Column 4: Additional notes (payment info, dates)

Output: Structured invoice list with invoice_number, invoice_date, amount, notes.
Ready for database import or further processing.
"""

import re
from datetime import datetime
from decimal import Decimal

# Raw data from attachment (invoice_num, date_str, amount_str, notes)
FIBRENEW_INVOICES = [
    ('4318', '24/01/2012', '$1,050.00', ''),
    ('4401', '01/04/2012', '$1,050.00', ''),
    ('4436', '01/05/2012', '$1,050.00', ''),
    ('4439', '28/02/2012', '$1,050.00', ''),
    ('4560', '12/06/2012', '$1,050.00', ''),
    ('4654', '03/08/2012', '$1,207.50', ''),
    ('4686', '21/09/2012', '$1,445.62', 'paid 1445.62 10/22/2012'),
    ('4702', '04/09/2012', '$1,163.75', ''),
    ('4703', '04/09/2012', '$170.43', ''),
    ('4788', '31/10/2012', '$183.84', ''),
    ('4839', '30/11/2012', '$1,403.27', 'paid 1300.00 mar 5 2013'),
    ('4841', '01/11/2012', '$1,268.48', ''),
    ('4853', '06/11/2012', '$1,268.48', ''),
    ('4887', '31/12/2012', '$1,450.96', ''),
    ('4916', '31/01/2013', '$1,492.12', 'mar 26 paid 445.77'),
    ('4938', '06/02/2013', '-$243.74', ''),  # Credit note
    ('4956', '28/02/2013', '$1,575.00', ''),
    ('4960', '31/03/2013', '-$242.69', ''),  # Credit note
    ('4985', '31/03/2013', '$1,575.00', ''),
    ('4996', '30/04/2013', '$1,575.00', ''),
    ('4996', '30/04/2013', '$185.57', ''),
    ('5028', '30/04/2013', '$1,575.00', ''),
    ('5032', '31/05/2013', '-$377.08', ''),  # Credit note
    ('5049', '01/06/2013', '$1,575.00', 'paid cheque 217'),
    ('5055', '01/06/2013', '-$200.43', ''),  # Credit note
    ('5087', '02/07/2013', '$1,575.00', ''),
    ('5090', '31/07/2013', '-$196.14', ''),  # Credit note
    ('5118', '31/07/2013', '$1,575.00', ''),
    ('5144', '31/08/2013', '$1,575.00', ''),
    ('5145', '30/08/2013', '-$232.90', ''),  # Credit note
    ('5177', '31/08/2013', '$255.63', ''),
    ('5202', '01/10/2013', '$1,575.00', ''),
    ('5205', '31/10/2013', '-$270.15', ''),  # Credit note
    ('5259', '01/11/2013', '$1,706.25', ''),
    ('5274', '30/11/2013', '-$222.11', ''),  # Credit note
    ('5286', '30/11/2013', '$1,706.25', 'paid cheque 288 dec 22'),
    ('5292', '01/01/2014', '$2,552.83', ''),
    ('5327', '06/01/2014', '$1,706.25', ''),
    ('5344', '01/02/2014', '$1,706.25', ''),
    ('5387', '31/03/2014', '$260.32', ''),
    ('5415', '01/04/2014', '$1,706.25', ''),
    ('5416', '30/04/2014', '$268.33', ''),
    ('5466', '01/05/2014', '$1,706.25', 'Final payment 280.83 02/10/2014'),
    ('5467', '31/05/2014', '$238.42', 'payment 238.42 02/10/2014'),
    ('5500', '31/05/2014', '$1,706.25', 'paid 21/10/2014 paid 480.75 02/10/2014'),
    ('5509', '30/06/2014', '$268.70', 'paid 21/10/2014'),
    ('5550', '31/05/2014', '', 'payment 480.75 03/09/2014'),
    ('5553', '02/07/2017', '$1,706.25', 'paid by cash'),  # Note: 2017 date in 2014 sequence
    ('5570', '31/07/2014', '$261.89', 'paid 21/10/2014'),
    ('5616', '12/08/2014', '$1,706.25', 'paid 03/11/2014 and paid 21/10/2014. 1245.91'),
    ('5640', '30/08/2014', '$201.30', ''),
    ('5646', '01/09/2014', '$1,706.25', 'paid 22/12/2014'),
    ('5646', '01/09/2014', '$1,706.25', 'payment 1288.36'),
    ('5681', '29/09/2014', '$201.95', 'paid 22/12/2014'),
    ('5692', '01/10/2014', '$1,706.25', 'payment 1380.16 22/12/2014'),
    ('5709', '31/10/2014', '$256.28', 'payment 256.28 27/01/2015'),
    ('5732', '01/11/2014', '$1,706.25', 'pmt 1117.63'),
    ('5760', '01/11/2014', '$256.75', ''),
    ('5767', '01/12/2014', '$1,706.25', 'pmt 1706.25'),
    ('5797', '31/12/2014', '$259.49', 'pmt 154.6'),
    ('5802', '08/01/2015', '$1,706.25', ''),
    ('5843', '28/02/2015', '$195.87', ''),
    ('5860', '28/02/2015', '$957.69', 'pmt 748.65'),
    ('5910', '31/03/2015', '$1,706.25', ''),
    ('5977', '04/04/2015', '', '09/08/2015 383.84 on 5977'),
    ('5977', '04/05/2015', '$1,706.25', ''),
    ('5978', '04/05/2015', '$144.13', ''),
    ('5987', '04/04/2015', '', '09/08/2015'),
    ('6030', '06/01/2015', '$1,706.25', '1706.25 pmt 09/08/2015'),
    ('6031', '06/01/2015', '$141.30', '141.3pmt 09/08/2015'),
    ('6087', '07/06/2015', '', '09/08/2015'),
    ('6087', '06/07/2015', '$1,779.75', ''),
    ('6088', '07/06/2015', '$140.61', ''),
    ('6088', '06/07/2015', '$140.61', ''),
    ('6119', '07/22/2015', '$158.92', ''),
    ('6128', '08/01/2015', '$1,706.25', ''),
    ('6177', '08/26/2015', '$200.64', ''),
    ('6177', '08/26/2015', '$200.64', ''),
    ('6185', '09/01/2015', '$1,706.25', ''),
    ('6185', '09/01/2015', '$1,706.25', ''),
    ('6231', '10/01/2015', '$1,706.25', ''),
    ('6231', '10/01/2015', '$1,706.25', ''),
    ('6232', '09/30/2015', '$128.74', ''),
    ('6232', '09/30/2015', '$128.47', ''),
    ('6275', '10/26/2015', '$208.09', ''),
    ('6275', '10/26/2015', '$208.09', ''),
    ('6297', '11/01/2015', '$1,706.25', ''),
    ('6331', '11/23/2015', '$177.40', ''),
    ('6374', '12/01/2015', '1706.25', ''),  # Missing $ sign
]

def parse_amount(amount_str):
    """Parse amount string, handling negative values and missing amounts."""
    if not amount_str or amount_str.strip() == '':
        return None
    
    # Remove currency symbols and commas
    clean = amount_str.replace('$', '').replace(',', '').strip()
    
    # Handle negative values
    if clean.startswith('-'):
        return -Decimal(clean[1:])
    
    try:
        return Decimal(clean)
    except:
        return None

def parse_date(date_str):
    """Parse date in DD/MM/YYYY or MM/DD/YYYY format."""
    if not date_str or date_str.strip() == '':
        return None
    
    # Try DD/MM/YYYY first (European format - likely for Fibrenew Canada)
    for fmt in ['%d/%m/%Y', '%m/%d/%Y']:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except:
            continue
    
    return None

def extract_payment_info(notes):
    """Extract payment dates and amounts from notes column."""
    if not notes:
        return []
    
    payments = []
    
    # Pattern: "paid 1445.62 10/22/2012" or "payment 238.42 02/10/2014"
    payment_pattern = r'(?:paid|payment|pmt)\s+(\d+\.?\d*)\s*(\d{1,2}/\d{1,2}/\d{4})?'
    
    matches = re.finditer(payment_pattern, notes.lower())
    for match in matches:
        amount_str = match.group(1)
        date_str = match.group(2) if match.group(2) else None
        
        payment = {
            'amount': parse_amount(amount_str),
            'date': parse_date(date_str) if date_str else None
        }
        payments.append(payment)
    
    return payments

def main():
    print("="*80)
    print("FIBRENEW INVOICE PARSER")
    print("="*80)
    
    invoices = []
    total_invoices = Decimal('0')
    total_credits = Decimal('0')
    payment_info_count = 0
    
    for inv_num, date_str, amount_str, notes in FIBRENEW_INVOICES:
        inv_date = parse_date(date_str)
        amount = parse_amount(amount_str)
        payments = extract_payment_info(notes)
        
        invoice = {
            'invoice_number': inv_num,
            'invoice_date': inv_date,
            'amount': amount,
            'notes': notes.strip(),
            'payments': payments
        }
        
        invoices.append(invoice)
        
        if amount:
            if amount < 0:
                total_credits += abs(amount)
            else:
                total_invoices += amount
        
        if payments:
            payment_info_count += 1
    
    # Summary
    print(f"\nTotal invoices parsed: {len(invoices)}")
    print(f"Date range: {min(i['invoice_date'] for i in invoices if i['invoice_date'])} to {max(i['invoice_date'] for i in invoices if i['invoice_date'])}")
    print(f"\nTotal invoice amount: ${total_invoices:,.2f}")
    print(f"Total credit notes: ${total_credits:,.2f}")
    print(f"Net amount: ${total_invoices - total_credits:,.2f}")
    print(f"\nInvoices with payment info: {payment_info_count}")
    
    # Show samples
    print("\n" + "="*80)
    print("SAMPLE INVOICES (first 10)")
    print("="*80)
    
    for i, inv in enumerate(invoices[:10], 1):
        print(f"\n{i}. Invoice #{inv['invoice_number']} - {inv['invoice_date']}")
        print(f"   Amount: ${inv['amount']:.2f}" if inv['amount'] else "   Amount: [missing]")
        if inv['notes']:
            print(f"   Notes: {inv['notes']}")
        if inv['payments']:
            print(f"   Payments found:")
            for p in inv['payments']:
                pmt_str = f"${p['amount']:.2f}" if p['amount'] else "[amount missing]"
                date_str = str(p['date']) if p['date'] else "[date missing]"
                print(f"     - {pmt_str} on {date_str}")
    
    # Identify issues
    print("\n" + "="*80)
    print("DATA QUALITY ISSUES")
    print("="*80)
    
    missing_amounts = [i for i in invoices if not i['amount']]
    print(f"\nInvoices with missing amounts: {len(missing_amounts)}")
    for inv in missing_amounts:
        print(f"  - Invoice #{inv['invoice_number']} ({inv['invoice_date']})")
    
    duplicate_invoices = {}
    for inv in invoices:
        key = (inv['invoice_number'], inv['invoice_date'])
        if key in duplicate_invoices:
            duplicate_invoices[key].append(inv)
        else:
            duplicate_invoices[key] = [inv]
    
    duplicates = {k: v for k, v in duplicate_invoices.items() if len(v) > 1}
    print(f"\nDuplicate invoice numbers: {len(duplicates)}")
    for (inv_num, date), invs in list(duplicates.items())[:5]:
        print(f"  - Invoice #{inv_num} ({date}): {len(invs)} entries")
        for inv in invs:
            amt_str = f"${inv['amount']:.2f}" if inv['amount'] else "[no amount]"
            print(f"    * {amt_str} - {inv['notes'][:50] if inv['notes'] else '(no notes)'}")
    
    # Credit notes
    credits = [i for i in invoices if i['amount'] and i['amount'] < 0]
    print(f"\nCredit notes: {len(credits)}")
    for inv in credits[:5]:
        print(f"  - Invoice #{inv['invoice_number']} ({inv['invoice_date']}): ${inv['amount']:.2f}")
    
    print("\n" + "="*80)
    print("READY FOR IMPORT")
    print("="*80)
    print("\nParsed invoice data structure ready.")
    print("Next steps:")
    print("  1. Review payment information accuracy")
    print("  2. Resolve duplicate invoice numbers")
    print("  3. Fill missing amounts")
    print("  4. Import to email_financial_events or dedicated fibrenew_invoices table")
    print("\nWaiting for payment information file before database upload.")

if __name__ == '__main__':
    main()
