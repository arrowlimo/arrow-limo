"""
Inventory of 2012 Payroll Documents

Scans pdf and docs folders to identify available monthly payroll summaries,
individual pay stubs, and related documents.
"""

import os
from pathlib import Path

def scan_2012_payroll_docs():
    """Scan for 2012 payroll documents in pdf and docs folders."""
    
    pdf_folder = Path(r"L:\limo\pdf")
    docs_folder = Path(r"L:\limo\docs")
    
    print("="*80)
    print("2012 PAYROLL DOCUMENT INVENTORY")
    print("="*80)
    
    # Monthly Payroll Summaries
    print("\n📊 MONTHLY PAYROLL SUMMARIES (Complete Employee Data)")
    print("-" * 80)
    
    monthly_summaries = {
        'August': [],
        'September': [],
        'October': [],
        'November': [],
        'December': []
    }
    
    # Check PDF folder
    for file in pdf_folder.glob("*2012*"):
        name = file.name.lower()
        if 'payroll summary' in name:
            for month in monthly_summaries.keys():
                if month.lower() in name:
                    monthly_summaries[month].append(str(file))
    
    # Check docs folder
    for file in docs_folder.rglob("*2012*"):
        name = file.name.lower()
        if 'payroll summary' in name:
            for month in monthly_summaries.keys():
                if month.lower() in name:
                    monthly_summaries[month].append(str(file))
    
    found_months = []
    missing_months = []
    
    for month in ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']:
        files = monthly_summaries.get(month, [])
        if files:
            print(f"[OK] {month:12} : {len(files)} file(s)")
            for f in files:
                print(f"   - {Path(f).name}")
            found_months.append(month)
        else:
            print(f"[FAIL] {month:12} : NOT FOUND")
            missing_months.append(month)
    
    # Individual Pay Stubs
    print("\n📄 INDIVIDUAL PAY STUBS (August 2012)")
    print("-" * 80)
    
    august_stubs = []
    for file in pdf_folder.glob("*2012-08-31*"):
        august_stubs.append(file.name)
    
    if august_stubs:
        print(f"Found {len(august_stubs)} individual pay stubs:")
        for stub in sorted(august_stubs):
            employee_name = stub.split('-(EE)')[0].strip()
            print(f"  • {employee_name}")
    
    # Other December Documents
    print("\n📄 DECEMBER 2012 DOCUMENTS")
    print("-" * 80)
    
    dec_docs = []
    for file in pdf_folder.glob("*ecember*2012*"):
        dec_docs.append(file.name)
    
    for doc in sorted(dec_docs):
        print(f"  • {doc}")
    
    # PD7A and Tax Documents
    print("\n📄 TAX & REMITTANCE DOCUMENTS")
    print("-" * 80)
    
    tax_docs = []
    for pattern in ['*2012*PD7A*', '*2012*PDTA*', '*2012*T4*', '*2012*Remittance*']:
        for file in pdf_folder.glob(pattern):
            if file.name not in tax_docs:
                tax_docs.append(file.name)
    
    for doc in sorted(set(tax_docs)):
        print(f"  • {doc}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    print(f"\nMonthly Payroll Summaries Found: {len(found_months)}/12")
    if found_months:
        print(f"  [OK] Available: {', '.join(found_months)}")
    if missing_months:
        print(f"  [FAIL] Missing: {', '.join(missing_months)}")
    
    print(f"\nIndividual Pay Stubs: {len(august_stubs)} (August 2012 only)")
    print(f"Tax Documents: {len(set(tax_docs))}")
    
    print("\n" + "="*80)
    print("RECOMMENDED IMPORT STRATEGY")
    print("="*80)
    
    if len(found_months) >= 4:
        print("\n[OK] Sufficient monthly summaries found to close payroll gap!")
        print("\nStep 1: Parse available monthly payroll summaries")
        for month in found_months:
            print(f"  • {month} 2012")
        
        print("\nStep 2: Import employee-level data from summaries")
        print("  • Hours, wages, gratuities, expenses")
        print("  • CPP, EI, Tax withholdings")
        print("  • Net pay calculations")
        
        print("\nStep 3: Verify against individual pay stubs (August)")
        print("\nStep 4: Reconcile to December YTD paystub totals ($116,859.97)")
    else:
        print("\n[WARN]  Limited monthly summaries - may need alternate approach")
        print("  • Use available summaries (Aug, Oct, Nov)")
        print("  • Look for quarterly reports or year-end documents")
        print("  • Check for PD7A remittance summaries with details")
    
    return found_months, missing_months

if __name__ == '__main__':
    found, missing = scan_2012_payroll_docs()
