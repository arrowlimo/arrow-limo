#!/usr/bin/env python3
"""
Analyze specific Scotia Bank transaction IDs that user provided.

Transaction IDs to investigate:
52174, 52173, 55534, 52104, 52105, 52106, 52107, 52108, 52109, 52110, 52111, 
52112, 52113, 52114, 52115, 52116, 52117, 52118, 52119, 52120, 52121, 52122, 
52123, 52124, 52125, 52126, 52127, 52128, 52129, 52130, 52131, 52132, 52133, 
52134, 52135
"""

import os
import psycopg2
import csv

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

# Transaction IDs from user
specified_ids = [
    52174, 52173, 55534, 52104, 52105, 52106, 52107, 52108, 52109, 52110, 52111,
    52112, 52113, 52114, 52115, 52116, 52117, 52118, 52119, 52120, 52121, 52122,
    52123, 52124, 52125, 52126, 52127, 52128, 52129, 52130, 52131, 52132, 52133,
    52134, 52135
]

print("=" * 100)
print("ANALYSIS OF SPECIFIED SCOTIA BANK TRANSACTION IDs")
print("=" * 100)
print(f"\nAnalyzing {len(specified_ids)} transaction IDs")
print(f"ID range: {min(specified_ids)} to {max(specified_ids)}")

conn = get_db_connection()
cur = conn.cursor()

# Step 1: Get details of these transactions from banking_transactions
print("\n" + "=" * 100)
print("STEP 1: Current Database Records")
print("=" * 100)

cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        category,
        source_file,
        created_at
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    ORDER BY transaction_id
""", (specified_ids,))

existing_records = cur.fetchall()

print(f"\nFound {len(existing_records)} of {len(specified_ids)} specified IDs in database")

if existing_records:
    # Group by account number
    by_account = {}
    for row in existing_records:
        account = row[1]
        if account not in by_account:
            by_account[account] = []
        by_account[account].append(row)
    
    print(f"\nTransactions by account:")
    for account, records in by_account.items():
        print(f"\n  Account {account}: {len(records)} transactions")
        
        # Date range
        dates = [r[2] for r in records]
        print(f"    Date range: {min(dates)} to {max(dates)}")
        
        # Amount totals
        total_debit = sum(r[4] for r in records if r[4])
        total_credit = sum(r[5] for r in records if r[5])
        print(f"    Total debits: ${total_debit:,.2f}")
        print(f"    Total credits: ${total_credit:,.2f}")
        
        # Source files
        sources = set(r[8] for r in records if r[8])
        if sources:
            print(f"    Source files: {', '.join(sources)}")

# Missing IDs
missing_ids = [tid for tid in specified_ids if tid not in [r[0] for r in existing_records]]
if missing_ids:
    print(f"\n[WARN]  Missing {len(missing_ids)} IDs from database: {missing_ids[:10]}{'...' if len(missing_ids) > 10 else ''}")

# Step 2: Check if these are Scotia 2012 transactions
print("\n" + "=" * 100)
print("STEP 2: Scotia Bank 2012 Analysis")
print("=" * 100)

scotia_2012_records = [r for r in existing_records if r[1] == '903990106011' and r[2] and r[2].year == 2012]

if scotia_2012_records:
    print(f"\n✓ Found {len(scotia_2012_records)} Scotia Bank 2012 transactions")
    print(f"  Date range: {min(r[2] for r in scotia_2012_records)} to {max(r[2] for r in scotia_2012_records)}")
else:
    print("\n[WARN]  NONE of these IDs are Scotia Bank (903990106011) 2012 transactions")

# Check other years
other_scotia = [r for r in existing_records if r[1] == '903990106011' and (not r[2] or r[2].year != 2012)]
if other_scotia:
    years = set(r[2].year for r in other_scotia if r[2])
    print(f"\n  Found {len(other_scotia)} Scotia Bank transactions from other years: {sorted(years)}")

# Check other accounts
other_accounts = [r for r in existing_records if r[1] != '903990106011']
if other_accounts:
    accounts = set(r[1] for r in other_accounts)
    print(f"\n  Found {len(other_accounts)} transactions from OTHER accounts:")
    for acc in sorted(accounts):
        acc_records = [r for r in other_accounts if r[1] == acc]
        dates = [r[2] for r in acc_records if r[2]]
        date_range = f"{min(dates)} to {max(dates)}" if dates else "no dates"
        print(f"    Account {acc}: {len(acc_records)} transactions ({date_range})")

# Step 3: Check if they match staged verified data
print("\n" + "=" * 100)
print("STEP 3: Comparison with Staged Verified Data")
print("=" * 100)

cur.execute("""
    SELECT 
        csv_transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        source_hash
    FROM staging_scotia_2012_verified
    WHERE csv_transaction_id = ANY(%s)
    ORDER BY csv_transaction_id
