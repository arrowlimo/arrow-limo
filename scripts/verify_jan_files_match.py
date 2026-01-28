"""
Verify that the January 2012 data in both verification files matches exactly.

This script compares:
1. 2012_cibc_jan_running_balance_verification.md (original January file)
2. 2012_cibc_complete_running_balance_verification.md (master file with all months)

Purpose: Ensure today's work consolidating files didn't corrupt the January data.
"""
import re
from pathlib import Path

JAN_FILE = Path(r'l:\limo\reports\2012_cibc_jan_running_balance_verification.md')
COMPLETE_FILE = Path(r'l:\limo\reports\2012_cibc_complete_running_balance_verification.md')


def extract_transactions(file_path, month_filter='Jan'):
    """Extract transaction lines from markdown file."""
    transactions = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all table rows that start with the month
    pattern = rf'\| {month_filter} \d+ \| (.+?) \| ([WD-]) \| ([\d,\.]+|-) \| ([\d,\.]+|-) \| ([\d,\.]+) \| ([\d,\.]+) \| (.+?) \|'
    
    for match in re.finditer(pattern, content):
        date_desc = match.group(0)
        transactions.append(date_desc.strip())
    
    return transactions


def extract_summary_data(file_path):
    """Extract opening/closing balance and totals."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    data = {}
    
    # Opening balance
    opening_match = re.search(r'\*\*Opening [Bb]alance.*?\$([0-9,\.]+)', content)
    if opening_match:
        data['opening'] = opening_match.group(1)
    
    # Closing balance
    closing_match = re.search(r'\*\*Closing [Bb]alance.*?[\$\-]+([0-9,\.]+)', content)
    if closing_match:
        data['closing'] = closing_match.group(1)
    
    # Total withdrawals
    withdrawals_match = re.search(r'\*\*Total [Ww]ithdrawals.*?\$([0-9,\.]+)', content)
    if withdrawals_match:
        data['withdrawals'] = withdrawals_match.group(1)
    
    # Total deposits
    deposits_match = re.search(r'\*\*Total [Dd]eposits.*?\$([0-9,\.]+)', content)
    if deposits_match:
        data['deposits'] = deposits_match.group(1)
    
    return data


def main():
    print("=" * 80)
    print("JANUARY 2012 FILE VERIFICATION")
    print("=" * 80)
    print()
    
    # Check files exist
    if not JAN_FILE.exists():
        print(f"[FAIL] January file not found: {JAN_FILE}")
        return
    if not COMPLETE_FILE.exists():
        print(f"[FAIL] Complete file not found: {COMPLETE_FILE}")
        return
    
    print(f"[OK] Found January file: {JAN_FILE.name}")
    print(f"[OK] Found Complete file: {COMPLETE_FILE.name}")
    print()
    
    # Extract summary data
    print("=" * 80)
    print("SUMMARY DATA COMPARISON")
    print("=" * 80)
    
    jan_summary = extract_summary_data(JAN_FILE)
    complete_summary = extract_summary_data(COMPLETE_FILE)
    
    summary_match = True
    for key in ['opening', 'closing', 'withdrawals', 'deposits']:
        jan_val = jan_summary.get(key, 'NOT FOUND')
        complete_val = complete_summary.get(key, 'NOT FOUND')
        match_status = '[OK]' if jan_val == complete_val else '[FAIL]'
        
        if jan_val != complete_val:
            summary_match = False
        
        print(f"{match_status} {key.upper():12s} | Jan: ${jan_val:>12s} | Complete: ${complete_val:>12s}")
    
    print()
    
    # Extract transactions
    print("=" * 80)
    print("TRANSACTION LINE COMPARISON")
    print("=" * 80)
    
    jan_transactions = extract_transactions(JAN_FILE, 'Jan')
    complete_transactions = extract_transactions(COMPLETE_FILE, 'Jan')
    
    print(f"January file: {len(jan_transactions)} transaction lines")
    print(f"Complete file: {len(complete_transactions)} transaction lines")
    print()
    
    # Compare transactions
    if len(jan_transactions) != len(complete_transactions):
        print(f"[WARN]  WARNING: Different number of transactions!")
        print(f"   January file: {len(jan_transactions)} lines")
        print(f"   Complete file: {len(complete_transactions)} lines")
        print()
    
    # Find differences
    differences = []
    max_len = max(len(jan_transactions), len(complete_transactions))
    
    for i in range(max_len):
        jan_line = jan_transactions[i] if i < len(jan_transactions) else None
        complete_line = complete_transactions[i] if i < len(complete_transactions) else None
        
        if jan_line != complete_line:
            differences.append((i + 1, jan_line, complete_line))
    
    if differences:
        print(f"[FAIL] FOUND {len(differences)} DIFFERENCES:")
        print()
        for line_num, jan_line, complete_line in differences[:10]:  # Show first 10
            print(f"Line {line_num}:")
            print(f"  JAN FILE:      {jan_line[:100] if jan_line else 'MISSING'}")
            print(f"  COMPLETE FILE: {complete_line[:100] if complete_line else 'MISSING'}")
            print()
        
        if len(differences) > 10:
            print(f"... and {len(differences) - 10} more differences")
        print()
    else:
        print("[OK] All transaction lines MATCH perfectly!")
        print()
    
    # Extract balance validation notes
    with open(JAN_FILE, 'r', encoding='utf-8') as f:
        jan_content = f.read()
    with open(COMPLETE_FILE, 'r', encoding='utf-8') as f:
        complete_content = f.read()
    
    # Count status markers
    jan_ok_count = jan_content.count('[OK] OK')
    jan_warning_count = jan_content.count('[WARN]')
    complete_ok_count = complete_content[:5000].count('[OK] OK')  # Only check Jan section
    complete_warning_count = complete_content[:5000].count('[WARN]')
    
    print("=" * 80)
    print("VALIDATION STATUS MARKERS")
    print("=" * 80)
    print(f"January file:  {jan_ok_count} [OK] OK, {jan_warning_count} [WARN] warnings")
    print(f"Complete file: {complete_ok_count} [OK] OK (Jan section), {complete_warning_count} [WARN] warnings")
    print()
    
    # Final verdict
    print("=" * 80)
    print("FINAL VERIFICATION RESULT")
    print("=" * 80)
    
    if summary_match and not differences:
        print("[OK] [OK] [OK] PERFECT MATCH!")
        print()
        print("All January 2012 data matches exactly between files:")
        print("  - Opening/closing balances match")
        print("  - Total withdrawals/deposits match")
        print("  - All transaction lines match")
        print()
        print("The January data in the complete file is intact and accurate.")
    else:
        print("[FAIL] DISCREPANCIES FOUND!")
        print()
        if not summary_match:
            print("  - Summary data does not match")
        if differences:
            print(f"  - {len(differences)} transaction lines differ")
        print()
        print("[WARN]  The January data may have been corrupted during consolidation.")
        print("    Review the differences above and restore from backup if needed.")
    
    print()


if __name__ == '__main__':
    main()
