#!/usr/bin/env python3
"""
Import Scotia Bank December 2013 COMPLETE bank statement.
This supplements the QuickBooks reconciliation data already imported.
Hash-based deduplication will prevent duplicates automatically.
"""

import os
import sys
import psycopg2
import hashlib

ACCOUNT = '903990106011'
DRY_RUN = '--write' not in sys.argv

# Complete December 2013 bank statement transactions
# Extracted from all statement pages provided
SCOTIA_DEC_2013_STATEMENT = [
    # December 2 - NSF and misc
    ('2013-12-02', 'Overdrawn Handling Chg', 5.00, None),
    ('2013-12-02', 'Returned Cheque - NSF', 2695.40, None),
    ('2013-12-02', 'Returned Cheque - NSF', 989.87, None),
    ('2013-12-02', 'Returned Cheque - NSF', 398.33, None),
    ('2013-12-02', 'Returned Cheque - NSF', 0.30, None),
    ('2013-12-02', 'Miscellaneous Payment PAYMENTECH CA DEBTCD FEE DR', 0.30, None),
    ('2013-12-02', 'Miscellaneous Payment PAYMENTECH CA MCARD FEE DR', None, 398.33),
    ('2013-12-02', 'Rent/Lease HEFFNER AUTO FC', 889.87, None),
    ('2013-12-02', 'Rent/Lease ACE TRUCK RENTALS LTD', 2695.40, None),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', 418.86, None),
    ('2013-12-02', 'Miscellaneous Payment AMEX BANK OF CANADA', 1044.37, None),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 MCARD', 1950.90, None),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', 616.46, None),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', 939.66, None),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', 234.85, None),
    
    # December 3
    ('2013-12-03', 'Cheque 273', 1359.75, None),
    ('2013-12-03', 'Service Charge', 170.00, None),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 MCARD', 2079.24, None),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 VISA', 935.80, None),
    
    # December 4
    ('2013-12-04', 'POS Purchase RUNN ON EMPTY 50AVOPE RED D', 66.70, None),
    ('2013-12-04', 'POS Purchase SUMMIT ESSO RED D', 140.03, None),
    ('2013-12-04', 'Miscellaneous Payment AMEX BANK OF CANADA', 742.63, None),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 VISA', 1103.12, None),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 MCARD', 187.88, None),
    
    # December 5
    ('2013-12-05', 'Cheque 274', 1458.88, None),
    ('2013-12-05', 'POS Purchase MONEY MART #1205 RED D', 140.00, None),
    ('2013-12-05', 'Deposit', 1944.42, None),
    
    # December 6
    ('2013-12-06', 'POS Purchase RUNN ON EMPTY 50AVOPE RED D', 142.00, None),
    ('2013-12-06', 'POS Purchase PRINCESS AUTO RED D', 41.99, None),
    ('2013-12-06', 'Bill Payment PC-CAPITAL ONE MASTERCARD 01802347', 550.00, None),
    ('2013-12-06', 'ABM Withdrawal', 400.00, None),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 MCARD', 250.37, None),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 VISA', 41.85, None),
    
    # December 9
    ('2013-12-09', 'Bill Payment PC-CAPITAL ONE MASTERCARD 00386192', 650.00, None),
    ('2013-12-09', 'POS Purchase RUNN ON EMPTY 50AVOPE RED D', 45.00, None),
    ('2013-12-09', 'POS Purchase WAL-MART #3075 RED D', 49.23, None),
    ('2013-12-09', 'ABM Withdrawal', 202.00, None),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', 843.50, None),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', 1855.17, None),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 MCARD', 535.89, None),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 MCARD', 205.00, None),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', 1283.03, None),
    
    # December 10
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 26.25, None),
    ('2013-12-10', 'Cheque 276', 1876.76, None),
    ('2013-12-10', 'Cheque 280', 1910.96, None),
    ('2013-12-10', 'Cheque 275', 948.46, None),
    ('2013-12-10', 'Debit Memo DRAFT PURCHASE', 2720.04, None),
    ('2013-12-10', 'POS Purchase AUTOMOTIVE UNIVERSE RED D', 1043.11, None),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 VISA', 4356.97, None),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 MCARD', 82.69, None),
    ('2013-12-10', 'Deposit', 88.92, None),
    
    # December 11
    ('2013-12-11', 'Cheque 282', 1210.95, None),
    ('2013-12-11', 'ABM Withdrawal', 200.00, None),
    ('2013-12-11', 'Merchant Deposit Credit 566756800000 00001 VISA', 1013.08, None),
    
    # December 12
    ('2013-12-12', 'POS Purchase THE TIRE GARAGE RED D', 673.05, None),
    ('2013-12-12', 'Merchant Deposit Credit 566756800000 00001 VISA', 846.53, None),
    
    # December 13
    ('2013-12-13', 'POS Purchase 604 - LB 67TH ST. RED D', 863.37, None),
    ('2013-12-13', 'POS Purchase RUNN ON EMPTY 50AVOPE RED D', 50.00, None),
    ('2013-12-13', 'Merchant Deposit Credit 566756800000 00001 VISA', 156.93, None),
    
    # December 16
    ('2013-12-16', 'ABM Withdrawal', 300.00, None),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', 2618.69, None),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 MCARD', 1835.00, None),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 99.23, None),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 MCARD', 360.56, None),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', 811.13, None),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', 3776.37, None),
    ('2013-12-16', 'Deposit', 1000.00, None),
    
    # December 17
    ('2013-12-17', 'Cheque 279', 1762.90, None),
    ('2013-12-17', 'Merchant Deposit Credit 566756800000 00001 MCARD', 2681.00, None),
    ('2013-12-17', 'Merchant Deposit Credit 566756800000 00001 VISA', 206.94, None),
    
    # December 18
    ('2013-12-18', 'Cheque 277', 733.68, None),
    ('2013-12-18', 'POS Purchase A T R. LOGISTICS AIRDR', 550.73, None),
    ('2013-12-18', 'POS Purchase RED DEER CO-OP TAYLOR RED D', 40.00, None),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 VISA', 1168.00, None),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 MCARD', 336.25, None),
    
    # December 19
    ('2013-12-19', 'Cheque 281', 941.09, None),
    ('2013-12-19', 'POS Purchase CENTRAL AB CO-OP LTD. RED D', 4.82, None),
    ('2013-12-19', 'POS Purchase CANADIAN TIRE #235 EDMON', 64.38, None),
    ('2013-12-19', 'POS Purchase RED DEER REGISTRIES RED D', 704.35, None),
    ('2013-12-19', 'POS Purchase RED DEER REGISTRIES RED D', 392.35, None),
    ('2013-12-19', 'Miscellaneous Payment AMEX BANK OF CANADA', 208.73, None),
    ('2013-12-19', 'Merchant Deposit Credit 566756800000 00001 VISA', 2617.50, None),
    
    # December 20
    ('2013-12-20', 'POS Purchase ERLES AUTO REPAIR RED D', 265.92, None),
    ('2013-12-20', 'POS Purchase CHOICE AUTO ELECTRIC REPAIRED D', 137.35, None),
    ('2013-12-20', 'ABM Withdrawal', 202.00, None),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 VISA', 425.00, None),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 MCARD', 175.00, None),
    ('2013-12-20', 'POS Purchase TOYS R US #8357 RED D', 145.87, None),
    ('2013-12-20', 'POS Purchase CENTEX DEERPARK/C-STOR RED D', 61.00, None),
    ('2013-12-20', 'Service Charge', 1.50, None),
    ('2013-12-20', 'Insurance EQUITY PREMIUM FINANCE INC', 1157.94, None),
    ('2013-12-20', 'ABM Withdrawal', 201.85, None),
    ('2013-12-20', 'Service Charge', 1.50, None),
    ('2013-12-20', 'POS Purchase PART SOURCE #7191 RED D', 32.93, None),
    
    # December 23
    ('2013-12-23', 'POS Purchase SHOPPERS DRUG MART #24 RED D', 77.96, None),
    ('2013-12-23', 'Cheque 287', 300.00, None),
    ('2013-12-23', 'POS Purchase CANADA SAFEWAY #813 RED D', 300.00, None),
    ('2013-12-23', 'POS Purchase FAS GAS WESTPARK SVC # RED D', 77.50, None),
    ('2013-12-23', 'POS Purchase PETRO-CANADA RED D', 170.02, None),
    ('2013-12-23', 'POS Purchase CANADIAN TIRE #235 EDMON', 64.38, None),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', 2654.01, None),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', 2691.04, None),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 MCARD', 255.58, None),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', 2105.07, None),
    
    # December 24
    ('2013-12-24', 'Cheque 283', 1260.00, None),
    ('2013-12-24', 'Cheque 284', 500.00, None),
    ('2013-12-24', 'Cheque 286', 519.75, None),
    ('2013-12-24', 'Merchant Deposit Credit 566756800000 00001 VISA', 4333.94, None),
    
    # December 27
    ('2013-12-27', 'Cheque 266', 383.22, None),
    ('2013-12-27', 'Cheque 290', 1500.00, None),
    ('2013-12-27', 'Bill Payment PC-CAPITAL ONE MASTERCARD 00386192', 500.00, None),
    ('2013-12-27', 'Bill Payment PC-CAPITAL ONE MASTERCARD 00713058', 500.00, None),
    ('2013-12-27', 'Bill Payment PC-TELUS MOBILITYMOBILITE 38713050', 121.79, None),
    ('2013-12-27', 'Bill Payment PC-WORKERS COMP BOARD ALBERTA 38703318', None, 1124.23),
    ('2013-12-27', 'Bill Payment PC-TELUS COMMUNICATIONS 38703312', 1665.63, None),
    ('2013-12-27', 'Bill Payment PC-TELUS COMMUNICATIONS 38703307', 378.35, None),
    ('2013-12-27', 'Bill Payment PC-TELUS COMMUNICATIONS 38703303', 1077.45, None),
    ('2013-12-27', 'Bill Payment PC-ROGERS WIRELESS SERVICES 38703302', 740.17, None),
    ('2013-12-27', 'POS Purchase RUNN ON EMPTY 50AVOPE RED D', 29.00, None),
    ('2013-12-27', 'ABM Withdrawal', 200.00, None),
    ('2013-12-27', 'Miscellaneous Payment AMEX BANK OF CANADA', 611.18, None),
    ('2013-12-27', 'Merchant Deposit Credit 566756800000 00001 MCARD', 206.00, None),
    ('2013-12-27', 'Deposit', 1757.25, None),
    
    # December 30
    ('2013-12-30', 'Service Charge', 112.50, None),
    ('2013-12-30', 'Debit Memo MONEY ORDER PURCHASE', 405.66, None),
    ('2013-12-30', 'ABM Withdrawal', 700.00, None),
    ('2013-12-30', 'ABM Withdrawal', 1000.00, None),
    ('2013-12-30', 'ABM Withdrawal', 1000.00, None),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 VISA', 420.00, None),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 MCARD', 1960.05, None),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 MCARD', 98.20, None),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 VISA', 1026.18, None),
    ('2013-12-30', 'Deposit', 3155.00, None),
    ('2013-12-30', 'Bill Payment PC-SCOTIABANK VALUE VISA 39813660', 600.00, None),
    ('2013-12-30', 'Service Charge', 7.50, None),
    
    # December 31
    ('2013-12-31', 'Overdraft Charge', 5.23, None),
    ('2013-12-31', 'Service Charge', 112.50, None),
    ('2013-12-31', 'Cheque 289', 492.26, None),
    ('2013-12-31', 'Cheque 288', 1706.25, None),
    ('2013-12-31', 'Debit Memo OTHER', 1200.00, None),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 VISA', 1868.50, None),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 MCARD', 830.00, None),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 67.52, None),
    ('2013-12-31', 'Deposit', 63324.91, None),
]

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def generate_hash(date_str, description, amount):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date_str}|{description}|{amount}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    print("\n" + "="*80)
    print("IMPORT SCOTIA BANK DECEMBER 2013 COMPLETE BANK STATEMENT")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    print(f"Total transactions: {len(SCOTIA_DEC_2013_STATEMENT)}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check existing data
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-12-01' 
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    existing_count = cur.fetchone()[0]
    
    print(f"\nExisting Dec 2013 Scotia transactions in DB: {existing_count}")
    
    # Load existing hashes to prevent duplicates
    cur.execute("""
        SELECT source_hash FROM banking_transactions
        WHERE account_number = %s
        AND source_hash IS NOT NULL
    """, (ACCOUNT,))
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    print(f"Loaded {len(existing_hashes)} existing transaction hashes")
    
    # Prepare transactions
    to_import = []
    skipped = []
    
    for txn_date, description, debit, credit in SCOTIA_DEC_2013_STATEMENT:
        amount = debit if debit else credit
        source_hash = generate_hash(txn_date, description, amount)
        
        if source_hash in existing_hashes:
            skipped.append((txn_date, description, amount))
        else:
            to_import.append((txn_date, description, debit, credit, source_hash))
    
    print(f"\nTo import: {len(to_import)} NEW transactions")
    print(f"Skipped (already in DB): {len(skipped)}")
    
    if len(to_import) == 0:
        print("\n[OK] No new transactions to import - database already complete!")
        cur.close()
        conn.close()
        return
    
    # Calculate totals
    total_debits = sum(t[2] for t in to_import if t[2])
    total_credits = sum(t[3] for t in to_import if t[3])
    
    print(f"\nNew transaction totals:")
    print(f"Total debits: ${total_debits:,.2f}")
    print(f"Total credits: ${total_credits:,.2f}")
    print(f"Net change: ${total_credits - total_debits:+,.2f}")
    
    if DRY_RUN:
        print("\n[DRY RUN] No changes applied to database.")
        print("Run with --write flag to apply changes.")
        cur.close()
        conn.close()
        return
    
    # Import transactions
    print("\n" + "="*80)
    print("IMPORTING TRANSACTIONS...")
    print("="*80)
    
    imported = 0
    for txn_date, description, debit, credit, source_hash in to_import:
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number, transaction_date, description,
                debit_amount, credit_amount, source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (ACCOUNT, txn_date, description, debit, credit, source_hash))
        imported += 1
    
    conn.commit()
    print(f"\n[SUCCESS] Imported {imported} new transactions")
    
    # Final verification
    cur.execute("""
        SELECT COUNT(*), 
               SUM(debit_amount), 
               SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    total_count, total_debits_db, total_credits_db = cur.fetchone()
    
    print(f"\n{'='*80}")
    print(f"FINAL DECEMBER 2013 TOTALS")
    print(f"{'='*80}")
    print(f"Total transactions: {total_count}")
    print(f"Total debits: ${float(total_debits_db or 0):,.2f}")
    print(f"Total credits: ${float(total_credits_db or 0):,.2f}")
    print(f"Net change: ${float(total_credits_db or 0) - float(total_debits_db or 0):+,.2f}")
    
    print(f"\nExpected from statement: $59,578.37 debits, $70,463.81 credits")
    debit_diff = abs(float(total_debits_db or 0) - 59578.37)
    credit_diff = abs(float(total_credits_db or 0) - 70463.81)
    print(f"Variance: ${debit_diff:.2f} debits, ${credit_diff:.2f} credits")
    
    if debit_diff < 1.00 and credit_diff < 1.00:
        print("\n✅ PERFECT MATCH - Complete coverage achieved!")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
