#!/usr/bin/env python3
"""
Verify that all CIBC PDF statements are from the same account and check date coverage.
"""

import pdfplumber
import re
from datetime import datetime, timedelta
from collections import defaultdict
import os

def extract_account_info(pdf_path):
    """Extract account number and branch transit from PDF."""
    
    account_number = None
    branch_transit = None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Check first 2 pages for account info
            for page in pdf.pages[:2]:
                text = page.extract_text()
                if not text:
                    continue
                
                # Look for account number pattern
                acc_match = re.search(r'Account number[:\s]+(\d+-?\d+)', text, re.IGNORECASE)
                if acc_match and not account_number:
                    account_number = acc_match.group(1).strip()
                
                # Look for branch transit
                branch_match = re.search(r'Branch transit number[:\s]+(\d+)', text, re.IGNORECASE)
                if branch_match and not branch_transit:
                    branch_transit = branch_match.group(1).strip()
                
                if account_number and branch_transit:
                    break
    
    except Exception as e:
        print(f"   [WARN]  Error reading {os.path.basename(pdf_path)}: {e}")
    
    return account_number, branch_transit

def parse_month_day(text, year=2012):
    """Parse 'Jan 3' format to date."""
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    match = re.match(r'([a-z]{3})\s*(\d{1,2})', text.lower())
    if match:
        month_str, day_str = match.groups()
        month = month_map.get(month_str)
        if month:
            try:
                return datetime(year, month, int(day_str)).date()
            except:
                pass
    return None

def extract_statement_period(pdf_path):
    """Extract statement period from PDF header."""
    
    period_start = None
    period_end = None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Check first page for period
            text = pdf.pages[0].extract_text()
            if not text:
                return None, None
            
            # Look for "For Jan 1 to Jan 31, 2012" pattern
            period_match = re.search(r'For\s+([A-Z][a-z]{2})\s+(\d{1,2})\s+to\s+([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(\d{4})', text)
            if period_match:
                start_month_str, start_day, end_month_str, end_day, year = period_match.groups()
                
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                
                start_month = month_map.get(start_month_str.lower())
                end_month = month_map.get(end_month_str.lower())
                
                if start_month and end_month:
                    period_start = datetime(int(year), start_month, int(start_day)).date()
                    period_end = datetime(int(year), end_month, int(end_day)).date()
    
    except Exception as e:
        print(f"   [WARN]  Error extracting period: {e}")
    
    return period_start, period_end

def extract_transaction_dates(pdf_path):
    """Extract all transaction dates from PDF."""
    
    dates = set()
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                
                for line in lines:
                    # Check for date at start of line (e.g., "Jan 3")
                    date_match = re.match(r'^([A-Z][a-z]{2}\s+\d{1,2})\s+', line)
                    if date_match:
                        trans_date = parse_month_day(date_match.group(1))
                        if trans_date and trans_date.year == 2012:
                            dates.add(trans_date)
    
    except Exception as e:
        print(f"   [WARN]  Error extracting dates: {e}")
    
    return sorted(dates)

