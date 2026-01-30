#!/usr/bin/env python3
"""
Match QuickBooks data to Bank Statement to find orphaned/unmatched transactions.
Uses bank statement as the authoritative source.
"""

import os
import psycopg2
from decimal import Decimal
from difflib import SequenceMatcher

ACCOUNT = '903990106011'

# Bank statement transactions (authoritative)
STATEMENT_TRANSACTIONS = [
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
    ('2013-12-03', 'Cheque 273', 1359.75, None),
    ('2013-12-03', 'Service Charge', 170.00, None),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 2079.24),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 938.80),
    ('2013-12-04', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 65.70, None),
    ('2013-12-04', 'POS Purchase SUMMIT ESSO REDD', 140.03, None),
    ('2013-12-04', 'Miscellaneous Payment AMEX BANK OF CANADA', None, 742.63),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1103.12),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 187.88),
    ('2013-12-05', 'Cheque 274', 1458.88, None),
    ('2013-12-05', 'POS Purchase MONEY MART#1205 REDD', 140.00, None),
    ('2013-12-06', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 142.00, None),
    ('2013-12-06', 'POS Purchase PRINCESS AUTO REDD', 41.99, None),
    ('2013-12-06', 'Bill Payment PC-CAPITAL ONE MASTERCARD 01602347', 550.00, None),
    ('2013-12-06', 'ABM Withdrawal', 400.00, None),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 250.37),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 41.85),
    ('2013-12-06', 'Deposit', None, 1944.42),
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
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 26.25),
    ('2013-12-10', 'Cheque 278', 1876.76, None),
    ('2013-12-10', 'Cheque 280', 1910.96, None),
    ('2013-12-10', 'Cheque 275', 948.46, None),
    ('2013-12-10', 'Debit Memo DRAFT PURCHASE', 2720.04, None),
    ('2013-12-10', 'POS Purchase AUTOMOTIVE UNIVERSE REDD', 1043.11, None),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 4355.97),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 82.69),
    ('2013-12-10', 'Deposit', None, 88.92),
    ('2013-12-11', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 151.00, None),
    ('2013-12-11', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 250.00),
    ('2013-12-11', 'Cheque 282', 1210.95, None),
    ('2013-12-11', 'ABM Withdrawal', 200.00, None),
    ('2013-12-11', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1013.08),
    ('2013-12-12', 'POS Purchase THE TIRE GARAGE REDD', 673.05, None),
    ('2013-12-12', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 946.53),
    ('2013-12-13', 'POS Purchase 604 - LB 67TH ST. REDD', 863.37, None),
    ('2013-12-13', 'POS Purchase RUN\'N ON EMPTY 50AVQPE REDD', 50.00, None),
    ('2013-12-13', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 156.53),
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
    ('2013-12-17', 'Cheque 279', 1762.90, None),
    ('2013-12-17', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 2681.09),
    ('2013-12-17', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 206.94),
    ('2013-12-18', 'POS Purchase WAL-MART #3194 REDD', 62.79, None),
    ('2013-12-18', 'Cheque 277', 733.68, None),
    ('2013-12-18', 'POS Purchase A.T.R. LOGISTICS AIRDR', 550.73, None),
    ('2013-12-18', 'POS Purchase RED DEER CO-OP TAYLOR REDD', 40.00, None),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1168.06),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 336.25),
    ('2013-12-19', 'POS Purchase TOYS R US #3557 REDD', 145.87, None),
    ('2013-12-19', 'Cheque 281', 941.09, None),
    ('2013-12-19', 'POS Purchase CENTRAL AB CO-OP LTD. REDD', 4.82, None),
    ('2013-12-19', 'POS Purchase CANADIAN TIRE #645 REDD', 123.45, None),
    ('2013-12-19', 'POS Purchase RED DEER REGISTRIES REDD', 704.35, None),
    ('2013-12-19', 'POS Purchase SUSHI SUSHI INTERAC REDD', 35.31, None),
    ('2013-12-19', 'POS Purchase RED DEER REGISTRIES REDD', 392.35, None),
    ('2013-12-19', 'Miscellaneous Payment AMEX BANK OF CANADA', None, 208.73),
    ('2013-12-19', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2617.50),
    ('2013-12-20', 'POS Purchase CENTEX DEERPARK(C-STOR REDD', 61.00, None),
    ('2013-12-20', 'Service Charge', 1.50, None),
    ('2013-12-20', 'Insurance EQUITY PREMIUM FINANCE INC.', 1157.94, None),
    ('2013-12-20', 'ABM Withdrawal', 201.85, None),
    ('2013-12-20', 'Service Charge', 1.50, None),
    ('2013-12-20', 'POS Purchase PART SOURCE #791 REDD', 32.93, None),
    ('2013-12-20', 'POS Purchase ERLES AUTO REPAIR REDD', 265.92, None),
    ('2013-12-20', 'POS Purchase CHOICE AUTO ELECTRIC REPAIR REDD', 137.35, None),
    ('2013-12-20', 'ABM Withdrawal', 202.00, None),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 425.00),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 175.00),
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
    ('2013-12-24', 'Cheque 283', 1260.00, None),
    ('2013-12-24', 'Cheque 284', 500.00, None),
    ('2013-12-24', 'Cheque 286', 519.75, None),
    ('2013-12-24', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 4333.94),
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

