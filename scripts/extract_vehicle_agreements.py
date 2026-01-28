#!/usr/bin/env python3
"""
Extract vehicle purchase/lease/buyout agreements from documents.
Reads from reports/verify_content_samples.csv and produces reports/vehicle_agreements.csv
with columns: source_file, agreement_type, vin, make_model, year, principal_amount, 
down_payment, monthly_payment, term_months, interest_rate, dealer, date_signed
"""
import os
import csv
import re
from datetime import datetime

REPORTS_DIR = r"L:\\limo\\reports"
INPUT_CSV = os.path.join(REPORTS_DIR, 'verify_content_samples.csv')
OUTPUT_CSV = os.path.join(REPORTS_DIR, 'vehicle_agreements.csv')

def parse_vehicle_agreement(path: str, sample: str, summary: str) -> dict | None:
    """Extract vehicle financing agreement details from document content"""
    sample_upper = sample.upper()
    
    # Check if this looks like a vehicle financing document
    finance_keywords = ['LEASE', 'PURCHASE', 'BUYOUT', 'FINANCING', 'AUTO LOAN', 'VEHICLE', 'CAR LOAN']
    if not any(keyword in sample_upper for keyword in finance_keywords):
        return None
    
    # Determine agreement type
    agreement_type = 'purchase'  # default
    if 'LEASE' in sample_upper:
        agreement_type = 'lease'
    elif 'BUYOUT' in sample_upper or 'BUY OUT' in sample_upper:
        agreement_type = 'buyout'
    elif 'LOAN' in sample_upper:
        agreement_type = 'loan'
    
    # Extract VIN
    vins = re.findall(r'\b([0-9A-HJ-NPR-Z]{17})\b', sample)
    vin = vins[0] if vins else ''
    
    # Extract make/model/year
    make_model = ''
    year = ''
    
    # Year patterns (common in vehicle docs)
    years = re.findall(r'\b(20[0-9]{2}|19[89][0-9])\b', sample)
    if years:
        year = years[0]
    
    # Common vehicle makes
    makes = ['HONDA', 'TOYOTA', 'FORD', 'CHEVROLET', 'CHEV', 'GMC', 'KIA', 'HYUNDAI', 'NISSAN', 'MAZDA', 'BMW', 'MERCEDES', 'AUDI', 'LEXUS', 'ACURA']
    found_make = None
    for make in makes:
        if make in sample_upper:
            found_make = make
            break
    
    # Try to extract model (word after make)
    if found_make:
        make_pattern = rf'\b{re.escape(found_make)}\s+(\w+)'
        make_match = re.search(make_pattern, sample_upper)
        if make_match:
            make_model = f"{found_make} {make_match.group(1)}"
        else:
            make_model = found_make
    
    # Extract financial amounts
    amounts = re.findall(r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', sample)
    
    # Try to categorize amounts by context
    principal_amount = ''
    down_payment = ''
    monthly_payment = ''
    
    # Look for specific amount contexts
    for amount in amounts:
        amount_clean = amount.replace(',', '')
        amount_context = ''
        
        # Find text around this amount
        amount_pattern = re.escape(f'${amount}')
        context_match = re.search(f'.{{0,100}}{amount_pattern}.{{0,100}}', sample, re.IGNORECASE)
        if context_match:
            amount_context = context_match.group(0).upper()
        
        # Categorize based on context
        if any(word in amount_context for word in ['TOTAL', 'PRINCIPAL', 'FINANCE', 'AMOUNT FINANCED']):
            principal_amount = amount_clean
        elif any(word in amount_context for word in ['DOWN', 'DEPOSIT', 'CASH DOWN']):
            down_payment = amount_clean
        elif any(word in amount_context for word in ['MONTHLY', '/MONTH', 'PAYMENT', 'PER MONTH']):
            monthly_payment = amount_clean
    
    # If we couldn't categorize, use largest as principal, smallest as down payment
    if not principal_amount and amounts:
        amounts_float = [float(a.replace(',', '')) for a in amounts]
        amounts_float.sort()
        if len(amounts_float) >= 2:
            principal_amount = str(amounts_float[-1])  # largest
            down_payment = str(amounts_float[0])       # smallest
        elif len(amounts_float) == 1:
            principal_amount = str(amounts_float[0])
    
    # Extract term (months)
    term_months = ''
    term_patterns = [
        r'(\d+)\s*MONTHS?',
        r'(\d+)\s*MO\b',
        r'TERM[:\s]+(\d+)',
        r'(\d+)\s*YEAR[S]?',  # convert years to months
    ]
    
    for pattern in term_patterns:
        term_match = re.search(pattern, sample_upper)
        if term_match:
            term_val = int(term_match.group(1))
            if 'YEAR' in pattern:
                term_val *= 12  # convert years to months
            term_months = str(term_val)
            break
    
    # Extract interest rate
    interest_rate = ''
    interest_patterns = [
        r'(\d+\.?\d*)\s*%',
        r'RATE[:\s]+(\d+\.?\d*)',
        r'APR[:\s]+(\d+\.?\d*)',
    ]
    
    for pattern in interest_patterns:
        rate_match = re.search(pattern, sample_upper)
        if rate_match:
            interest_rate = rate_match.group(1) + '%'
            break
    
    # Extract dealer/lender
    dealer = ''
    dealer_keywords = ['DEALER', 'HONDA', 'TOYOTA', 'FORD', 'CHEVROLET', 'HEFFNER', 'FINANCING']
    for keyword in dealer_keywords:
        if keyword in sample_upper:
            # Try to find the full dealer name
            dealer_pattern = rf'\b(\w+\s+)*{re.escape(keyword)}(\s+\w+)*'
            dealer_match = re.search(dealer_pattern, sample)
            if dealer_match:
                dealer = dealer_match.group(0).strip()
                break
    
    # Extract date signed
    dates = re.findall(r'\b(20[0-9]{2}[-/][01]?[0-9][-/][0-3]?[0-9])\b', sample)
    date_signed = dates[0] if dates else ''
    
    return {
        'source_file': path,
        'agreement_type': agreement_type,
        'vin': vin,
        'make_model': make_model,
        'year': year,
        'principal_amount': principal_amount,
        'down_payment': down_payment,
        'monthly_payment': monthly_payment,
        'term_months': term_months,
        'interest_rate': interest_rate,
        'dealer': dealer,
        'date_signed': date_signed
    }

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"Input file not found: {INPUT_CSV}")
        print("Run: python scripts/scan_verify_data.py --with-content first")
        return 1
    
    agreement_records = []
    
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            path = row.get('path', '')
            sample = row.get('sample', '')
            summary = row.get('summary', '')
            
            record = parse_vehicle_agreement(path, sample, summary)
            if record:
                agreement_records.append(record)
    
    # Write output
    fieldnames = ['source_file', 'agreement_type', 'vin', 'make_model', 'year', 'principal_amount', 
                  'down_payment', 'monthly_payment', 'term_months', 'interest_rate', 'dealer', 'date_signed']
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(agreement_records)
    
    print(f"Extracted {len(agreement_records)} vehicle agreement records")
    print(f"Output: {OUTPUT_CSV}")
    
    # Summary by agreement type
    type_counts = {}
    for record in agreement_records:
        atype = record['agreement_type']
        type_counts[atype] = type_counts.get(atype, 0) + 1
    
    if type_counts:
        print("Agreement types found:")
        for atype, count in sorted(type_counts.items()):
            print(f"  {atype}: {count}")
    
    return 0

if __name__ == '__main__':
    raise SystemExit(main())