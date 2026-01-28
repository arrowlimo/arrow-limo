#!/usr/bin/env python3
"""
Import 2011 and complete 2012 banking data.

Key Data Point: Dec 31, 2011 closing balance = $7,177.34 (from PDF)
This becomes the 2012 Jan 1 opening balance.
"""

import psycopg2
from datetime import datetime, date

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('='*80)
print('2011-2012 BANKING DATA IMPORT - DATA COMPLETION PHASE')
print('='*80)
print()

# Step 1: Check what data we have
print('CURRENT STATUS:')
print('-'*80)

for year in [2011, 2012]:
    cur.execute('''
        SELECT 
            COUNT(*) as txn_count,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_balances
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
    ''', (year,))
    
    row = cur.fetchone()
    txn_count, first_date, last_date, debits, credits, nulls = row
    
    print(f'{year}: {txn_count} transactions')
    if first_date:
        print(f'      Date range: {first_date} to {last_date}')
    if debits or credits:
        print(f'      Debits: ${debits:,.2f}, Credits: ${credits:,.2f}')
    if nulls:
        print(f'      NULL balances: {nulls}')
    print()

# Step 2: Data gaps identified
print('DATA GAPS IDENTIFIED:')
print('-'*80)
print('2011: Missing historical data (Jan-Dec) - only extracted Jan-Jun from PDF')
print('2012: Only January has full data (from manual PDF verification)')
print('      Feb-Dec needs to be imported from PDF or QuickBooks exports')
print()

# Step 3: Next steps
print('NEXT STEPS FOR DATA COMPLETION:')
print('-'*80)
print()
print('PHASE 1 - Establish 2011 Opening Balance:')
print('  Dec 31, 2011 closing = $7,177.34 (from user-confirmed PDF)')
print('  This becomes 2012 Jan 1 opening balance')
print('  Action: Create synthetic opening balance record')
print()

print('PHASE 2 - Import Complete 2011 Data:')
print('  Source: 2011 CIBC 1615 PDF statements (L:\\limo\\pdf\\2011\\)')
print('  Range: Jan 1 - Dec 31, 2011')
print('  Current: Only Jan-Jun extracted')
print('  Action: Extract Jul-Dec 2011 and import all transactions')
print()

print('PHASE 3 - Import Complete 2012 Data:')
print('  Source: 2012 CIBC 1615 PDF statements')
print('  Current: Only January verified and imported')
print('  Action: Manually verify and import Feb-Dec 2012')
print('  Note: NSF issue found - 293 NSF charges with no reversals')
print()

print('PHASE 4 - Verify Balance Continuity:')
print('  Check: Dec 31, year N = Jan 1, year N+1')
print('  Range: 2011 → 2012 → 2013 (and beyond as needed)')
print()

print('CRITICAL CONTEXT:')
print('-'*80)
print('• NSF Transaction Issue: 293 NSF charges in 2012 total $188,870.51')
print('  All are POSITIVE (charges), no NEGATIVE (reversals)')
print('  This suggests original payments were not reversed when bounced')
print()

print('• Balance Reconstruction:')
print('  Needed: Opening balance on 2012 Jan 1 = $7,177.34')
print('  Then recalculate all balances chronologically through year')
print()

print('• Data Sources:')
print('  Primary: PDF bank statements (L:\\limo\\pdf\\)')
print('  Secondary: QuickBooks exports if available')
print('  Manual verification required for accuracy')
print()

cur.close()
conn.close()

print('='*80)
print('STATUS: Ready for 2011-2012 data import')
print('        See next scripts for detailed import procedures')
print('='*80)
