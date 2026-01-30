"""Validate Square negative payments against Square transaction records.

For each negative payment with Square IDs, checks:
  1. Does a corresponding positive Square transaction exist?
  2. Does Square have a matching refund record?
  3. Are amounts and dates consistent?

Outputs:
  reports/square_negatives_validation.csv
  Console summary
"""

import os
import csv
import psycopg2
import psycopg2.extras
from datetime import datetime


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Fetch negative payments with Square IDs
    cur.execute("""
        SELECT 
            payment_id,
            payment_key,
            reserve_number,
            charter_id,
            COALESCE(payment_amount, amount, 0) as amount,
            payment_method,
            payment_date,
            status,
            square_transaction_id,
            square_payment_id,
            notes
        FROM payments
        WHERE COALESCE(payment_amount, amount, 0) < 0
          AND (square_transaction_id IS NOT NULL OR square_payment_id IS NOT NULL)
        ORDER BY payment_date DESC NULLS LAST
    """)
    
    neg_payments = cur.fetchall()
    print(f"🔍 Validating {len(neg_payments)} Square-linked negative payments...")
    
    results = []
    validated = 0
    missing_original = 0
    missing_refund_record = 0
    amount_mismatch = 0
    
    for neg in neg_payments:
        neg_id = neg['payment_id']
        neg_amt = float(neg['amount'])
        sq_txn_id = neg['square_transaction_id']
        sq_pay_id = neg['square_payment_id']
        
        # Look for the original positive transaction in square_transactions
        cur.execute("""
            SELECT 
                transaction_id,
                square_transaction_id,
                square_payment_id,
                amount,
                net_amount,
                status,
                transaction_date,
                card_brand,
                last_4
            FROM square_transactions
            WHERE (square_transaction_id = %s OR square_payment_id = %s)
              AND amount > 0
            ORDER BY transaction_date DESC
            LIMIT 1
        """, (sq_txn_id, sq_pay_id))
        
        original_txn = cur.fetchone()
        
        if not original_txn:
            results.append({
                'payment_id': neg_id,
                'reserve_number': neg['reserve_number'],
                'negative_amount': f"{neg_amt:.2f}",
                'payment_date': neg['payment_date'],
                'square_txn_id': sq_txn_id,
                'square_pay_id': sq_pay_id,
                'validation_status': 'MISSING_ORIGINAL',
                'original_amount': '',
                'original_date': '',
                'has_refund_record': 'N/A',
                'refund_amount': '',
                'amount_diff': '',
                'notes': 'No positive Square transaction found for these IDs'
            })
            missing_original += 1
            continue
        
        # Check if Square has a refund record (negative amount entry)
        cur.execute("""
            SELECT 
                transaction_id,
                amount,
                status,
                transaction_date
            FROM square_transactions
            WHERE (square_transaction_id = %s OR square_payment_id = %s)
              AND amount < 0
            ORDER BY transaction_date DESC
            LIMIT 1
        """, (sq_txn_id, sq_pay_id))
        
        refund_record = cur.fetchone()
        
        if refund_record:
            refund_amt = float(refund_record['amount'])
            amount_diff = abs(abs(refund_amt) - abs(neg_amt))
            
            if amount_diff <= 0.02:
                status = 'VALIDATED'
                validated += 1
            else:
                status = 'AMOUNT_MISMATCH'
                amount_mismatch += 1
            
            results.append({
                'payment_id': neg_id,
                'reserve_number': neg['reserve_number'],
                'negative_amount': f"{neg_amt:.2f}",
                'payment_date': neg['payment_date'],
                'square_txn_id': sq_txn_id,
                'square_pay_id': sq_pay_id,
                'validation_status': status,
                'original_amount': f"{original_txn['amount']:.2f}",
                'original_date': original_txn['transaction_date'],
                'has_refund_record': 'YES',
                'refund_amount': f"{refund_amt:.2f}",
                'amount_diff': f"{amount_diff:.2f}",
                'notes': 'Square refund record found and validated' if status == 'VALIDATED' else f'Amount differs by ${amount_diff:.2f}'
            })
        else:
            # Original exists but no refund record in Square
            results.append({
                'payment_id': neg_id,
                'reserve_number': neg['reserve_number'],
                'negative_amount': f"{neg_amt:.2f}",
                'payment_date': neg['payment_date'],
                'square_txn_id': sq_txn_id,
                'square_pay_id': sq_pay_id,
                'validation_status': 'MISSING_REFUND_RECORD',
                'original_amount': f"{original_txn['amount']:.2f}",
                'original_date': original_txn['transaction_date'],
                'has_refund_record': 'NO',
                'refund_amount': '',
                'amount_diff': '',
                'notes': 'Refund in payments table but no corresponding negative entry in square_transactions'
            })
            missing_refund_record += 1
    
    # Write results
    out_path = 'reports/square_negatives_validation.csv'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    if results:
        fieldnames = list(results[0].keys())
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
    
    # Summary
    print(f"\n[OK] Square validation complete")
    print(f"   Total Square negatives: {len(neg_payments)}")
    print(f"   ✓ Validated (matching refund in Square): {validated}")
    print(f"   [WARN] Missing original transaction: {missing_original}")
    print(f"   [WARN] Missing refund record in Square: {missing_refund_record}")
    print(f"   [WARN] Amount mismatch: {amount_mismatch}")
    print(f"\n📄 Full report: {out_path}")
    
    # Show samples of issues
    missing = [r for r in results if r['validation_status'] == 'MISSING_REFUND_RECORD']
    if missing:
        print(f"\n🔍 Refunds in payments but not in square_transactions (first 5):")
        for r in missing[:5]:
            print(f"   Payment {r['payment_id']}: ${r['negative_amount']} on {r['payment_date']}")
            print(f"      Reserve: {r['reserve_number']}, Original: ${r['original_amount']} on {r['original_date']}")
            print(f"      Square TXN: {r['square_txn_id'][:20]}...")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
