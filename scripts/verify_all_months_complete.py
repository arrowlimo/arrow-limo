"""
Verify ALL months (Jan-Dec 2012) have complete records with matching PDF vs calculated totals.

This script:
1. Reads the complete verification file
2. Extracts opening/closing balances for each month
3. Calculates running totals from transactions
4. Compares calculated vs PDF balances
5. Identifies missing months or incomplete data
"""
import re
from pathlib import Path
from decimal import Decimal

COMPLETE_FILE = Path(r'l:\limo\reports\2012_cibc_complete_running_balance_verification.md')


def parse_month_section(content, month_name):
    """Extract month section and parse all transactions."""
    # Find the month header
    month_pattern = rf'## {month_name} 2012.*?(?=## |$)'
    month_match = re.search(month_pattern, content, re.DOTALL)
    
    if not month_match:
        return None
    
    month_text = month_match.group(0)
    
    # Extract opening balance
    opening_match = re.search(r'\*\*Opening [Bb]alance.*?[\$\-]*([0-9,\.]+)', month_text)
    opening_balance = Decimal(opening_match.group(1).replace(',', '')) if opening_match else None
    
    # Extract closing balance
    closing_match = re.search(r'\*\*Closing [Bb]alance.*?[\$\-]*([0-9,\.]+)', month_text)
    closing_balance = Decimal(closing_match.group(1).replace(',', '')) if closing_match else None
    
    # Extract total withdrawals
    withdrawals_match = re.search(r'\*\*Total [Ww]ithdrawals.*?\$([0-9,\.]+)', month_text)
    total_withdrawals = Decimal(withdrawals_match.group(1).replace(',', '')) if withdrawals_match else None
    
    # Extract total deposits
    deposits_match = re.search(r'\*\*Total [Dd]eposits.*?\$([0-9,\.]+)', month_text)
    total_deposits = Decimal(deposits_match.group(1).replace(',', '')) if deposits_match else None
    
    # Parse all transaction lines
    transactions = []
    tx_pattern = r'\| ([A-Z][a-z]{2}) (\d+) \| (.+?) \| ([WD-]) \| ([\d,\.]+|-) \| ([\d,\.]+|-) \| ([\d,\.]+) \| ([\d,\.]+) \| (.+?) \|'
    
    for match in re.finditer(tx_pattern, month_text):
        month_abbr = match.group(1)
        day = int(match.group(2))
        description = match.group(3).strip()
        tx_type = match.group(4)
        amount_str = match.group(5)
        prev_balance_str = match.group(6)
        expected_balance_str = match.group(7)
        pdf_balance_str = match.group(8)
        status = match.group(9).strip()
        
        # Skip balance forward lines
        if 'balance forward' in description.lower() or 'opening balance' in description.lower():
            continue
        
        amount = Decimal(amount_str.replace(',', '')) if amount_str != '-' else Decimal('0')
        pdf_balance = Decimal(pdf_balance_str.replace(',', ''))
        expected_balance = Decimal(expected_balance_str.replace(',', ''))
        
        transactions.append({
            'day': day,
            'description': description,
            'type': tx_type,
            'amount': amount,
            'expected_balance': expected_balance,
            'pdf_balance': pdf_balance,
            'status': status
        })
    
    return {
        'opening_balance': opening_balance,
        'closing_balance': closing_balance,
        'total_withdrawals': total_withdrawals,
        'total_deposits': total_deposits,
        'transactions': transactions,
        'section_text': month_text
    }


def calculate_running_total(opening_balance, transactions):
    """Calculate running total from transactions and compare to PDF."""
    if opening_balance is None:
        return None, []
    
    running_balance = opening_balance
    errors = []
    
    for i, tx in enumerate(transactions):
        # Calculate expected balance
        if tx['type'] == 'W':
            expected = running_balance - tx['amount']
        elif tx['type'] == 'D':
            expected = running_balance + tx['amount']
        else:
            expected = running_balance
        
        # Compare to PDF balance
        diff = abs(expected - tx['pdf_balance'])
        
        if diff > Decimal('0.01'):  # Allow 1 cent rounding
            errors.append({
                'line': i + 1,
                'day': tx['day'],
                'description': tx['description'],
                'expected': expected,
                'pdf': tx['pdf_balance'],
                'difference': expected - tx['pdf_balance']
            })
        
        # Use PDF balance as truth for next transaction
        running_balance = tx['pdf_balance']
    
    return running_balance, errors


