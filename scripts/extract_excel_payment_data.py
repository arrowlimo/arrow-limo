#!/usr/bin/env python3
"""
Detailed Excel Data Extractor
=============================

Extracts specific payment and employee data found by the scanner:
1. Payment method summaries from charge summary files
2. Employee email addresses from employee file

Based on the scanner findings, this will extract the actual data rows.
"""

import pandas as pd
import os
import re
from pathlib import Path

def extract_payment_summaries():
    """Extract payment method summaries from charge summary files"""
    
    files = [
        {"path": r"E:\2achargesummary.xls", "period": "2002-2018"},
        {"path": r"E:\2chargesummary.xls", "period": "2019-2024"}, 
        {"path": r"E:\chargesummary.xls", "period": "2025"}
    ]
    
    payment_summary = {}
    
    for file_info in files:
        filepath = file_info["path"]
        period = file_info["period"]
        
        if not os.path.exists(filepath):
            continue
            
        try:
            df = pd.read_excel(filepath, header=0)
            
            # Find payment summary rows
            payment_types = []
            
            for idx, row in df.iterrows():
                cell_value = str(df.iloc[idx, 0])
                
                # Look for payment type summary patterns
                if "Sub-Total For" in cell_value:
                    # Extract payment type and amount
                    if "Cash" in cell_value:
                        amount = re.search(r'(\d+(?:,\d+)*)', cell_value)
                        if amount:
                            payment_types.append({"type": "Cash", "amount": amount.group(1), "period": period})
                    
                    elif "Credit Card" in cell_value:
                        amount = re.search(r'(\d+(?:,\d+)*)', cell_value)
                        if amount:
                            payment_types.append({"type": "Credit Card", "amount": amount.group(1), "period": period})
                    
                    elif "Debit Card" in cell_value:
                        amount = re.search(r'(\d+(?:,\d+)*)', cell_value)
                        if amount:
                            payment_types.append({"type": "Debit Card", "amount": amount.group(1), "period": period})
                    
                    elif "Interac E Transfer" in cell_value:
                        amount = re.search(r'(\d+(?:,\d+)*)', cell_value)
                        if amount:
                            payment_types.append({"type": "Interac E-Transfer", "amount": amount.group(1), "period": period})
                    
                    elif "Master Card" in cell_value:
                        amount = re.search(r'(\d+(?:,\d+)*)', cell_value)
                        if amount:
                            payment_types.append({"type": "MasterCard", "amount": amount.group(1), "period": period})
                    
                    elif "Visa" in cell_value:
                        amount = re.search(r'(\d+(?:,\d+)*)', cell_value)
                        if amount:
                            payment_types.append({"type": "Visa", "amount": amount.group(1), "period": period})
            
            payment_summary[period] = payment_types
            
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
    
    return payment_summary

def extract_employee_emails():
    """Extract employee email addresses from employee file"""
    
    filepath = r"E:\employeelistbasic.xls"
    
    if not os.path.exists(filepath):
        print(f"Employee file not found: {filepath}")
        return []
    
    try:
        df = pd.read_excel(filepath, header=0)
        
        # Based on scanner findings, emails are in column 17
        emails = []
        
        for idx in range(len(df)):
            # Check column 17 for email addresses
            if len(df.columns) > 17:
                email_cell = df.iloc[idx, 17]
                if pd.notna(email_cell):
                    email_str = str(email_cell).strip()
                    # Validate email pattern
                    if '@' in email_str and '.' in email_str and len(email_str) > 5:
                        # Also get employee name from nearby columns
                        name = ""
                        for col_idx in range(min(5, len(df.columns))):
                            name_cell = df.iloc[idx, col_idx]
                            if pd.notna(name_cell) and str(name_cell).strip():
                                name_str = str(name_cell).strip()
                                # Skip header-like content
                                if not any(skip in name_str.lower() for skip in ['arrow', 'limousine', 'ave', 'alberta', 'phone', 'fax']):
                                    name = name_str
                                    break
                        
                        emails.append({
                            "name": name,
                            "email": email_str,
                            "row": idx
                        })
        
        return emails
        
    except Exception as e:
        print(f"Error processing employee file: {e}")
        return []

def main():
    """Generate detailed extraction report"""
    
    print("📊 DETAILED DATA EXTRACTION REPORT")
    print("=" * 60)
    
    # Extract payment summaries
    print("\n💰 PAYMENT METHOD SUMMARIES BY PERIOD:")
    print("-" * 50)
    
    payment_data = extract_payment_summaries()
    
    for period, payments in payment_data.items():
        print(f"\n📅 Period: {period}")
        if payments:
            for payment in payments:
                print(f"   {payment['type']}: {payment['amount']} transactions")
        else:
            print("   No payment data found")
    
    # Extract employee emails
    print("\n\n📧 EMPLOYEE EMAIL ADDRESSES:")
    print("-" * 50)
    
    emails = extract_employee_emails()
    
    if emails:
        print(f"Found {len(emails)} employee email addresses:")
        for i, emp in enumerate(emails, 1):
            print(f"{i:3d}. {emp['name']:<25} → {emp['email']}")
    else:
        print("No employee email addresses found")
    
    # Summary for etransfer analysis
    print(f"\n\n🔍 E-TRANSFER ANALYSIS SUMMARY:")
    print("-" * 50)
    
    total_etransfers = 0
    for period, payments in payment_data.items():
        for payment in payments:
            if payment['type'] == "Interac E-Transfer":
                etransfer_count = int(payment['amount'].replace(',', ''))
                total_etransfers += etransfer_count
                print(f"   {period}: {etransfer_count} Interac E-Transfers")
    
    print(f"\n📈 TOTAL E-TRANSFERS ACROSS ALL PERIODS: {total_etransfers}")
    
    if emails:
        print(f"\n👥 EMPLOYEES WITH EMAIL ADDRESSES: {len(emails)}")
        print("   These employees could potentially receive e-transfers")
        
        # Look for potential banking-related emails
        banking_emails = []
        for emp in emails:
            email_domain = emp['email'].split('@')[1].lower()
            if any(bank in email_domain for bank in ['cibc', 'rbc', 'td', 'scotiabank', 'bmo']):
                banking_emails.append(emp)
        
        if banking_emails:
            print(f"\n🏦 EMPLOYEES WITH BANKING EMAIL DOMAINS: {len(banking_emails)}")
            for emp in banking_emails:
                print(f"   {emp['name']} → {emp['email']}")
    
    print(f"\n[OK] Extraction complete!")
    print(f"\nNext steps for e-transfer matching:")
    print(f"1. Compare the {total_etransfers} e-transfers with database payment records")
    print(f"2. Match employee emails with payment recipient information")
    print(f"3. Identify cash/credit patterns for payment reconciliation")

if __name__ == "__main__":
    main()