#!/usr/bin/env python3
"""
Verify the exact transaction list the user provided.
Compare against both current database and staged verified CSV.
"""

import os
import psycopg2
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

# User's exact data from the image
user_data = [
    (52174, '2012-12-04', 'December 4, 2012 Merchant Deposit Debit 281.56', 281.56, None),
    (52173, '2012-12-04', 'December 4, 2012 Merchant Deposit Debit 411.47', 411.47, None),
    (55534, '2012-12-19', 'DEPOSIT 243960', None, 160.00),
    (52104, '2012-12-19', 'December 19, 2012 Merchant Deposit Credit 380.00', None, 380.00),
    (55516, '2012-12-19', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 440.92),
    (55515, '2012-12-19', 'DEPOSIT 0873847000019 00001 visa DEP CR CHASE PAYMENTECH', None, 3228.26),
    (55553, '2012-12-21', 'DEPOSIT 0973847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 432.18),
    (55547, '2012-12-21', 'GAETZ AND 67TH STREET CASH/COIN ORDER ABM WITHDRAWAL', 700.00, None),
    (55558, '2012-12-27', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', None, 60.95),
    (55567, '2012-12-31', 'CHQ 108 3700477911', 114.57, None),
    (52156, '2012-12-10', 'December 10, 2012 Merchant Deposit Credit 715.01', None, 715.01),
    (52157, '2012-12-10', 'December 10, 2012 Merchant Deposit Credit 1,447.10', None, 1447.10),
    (52158, '2012-12-10', 'December 10, 2012 Merchant Deposit Credit 600.00', None, 600.00),
    (55468, '2012-12-10', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 256.57),
    (55466, '2012-12-12', 'CHQ 97 3700119435', 70.03, None),
    (55472, '2012-12-12', 'INTERAC ABM FEE REFUND', None, 1.50),
    (52103, '2012-12-18', 'December 18, 2012 Merchant Deposit Credit 300.00', None, 300.00),
    (55508, '2012-12-18', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1200.00),
    (55509, '2012-12-18', 'DEPOSIT 0873847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 1169.50),
    (55494, '2012-12-17', 'PC BILL PAYMENT BELL 801', None, 2120.22),
    (55499, '2012-12-17', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 455.19),
    (55503, '2012-12-17', 'POINT OF SALE PURCHASE RIVERSTONE CHIROPRACTIC REPARED DEER ABCD', 31.53, None),
    (55504, '2012-12-17', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 665.00),
    (55505, '2012-12-17', 'DEPOSIT 0873847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 285.00),
    (52183, '2012-12-04', 'December 4, 2012 Merchant Deposit Credit 2,129.00', None, 2129.00),
    (55432, '2012-12-04', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 165.00),
    (55433, '2012-12-04', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1113.35),
    (55478, '2012-12-14', 'DEPOSIT 0873847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 2740.42),
    (55492, '2012-12-14', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 391.47),
    (52171, '2012-12-05', 'December 5, 2012 Merchant Deposit Credit 1,046.00', None, 1046.00),
    (52172, '2012-12-05', 'December 5, 2012 Merchant Deposit Credit 941.25', None, 941.25),
    (55434, '2012-12-05', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 1177.00),
    (55476, '2012-12-13', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 387.58),
    (55477, '2012-12-13', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1951.55),
    (55454, '2012-12-06', 'POINT OF SALE PURCHASE CINEPLEX #3132 QPS RED DEER ABCA', 96.84, None),
]

print("=" * 120)
print("VERIFICATION OF USER-PROVIDED TRANSACTION DATA")
print("=" * 120)
print(f"\nUser provided {len(user_data)} specific transactions")

conn = get_db_connection()
cur = conn.cursor()

# Get all transaction IDs from user data
user_ids = [t[0] for t in user_data]

print("\n" + "=" * 120)
print("CHECKING CURRENT DATABASE")
print("=" * 120)

# Check what's in the database for these IDs
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        source_file
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    ORDER BY transaction_id
""", (user_ids,))

db_records = {row[0]: row for row in cur.fetchall()}

print(f"\nFound {len(db_records)} of {len(user_data)} IDs in database")

# Compare each transaction
matches = 0
mismatches = 0
not_in_db = 0

print("\n" + "=" * 120)
print("TRANSACTION-BY-TRANSACTION COMPARISON")
print("=" * 120)

for user_trans in user_data:
    user_id, user_date, user_desc, user_debit, user_credit = user_trans
    
    if user_id in db_records:
        db_trans = db_records[user_id]
        db_id, db_date, db_desc, db_debit, db_credit, db_source = db_trans
        
        # Compare amounts (convert to Decimal for proper comparison)
        user_debit_dec = Decimal(str(user_debit)) if user_debit else None
        user_credit_dec = Decimal(str(user_credit)) if user_credit else None
        
        amounts_match = (
            (user_debit_dec == db_debit if user_debit_dec else db_debit is None) and
            (user_credit_dec == db_credit if user_credit_dec else db_credit is None)
        )
        
        # Description comparison (normalize whitespace)
        desc_match = user_desc.strip().lower() == db_desc.strip().lower()
        
        if amounts_match and desc_match:
            matches += 1
            print(f"✓ ID {user_id}: EXACT MATCH")
        else:
            mismatches += 1
            print(f"\n[WARN]  ID {user_id}: MISMATCH")
            print(f"   USER: {user_date} | {user_desc[:60]}")
            print(f"         Debit: ${user_debit or 0:.2f} Credit: ${user_credit or 0:.2f}")
            print(f"   DB:   {db_date} | {db_desc[:60]}")
            print(f"         Debit: ${float(db_debit or 0):.2f} Credit: ${float(db_credit or 0):.2f}")
            if not amounts_match:
                print(f"         AMOUNT MISMATCH!")
            if not desc_match:
                print(f"         DESCRIPTION MISMATCH!")
    else:
        not_in_db += 1
        print(f"[FAIL] ID {user_id}: NOT IN DATABASE")

print("\n" + "=" * 120)
print("CHECKING STAGED VERIFIED CSV")
print("=" * 120)

# Check staged data
cur.execute("""
    SELECT 
        csv_transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM staging_scotia_2012_verified
    WHERE csv_transaction_id = ANY(%s)
    ORDER BY csv_transaction_id
""", (user_ids,))

staged_records = {row[0]: row for row in cur.fetchall()}

print(f"\nFound {len(staged_records)} of {len(user_data)} IDs in staged CSV")

staged_matches = 0
staged_mismatches = 0
not_in_staged = 0

print("\nComparing user data vs staged CSV:")

for user_trans in user_data:
    user_id, user_date, user_desc, user_debit, user_credit = user_trans
    
    if user_id in staged_records:
        staged_trans = staged_records[user_id]
        staged_id, staged_date, staged_desc, staged_debit, staged_credit = staged_trans
        
        # Compare amounts
        user_debit_dec = Decimal(str(user_debit)) if user_debit else None
        user_credit_dec = Decimal(str(user_credit)) if user_credit else None
        
        amounts_match = (
            (user_debit_dec == staged_debit if user_debit_dec else staged_debit is None) and
            (user_credit_dec == staged_credit if user_credit_dec else staged_credit is None)
        )
        
        desc_match = user_desc.strip().lower() == staged_desc.strip().lower()
        
        if amounts_match and desc_match:
            staged_matches += 1
        else:
            staged_mismatches += 1
            print(f"\n[WARN]  ID {user_id}: MISMATCH WITH STAGED")
            print(f"   USER:   {user_desc[:60]}")
            print(f"           Debit: ${user_debit or 0:.2f} Credit: ${user_credit or 0:.2f}")
            print(f"   STAGED: {staged_desc[:60]}")
            print(f"           Debit: ${float(staged_debit or 0):.2f} Credit: ${float(staged_credit or 0):.2f}")
    else:
        not_in_staged += 1

print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)

print(f"\nUser provided: {len(user_data)} transactions")
print(f"\nVs Current Database:")
print(f"  ✓ Exact matches: {matches}")
print(f"  [WARN]  Mismatches: {mismatches}")
print(f"  [FAIL] Not in DB: {not_in_db}")

print(f"\nVs Staged Verified CSV:")
print(f"  ✓ Exact matches: {staged_matches}")
print(f"  [WARN]  Mismatches: {staged_mismatches}")
print(f"  [FAIL] Not in staged: {not_in_staged}")

print("\n" + "=" * 120)
print("CONCLUSION")
print("=" * 120)

if matches == len(user_data):
    print("\n✓ ALL user-provided transactions match current database exactly")
    print("  → Current database is CORRECT for these transactions")
elif staged_matches == len(user_data):
    print("\n✓ ALL user-provided transactions match staged CSV exactly")
    print("  → Staged CSV is CORRECT, database needs updating")
elif matches > 0 and not_in_db > 0:
    print(f"\n[WARN]  MIXED RESULTS:")
    print(f"  - {matches} transactions match database")
    print(f"  - {not_in_db} transactions NOT in database")
    print(f"  - These {not_in_db} transactions may have been deleted or never imported")
elif not_in_db == len(user_data):
    print(f"\n[FAIL] NONE of these transactions exist in current database")
    print(f"  → These may have been deleted or belong to a different dataset")
else:
    print(f"\n[WARN]  DATA INTEGRITY ISSUE:")
    print(f"  - Some transactions match, others don't")
    print(f"  - Manual review required")

# Check if these are Scotia 2012 transactions
print("\n" + "=" * 120)
print("ACCOUNT VERIFICATION")
print("=" * 120)

cur.execute("""
    SELECT DISTINCT account_number, COUNT(*)
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    GROUP BY account_number
""", (user_ids,))

accounts = cur.fetchall()
if accounts:
    print(f"\nThese transactions are from:")
    for account, count in accounts:
        print(f"  Account {account}: {count} transactions")
        if account == '903990106011':
            print(f"    ✓ This is Scotia Bank account")
        else:
            print(f"    [WARN]  This is NOT Scotia Bank account!")
else:
    print("\n[FAIL] No transactions found in database for any account")

cur.close()
conn.close()

print("\n" + "=" * 120)