def main():
    print("=" * 100)
    print("2012 COMPLETE YEAR VERIFICATION (January - December)")
    print("=" * 100)
    print()
    
    if not COMPLETE_FILE.exists():
        print(f"[FAIL] File not found: {COMPLETE_FILE}")
        return
    
    with open(COMPLETE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    results = {}
    missing_months = []
    incomplete_months = []
    
    print("SCANNING ALL MONTHS...")
    print("-" * 100)
    
    for month in months:
        data = parse_month_section(content, month)
        
        if data is None:
            missing_months.append(month)
            print(f"[FAIL] {month:12s} | NOT FOUND in file")
            results[month] = None
        else:
            results[month] = data
            
            # Check completeness
            has_opening = data['opening_balance'] is not None
            has_closing = data['closing_balance'] is not None
            has_totals = data['total_withdrawals'] is not None and data['total_deposits'] is not None
            tx_count = len(data['transactions'])
            
            if not (has_opening and has_closing and has_totals):
                incomplete_months.append(month)
                status = "[WARN]  INCOMPLETE"
            elif tx_count == 0:
                incomplete_months.append(month)
                status = "[WARN]  NO TRANSACTIONS"
            else:
                status = f"[OK] FOUND ({tx_count} transactions)"
            
            # Format balances safely
            open_str = f"${data['opening_balance']:>12,.2f}" if data['opening_balance'] is not None else "NOT FOUND"
            close_str = f"${data['closing_balance']:>12,.2f}" if data['closing_balance'] is not None else "NOT FOUND"
            
            print(f"{status:30s} | {month:12s} | Open: {open_str:>15s} | Close: {close_str:>15s}")
    
    print()
    print("=" * 100)
    print("RUNNING BALANCE VALIDATION")
    print("=" * 100)
    print()
    
    total_errors = 0
    
    for month in months:
        data = results.get(month)
        
        if data is None:
            continue
        
        if not data['transactions']:
            continue
        
        final_balance, errors = calculate_running_total(data['opening_balance'], data['transactions'])
        
        if errors:
            total_errors += len(errors)
            print(f"[FAIL] {month:12s} | {len(errors)} BALANCE MISMATCHES")
            for err in errors[:3]:  # Show first 3
                print(f"   Line {err['line']}: Day {err['day']} | Expected: ${err['expected']:,.2f} | PDF: ${err['pdf']:,.2f} | Diff: ${err['difference']:,.2f}")
                print(f"      {err['description'][:80]}")
            if len(errors) > 3:
                print(f"   ... and {len(errors) - 3} more errors")
        else:
            # Verify final balance matches closing
            if final_balance is not None and data['closing_balance'] is not None:
                diff = abs(final_balance - data['closing_balance'])
                if diff > Decimal('0.01'):
                    print(f"[WARN]  {month:12s} | Final balance ${final_balance:,.2f} != Closing ${data['closing_balance']:,.2f}")
                    total_errors += 1
                else:
                    print(f"[OK] {month:12s} | Running balance VERIFIED | Final: ${final_balance:,.2f}")
            else:
                print(f"[WARN]  {month:12s} | Cannot verify final balance (missing data)")
    
    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print()
    
    complete_count = len([m for m in months if results.get(m) and results[m]['transactions']])
    
    print(f"Total months analyzed:     12")
    print(f"Complete months:           {complete_count}")
    print(f"Missing months:            {len(missing_months)}")
    print(f"Incomplete months:         {len(incomplete_months)}")
    print(f"Balance mismatch errors:   {total_errors}")
    print()
    
    if missing_months:
        print("[FAIL] MISSING MONTHS:")
        for m in missing_months:
            print(f"   - {m}")
        print()
    
    if incomplete_months:
        print("[WARN]  INCOMPLETE MONTHS:")
        for m in incomplete_months:
            print(f"   - {m}")
        print()
    
    if total_errors > 0:
        print(f"[FAIL] FOUND {total_errors} BALANCE VALIDATION ERRORS")
        print("   Review the errors above - PDF balances don't match calculated running totals.")
        print()
    
    # Final verdict
    if complete_count == 12 and len(missing_months) == 0 and len(incomplete_months) == 0 and total_errors == 0:
        print("🎉 [OK] [OK] [OK] PERFECT! ALL 12 MONTHS VERIFIED!")
        print()
        print("   - All months have complete data")
        print("   - All running balances match PDF")
        print("   - All opening/closing balances present")
        print("   - Ready for database import")
    else:
        print("[WARN]  VERIFICATION INCOMPLETE")
        print()
        if missing_months:
            print(f"   - {len(missing_months)} month(s) need to be added to the file")
        if incomplete_months:
            print(f"   - {len(incomplete_months)} month(s) need transaction data")
        if total_errors > 0:
            print(f"   - {total_errors} balance calculation error(s) need review")
    
    print()


if __name__ == '__main__':
    main()
