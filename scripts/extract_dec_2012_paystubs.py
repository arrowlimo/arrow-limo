#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Extract December 2012 individual paystub data from PDF.
This gives us per-employee breakdown for December 2012.
"""
import PyPDF2
import re
from decimal import Decimal

pdf_path = r'L:\limo\pdf\December 2012 Pay Cheques_ocred (1).pdf'

def parse_paystub_page(text):
    """Extract key data from a paystub page."""
    data = {}
    
    # Employee name (appears after "Employee Paystub" or before address)
    name_match = re.search(r'(?:Employee\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]*)?(?:\s+[A-Z][a-z]+))\s+\d+\s+[A-Z]', text)
    if name_match:
        data['name'] = name_match.group(1).strip()
    
    # Cheque number
    cheque_match = re.search(r'Cheque number:\s*P\s*(\d+)', text)
    if cheque_match:
        data['cheque_number'] = cheque_match.group(1)
    
    # Pay period
    period_match = re.search(r'Pay Period:\s*([\d/]+)\s*-\s*([\d/]+)', text)
    if period_match:
        data['period_start'] = period_match.group(1)
        data['period_end'] = period_match.group(2)
    
    # Current and YTD earnings
    # Pattern: "Current YTD Amount" followed by amounts
    amounts_match = re.search(r'(\d[\d,]+\.\d{2})\s+(\d[\d,]+\.\d{2})\s+-[\d,]+\.\d{2}\s+-[\d,]+\.\d{2}', text)
    if amounts_match:
        data['current_gross'] = amounts_match.group(1).replace(',', '')
        data['ytd_gross'] = amounts_match.group(2).replace(',', '')
    
    # Net pay
    net_match = re.search(r'Net Pay\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', text)
    if net_match:
        data['current_net'] = net_match.group(1).replace(',', '')
        data['ytd_net'] = net_match.group(2).replace(',', '')
    
    # Withholdings - CPP
    cpp_match = re.search(r'CPP - Employee\s+-(\d+\.\d{2})\s+-(\d+\.\d{2})', text)
    if cpp_match:
        data['current_cpp'] = cpp_match.group(1)
        data['ytd_cpp'] = cpp_match.group(2)
    
    # Withholdings - EI
    ei_match = re.search(r'EI - Employee\s+-(\d+\.\d{2})\s+-(\d+\.\d{2})', text)
    if ei_match:
        data['current_ei'] = ei_match.group(1)
        data['ytd_ei'] = ei_match.group(2)
    
    # Withholdings - Federal Tax
    tax_match = re.search(r'Federal Income Tax\s+-(\d+\.\d{2})\s+-(\d+\.\d{2})', text)
    if tax_match:
        data['current_tax'] = tax_match.group(1)
        data['ytd_tax'] = tax_match.group(2)
    
    # Wages
    wages_match = re.search(r'Wages\s+(?:[\d.]+\s+[\d.]+\s+)?([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', text)
    if wages_match:
        data['current_wages'] = wages_match.group(1).replace(',', '')
        data['ytd_wages'] = wages_match.group(2).replace(',', '')
    
    # Gratuities
    grat_match = re.search(r'Gratuities - Taxable\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', text)
    if grat_match:
        data['current_gratuity'] = grat_match.group(1).replace(',', '')
        data['ytd_gratuity'] = grat_match.group(2).replace(',', '')
    
    return data if data else None


def main():
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        print(f"December 2012 Paystub Extraction")
        print(f"Pages: {len(reader.pages)}")
        print("=" * 100)
        
        paystubs = []
        for i in range(len(reader.pages)):
            text = reader.pages[i].extract_text()
            data = parse_paystub_page(text)
            if data and 'name' in data:
                paystubs.append(data)
                print(f"\n{data.get('name', 'Unknown')} (Cheque #{data.get('cheque_number', 'N/A')})")
                print(f"  Period: {data.get('period_start', '')} - {data.get('period_end', '')}")
                print(f"  Current: Gross ${data.get('current_gross', '0.00'):>10s}  Net ${data.get('current_net', '0.00'):>10s}")
                print(f"  YTD:     Gross ${data.get('ytd_gross', '0.00'):>10s}  Net ${data.get('ytd_net', '0.00'):>10s}")
                if 'current_cpp' in data:
                    print(f"  Deductions: CPP ${data.get('current_cpp', '0'):>8s}  EI ${data.get('current_ei', '0'):>8s}  Tax ${data.get('current_tax', '0'):>8s}")
                if 'ytd_cpp' in data:
                    print(f"  YTD Deduc:  CPP ${data.get('ytd_cpp', '0'):>8s}  EI ${data.get('ytd_ei', '0'):>8s}  Tax ${data.get('ytd_tax', '0'):>8s}")
        
        print("\n" + "=" * 100)
        print(f"\nTotal employees: {len(paystubs)}")
        
        # Calculate totals
        if paystubs:
            total_current_gross = sum(Decimal(p.get('current_gross', '0')) for p in paystubs)
            total_ytd_gross = sum(Decimal(p.get('ytd_gross', '0')) for p in paystubs)
            total_current_cpp = sum(Decimal(p.get('current_cpp', '0')) for p in paystubs)
            total_ytd_cpp = sum(Decimal(p.get('ytd_cpp', '0')) for p in paystubs)
            total_current_ei = sum(Decimal(p.get('current_ei', '0')) for p in paystubs)
            total_ytd_ei = sum(Decimal(p.get('ytd_ei', '0')) for p in paystubs)
            total_current_tax = sum(Decimal(p.get('current_tax', '0')) for p in paystubs)
            total_ytd_tax = sum(Decimal(p.get('ytd_tax', '0')) for p in paystubs)
            
            print(f"\nDecember 2012 Totals:")
            print(f"  Current Gross: ${total_current_gross:,.2f}")
            print(f"  Current CPP:   ${total_current_cpp:,.2f}")
            print(f"  Current EI:    ${total_current_ei:,.2f}")
            print(f"  Current Tax:   ${total_current_tax:,.2f}")
            
            print(f"\n2012 Year-End Totals:")
            print(f"  YTD Gross:     ${total_ytd_gross:,.2f}")
            print(f"  YTD CPP:       ${total_ytd_cpp:,.2f}")
            print(f"  YTD EI:        ${total_ytd_ei:,.2f}")
            print(f"  YTD Tax:       ${total_ytd_tax:,.2f}")

if __name__ == '__main__':
    main()
