"""
Import Scotia Bank February-March 2013 batch 4 transactions from screenshots.
Covers Feb 21 - March 4, 2013.
"""

import psycopg2
import hashlib
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def generate_hash(date, description, withdrawal, deposit):
    hash_input = f"{date}|{description}|{withdrawal:.2f}|{deposit:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def extract_vendor(description):
    desc = description.upper().strip()
    prefixes = ['POINT OF SALE PURCHASE', 'DEPOSIT', 'CHQ', 'CHEQUE', 'ABM WITHDRAWAL', 
                'RENT/LEASES', 'PC BILL PAYMENT', 'OVERDRAWN HANDLING CHGS', 'AUTO LEASE',
                'SERVICE CHARGE', 'OVERDRAFT INTEREST CHG', 'MISC PAYMENT', 'AUTO INSURANCE',
                'IFS PREMIUM FIN', 'ERROR CORRECTION', 'DEBIT MEMO', 'PC-EMAIL MONEY TRF']
    for prefix in prefixes:
        if desc.startswith(prefix):
            desc = desc[len(prefix):].strip()
            break
    desc = desc.replace('RED DEER AB', '').replace('RED DEER ABCA', '').replace('RED DEER ABCD', '')
    return desc.strip()[:50] if desc.strip() else 'UNKNOWN'