def main():
    pdf_files = [
        r"L:\limo\CIBC UPLOADS\2012cibc banking jan-mar_ocred.pdf",
        r"L:\limo\CIBC UPLOADS\2012cibc banking apr- may_ocred.pdf",
        r"L:\limo\CIBC UPLOADS\2012cibc banking jun-dec_ocred.pdf",
    ]
    
    print(f"{'='*80}")
    print(f"🔍 VERIFYING CIBC PDF STATEMENTS")
    print(f"{'='*80}\n")
    
    # Step 1: Verify all from same account
    print(f"📋 STEP 1: Account Verification")
    print(f"{'-'*80}")
    
    accounts = {}
    for pdf_file in pdf_files:
        if not os.path.exists(pdf_file):
            print(f"[WARN]  File not found: {pdf_file}")
            continue
        
        filename = os.path.basename(pdf_file)
        account_num, branch_num = extract_account_info(pdf_file)
        accounts[filename] = {'account': account_num, 'branch': branch_num}
        
        print(f"📄 {filename}")
        print(f"   Account: {account_num or 'NOT FOUND'}")
        print(f"   Branch:  {branch_num or 'NOT FOUND'}")
    
    # Check if all match
    account_numbers = [info['account'] for info in accounts.values() if info['account']]
    branch_numbers = [info['branch'] for info in accounts.values() if info['branch']]
    
    if len(set(account_numbers)) == 1 and len(set(branch_numbers)) == 1:
        print(f"\n[OK] VERIFIED: All PDFs are from the SAME account:")
        print(f"   Account Number: {account_numbers[0]}")
        print(f"   Branch Transit: {branch_numbers[0]}")
    else:
        print(f"\n[WARN]  WARNING: Account numbers may differ!")
        print(f"   Unique accounts found: {set(account_numbers)}")
        print(f"   Unique branches found: {set(branch_numbers)}")
    
    # Step 2: Check statement periods
    print(f"\n{'='*80}")
    print(f"📅 STEP 2: Statement Period Verification")
    print(f"{'-'*80}")
    
    periods = []
    for pdf_file in pdf_files:
        if not os.path.exists(pdf_file):
            continue
        
        filename = os.path.basename(pdf_file)
        period_start, period_end = extract_statement_period(pdf_file)
        
        print(f"📄 {filename}")
        if period_start and period_end:
            print(f"   Period: {period_start} to {period_end}")
            print(f"   Days: {(period_end - period_start).days + 1}")
            periods.append((period_start, period_end, filename))
        else:
            print(f"   Period: NOT FOUND")
    
    # Check for gaps
    if periods:
        periods.sort()
        print(f"\n📊 Period Coverage Analysis:")
        print(f"{'-'*80}")
        
        for i, (start, end, filename) in enumerate(periods):
            print(f"{i+1}. {start} to {end} ({filename})")
            
            # Check gap with next period
            if i < len(periods) - 1:
                next_start = periods[i + 1][0]
                gap_days = (next_start - end).days - 1
                
                if gap_days > 0:
                    print(f"   [WARN]  GAP: {gap_days} days missing before next statement")
                elif gap_days == 0:
                    print(f"   ✓ Continuous with next statement")
                elif gap_days < 0:
                    print(f"   [WARN]  OVERLAP: {abs(gap_days)} days overlap with next statement")
        
        # Overall coverage
        first_date = periods[0][0]
        last_date = periods[-1][1]
        total_days = (last_date - first_date).days + 1
        
        print(f"\n📈 Overall Coverage:")
        print(f"   First date: {first_date}")
        print(f"   Last date:  {last_date}")
        print(f"   Span: {total_days} days")
        
        # Check if covers full year
        year_start = datetime(2012, 1, 1).date()
        year_end = datetime(2012, 12, 31).date()
        
        if first_date <= year_start and last_date >= year_end:
            print(f"   [OK] Covers FULL YEAR 2012")
        else:
            missing_start = (first_date - year_start).days
            missing_end = (year_end - last_date).days
            
            if missing_start > 0:
                print(f"   [WARN]  Missing {missing_start} days at start of year")
            if missing_end > 0:
                print(f"   [WARN]  Missing {missing_end} days at end of year")
    
    # Step 3: Check daily transaction coverage
    print(f"\n{'='*80}")
    print(f"📆 STEP 3: Daily Transaction Coverage")
    print(f"{'-'*80}")
    
    all_dates = set()
    date_by_file = {}
    
    for pdf_file in pdf_files:
        if not os.path.exists(pdf_file):
            continue
        
        filename = os.path.basename(pdf_file)
        dates = extract_transaction_dates(pdf_file)
        date_by_file[filename] = dates
        all_dates.update(dates)
        
        print(f"📄 {filename}")
        if dates:
            print(f"   Transaction dates: {len(dates)} days")
            print(f"   Range: {min(dates)} to {max(dates)}")
        else:
            print(f"   No transaction dates found")
    
    if all_dates:
        all_dates_sorted = sorted(all_dates)
        print(f"\n📊 Combined Coverage:")
        print(f"   Total transaction days: {len(all_dates_sorted)}")
        print(f"   Date range: {all_dates_sorted[0]} to {all_dates_sorted[-1]}")
        
        # Find gaps (days with no transactions in entire period)
        date_range_start = all_dates_sorted[0]
        date_range_end = all_dates_sorted[-1]
        total_days_in_range = (date_range_end - date_range_start).days + 1
        
        print(f"   Total days in range: {total_days_in_range}")
        print(f"   Coverage: {len(all_dates_sorted)}/{total_days_in_range} days ({100*len(all_dates_sorted)/total_days_in_range:.1f}%)")
        
        # Find specific gaps
        gaps = []
        current = date_range_start
        while current <= date_range_end:
            if current not in all_dates:
                gaps.append(current)
            current += timedelta(days=1)
        
        if gaps:
            print(f"\n[WARN]  Days with NO transactions: {len(gaps)}")
            
            # Group consecutive gaps
            gap_ranges = []
            if gaps:
                range_start = gaps[0]
                range_end = gaps[0]
                
                for i in range(1, len(gaps)):
                    if gaps[i] == range_end + timedelta(days=1):
                        range_end = gaps[i]
                    else:
                        gap_ranges.append((range_start, range_end))
                        range_start = gaps[i]
                        range_end = gaps[i]
                
                gap_ranges.append((range_start, range_end))
            
            # Show first 10 gap ranges
            print(f"   Gap ranges (showing first 10):")
            for start, end in gap_ranges[:10]:
                if start == end:
                    print(f"   • {start}")
                else:
                    days = (end - start).days + 1
                    print(f"   • {start} to {end} ({days} days)")
            
            if len(gap_ranges) > 10:
                print(f"   ... and {len(gap_ranges) - 10} more gap ranges")
        else:
            print(f"\n[OK] NO GAPS: Every day has at least one transaction!")
    
    # Step 4: Month-by-month breakdown
    print(f"\n{'='*80}")
    print(f"📊 STEP 4: Month-by-Month Coverage")
    print(f"{'-'*80}")
    
    if all_dates:
        monthly_coverage = defaultdict(set)
        for date in all_dates:
            monthly_coverage[date.strftime('%Y-%m')].add(date)
        
        print(f"{'Month':<12} {'Days with Transactions':>25} {'Expected Days':>15} {'Status':>10}")
        print(f"{'-'*80}")
        
        for month in sorted(monthly_coverage.keys()):
            year, month_num = map(int, month.split('-'))
            
            # Calculate expected days in month
            if month_num == 12:
                next_month = datetime(year + 1, 1, 1).date()
            else:
                next_month = datetime(year, month_num + 1, 1).date()
            
            month_start = datetime(year, month_num, 1).date()
            expected_days = (next_month - month_start).days
            
            actual_days = len(monthly_coverage[month])
            coverage_pct = (actual_days / expected_days) * 100
            
            status = "[OK]" if actual_days == expected_days else "[WARN]"
            
            print(f"{month:<12} {actual_days:>25} {expected_days:>15} {status:>10} ({coverage_pct:.0f}%)")
    
    print(f"\n{'='*80}")
    print(f"[OK] Verification Complete!")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()
