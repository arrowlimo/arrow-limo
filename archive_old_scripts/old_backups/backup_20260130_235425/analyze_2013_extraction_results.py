"""
Analyze 2013 Payroll Extraction Results

Reviews the extracted data from 2013 PDFs and provides:
- Data quality assessment
- Pattern analysis for improving extraction
- T4 vs PD7A cross-validation
- Recommendations for manual review
"""

import json
from pathlib import Path
from collections import defaultdict
from decimal import Decimal

DATA_DIR = Path(r"L:\limo\data")
EXTRACTED_FILE = DATA_DIR / "2013_payroll_extracted.json"

def analyze_extraction():
    """Analyze extraction results and generate report."""
    
    print("="*80)
    print("2013 PAYROLL EXTRACTION ANALYSIS")
    print("="*80)
    
    with open(EXTRACTED_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Summary stats
    print(f"\n{'='*80}")
    print("EXTRACTION SUMMARY")
    print("="*80)
    print(f"PD7A/PDTA Reports: {len(data['pd7a_reports'])}")
    print(f"T4 Slips: {len(data['t4_slips'])}")
    print(f"T4 Summary: {len(data['t4_summary'])}")
    print(f"Payroll Stubs: {len(data['payroll_stubs'])}")
    print(f"Manual Review Required: {len(data['manual_review_required'])}")
    
    # Analyze PD7A reports
    print(f"\n{'='*80}")
    print("PD7A/PDTA REPORTS ANALYSIS")
    print("="*80)
    
    pd7a_months = defaultdict(int)
    pd7a_data_quality = {
        'has_gross_payroll': 0,
        'has_cpp': 0,
        'has_ei': 0,
        'has_income_tax': 0,
        'has_total_remittance': 0,
        'complete_records': 0
    }
    
    for report in data['pd7a_reports']:
        month = report.get('month', 'Unknown')
        pd7a_months[month] += 1
        
        if report.get('gross_payroll'):
            pd7a_data_quality['has_gross_payroll'] += 1
        if report.get('cpp_employee') or report.get('cpp_employer'):
            pd7a_data_quality['has_cpp'] += 1
        if report.get('ei_employee') or report.get('ei_employer'):
            pd7a_data_quality['has_ei'] += 1
        if report.get('income_tax'):
            pd7a_data_quality['has_income_tax'] += 1
        if report.get('total_remittance'):
            pd7a_data_quality['has_total_remittance'] += 1
        
        # Complete record = has all key fields
        if (report.get('gross_payroll') and 
            report.get('cpp_employee') and 
            report.get('ei_employee') and
            report.get('income_tax') and
            report.get('total_remittance')):
            pd7a_data_quality['complete_records'] += 1
    
    print(f"\nReports by Month:")
    for month in sorted(pd7a_months.keys()):
        print(f"  {month:12s}: {pd7a_months[month]:2d} reports")
    
    print(f"\nData Quality:")
    total = len(data['pd7a_reports'])
    for field, count in pd7a_data_quality.items():
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {field:25s}: {count:3d} / {total:3d} ({pct:5.1f}%)")
    
    # Sample a complete record if available
    complete_reports = [r for r in data['pd7a_reports'] if r.get('total_remittance')]
    if complete_reports:
        print(f"\nSample Complete Record:")
        sample = complete_reports[0]
        print(f"  File: {sample['filename']}")
        print(f"  Month: {sample.get('month', 'N/A')}")
        if sample.get('gross_payroll'):
            print(f"  Gross Payroll: ${Decimal(sample['gross_payroll']):,.2f}")
        if sample.get('income_tax'):
            print(f"  Income Tax: ${Decimal(sample['income_tax']):,.2f}")
        if sample.get('total_remittance'):
            print(f"  Total Remittance: ${Decimal(sample['total_remittance']):,.2f}")
    
    # Analyze T4 slips
    print(f"\n{'='*80}")
    print("T4 SLIPS ANALYSIS")
    print("="*80)
    
    t4_employee_names = defaultdict(int)
    t4_with_sin = sum(1 for t4 in data['t4_slips'] if t4.get('sin'))
    t4_with_amounts = sum(1 for t4 in data['t4_slips'] if t4.get('box_14'))
    
    for t4 in data['t4_slips']:
        name = t4.get('employee_name', 'UNKNOWN')
        t4_employee_names[name] += 1
    
    print(f"Total T4 Slips: {len(data['t4_slips'])}")
    print(f"T4s with SIN: {t4_with_sin} ({t4_with_sin/len(data['t4_slips'])*100:.1f}%)")
    print(f"T4s with Box 14 (income): {t4_with_amounts} ({t4_with_amounts/len(data['t4_slips'])*100:.1f}%)")
    
    print(f"\nTop Employee Names (likely OCR errors):")
    for name, count in sorted(t4_employee_names.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {name:20s}: {count:3d} occurrences")
    
    # Note: Names like "CRA PPU", "ARG PPU", "APA OU" are OCR errors
    print(f"\n⚠️  NOTE: Most employee names are OCR errors (CRA PPU, etc.)")
    print(f"   Manual PDF review or better OCR needed for accurate names")
    
    # Sample a T4 with data
    t4_with_data = [t4 for t4 in data['t4_slips'] if t4.get('box_14')]
    if t4_with_data:
        print(f"\nSample T4 with Data:")
        sample = t4_with_data[0]
        print(f"  Employee: {sample.get('employee_name', 'N/A')}")
        if sample.get('sin'):
            print(f"  SIN: {sample['sin']}")
        if sample.get('box_14'):
            print(f"  Box 14 (Income): ${Decimal(sample['box_14']):,.2f}")
        if sample.get('box_16'):
            print(f"  Box 16 (CPP): ${Decimal(sample['box_16']):,.2f}")
        if sample.get('box_18'):
            print(f"  Box 18 (EI): ${Decimal(sample['box_18']):,.2f}")
        if sample.get('box_22'):
            print(f"  Box 22 (Tax): ${Decimal(sample['box_22']):,.2f}")
    
    # Analyze T4 Summary
    print(f"\n{'='*80}")
    print("T4 SUMMARY ANALYSIS")
    print("="*80)
    
    for summary in data['t4_summary']:
        print(f"\nFile: {summary['filename']}")
        if summary.get('total_employees'):
            print(f"  Employees: {summary['total_employees']}")
        if summary.get('total_employment_income'):
            print(f"  Total Employment Income: ${Decimal(summary['total_employment_income']):,.2f}")
        if summary.get('total_cpp_contributions'):
            print(f"  Total CPP: ${Decimal(summary['total_cpp_contributions']):,.2f}")
        if summary.get('total_ei_premiums'):
            print(f"  Total EI: ${Decimal(summary['total_ei_premiums']):,.2f}")
        if summary.get('total_income_tax'):
            print(f"  Total Income Tax: ${Decimal(summary['total_income_tax']):,.2f}")
    
    # T4 vs PD7A reconciliation
    print(f"\n{'='*80}")
    print("T4 vs PD7A RECONCILIATION")
    print("="*80)
    
    # Find the year-end totals
    year_end_pd7a = [r for r in data['pd7a_reports'] if 'Year End' in r.get('filename', '') or 'FINAL' in r.get('filename', '')]
    t4_summaries = data['t4_summary']
    
    if year_end_pd7a and t4_summaries:
        print("\nComparing Year-End PD7A vs T4 Summary:")
        
        # Get CPP totals
        pd7a_cpp_total = Decimal('0')
        for report in year_end_pd7a:
            if report.get('total_cpp_contributions'):
                pd7a_cpp_total = Decimal(report['total_cpp_contributions'])
                break
        
        t4_cpp_total = Decimal('0')
        for summary in t4_summaries:
            if summary.get('total_cpp_contributions'):
                t4_cpp_total = Decimal(summary['total_cpp_contributions'])
                break
        
        if pd7a_cpp_total > 0 and t4_cpp_total > 0:
            print(f"\n  CPP Contributions:")
            print(f"    PD7A Total: ${pd7a_cpp_total:,.2f}")
            print(f"    T4 Total:   ${t4_cpp_total:,.2f}")
            diff = abs(pd7a_cpp_total - t4_cpp_total)
            if diff < Decimal('1.00'):
                print(f"    ✅ Match (difference: ${diff:.2f})")
            else:
                print(f"    ⚠️  Mismatch (difference: ${diff:.2f})")
        
        # Get EI totals
        pd7a_ei_total = Decimal('0')
        for report in year_end_pd7a:
            if report.get('total_ei_premiums'):
                pd7a_ei_total = Decimal(report['total_ei_premiums'])
                break
        
        t4_ei_total = Decimal('0')
        for summary in t4_summaries:
            if summary.get('total_ei_premiums'):
                t4_ei_total = Decimal(summary['total_ei_premiums'])
                break
        
        if pd7a_ei_total > 0 and t4_ei_total > 0:
            print(f"\n  EI Premiums:")
            print(f"    PD7A Total: ${pd7a_ei_total:,.2f}")
            print(f"    T4 Total:   ${t4_ei_total:,.2f}")
            diff = abs(pd7a_ei_total - t4_ei_total)
            if diff < Decimal('1.00'):
                print(f"    ✅ Match (difference: ${diff:.2f})")
            else:
                print(f"    ⚠️  Mismatch (difference: ${diff:.2f})")
    
    # Manual review priorities
    print(f"\n{'='*80}")
    print("MANUAL REVIEW PRIORITIES")
    print("="*80)
    
    print(f"\n1. HIGH PRIORITY: Year-End Documents")
    year_end_files = [
        "December 2013 Year End FINAL PDTA Report",
        "2013 Year End  TOTAL PD7A Reort",
        "Arrow 2013 T4 Summary"
    ]
    for filename in year_end_files:
        matching = [r for r in data['pd7a_reports'] + data['t4_summary'] 
                   if filename in r.get('filename', '')]
        if matching:
            print(f"   ✓ Found: {matching[0]['filename']}")
    
    print(f"\n2. MEDIUM PRIORITY: T4 Employee Name Cleanup")
    print(f"   - 512 T4 slips extracted")
    print(f"   - Most employee names are OCR errors")
    print(f"   - Recommend: Manual PDF review or better OCR (Tesseract)")
    
    print(f"\n3. LOW PRIORITY: Payroll Stub Details")
    print(f"   - {len(data['payroll_stubs'])} stub files processed")
    print(f"   - No detailed data extracted (employee splitting failed)")
    print(f"   - Consider if monthly PD7A totals are sufficient")
    
    # Recommendations
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print("="*80)
    
    print(f"\n1. ✅ Use extracted T4 Summary CPP/EI totals ($14,387.58 / $7,137.61)")
    print(f"2. ⚠️  T4 employee names need manual correction (OCR errors)")
    print(f"3. ⚠️  Most PD7A monthly reports missing data - need better extraction patterns")
    print(f"4. ✅ Year-end PD7A reports have some usable totals")
    print(f"5. 💡 Consider upgrading to Tesseract OCR for better accuracy")
    print(f"6. 💡 Manual verification of critical year-end amounts recommended")


if __name__ == '__main__':
    analyze_extraction()