def fuzzy_match(str1, str2):
    """Return similarity ratio between two strings."""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def main():
    print("\n" + "="*80)
    print("MATCH QUICKBOOKS TO BANK STATEMENT")
    print("="*80)
    print("Bank statement is authoritative source")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Load QuickBooks (database) transactions
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        ORDER BY transaction_date, transaction_id
    """, (ACCOUNT,))
    
    qb_transactions = []
    for txn_id, date, desc, debit, credit in cur.fetchall():
        qb_transactions.append({
            'id': txn_id,
            'date': date.strftime('%Y-%m-%d'),
            'description': desc,
            'debit': float(debit) if debit else 0,
            'credit': float(credit) if credit else 0,
            'matched': False
        })
    
    cur.close()
    conn.close()
    
    print(f"\nBank Statement: {len(STATEMENT_TRANSACTIONS)} transactions")
    print(f"QuickBooks: {len(qb_transactions)} transactions")
    
    # Match statement to QuickBooks
    matched_count = 0
    statement_matched = []
    
    for stmt_date, stmt_desc, stmt_debit, stmt_credit in STATEMENT_TRANSACTIONS:
        stmt_amount = stmt_debit if stmt_debit else stmt_credit
        is_debit = stmt_debit is not None
        
        # Try to find exact match
        best_match = None
        best_score = 0
        
        for qb_txn in qb_transactions:
            if qb_txn['matched']:
                continue
            
            # Check date match
            if qb_txn['date'] != stmt_date:
                continue
            
            # Check amount match (within 1 cent)
            qb_amount = qb_txn['debit'] if is_debit else qb_txn['credit']
            if abs(qb_amount - stmt_amount) > 0.01:
                continue
            
            # Check description similarity
            score = fuzzy_match(stmt_desc, qb_txn['description'])
            if score > best_score:
                best_score = score
                best_match = qb_txn
        
        if best_match and best_score > 0.6:
            best_match['matched'] = True
            matched_count += 1
            statement_matched.append({
                'date': stmt_date,
                'description': stmt_desc,
                'amount': stmt_amount,
                'type': 'W' if is_debit else 'D',
                'qb_match': best_match['description'],
                'score': best_score
            })
    
    # Find unmatched
    unmatched_statement = []
    for stmt_date, stmt_desc, stmt_debit, stmt_credit in STATEMENT_TRANSACTIONS:
        found = False
        for m in statement_matched:
            if m['date'] == stmt_date and m['description'] == stmt_desc:
                found = True
                break
        if not found:
            unmatched_statement.append({
                'date': stmt_date,
                'description': stmt_desc,
                'debit': stmt_debit,
                'credit': stmt_credit
            })
    
    orphaned_qb = [txn for txn in qb_transactions if not txn['matched']]
    
    print(f"\n{'='*80}")
    print(f"MATCHING RESULTS")
    print(f"{'='*80}")
    print(f"Matched: {matched_count}")
    print(f"Unmatched in statement (missing from QB): {len(unmatched_statement)}")
    print(f"Orphaned in QuickBooks (not in statement): {len(orphaned_qb)}")
    
    # Show unmatched from statement
    if unmatched_statement:
        print(f"\n{'='*80}")
        print(f"MISSING FROM QUICKBOOKS ({len(unmatched_statement)} transactions)")
        print(f"{'='*80}")
        
        stmt_w_total = Decimal('0')
        stmt_d_total = Decimal('0')
        
        for txn in unmatched_statement[:50]:  # Show first 50
            if txn['debit']:
                stmt_w_total += Decimal(str(txn['debit']))
                print(f"{txn['date']} W ${txn['debit']:>10.2f} {txn['description'][:60]}")
            else:
                stmt_d_total += Decimal(str(txn['credit']))
                print(f"{txn['date']} D ${txn['credit']:>10.2f} {txn['description'][:60]}")
        
        if len(unmatched_statement) > 50:
            print(f"... and {len(unmatched_statement)-50} more")
        
        print(f"\nMissing totals: ${stmt_w_total:,.2f} withdrawals, ${stmt_d_total:,.2f} deposits")
    
    # Show orphaned QuickBooks
    if orphaned_qb:
        print(f"\n{'='*80}")
        print(f"ORPHANED IN QUICKBOOKS ({len(orphaned_qb)} transactions)")
        print(f"{'='*80}")
        print("These are in QuickBooks but NOT in the bank statement")
        
        qb_w_total = Decimal('0')
        qb_d_total = Decimal('0')
        
        for txn in orphaned_qb[:50]:  # Show first 50
            if txn['debit'] > 0:
                qb_w_total += Decimal(str(txn['debit']))
                print(f"{txn['date']} W ${txn['debit']:>10.2f} {txn['description'][:60]}")
            else:
                qb_d_total += Decimal(str(txn['credit']))
                print(f"{txn['date']} D ${txn['credit']:>10.2f} {txn['description'][:60]}")
        
        if len(orphaned_qb) > 50:
            print(f"... and {len(orphaned_qb)-50} more")
        
        print(f"\nOrphaned totals: ${qb_w_total:,.2f} withdrawals, ${qb_d_total:,.2f} deposits")
    
    print(f"\n{'='*80}")

if __name__ == '__main__':
    main()
