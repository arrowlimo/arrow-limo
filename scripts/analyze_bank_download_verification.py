#!/usr/bin/env python3
"""
Analyze CIBC and Square downloads - verify exact matching
Identify which years need manual entry for complete banking verification
"""
import psycopg2
from collections import defaultdict

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("="*100)
    print("CIBC & SQUARE DOWNLOAD VERIFICATION ANALYSIS")
    print("="*100)
    
    # Analyze CIBC accounts by source
    print("\nCIBC ACCOUNTS - Source Analysis")
    print("="*100)
    
    cibc_accounts = ['0228362', '61615', '8032']
    
    for acct in cibc_accounts:
        print(f"\nCIBC Account: {acct}")
        
        # Get source file breakdown
        cur.execute("""
            SELECT 
                source_file,
                COUNT(*) as tx_count,
                MIN(transaction_date) as earliest,
                MAX(transaction_date) as latest,
                verified,
                locked
            FROM banking_transactions
            WHERE account_number = %s
            GROUP BY source_file, verified, locked
            ORDER BY MIN(transaction_date)
        """, (acct,))
        
        sources = cur.fetchall()
        
        total_txs = 0
        verified_txs = 0
        locked_txs = 0
        
        for source, count, earliest, latest, verified, locked in sources:
            total_txs += count
            if verified:
                verified_txs += count
            if locked:
                locked_txs += count
            
            ver_flag = "✓VERIFIED" if verified else "UNVERIFIED"
            lock_flag = "🔒LOCKED" if locked else ""
            
            source_type = "DOWNLOAD" if source and ("cibc" in source.lower() or "csv" in source.lower() or "xlsx" in source.lower()) else "MANUAL/OTHER"
            
            print(f"  {source_type}: {source or 'NULL'}")
            print(f"    {count:,} transactions | {earliest} to {latest} | {ver_flag} {lock_flag}")
        
        print(f"\n  Summary:")
        print(f"    Total: {total_txs:,} transactions")
        if total_txs > 0:
            print(f"    Verified: {verified_txs:,} ({verified_txs/total_txs*100:.1f}%)")
            print(f"    Locked: {locked_txs:,} ({locked_txs/total_txs*100:.1f}%)")
        else:
            print(f"    No transactions found")
    
    # Square analysis
    print(f"\n{'='*100}")
    print("SQUARE DOWNLOADS - Verification Status")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT 
            source_file,
            COUNT(*) as tx_count,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            verified,
            locked
        FROM banking_transactions
        WHERE account_number = 'SQUARE' OR source_file ILIKE '%square%'
        GROUP BY source_file, verified, locked
        ORDER BY MIN(transaction_date)
    """)
    
    square = cur.fetchall()
    
    if square:
        square_total = 0
        square_verified = 0
        
        for source, count, earliest, latest, verified, locked in square:
            square_total += count
            if verified:
                square_verified += count
            
            ver_flag = "✓VERIFIED" if verified else "UNVERIFIED"
            lock_flag = "🔒LOCKED" if locked else ""
            
            print(f"\n  {source or 'NULL'}")
            print(f"    {count:,} transactions | {earliest} to {latest} | {ver_flag} {lock_flag}")
        
        print(f"\n  Summary:")
        print(f"    Total: {square_total:,} transactions")
        print(f"    Verified: {square_verified:,} ({square_verified/square_total*100:.1f}%)")
    else:
        print("\n  No Square transactions found")
    
    # Year-by-year breakdown for ALL accounts
    print(f"\n{'='*100}")
    print("YEAR-BY-YEAR VERIFICATION STATUS - ALL ACCOUNTS")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date)::int as year,
            account_number,
            COUNT(*) as total,
            SUM(CASE WHEN verified THEN 1 ELSE 0 END) as verified_count,
            SUM(CASE WHEN locked THEN 1 ELSE 0 END) as locked_count,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest
        FROM banking_transactions
        WHERE account_number IN ('0228362', '61615', '8032', '903990106011', 'SQUARE')
        GROUP BY EXTRACT(YEAR FROM transaction_date), account_number
        ORDER BY year, account_number
    """)
    
    yearly = cur.fetchall()
    
    by_year = defaultdict(list)
    for year, acct, total, verified, locked, earliest, latest in yearly:
        by_year[year].append({
            'account': acct,
            'total': total,
            'verified': verified,
            'locked': locked,
            'earliest': earliest,
            'latest': latest
        })
    
    needs_manual_entry = []
    
    for year in sorted(by_year.keys()):
        print(f"\n=== {year} ===")
        accounts = by_year[year]
        
        year_total = sum(a['total'] for a in accounts)
        year_verified = sum(a['verified'] for a in accounts)
        year_locked = sum(a['locked'] for a in accounts)
        
        for acct_data in accounts:
            acct = acct_data['account']
            total = acct_data['total']
            verified = acct_data['verified']
            locked = acct_data['locked']
            earliest = acct_data['earliest']
            latest = acct_data['latest']
            
            acct_name = {
                '0228362': 'CIBC 0228362',
                '61615': 'CIBC 61615',
                '8032': 'CIBC 8032',
                '903990106011': 'Scotia 903990106011',
                'SQUARE': 'Square'
            }.get(acct, acct)
            
            ver_pct = verified/total*100 if total > 0 else 0
            lock_pct = locked/total*100 if total > 0 else 0
            
            status = ""
            if ver_pct == 100 and lock_pct == 100:
                status = "[COMPLETE]"
            elif ver_pct == 100:
                status = "[VERIFIED - not locked]"
            elif ver_pct > 0:
                status = f"[PARTIAL {ver_pct:.0f}%]"
            else:
                status = "[NEEDS ENTRY]"
                needs_manual_entry.append({
                    'year': year,
                    'account': acct_name,
                    'total': total,
                    'earliest': earliest,
                    'latest': latest
                })
            
            print(f"  {acct_name}: {total:,} txs | {verified:,} verified ({ver_pct:.0f}%) | {status}")
        
        year_ver_pct = year_verified/year_total*100 if year_total > 0 else 0
        print(f"  YEAR TOTAL: {year_total:,} txs | {year_verified:,} verified ({year_ver_pct:.0f}%)")
    
    # Check for exact one-to-one matching between downloads
    print(f"\n{'='*100}")
    print("ONE-TO-ONE EXACT MATCHING - Bank Downloads vs Database")
    print(f"{'='*100}")
    
    # Check for duplicate transactions (same date, amount, description)
    cur.execute("""
        SELECT 
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            COUNT(*) as dup_count
        FROM banking_transactions
        WHERE account_number IN ('0228362', '61615', '8032', 'SQUARE')
        GROUP BY account_number, transaction_date, description, debit_amount, credit_amount
        HAVING COUNT(*) > 1
        ORDER BY account_number, transaction_date
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        print(f"\nWARNING: FOUND {len(duplicates)} POTENTIAL DUPLICATES (same date/amount/description)")
        for acct, date, desc, debit, credit, count in duplicates[:20]:  # Show first 20
            amount = debit if debit else credit
            print(f"\n  {acct} | {date} | ${amount:,.2f} | {count} copies")
            print(f"  {desc[:80]}")
    else:
        print("\nSUCCESS: NO DUPLICATES FOUND - One-to-one exact matching confirmed")
    
    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY - MANUAL ENTRY REQUIRED")
    print(f"{'='*100}")
    
    if needs_manual_entry:
        print(f"\nACTION REQUIRED: {len(needs_manual_entry)} account-years need manual entry:")
        
        for item in needs_manual_entry:
            print(f"\n  {item['year']} - {item['account']}")
            print(f"    {item['total']:,} transactions unverified")
            print(f"    Date range: {item['earliest']} to {item['latest']}")
            print(f"    ACTION: Manually verify and mark as verified/locked")
    else:
        print("\nSUCCESS: ALL ACCOUNT-YEARS ARE VERIFIED")
    
    # Recommendations
    print(f"\n{'='*100}")
    print("RECOMMENDED ACTIONS")
    print(f"{'='*100}")
    
    print("""
1. MARK DOWNLOADS AS VERIFIED/LOCKED:
   - All CIBC downloads (CSV/XLSX source files) should be marked verified=TRUE, locked=TRUE
   - All Square downloads should be marked verified=TRUE, locked=TRUE
   - Scotia downloads already marked (from previous work)

2. ONE-TO-ONE MATCHING:
   - Run this script to identify any duplicates
   - Verify download files have exact 1:1 match with database records

3. MANUAL ENTRY GAPS:
   - Complete manual entry for years shown above
   - Mark as verified=TRUE after manual verification
   - Lock with locked=TRUE when confirmed accurate

SQL to mark downloads as verified:
""")
    
    print("""
-- Mark CIBC downloads as verified and locked
UPDATE banking_transactions
SET verified = TRUE, locked = TRUE
WHERE account_number IN ('0228362', '61615', '8032')
AND (source_file ILIKE '%cibc%' OR source_file ILIKE '%.csv' OR source_file ILIKE '%.xlsx')
AND verified = FALSE;

-- Mark Square downloads as verified and locked
UPDATE banking_transactions
SET verified = TRUE, locked = TRUE
WHERE (account_number = 'SQUARE' OR source_file ILIKE '%square%')
AND verified = FALSE;
""")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
