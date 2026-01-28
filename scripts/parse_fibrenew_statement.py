"""
Extract Fibrenew unpaid invoices from statement Excel file
Statement date: 1/31/2019
Total Amount Due: $16,119.69
"""
import pandas as pd
import re
from datetime import datetime
from decimal import Decimal

EXCEL_FILE = r"L:\limo\receipts\Document_20171129_0001.xlsx"

def parse_invoice_line(desc_text):
    """Parse invoice line like 'INV #7704. Due 11/29/2017. Orig. Amount $2,671.19.'

    Also tolerate common OCR/typing mistakes like '1NV' and 'NV' (missing I).
    """
    if not isinstance(desc_text, str):
        return None

    # Accept "INV", "1NV", and "NV" (missing I)
    upper_desc = desc_text.upper()
    if not any(tag in upper_desc for tag in ('INV', '1NV', 'NV')):
        return None

    # Extract invoice number (handle both "INV", "1NV", and "NV" typo)
    inv_match = re.search(r'(?:[1I]?NV)\s*#?\s*(\d+)', upper_desc, re.IGNORECASE)
    if not inv_match:
        return None
    invoice_number = inv_match.group(1)
    
    # Extract original amount
    orig_match = re.search(r'Orig\. Amount \$?([\d,]+\.?\d*)', desc_text)
    original_amount = None
    if orig_match:
        original_amount = float(orig_match.group(1).replace(',', ''))
    
    return {
        'invoice_number': invoice_number,
        'original_amount': original_amount
    }

try:
    # Read Sheet1 (main invoice list)
    df = pd.read_excel(EXCEL_FILE, sheet_name='Sheet1', header=None)
    print(f"Sheet1 has {len(df)} rows")
    
    # Find the data rows - look for date column
    invoices = []
    
    for idx, row in df.iterrows():
        # Check if first column looks like a date
        try:
            if pd.notna(row.iloc[0]):
                date_val = pd.to_datetime(row.iloc[0], errors='coerce')
                if pd.notna(date_val):
                    # Found a date row
                    invoice_date = date_val.date()
                    
                    # Description is typically in column 1
                    description = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                    
                    # Parse invoice details
                    inv_details = parse_invoice_line(description)
                    if inv_details:
                        # Amount is typically in a later column (around column 5-6)
                        amount_due = None
                        balance = None
                        
                        for col_idx in range(2, len(row)):
                            val = row.iloc[col_idx]
                            if pd.notna(val) and isinstance(val, (int, float)):
                                if amount_due is None:
                                    amount_due = float(val)
                                elif balance is None:
                                    balance = float(val)
                                    break
                        
                        invoices.append({
                            'invoice_number': inv_details['invoice_number'],
                            'invoice_date': invoice_date,
                            'description': description,
                            'original_amount': inv_details['original_amount'],
                            'amount_due': amount_due,
                            'balance': balance
                        })
        except:
            continue
    
    # Read Sheet2 for additional invoices
    df2 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet2', header=None)
    print(f"\nSheet2 has {len(df2)} rows")
    
    for idx, row in df2.iterrows():
        try:
            if pd.notna(row.iloc[0]):
                date_val = pd.to_datetime(row.iloc[0], errors='coerce')
                if pd.notna(date_val):
                    invoice_date = date_val.date()
                    description = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                    
                    inv_details = parse_invoice_line(description)
                    if inv_details:
                        amount_due = None
                        balance = None
                        
                        for col_idx in range(2, len(row)):
                            val = row.iloc[col_idx]
                            if pd.notna(val) and isinstance(val, (int, float)):
                                if amount_due is None:
                                    amount_due = float(val)
                                elif balance is None:
                                    balance = float(val)
                                    break
                        
                        invoices.append({
                            'invoice_number': inv_details['invoice_number'],
                            'invoice_date': invoice_date,
                            'description': description,
                            'original_amount': inv_details['original_amount'],
                            'amount_due': amount_due,
                            'balance': balance
                        })
                        print(f"  Sheet2 Row {idx}: Invoice {inv_details['invoice_number']} - ${amount_due or 0:.2f}")
        except Exception as ex:
            if idx < 30:  # Debug first 30 rows
                print(f"  Sheet2 Row {idx}: SKIP - {ex}")
            continue
    
    # Display results
    print("\n" + "="*120)
    print("FIBRENEW UNPAID INVOICES - Statement Date: 1/31/2019")
    print("="*120)
    print(f"{'Invoice':<10} {'Date':<12} {'Original':>12} {'Amount Due':>12} {'Balance':>12} {'Paid':>12}")
    print("-"*120)
    
    total_original = 0
    total_due = 0
    total_paid = 0
    
    for inv in invoices:
        orig = inv['original_amount'] or 0
        due = inv['amount_due'] or 0
        paid = orig - due if orig and due else 0
        
        total_original += orig
        total_due += due
        total_paid += paid
        
        print(f"{inv['invoice_number']:<10} {str(inv['invoice_date']):<12} ${orig:>10,.2f} ${due:>10,.2f} ${inv['balance'] or 0:>10,.2f} ${paid:>10,.2f}")
    
    print("-"*120)
    print(f"{'TOTALS':<24} ${total_original:>10,.2f} ${total_due:>10,.2f} {'':>12} ${total_paid:>10,.2f}")
    print("="*120)
    
    print(f"\nSUMMARY:")
    print(f"  Total invoices: {len(invoices)}")
    print(f"  Total original amount: ${total_original:,.2f}")
    print(f"  Total amount still due: ${total_due:,.2f}")
    print(f"  Total already paid: ${total_paid:,.2f}")
    print(f"  Statement balance: $16,119.69")
    
    # Check for partial payments
    partial_payments = [inv for inv in invoices if inv['original_amount'] and inv['amount_due'] and inv['original_amount'] > inv['amount_due']]
    if partial_payments:
        print(f"\n  Invoices with partial payments: {len(partial_payments)}")
        for inv in partial_payments[:5]:
            paid = inv['original_amount'] - inv['amount_due']
            print(f"    Invoice {inv['invoice_number']}: ${inv['original_amount']:.2f} → ${inv['amount_due']:.2f} (paid ${paid:.2f})")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
