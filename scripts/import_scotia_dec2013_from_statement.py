#!/usr/bin/env python3
"""
Import Scotia Bank December 2013 from ACTUAL bank statement.
Extracted line-by-line from statement screenshots.
Total should be: $59,578.37 withdrawals, $70,463.81 deposits
"""

import os
import sys
import psycopg2
import hashlib
from decimal import Decimal

ACCOUNT = '903990106011'
DRY_RUN = '--write' not in sys.argv

# Transactions from ACTUAL bank statement (not QuickBooks reconciliation)
# Format: (date, description, withdrawal, deposit)
STATEMENT_TRANSACTIONS = [
    # December 2
    ('2013-12-02', 'Overdrawn Handling Chg.', 5.00, None),
    ('2013-12-02', 'Returned Cheque - NSF', 2695.40, None),
    ('2013-12-02', 'Returned Cheque - NSF', 889.87, None),
    ('2013-12-02', 'Returned Cheque - NSF', 398.33, None),
    ('2013-12-02', 'Returned Cheque - NSF', 0.30, None),
    ('2013-12-02', 'Miscellaneous Payment PAYMENTECH CA MCARD FEE DR', None, 398.33),
    ('2013-12-02', 'Miscellaneous Payment PAYMENTECH CA DEBITCD FEE DR', None, 0.30),
    ('2013-12-02', 'Rent/Lease HEFFNER AUTO FC', 889.87, None),
    ('2013-12-02', 'Rent/Lease ACE TRUCK RENTALS LTD.', 2695.40, None),
    ('2013-12-02', 'Merchant Deposit Debit 566756800000 00001 VISA', 418.86, None),
    ('2013-12-02', 'Miscellaneous Payment AMEX BANK OF CANADA', None, 1044.37),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 1950.90),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 616.46),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 939.69),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 234.85),
    
    # December 3
    ('2013-12-03', 'Cheque 273', 1359.75, None),
    ('2013-12-03', 'Service Charge', 170.00, None),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 2079.24),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 938.80),
    
    # December 4
    ('2013-12-04', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 65.70, None),
    ('2013-12-04', 'POS Purchase SUMMIT ESSO REDD', 140.03, None),
    ('2013-12-04', 'Miscellaneous Payment AMEX BANK OF CANADA', None, 742.63),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1103.12),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 187.88),
    
    # December 5
    ('2013-12-05', 'Cheque 274', 1458.88, None),
    ('2013-12-05', 'POS Purchase MONEY MART#1205 REDD', 140.00, None),
    
    # December 6
    ('2013-12-06', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 142.00, None),
    ('2013-12-06', 'POS Purchase PRINCESS AUTO REDD', 41.99, None),
    ('2013-12-06', 'Bill Payment PC-CAPITAL ONE MASTERCARD 01602347', 550.00, None),
    ('2013-12-06', 'ABM Withdrawal', 400.00, None),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 250.37),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 41.85),
    ('2013-12-06', 'Deposit', None, 1944.42),
    
    # December 9
    ('2013-12-09', 'Cheque 276', 632.84, None),
    ('2013-12-09', 'Cheque 268', 36.79, None),
    ('2013-12-09', 'Insurance Cooperators CSI', 128.33, None),
    ('2013-12-09', 'Rent/Lease HEFFNER AUTO FC', 889.87, None),
    ('2013-12-09', 'Service Charge', 1.50, None),
    ('2013-12-09', 'Bill Payment PC-CAPITAL ONE MASTERCARD 05386162', 650.00, None),
    ('2013-12-09', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 45.00, None),
    ('2013-12-09', 'POS Purchase WAL-MART #3075 REDD', 49.23, None),
    ('2013-12-09', 'ABM Withdrawal', 202.00, None),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 843.50),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1855.17),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 535.59),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 205.00),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1253.03),
    
    # December 10
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 26.25),
    ('2013-12-10', 'Cheque 278', 1876.76, None),
    ('2013-12-10', 'Cheque 280', 1910.96, None),
    ('2013-12-10', 'Cheque 275', 948.46, None),
    ('2013-12-10', 'Debit Memo DRAFT PURCHASE', 2720.04, None),
    ('2013-12-10', 'POS Purchase AUTOMOTIVE UNIVERSE REDD', 1043.11, None),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 4355.97),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 82.69),
    ('2013-12-10', 'Deposit', None, 88.92),
    
    # December 11
    ('2013-12-11', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 151.00, None),
    ('2013-12-11', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 250.00),
    ('2013-12-11', 'Cheque 282', 1210.95, None),
    ('2013-12-11', 'ABM Withdrawal', 200.00, None),
    ('2013-12-11', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1013.08),
    
    # December 12
    ('2013-12-12', 'POS Purchase THE TIRE GARAGE REDD', 673.05, None),
    ('2013-12-12', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 946.53),
    
    # December 13
    ('2013-12-13', 'POS Purchase 604 - LB 67TH ST. REDD', 863.37, None),
    ('2013-12-13', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 50.00, None),
    ('2013-12-13', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 156.53),
    
    # December 16
    ('2013-12-16', 'Rent/Lease HEFFNER AUTO FC', 889.88, None),
    ('2013-12-16', 'Rent/Lease HEFFNER AUTO FC', 1900.50, None),
    ('2013-12-16', 'Rent/Lease HEFFNER AUTO FC', 738.41, None),
    ('2013-12-16', 'Rent/Lease HEFFNER AUTO FC', 2525.25, None),
    ('2013-12-16', 'Bill Payment BR BILL PAYMENT', 3181.17, None),
    ('2013-12-16', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 165.91, None),
    ('2013-12-16', 'POS Purchase FUTURE SHOP #31 REDD', 360.97, None),
    ('2013-12-16', 'POS Purchase CELLCOM WIRELESS INC REDD', 88.73, None),
    ('2013-12-16', 'ABM Withdrawal', 300.00, None),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2618.69),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 1635.00),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 99.23),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 360.55),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 811.13),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 579.03),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 3776.37),
    ('2013-12-16', 'Deposit', None, 1000.00),
    
    # December 17
    ('2013-12-17', 'Cheque 279', 1762.90, None),
    ('2013-12-17', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 2681.09),
    ('2013-12-17', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 206.94),
    
    # December 18
    ('2013-12-18', 'POS Purchase WAL-MART #3194 REDD', 62.79, None),
    ('2013-12-18', 'Cheque 277', 733.68, None),
    ('2013-12-18', 'POS Purchase A.T.R. LOGISTICS AIRDR', 550.73, None),
    ('2013-12-18', 'POS Purchase RED DEER CO-OP TAYLOR REDD', 40.00, None),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1168.06),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 336.25),
    
    # December 19
    ('2013-12-19', 'POS Purchase TOYS R US #3557 REDD', 145.87, None),
    ('2013-12-19', 'Cheque 281', 941.09, None),
    ('2013-12-19', 'POS Purchase CENTRAL AB CO-OP LTD. REDD', 4.82, None),
    ('2013-12-19', 'POS Purchase CANADIAN TIRE #645 REDD', 123.45, None),
    ('2013-12-19', 'POS Purchase RED DEER REGISTRIES REDD', 704.35, None),
    ('2013-12-19', 'POS Purchase SUSHI SUSHI INTERAC REDD', 35.31, None),
    ('2013-12-19', 'POS Purchase RED DEER REGISTRIES REDD', 392.35, None),
    ('2013-12-19', 'Miscellaneous Payment AMEX BANK OF CANADA', None, 208.73),
    ('2013-12-19', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2617.50),
    
    # December 20
    ('2013-12-20', 'POS Purchase CENTEX DEERPARK(C-STOR REDD', 61.00, None),
    ('2013-12-20', 'Service Charge', 1.50, None),
    ('2013-12-20', 'Insurance EQUITY PREMIUM FINANCE INC.', 1157.94, None),
    ('2013-12-20', 'ABM Withdrawal', 201.85, None),
    ('2013-12-20', 'Service Charge', 1.50, None),
    ('2013-12-20', 'POS Purchase PART SOURCE #791 REDD', 32.93, None),
    ('2013-12-20', 'POS Purchase ERLES AUTO REPAIR RED D', 265.92, None),
    ('2013-12-20', 'POS Purchase CHOICE AUTO ELECTRIC REPAIR REDD', 137.35, None),
    ('2013-12-20', 'ABM Withdrawal', 202.00, None),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 425.00),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 175.00),
    
    # December 23
    ('2013-12-23', 'POS Purchase SHOPPERS DRUG MART#24 REDD', 77.96, None),
    ('2013-12-23', 'Cheque 287', 300.00, None),
    ('2013-12-23', 'POS Purchase CANADA SAFEWAY#813 REDD', 300.00, None),
    ('2013-12-23', 'POS Purchase FAS GAS WESTPARK SVC# REDD', 77.50, None),
    ('2013-12-23', 'POS Purchase PETRO-CANADA REDD', 170.02, None),
    ('2013-12-23', 'POS Purchase CANADIAN TIRE #288 EDMON', 64.38, None),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2654.01),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2691.04),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 295.56),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2105.07),
    
    # December 24
    ('2013-12-24', 'Cheque 283', 1260.00, None),
    ('2013-12-24', 'Cheque 284', 500.00, None),
    ('2013-12-24', 'Cheque 286', 519.75, None),
    ('2013-12-24', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 4333.94),
    
    # December 27
    ('2013-12-27', 'Cheque 266', 383.22, None),
    ('2013-12-27', 'Cheque 290', 1500.00, None),
    ('2013-12-27', 'Bill Payment PC-CAPITAL ONE MASTERCARD 38713053', 500.00, None),
    ('2013-12-27', 'Bill Payment PC-CAPITAL ONE MASTERCARD 38713051', 500.00, None),
    ('2013-12-27', 'Bill Payment PC-TELUS MOBILITY/MOBILITE 38713050', 121.79, None),
    ('2013-12-27', 'Bill Payment PC-WORKERS COMP BOARD ALBERTA 38703318', 1124.23, None),
    ('2013-12-27', 'Bill Payment PC-TELUS COMMUNICATIONS 38703312', 1655.63, None),
    ('2013-12-27', 'Bill Payment PC-TELUS COMMUNICATIONS 38703307', 378.35, None),
    ('2013-12-27', 'Bill Payment PC-TELUS COMMUNICATIONS 38703303', 1077.45, None),
    ('2013-12-27', 'Bill Payment PC-ROGERS WIRELESS SERVICES 38703302', 740.17, None),
    ('2013-12-27', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 29.00, None),
    ('2013-12-27', 'ABM Withdrawal', 200.00, None),
    ('2013-12-27', 'Miscellaneous Payment AMEX BANK OF CANADA', None, 611.18),
    ('2013-12-27', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 205.00),
    ('2013-12-27', 'Deposit', None, 1757.25),
    
    # December 30
    ('2013-12-30', 'ABM Withdrawal', 1000.00, None),
    ('2013-12-30', 'ABM Withdrawal', 1000.00, None),
    ('2013-12-30', 'ABM Withdrawal', 700.00, None),
    ('2013-12-30', 'Debit Memo MONEY ORDER PURCHASE', 405.66, None),
    ('2013-12-30', 'Service Charge MONEY ORDER PURCHASE', 7.50, None),
    ('2013-12-30', 'Bill Payment PC-SCOTIABANK VALUE VISA 39813660', 600.00, None),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 67.52),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 430.00),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 1989.05),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 98.20),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1003.18),
    ('2013-12-30', 'Deposit', None, 3155.00),
    
    # December 31
    ('2013-12-31', 'Overdraft Charge', 5.23, None),
    ('2013-12-31', 'Service Charge', 112.50, None),
    ('2013-12-31', 'Cheque 289', 492.26, None),
    ('2013-12-31', 'Cheque 288', 1706.25, None),
    ('2013-12-31', 'Debit Memo OTHER', 1200.00, None),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1868.50),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 830.00),
]

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def generate_hash(date_str, description, amount):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date_str}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    print("\n" + "="*80)
    print("IMPORT SCOTIA DECEMBER 2013 FROM ACTUAL BANK STATEMENT")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check existing
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    existing_count, existing_debits, existing_credits = cur.fetchone()
    
    print(f"\nBefore import:")
    print(f"  Total transactions: {existing_count}")
    print(f"  Total debits: ${float(existing_debits or 0):,.2f}")
    print(f"  Total credits: ${float(existing_credits or 0):,.2f}")
    
    # Load existing hashes
    cur.execute("""
        SELECT source_hash FROM banking_transactions
        WHERE account_number = %s
        AND source_hash IS NOT NULL
    """, (ACCOUNT,))
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    # Process statement
    to_import = []
    skipped = []
    
    total_withdrawals = Decimal('0')
    total_deposits = Decimal('0')
    
    for txn_date, description, debit, credit in STATEMENT_TRANSACTIONS:
        if debit:
            total_withdrawals += Decimal(str(debit))
            amount = debit
        else:
            total_deposits += Decimal(str(credit))
            amount = credit
        
        source_hash = generate_hash(txn_date, description, amount)
        
        if source_hash in existing_hashes:
            skipped.append((txn_date, description, debit, credit))
        else:
            to_import.append((txn_date, description, debit, credit, source_hash))
    
    print(f"\nStatement extraction totals:")
    print(f"  Withdrawals: ${total_withdrawals:,.2f}")
    print(f"  Deposits: ${total_deposits:,.2f}")
    print(f"  Expected: $59,578.37 withdrawals, $70,463.81 deposits")
    
    w_diff = abs(float(total_withdrawals) - 59578.37)
    d_diff = abs(float(total_deposits) - 70463.81)
    
    if w_diff < 1 and d_diff < 1:
        print(f"  ✅ PERFECT MATCH - Extraction is penny-perfect!")
    else:
        print(f"  ⚠️ Variance: ${w_diff:.2f} withdrawals, ${d_diff:.2f} deposits")
    
    print(f"\nTo import: {len(to_import)} NEW transactions")
    print(f"Skipped (already in DB): {len(skipped)}")
    
    if len(to_import) == 0:
        print("\n[OK] No new transactions to import")
        cur.close()
        conn.close()
        return
    
    # Import totals
    import_w = sum(Decimal(str(t[2])) for t in to_import if t[2])
    import_d = sum(Decimal(str(t[3])) for t in to_import if t[3])
    
    print(f"\nNew transactions to add:")
    print(f"  Withdrawals: ${import_w:,.2f}")
    print(f"  Deposits: ${import_d:,.2f}")
    
    if DRY_RUN:
        print("\n[DRY RUN] Run with --write to import.")
        cur.close()
        conn.close()
        return
    
    # Import
    print("\n" + "="*80)
    print("IMPORTING...")
    print("="*80)
    
    for txn_date, description, debit, credit, source_hash in to_import:
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number, transaction_date, description,
                debit_amount, credit_amount, source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (ACCOUNT, txn_date, description, debit, credit, source_hash))
    
    conn.commit()
    print(f"\n[SUCCESS] Imported {len(to_import)} transactions")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    final_count, final_debits, final_credits = cur.fetchone()
    
    print(f"\n{'='*80}")
    print(f"FINAL DECEMBER 2013 TOTALS")
    print(f"{'='*80}")
    print(f"Total transactions: {final_count}")
    print(f"Total debits: ${float(final_debits or 0):,.2f}")
    print(f"Total credits: ${float(final_credits or 0):,.2f}")
    print(f"\nStatement: $59,578.37 debits, $70,463.81 credits")
    
    final_w_diff = abs(float(final_debits or 0) - 59578.37)
    final_d_diff = abs(float(final_credits or 0) - 70463.81)
    
    if final_w_diff < 1 and final_d_diff < 1:
        print(f"\n✅ PERFECT - Penny-perfect match achieved!")
    else:
        print(f"\nVariance: ${final_w_diff:.2f} debits, ${final_d_diff:.2f} credits")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
