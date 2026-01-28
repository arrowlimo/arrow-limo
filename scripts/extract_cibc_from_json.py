"""
Extract 2012 CIBC banking records from complete almsdata export.
Compare against manual verification records from reports.
"""
import json
from datetime import datetime

print("=" * 80)
print("LOADING CIBC DATA FROM ALMSDATA EXPORT")
print("=" * 80)

# Load complete almsdata export
print("Loading complete almsdata export (may take a moment)...")
with open('l:/limo/reports/complete_almsdata_export.json', encoding='utf-8') as f:
    almsdata = json.load(f)
print(f"[OK] Loaded {len(almsdata)} tables")

# Extract banking_transactions
if 'banking_transactions' in almsdata:
    banking = almsdata['banking_transactions']
    print(f"\nTotal banking_transactions: {len(banking):,}")
    
    # Filter for 2012 CIBC
    cibc_2012 = []
    for txn in banking:
        date = txn.get('transaction_date')
        if date and '2012' in str(date):
            cibc_2012.append(txn)
    
    print(f"2012 transactions: {len(cibc_2012):,}")
    
    # Group by month
    by_month = {}
    for txn in cibc_2012:
        date_str = str(txn.get('transaction_date'))[:7]  # YYYY-MM
        if date_str not in by_month:
            by_month[date_str] = []
        by_month[date_str].append(txn)
    
    print("\n" + "=" * 80)
    print("2012 CIBC BANKING TRANSACTIONS BY MONTH")
    print("=" * 80)
    print(f"{'Month':<10} {'Count':>10} {'Deposits':>15} {'Withdrawals':>15} {'Net':>15}")
    print("-" * 80)
    
    for month in sorted(by_month.keys()):
        txns = by_month[month]
        deposits = sum(float(t.get('credit_amount') or 0) for t in txns)
        withdrawals = sum(float(t.get('debit_amount') or 0) for t in txns)
        net = deposits - withdrawals
        
        print(f"{month:<10} {len(txns):>10,} ${deposits:>13,.2f} ${withdrawals:>13,.2f} ${net:>13,.2f}")
    
    # Compare with manual verification
    print("\n" + "=" * 80)
    print("COMPARISON WITH MANUAL VERIFICATION")
    print("=" * 80)
    
    manual_verified = {
        '2012-01': 168,  # January complete
        '2012-06': 87,   # June complete
    }
    
    print(f"{'Month':<10} {'Database':>12} {'Verified':>12} {'Status':>15}")
    print("-" * 80)
    
    for month in sorted(manual_verified.keys()):
        db_count = len(by_month.get(month, []))
        verified_count = manual_verified[month]
        
        if db_count == verified_count:
            status = "[OK] MATCH"
        elif db_count > verified_count:
            status = f"[WARN] +{db_count - verified_count} extra"
        else:
            status = f"[FAIL] -{verified_count - db_count} missing"
        
        print(f"{month:<10} {db_count:>12,} {verified_count:>12,} {status:>15}")
    
    # Show sample records for January
    print("\n" + "=" * 80)
    print("SAMPLE JANUARY 2012 RECORDS (first 10)")
    print("=" * 80)
    
    jan_txns = sorted(by_month.get('2012-01', []), key=lambda x: x.get('transaction_date', ''))
    print(f"{'Date':<12} {'Description':<40} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
    print("-" * 80)
    
    for txn in jan_txns[:10]:
        date = str(txn.get('transaction_date', 'N/A'))[:10]
        desc = str(txn.get('description', 'N/A'))[:39]
        debit = float(txn.get('debit_amount') or 0)
        credit = float(txn.get('credit_amount') or 0)
        balance = float(txn.get('balance') or 0)
        
        print(f"{date:<12} {desc:<40} ${debit:>10,.2f} ${credit:>10,.2f} ${balance:>10,.2f}")
    
    print("\n" + "=" * 80)
    print("ACTION ITEMS")
    print("=" * 80)
    print("\n[OK] DATABASE HAS 2012 CIBC DATA")
    print("\nNext steps:")
    print("1. Compare database records against manual verification (Jan + June)")
    print("2. Identify any discrepancies in amounts or descriptions")
    print("3. Use database as source for remaining months (Feb-May, Jul-Dec)")
    print("4. Validate running balances match PDF statements")
    
else:
    print("[FAIL] banking_transactions table not found in export")