""", (specified_ids,))

staged_with_ids = cur.fetchall()

print(f"\nFound {len(staged_with_ids)} of {len(specified_ids)} IDs in staged verified CSV")

if staged_with_ids:
    print("\nSample staged transactions:")
    for row in staged_with_ids[:5]:
        print(f"  ID {row[0]}: {row[1]} - {row[2][:50]} - Debit: ${row[3] or 0} Credit: ${row[4] or 0}")

# Check for matching by hash (same transaction, different ID)
if existing_records:
    print("\n" + "=" * 100)
    print("STEP 4: Hash Matching (Same Transaction, Different ID?)")
    print("=" * 100)
    
    # Get hashes from existing records
    cur.execute("""
        SELECT transaction_id, source_hash, description
        FROM banking_transactions
        WHERE transaction_id = ANY(%s)
          AND source_hash IS NOT NULL
    """, (specified_ids,))
    
    existing_hashes = cur.fetchall()
    
    if existing_hashes:
        existing_hash_list = [r[1] for r in existing_hashes]
        
        cur.execute("""
            SELECT csv_transaction_id, source_hash, description
            FROM staging_scotia_2012_verified
            WHERE source_hash = ANY(%s)
        """, (existing_hash_list,))
        
        hash_matches = cur.fetchall()
        
        if hash_matches:
            print(f"\n✓ Found {len(hash_matches)} EXACT MATCHES by hash (same transaction content)")
            print("\nThese transactions exist in both datasets with IDENTICAL content:")
            for existing_id, existing_hash, existing_desc in existing_hashes:
                for staged_id, staged_hash, staged_desc in hash_matches:
                    if existing_hash == staged_hash:
                        print(f"\n  Current DB: ID {existing_id}")
                        print(f"  Staged CSV: ID {staged_id}")
                        print(f"  Description: {existing_desc[:60]}")
                        if existing_id != staged_id:
                            print(f"  [WARN]  WARNING: Same transaction, DIFFERENT IDs!")
        else:
            print("\n[WARN]  NO hash matches - these are DIFFERENT transactions")

# Step 5: Save detailed report
print("\n" + "=" * 100)
print("STEP 5: Generating Detailed Report")
print("=" * 100)

os.makedirs('reports', exist_ok=True)
report_path = 'reports/specified_scotia_transactions_analysis.csv'

with open(report_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Specified ID', 'Found in DB', 'Account Number', 'Date', 'Description', 
        'Debit', 'Credit', 'Source File', 'In Staged CSV', 'Status'
    ])
    
    for tid in specified_ids:
        # Check if in current DB
        db_record = next((r for r in existing_records if r[0] == tid), None)
        
        # Check if in staged CSV
        staged_record = next((r for r in staged_with_ids if r[0] == tid), None)
        
        if db_record:
            status = []
            if db_record[1] == '903990106011':
                if db_record[2] and db_record[2].year == 2012:
                    status.append("SCOTIA_2012")
                else:
                    status.append(f"SCOTIA_{db_record[2].year if db_record[2] else 'UNKNOWN'}")
            else:
                status.append(f"OTHER_ACCOUNT_{db_record[1]}")
            
            if staged_record:
                status.append("ALSO_IN_STAGED")
            
            writer.writerow([
                tid, 'YES', db_record[1], db_record[2], db_record[3],
                db_record[4], db_record[5], db_record[8], 
                'YES' if staged_record else 'NO',
                '; '.join(status)
            ])
        else:
            writer.writerow([
                tid, 'NO', '', '', '', '', '', '', 
                'YES' if staged_record else 'NO',
                'NOT_IN_DB' + ('; IN_STAGED' if staged_record else '')
            ])

print(f"\n✓ Detailed report saved: {report_path}")

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)

print(f"\nSpecified IDs: {len(specified_ids)}")
print(f"  Found in current DB: {len(existing_records)}")
print(f"  Found in staged CSV: {len(staged_with_ids)}")
print(f"  Scotia 2012 transactions: {len(scotia_2012_records)}")
print(f"  Other account transactions: {len(other_accounts)}")

if len(scotia_2012_records) == 0 and len(other_accounts) > 0:
    print("\n[WARN]  CRITICAL FINDING:")
    print("    These IDs are NOT Scotia Bank 2012 transactions!")
    print("    They belong to OTHER accounts and should NOT be deleted.")
    print(f"    Affected accounts: {', '.join(sorted(set(r[1] for r in other_accounts)))}")

cur.close()
conn.close()

print("\n" + "=" * 100)