transactions = [
    # Screenshot 1 - Feb 21-24
    ('2013-02-21', 'BALANCE FORWARD', 0.00, 0.00, 17415.605),
    ('2013-02-21', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 100.01, 0.00, 17315.595),
    ('2013-02-21', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 407.76, 17723.355),
    ('2013-02-21', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 287.25, 18010.605),
    ('2013-02-21', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1777.88, 19788.485),
    ('2013-02-21', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 82.69, 19871.175),
    ('2013-02-21', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1250.00, 21121.175),
    ('2013-02-21', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', 559.70, 0.00, 20561.475),
    ('2013-02-21', 'AUTO INSURANCE JEVCO INSURANCE COMPANY INSURANCE', 726.29, 0.00, 19835.185),
    ('2013-02-21', 'IFS PREMIUM FIN CHQ 203 5000464420', 2383.24, 0.00, 17451.945),
    ('2013-02-21', 'POINT OF SALE PURCHASE FAS GAS LAKEVIEW SVC # SYLVAN LAKEABCA', 209.504, 0.00, 17242.441),
    ('2013-02-21', 'POINT OF SALE PURCHASE HUSKY DOWNTOWN #6795 RED DEER ABCA', 53.77, 0.00, 17188.671),
    ('2013-02-21', 'POINT OF SALE PURCHASE UPTOWN LIQUOR STORE RED DEER ABCA', 154.79, 0.00, 17033.881),
    ('2013-02-21', 'POINT OF SALE PURCHASE WINDFIELD SURGEONS RED DEER ABCA', 156.75, 0.00, 16877.131),
    ('2013-02-21', 'POINT OF SALE PURCHASE PET PLANET - RED DEER RED DEER ABCD', 420.00, 0.00, 16457.131),
    ('2013-02-21', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 45.14, 0.00, 16411.991),
    ('2013-02-21', 'OVERDRAWN HANDLING CHGS', 150.02, 0.00, 16261.971),
    
    # Screenshot 2 - Feb 24-26
    ('2013-02-24', 'BALANCE FORWARD', 0.00, 0.00, 16261.971),
    ('2013-02-24', 'DEPOSIT GAETZ AND 67TH STREET 51409 002', 0.00, 1202.76, 17464.731),
    ('2013-02-24', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 500.00, 17964.731),
    ('2013-02-24', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1265.25, 19229.981),
    ('2013-02-25', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', 667.78, 0.00, 18562.201),
    ('2013-02-25', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', 75.27, 0.00, 18486.931),
    ('2013-02-25', 'ERROR CORRECTION CHQ 8XX 3700968633', 166.11, 0.00, 18320.821),
    ('2013-02-25', 'CHQ 204 3700148838', 600.00, 0.00, 17720.821),
    ('2013-02-25', 'POINT OF SALE PURCHASE MOHAWK RED DEER #4320 RED DEER ABCA', 131.75, 0.00, 17589.071),
    ('2013-02-25', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 74.90, 0.00, 17514.171),
    ('2013-02-25', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 172.20, 0.00, 17341.971),
    ('2013-02-25', 'POINT OF SALE PURCHASE NORTHLAND RADIATOR RED DEER ABCD', 1198.47, 0.00, 16143.501),
    ('2013-02-25', 'DEBIT MEMO 44472367', 500.00, 0.00, 15643.501),
    ('2013-02-26', 'PC-EMAIL MONEY TRF SERVICE CHARGE', 1.00, 0.00, 15642.501),
    ('2013-02-26', 'PC-EMAIL MONEY TRF DEPOSIT', 0.00, 391.850, 16034.351),
    ('2013-02-26', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 527.71, 16562.061),
    ('2013-02-27', 'POINT OF SALE PURCHASE WAL-MART #3075 RED DEER ABCA', 89.50, 0.00, 16472.561),
    
    # Screenshot 3 - Feb 27-28
    ('2013-02-27', 'BALANCE FORWARD', 0.00, 0.00, 16472.561),
    ('2013-02-27', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 70.00, 0.00, 16402.561),
    ('2013-02-27', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 511.60, 16914.161),
    ('2013-02-27', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 375.00, 17289.161),
    ('2013-02-27', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1812.43, 19101.591),
    ('2013-02-27', 'POINT OF SALE PURCHASE SAVE ON FOODS #6682 RED DEER ABCA', 61.60, 0.00, 19039.991),
    ('2013-02-27', 'POINT OF SALE PURCHASE BUCK OR TWO #235 RED DEER ABCA', 75.60, 0.00, 18964.391),
    ('2013-02-27', 'POINT OF SALE PURCHASE RED DEER REGISTRIES RED DEER ABCA', 591.00, 0.00, 18373.391),
    ('2013-02-28', 'SERVICE CHARGE', 112.50, 0.00, 18260.891),
    ('2013-02-28', 'OVERDRAFT INTEREST CHG', 5.21, 0.00, 18255.681),
    
    # Screenshot 4 - Feb 28 - March 1
    ('2013-02-28', 'BALANCE FORWARD', 0.00, 0.00, 18255.681),
    ('2013-02-28', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 1807.00, 20062.681),
    ('2013-02-28', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 744.50, 20807.181),
    ('2013-02-28', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 574.14, 21381.321),
    ('2013-02-28', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 355.00, 21736.321),
    ('2013-02-28', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1201.25, 22937.571),
    ('2013-02-28', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 158.79, 23096.361),
    ('2013-02-28', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 3510.11, 26606.471),
    ('2013-02-28', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 526.25, 27132.721),
    ('2013-02-28', 'RENT/LEASES A0001<DEFTPYMT> ACE TRUCK RENTALS LTD.', 269.40, 0.00, 26863.321),
    ('2013-02-28', 'AUTO LEASE HEFFNER AUTO FC', 889.87, 0.00, 25973.451),
    ('2013-02-28', 'AUTO LEASE HEFFNER AUTO FC', 471.98, 0.00, 25501.471),
    ('2013-02-28', 'CHQ 205 3700471526', 1500.00, 0.00, 24001.471),
    ('2013-02-28', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCA', 83.80, 0.00, 23917.671),
    ('2013-02-28', 'POINT OF SALE PURCHASE RED DEER CO-OP TAYLOR RED DEER ABCA', 194.83, 0.00, 23722.841),
    ('2013-03-02', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 70.35, 0.00, 23652.491),
    
    # Screenshot 5 - March 2-4
    ('2013-03-02', 'BALANCE FORWARD', 0.00, 0.00, 23652.491),
    ('2013-03-02', 'DEPOSIT 087384700019 00001 VISA DEP DR CHASE PAYMENTECH', 652.81, 0.00, 22999.681),
    ('2013-03-02', 'DEPOSIT 097384700019 00001 MCARD FEE DR CHASE PAYMENTECH', 402.92, 0.00, 22596.761),
    ('2013-03-02', 'DEBIT MEMO 53461299', 200.00, 0.00, 22396.761),
    ('2013-03-02', 'PC-EMAIL MONEY TRF DEBIT MEMO 54056165', 100.00, 0.00, 22296.761),
    ('2013-03-02', 'PC-EMAIL MONEY TRF DEBIT MEMO 55000050', 600.00, 0.00, 21696.761),
    ('2013-03-02', 'PC-EMAIL MONEY TRF SERVICE CHARGE', 1.00, 0.00, 21695.761),
    ('2013-03-02', 'PC-EMAIL MONEY TRF SERVICE CHARGE', 1.00, 0.00, 21694.761),
    ('2013-03-02', 'PC-EMAIL MONEY TRF SERVICE CHARGE', 1.00, 0.00, 21693.761),
    ('2013-03-02', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 362.343, 22056.104),
    ('2013-03-02', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 989.61, 23045.714),
    ('2013-03-02', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 389.99, 23435.704),
    ('2013-03-03', 'CHQ 207 3700049340', 1666.11, 0.00, 21769.594),
    ('2013-03-03', 'CHQ 206 3700082625', 100.00, 0.00, 21669.594),
    ('2013-03-03', 'POINT OF SALE PURCHASE WINDSHIELD SURGEONS RED DEER ABCA', 211.525, 0.00, 21458.069),
    ('2013-03-03', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 122.75, 21580.819),
    ('2013-03-04', 'CHQ 208 3700132226', 562.50, 0.00, 21018.319),
    ('2013-03-04', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 426.00, 21444.319),
    ('2013-03-04', 'POINT OF SALE PURCHASE CANADA SAFEWAY #813 RED DEER ABCA', 15.56, 0.00, 21428.759),
]

def main():
    parser = argparse.ArgumentParser(description='Import Scotia Feb-Mar 2013 batch 4')
    parser.add_argument('--write', action='store_true', help='Apply to database')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2013-02-21'
        AND transaction_date < '2013-03-05'
    """)
    existing = {(row[0], row[1], row[2] or 0, row[3] or 0) for row in cur.fetchall()}
    
    print(f"\nScotia Bank February-March 2013 Batch 4 Import")
    print(f"{'='*80}")
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print(f"Existing transactions (Feb 21-Mar 4): {len(existing)}")
    print(f"Transactions to process: {len(transactions)}")
    print()
    
    imported = 0
    skipped = 0
    
    for date_str, desc, withdrawal, deposit, balance in transactions:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        key = (date, desc, withdrawal, deposit)
        
        if key in existing:
            skipped += 1
            continue
        
        source_hash = generate_hash(date, desc, withdrawal, deposit)
        vendor = extract_vendor(desc)
        
        if args.write:
            cur.execute("SELECT 1 FROM banking_transactions WHERE source_hash = %s", (source_hash,))
            if cur.fetchone():
                skipped += 1
                continue
            
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount, balance,
                    vendor_extracted, source_hash, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, ('903990106011', date, desc,
                  withdrawal if withdrawal > 0 else None,
                  deposit if deposit > 0 else None,
                  balance, vendor, source_hash))
            imported += 1
        else:
            print(f"{date_str} | {desc[:50]:50} | W:{withdrawal:>8.2f} D:{deposit:>8.2f}")
            imported += 1
    
    if args.write:
        conn.commit()
        print(f"\n✓ Imported {imported} transactions")
        print(f"✓ Skipped {skipped} duplicates")
    else:
        print(f"\nDRY-RUN: Would import {imported} new transactions")
        print(f"         Would skip {skipped} duplicates")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
