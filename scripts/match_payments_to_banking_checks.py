"""
Match unmatched payments to banking transactions by check amounts.

This cross-references:
1. Payments with check numbers to banking transactions
2. Payment amounts to banking debit amounts (checks drawn)
3. Date proximity (±7 days)
"""

import psycopg2
import os
from datetime import timedelta

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("MATCHING UNMATCHED PAYMENTS TO BANKING TRANSACTIONS")
    print("=" * 100)
    print()
    
    # Get unmatched payments with check numbers
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.check_number,
            p.payment_method,
            p.account_number,
            p.reserve_number,
            cl.client_name,
            p.notes
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE (p.charter_id IS NULL OR p.charter_id = 0)
        AND EXTRACT(YEAR FROM p.payment_date) BETWEEN 2007 AND 2024
        ORDER BY p.payment_date DESC
    """)
    
    unmatched_payments = cur.fetchall()
    print(f"Total unmatched payments (2007-2024): {len(unmatched_payments):,}")
    
    # Count by payment method
    with_check_number = sum(1 for p in unmatched_payments if p[3])
    check_method = sum(1 for p in unmatched_payments if p[4] and 'check' in p[4].lower())
    
    print(f"  With check number: {with_check_number:,}")
    print(f"  Payment method 'check': {check_method:,}")
    print()
    
    # Get banking transactions (checks - debit amounts)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            balance
        FROM banking_transactions
        WHERE debit_amount > 0
        AND (
            description ILIKE '%check%' OR
            description ILIKE '%chq%' OR
            description ILIKE '%cheque%'
        )
        ORDER BY transaction_date DESC
    """)
    
    banking_checks = cur.fetchall()
    print(f"Banking check transactions: {len(banking_checks):,}")
    print()
    
    # Match by check number
    print("=" * 100)
    print("MATCHING BY CHECK NUMBER:")
    print("=" * 100)
    print()
    
    check_number_matches = []
    
    for payment in unmatched_payments:
        payment_id, pdate, pamount, check_num, method, account, reserve, client, notes = payment
        
        if not check_num:
            continue
        
        # Look for check number in banking description
        for bank_txn in banking_checks:
            txn_id, txn_date, description, debit, balance = bank_txn
            
            if not description:
                continue
            
            # Check if check number appears in description
            check_str = str(check_num).strip()
            if check_str in description:
                # Also verify amount match (±$5 tolerance)
                amount_diff = abs(pamount - debit) if debit else 999999
                
                if amount_diff <= 5:
                    # And date proximity (±30 days)
                    if pdate and txn_date:
                        date_diff = abs((pdate - txn_date).days)
                        if date_diff <= 30:
                            check_number_matches.append({
                                'payment_id': payment_id,
                                'payment_date': pdate,
                                'payment_amount': pamount,
                                'check_number': check_num,
                                'client': client,
                                'bank_txn_id': txn_id,
                                'bank_date': txn_date,
                                'bank_amount': debit,
                                'bank_description': description,
                                'amount_diff': amount_diff,
                                'date_diff': date_diff
                            })
    
    print(f"Check number matches found: {len(check_number_matches)}")
    
    if check_number_matches:
        print("\nSample matches (first 20):")
        print("-" * 100)
        for i, match in enumerate(check_number_matches[:20], 1):
            print(f"\n{i}. CHECK #{match['check_number']}")
            print(f"   Payment {match['payment_id']}: {match['payment_date']} | ${match['payment_amount']:,.2f}")
            print(f"   Client: {match['client'] or 'Unknown'}")
            print(f"   ↓ MATCHES ↓")
            print(f"   Banking {match['bank_txn_id']}: {match['bank_date']} | ${match['bank_amount']:,.2f}")
            print(f"   Description: {match['bank_description'][:80]}")
            print(f"   Difference: ${match['amount_diff']:.2f}, {match['date_diff']} days apart")
    
    # Match by amount and date (no check number)
    print()
    print("=" * 100)
    print("MATCHING BY AMOUNT + DATE (payments without check numbers):")
    print("=" * 100)
    print()
    
    amount_matches = []
    
    for payment in unmatched_payments:
        payment_id, pdate, pamount, check_num, method, account, reserve, client, notes = payment
        
        # Skip if has check number (already processed above)
        if check_num:
            continue
        
        # Skip if amount is None or too common (too many false positives)
        if not pamount or pamount <= 0 or pamount > 10000:
            continue
        
        for bank_txn in banking_checks:
            txn_id, txn_date, description, debit, balance = bank_txn
            
            if not debit:
                continue
            
            # Amount match (±$1 tolerance for tighter match)
            amount_diff = abs(pamount - debit)
            if amount_diff <= 1:
                # Date proximity (±14 days for tighter match)
                if pdate and txn_date:
                    date_diff = abs((pdate - txn_date).days)
                    if date_diff <= 14:
                        amount_matches.append({
                            'payment_id': payment_id,
                            'payment_date': pdate,
                            'payment_amount': pamount,
                            'payment_method': method,
                            'client': client,
                            'bank_txn_id': txn_id,
                            'bank_date': txn_date,
                            'bank_amount': debit,
                            'bank_description': description,
                            'amount_diff': amount_diff,
                            'date_diff': date_diff
                        })
    
    print(f"Amount + date matches found: {len(amount_matches)}")
    
    if amount_matches:
        print("\nSample matches (first 20):")
        print("-" * 100)
        for i, match in enumerate(amount_matches[:20], 1):
            print(f"\n{i}. AMOUNT: ${match['payment_amount']:,.2f}")
            print(f"   Payment {match['payment_id']}: {match['payment_date']} | {match['payment_method'] or 'N/A'}")
            print(f"   Client: {match['client'] or 'Unknown'}")
            print(f"   ↓ MATCHES ↓")
            print(f"   Banking {match['bank_txn_id']}: {match['bank_date']} | ${match['bank_amount']:,.2f}")
            print(f"   Description: {match['bank_description'][:80]}")
            print(f"   Difference: ${match['amount_diff']:.2f}, {match['date_diff']} days apart")
    
    # Summary
    print()
    print("=" * 100)
    print("SUMMARY:")
    print("=" * 100)
    print(f"Total potential matches: {len(check_number_matches) + len(amount_matches)}")
    print(f"  By check number: {len(check_number_matches)}")
    print(f"  By amount + date: {len(amount_matches)}")
    print()
    
    # Check banking transactions without matches
    print("=" * 100)
    print("SAMPLE BANKING CHECK TRANSACTIONS:")
    print("=" * 100)
    print("\nRecent check transactions (last 20):")
    print("-" * 100)
    
    for i, bank_txn in enumerate(banking_checks[:20], 1):
        txn_id, txn_date, description, debit, balance = bank_txn
        print(f"\n{i}. Banking {txn_id}: {txn_date} | ${debit:,.2f}")
        print(f"   Description: {description[:80] if description else 'None'}")
    
    # Export matches to CSV
    if check_number_matches or amount_matches:
        csv_file = "L:\\limo\\payment_banking_check_matches.csv"
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write("Match Type,Payment ID,Payment Date,Payment Amount,Check Number,Client,")
            f.write("Banking Txn ID,Banking Date,Banking Amount,Banking Description,")
            f.write("Amount Diff,Date Diff\n")
            
            for match in check_number_matches:
                f.write(f"Check Number,{match['payment_id']},{match['payment_date']},")
                f.write(f"{match['payment_amount']},{match['check_number']},")
                f.write(f"\"{match['client'] or ''}\",")
                f.write(f"{match['bank_txn_id']},{match['bank_date']},")
                f.write(f"{match['bank_amount']},\"{match['bank_description']}\",")
                f.write(f"{match['amount_diff']},{match['date_diff']}\n")
            
            for match in amount_matches:
                f.write(f"Amount+Date,{match['payment_id']},{match['payment_date']},")
                f.write(f"{match['payment_amount']},,")
                f.write(f"\"{match['client'] or ''}\",")
                f.write(f"{match['bank_txn_id']},{match['bank_date']},")
                f.write(f"{match['bank_amount']},\"{match['bank_description']}\",")
                f.write(f"{match['amount_diff']},{match['date_diff']}\n")
        
        print()
        print("=" * 100)
        print(f"[OK] Exported {len(check_number_matches) + len(amount_matches)} matches to:")
        print(f"   {csv_file}")
        print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
