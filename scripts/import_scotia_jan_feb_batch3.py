"""
Import Scotia Bank January-February 2013 batch 3 transactions from screenshots.
Covers Feb 3-21, 2013.
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
                'SERVICE CHARGE', 'OVERDRAFT INTEREST CHG', 'MISC PAYMENT', 'RETURNED NSF CHEQUE']
    for prefix in prefixes:
        if desc.startswith(prefix):
            desc = desc[len(prefix):].strip()
            break
    desc = desc.replace('RED DEER AB', '').replace('RED DEER ABCA', '').replace('RED DEER ABCD', '').replace('RED DEER ABCD', '')
    return desc.strip()[:50] if desc.strip() else 'UNKNOWN'

transactions = [
    # Screenshot 1 - Feb 3-7
    ('2013-02-03', 'BALANCE FORWARD', 0.00, 0.00, 8731.00),
    ('2013-02-03', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 380.00, 9111.00),
    ('2013-02-03', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 406.00, 9517.00),
    ('2013-02-04', 'DEPOSIT 087384700019 00001 VISA DEP DR CHASE PAYMENTECH', 463.52, 0.00, 9053.48),
    ('2013-02-04', 'DEPOSIT 097384700019 00001 MCARD FEE DR CHASE PAYMENTECH', 335.46, 0.00, 8718.02),
    ('2013-02-04', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 675.00, 9393.02),
    ('2013-02-04', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 1675.00, 11068.02),
    ('2013-02-04', 'CHQ 193 3700484553', 745.77, 0.00, 10322.25),
    ('2013-02-04', 'CHQ 191 3900424013', 1960.86, 0.00, 8361.39),
    ('2013-02-04', 'POINT OF SALE PURCHASE HMV #723 RED DEER ABCA', 81.88, 0.00, 8279.51),
    ('2013-02-04', 'POINT OF SALE PURCHASE CINEPLEX #3132 QPS RED DEER ABCD', 31.01, 0.00, 8248.50),
    ('2013-02-04', 'POINT OF SALE PURCHASE MOHAWK RED DEER #4320 RED DEER ABCA', 74.00, 0.00, 8174.50),
    ('2013-02-05', 'OVERDRAWN HANDLING CHGS', 15.00, 0.00, 8159.50),
    ('2013-02-05', 'DEPOSIT 087384700019 00001 CHQ 192 3700544602', 0.00, 500.00, 8659.50),
    ('2013-02-06', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 240.00, 8899.50),
    ('2013-02-06', 'DEPOSIT 097384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 232.50, 9132.00),
    ('2013-02-07', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 679.00, 9811.00),
    
    # Screenshot 2 - Feb 7-10
    ('2013-02-07', 'BALANCE FORWARD', 0.00, 0.00, 9811.00),
    ('2013-02-07', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 58.01, 0.00, 9752.99),
    ('2013-02-07', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 50.00, 0.00, 9702.99),
    ('2013-02-07', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', 11.73, 0.00, 9691.26),
    ('2013-02-07', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 595.63, 10286.89),
    ('2013-02-07', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 500.00, 10786.89),
    ('2013-02-07', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 2690.46, 13477.35),
    ('2013-02-07', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 3085.75, 16563.10),
    ('2013-02-07', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 207.50, 16770.60),
    ('2013-02-07', 'CHQ 194 3700167676', 520.88, 0.00, 16249.72),
    ('2013-02-07', 'CHQ 187 7800188772', 500.00, 0.00, 15749.72),
    ('2013-02-07', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 157.30, 15907.02),
    ('2013-02-07', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 93.60, 0.00, 15813.42),
    ('2013-02-07', 'POINT OF SALE PURCHASE CANADA SAFEWAY #813 RED DEER ABCA', 110.96, 0.00, 15702.46),
    ('2013-02-07', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', 74.90, 0.00, 15627.56),
    ('2013-02-07', 'POINT OF SALE PURCHASE RED DEER CO-OP QPE RED DEER ABCA', 27.35, 0.00, 15600.21),
    ('2013-02-10', 'POINT OF SALE PURCHASE VILLAGE CHIROPRACTIC', 40.00, 0.00, 15560.21),
    
    # Screenshot 3 - Feb 10-11
    ('2013-02-10', 'BALANCE FORWARD', 0.00, 0.00, 15560.21),
    ('2013-02-10', 'POINT OF SALE PURCHASE MONEY MART #1205 RED DEER ABCA', 674.26, 0.00, 14885.95),
    ('2013-02-10', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 30.00, 0.00, 14855.95),
    ('2013-02-10', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 104.67, 0.00, 14751.28),
    ('2013-02-10', 'PC BILL PAYMENT TELUS COMMUNICATIONS 07066735', 293.218, 0.00, 14458.062),
    ('2013-02-10', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 587.50, 15045.562),
    ('2013-02-10', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 583.00, 15628.562),
    ('2013-02-11', 'CHQ 196 3700214513', 1351.99, 0.00, 14276.572),
    ('2013-02-11', 'CHQ 195 3700279538', 1575.00, 0.00, 12701.572),
    ('2013-02-11', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 175.00, 12876.572),
    ('2013-02-11', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 786.00, 13662.572),
    ('2013-02-12', 'CHQ 199 3700138449', 1000.00, 0.00, 12662.572),
    ('2013-02-12', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 221.01, 0.00, 12441.562),
    ('2013-02-12', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1397.00, 13838.562),
    ('2013-02-13', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 500.00, 14338.562),
    ('2013-02-13', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 288.74, 14627.302),
    ('2013-02-13', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', 470.60, 0.00, 14156.702),
    
    # Screenshot 4 - Feb 14
    ('2013-02-14', 'BALANCE FORWARD', 0.00, 0.00, 14156.702),
    ('2013-02-14', 'CHQ 201 3700510372', 849.84, 0.00, 13306.862),
    ('2013-02-14', 'POINT OF SALE PURCHASE CHOICE AUTO ELECTRIC REPARED DEER ABCD', 361.62, 0.00, 12945.242),
    ('2013-02-14', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 331.25, 13276.492),
    ('2013-02-14', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 2526.00, 15802.492),
    ('2013-02-14', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 504.28, 16306.772),
    ('2013-02-14', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 94.00, 16400.772),
    ('2013-02-14', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 175.00, 16575.772),
    ('2013-02-14', 'ABM WITHDRAWAL GAETZ & 67TH 1 RED DEER AB', 200.00, 0.00, 16375.772),
    ('2013-02-14', 'AUTO LEASE L08136 JACK CARTER', 188.565, 0.00, 16187.207),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', 252.525, 0.00, 15934.682),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', 147.525, 0.00, 15787.157),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', 190.050, 0.00, 15597.107),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', 889.88, 0.00, 14707.227),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', 471.97, 0.00, 14235.257),
    ('2013-02-14', 'CHQ 202 3700007047', 296.351, 0.00, 13938.906),
    ('2013-02-14', 'POINT OF SALE PURCHASE SHOPPERS DRUG MART #24 RED DEER ABCA', 77.96, 0.00, 13860.946),
    ('2013-02-14', 'POINT OF SALE PURCHASE FAS GAS E&STHLL SVC # RED DEER ABCA', 71.00, 0.00, 13789.946),
    ('2013-02-17', 'OVERDRAWN HANDLING CHGS', 25.00, 0.00, 13764.946),
    
    # Screenshot 5 - Feb 17-18
    ('2013-02-17', 'BALANCE FORWARD', 0.00, 0.00, 13764.946),
    ('2013-02-17', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 205.00, 13969.946),
    ('2013-02-17', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 1795.00, 15764.946),
    ('2013-02-18', 'RETURNED NSF CHEQUE', 296.351, 0.00, 15468.595),
    ('2013-02-18', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 108.00, 15576.595),
    ('2013-02-18', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 437.50, 16014.095),
    ('2013-02-18', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 192.50, 16206.595),
    ('2013-02-19', 'SERVICE CHARGE', 42.50, 0.00, 16164.095),
    ('2013-02-19', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 697.06, 16861.155),
    ('2013-02-19', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 115.50, 16976.655),
    ('2013-02-20', 'ABM WITHDRAWAL SHELL', 100.00, 0.00, 16876.655),
    ('2013-02-20', 'POINT OF SALE PURCHASE C00319 MOUNT ROYAL SHE CALGARY ABCA', 55.06, 0.00, 16821.595),
    ('2013-02-20', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1700.00, 18521.595),
    ('2013-02-20', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 205.00, 18726.595),
    ('2013-02-20', 'CHQ 188 3002530025', 500.00, 0.00, 18226.595),
    ('2013-02-20', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 46.51, 0.00, 18180.085),
    ('2013-02-20', 'POINT OF SALE PURCHASE STAPLES#285 RED DEER ABCA', 241.64, 0.00, 17938.445),
    ('2013-02-20', 'POINT OF SALE PURCHASE KISHI SUSHI INTERAC RED DEER ABCA', 11.50, 0.00, 17926.945),
    ('2013-02-21', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER', 511.34, 0.00, 17415.605),
]

def main():
    parser = argparse.ArgumentParser(description='Import Scotia Jan-Feb 2013 batch 3')
    parser.add_argument('--write', action='store_true', help='Apply to database')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2013-02-01'
        AND transaction_date < '2013-03-01'
    """)
    existing = {(row[0], row[1], row[2] or 0, row[3] or 0) for row in cur.fetchall()}
    
    print(f"\nScotia Bank January-February 2013 Batch 3 Import")
    print(f"{'='*80}")
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print(f"Existing Feb transactions: {len(existing)}")
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
            print(f"{date_str} | {desc[:50]:50} | W:{withdrawal:>8.2f} D:{deposit:>8.2f} | Bal:{balance:>10.2f}")
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
