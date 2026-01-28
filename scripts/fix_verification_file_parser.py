"""
Fix the verification file parser to correctly extract transactions from markdown tables.

Issues fixed:
1. Regex pattern now matches the actual table format with exact column structure
2. Handles month sections with and without transaction tables
3. Reports which months need data entry
"""

import re
from pathlib import Path

def parse_month_transactions(month_text, month_name):
    """Parse transactions from a month section using improved regex."""
    transactions = []
    
    # Pattern matches: | Jan 3 | PURCHASE Centex... | W | 63.50 | 7,177.34 | 7,113.84 | 7,113.84 | [OK] OK |
    # Captures: month (Jan), day (3), description, type (W/D/-), amount, prev_bal, expected_bal, pdf_bal, status
    pattern = r'\|\s*([A-Z][a-z]{2})\s+(\d+)\s*\|\s*(.+?)\s*\|\s*([WD-])\s*\|\s*([\d,\.]+|-)\s*\|\s*([\d,\.]+|-)\s*\|\s*([\d,\.]+|-)\s*\|\s*([\d,\.]+|-)\s*\|\s*(.+?)\s*\|'
    
    for match in re.finditer(pattern, month_text, re.MULTILINE):
        month_abbr, day, desc, tx_type, amount, prev_bal, expected_bal, pdf_bal, status = match.groups()
        
        # Skip if this doesn't match our target month
        if month_abbr.upper() != month_name[:3].upper():
            continue
            
        transactions.append({
            'date': f"{month_abbr} {day}",
            'description': desc.strip(),
            'type': tx_type,
            'amount': amount,
            'prev_balance': prev_bal,
            'expected_balance': expected_bal,
            'pdf_balance': pdf_bal,
            'status': status.strip()
        })
    
    return transactions

def extract_summary_values(month_text):
    """Extract opening/closing balances from month header."""
    opening = None
    closing = None
    
    # Match: **Opening Balance (Jun 1):** $7,544.86 or **Opening Balance:** $7,544.86
    open_match = re.search(r'\*\*Opening Balance[^:]*:\*\*\s*\$?([0-9,\.\-]+)', month_text)
    if open_match:
        try:
            opening = float(open_match.group(1).replace(',', ''))
        except ValueError:
            pass
    
    # Match: **Closing Balance (Jun 30):** $297.14 or -$49.17
    close_match = re.search(r'\*\*Closing Balance[^:]*:\*\*\s*-?\$?([0-9,\.\-]+)', month_text)
    if close_match:
        try:
            closing = float(close_match.group(1).replace(',', ''))
        except ValueError:
            pass
    
    return opening, closing

def main():
    """Analyze the verification file and report status."""
    
    file_path = Path('l:/limo/reports/2012_cibc_complete_running_balance_verification.md')
    
    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}")
        return
    
    content = file_path.read_text(encoding='utf-8')
    
    # Split into month sections
    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    
    print("=" * 80)
    print("2012 CIBC VERIFICATION FILE ANALYSIS")
    print("=" * 80)
    print()
    
    complete_months = []
    incomplete_months = []
    missing_months = []
    
    for i, month in enumerate(months):
        # Find this month's section
        pattern = f"## {month} 2012"
        month_match = re.search(pattern, content, re.IGNORECASE)
        
        if not month_match:
            missing_months.append(month)
            print(f"[FAIL] {month:12s} - MISSING (no section found)")
            continue
        
        # Extract text from this month to next month (or end of file)
        start = month_match.start()
        if i < len(months) - 1:
            next_pattern = f"## {months[i+1]} 2012"
            next_match = re.search(next_pattern, content[start:], re.IGNORECASE)
            if next_match:
                end = start + next_match.start()
            else:
                end = len(content)
        else:
            end = len(content)
        
        month_text = content[start:end]
        
        # Extract summary values
        opening, closing = extract_summary_values(month_text)
        
        # Parse transactions
        transactions = parse_month_transactions(month_text, month)
        
        # Check for PENDING marker
        is_pending = 'PENDING' in month_text[:200]  # Check first 200 chars
        
        # Determine status
        if is_pending or len(transactions) == 0:
            incomplete_months.append(month)
            status = "[WARN]  INCOMPLETE"
            if opening:
                details = f"(has opening ${opening:,.2f}, but {len(transactions)} transactions)"
            else:
                details = "(no data entered yet)"
        else:
            complete_months.append(month)
            status = "[OK] COMPLETE"
            ok_count = sum(1 for t in transactions if '[OK]' in t['status'])
            details = f"({len(transactions)} transactions, {ok_count} [OK] OK)"
        
        print(f"{status} {month:12s} {details}")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"[OK] Complete months: {len(complete_months)}/12 - {', '.join(complete_months)}")
    print(f"[WARN]  Incomplete months: {len(incomplete_months)}/12 - {', '.join(incomplete_months)}")
    print(f"[FAIL] Missing months: {len(missing_months)}/12 - {', '.join(missing_months)}")
    print()
    
    if incomplete_months:
        print("NEXT STEPS:")
        print("-" * 80)
        print("Incomplete months need transaction tables added:")
        for month in incomplete_months:
            print(f"  • {month} - Enter transaction data from PDF statement")
        print()
    
    if missing_months:
        print("Missing months need full sections created:")
        for month in missing_months:
            print(f"  • {month} - Create section with opening balance and transactions")
        print()

if __name__ == '__main__':
    main()
