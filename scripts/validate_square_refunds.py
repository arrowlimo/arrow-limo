"""Validate Square-sourced refund candidates against Square transaction records.

Reads reports/refund_candidates_enriched.csv and for each Square-sourced refund:
  1. Query square_transactions table for the matched positive payment
  2. Check if Square recorded a refund/reversal for that transaction
  3. Compare amounts and dates
  4. Flag discrepancies (refund in payments but not in Square, or vice versa)

Outputs:
  reports/square_refund_validation.csv
  Console summary of mismatches

Environment variables: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
"""

from __future__ import annotations
import os, csv, sys
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def load_enriched_candidates(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"[FAIL] File not found: {path}")
        sys.exit(1)
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def fetch_square_transaction(cur, payment_id: int) -> Optional[Dict[str, Any]]:
    """Fetch Square transaction details linked to a payment."""
    cur.execute("""
        SELECT 
            st.transaction_id, st.square_transaction_id, st.square_payment_id,
            st.amount, st.net_amount, st.status, st.transaction_date,
            st.card_brand, st.last_4, st.customer_name,
            p.payment_id, p.square_transaction_id as payment_square_txn,
            p.square_payment_id as payment_square_pay
        FROM payments p
        LEFT JOIN square_transactions st ON (
            st.square_transaction_id = p.square_transaction_id
            OR st.square_payment_id = p.square_payment_id
        )
        WHERE p.payment_id = %s
    """, (payment_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def check_square_refund_exists(cur, square_txn_id: str, square_pay_id: str, 
                               refund_amount: float, refund_date: datetime) -> Optional[Dict[str, Any]]:
    """Check if Square has a refund record for this transaction."""
    # Check square_transactions for refund/void status
    if square_txn_id:
        cur.execute("""
            SELECT transaction_id, square_transaction_id, amount, status, 
                   transaction_date, card_brand
            FROM square_transactions
            WHERE square_transaction_id = %s
              AND (status ILIKE '%%refund%%' OR status ILIKE '%%void%%' OR amount < 0)
        """, (square_txn_id,))
        refund = cur.fetchone()
        if refund:
            return dict(refund)
    
    # Also check by payment_id with negative amount near the refund date
    if square_pay_id:
        cur.execute("""
            SELECT transaction_id, square_payment_id, amount, status,
                   transaction_date, card_brand
            FROM square_transactions
            WHERE square_payment_id = %s
              AND amount < 0
              AND ABS(ABS(amount) - %s) < 0.02
        """, (square_pay_id, abs(refund_amount)))
        refund = cur.fetchone()
        if refund:
            return dict(refund)
    
    return None


def validate_square_refunds():
    candidates = load_enriched_candidates('reports/refund_candidates_enriched.csv')
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Filter to Square-sourced only
    square_candidates = [c for c in candidates if c.get('source_classification') == 'Square']
    
    print(f"🔍 Validating {len(square_candidates)} Square-sourced refund candidates...")
    
    results = []
    validated = 0
    missing_in_square = 0
    amount_mismatch = 0
    date_mismatch = 0
    
    for c in square_candidates:
        pos_payment_id = int(c['matched_positive_id']) if c.get('matched_positive_id') else None
        neg_payment_id = int(c['negative_payment_id'])
        neg_amount = float(c['negative_amount'])
        neg_date_str = c.get('negative_date')
        neg_date = datetime.fromisoformat(neg_date_str) if neg_date_str else None
        
        if not pos_payment_id:
            results.append({
                **c,
                'validation_status': 'NO_MATCH',
                'square_refund_found': 'N/A',
                'square_refund_amount': '',
                'square_refund_date': '',
                'amount_diff': '',
                'date_diff_days': '',
                'notes': 'No matched positive payment to validate'
            })
            continue
        
        # Fetch Square transaction for the positive payment
        sq_txn = fetch_square_transaction(cur, pos_payment_id)
        
        if not sq_txn or not sq_txn.get('square_transaction_id'):
            results.append({
                **c,
                'validation_status': 'NO_SQUARE_TXN',
                'square_refund_found': 'N/A',
                'square_refund_amount': '',
                'square_refund_date': '',
                'amount_diff': '',
                'date_diff_days': '',
                'notes': 'Positive payment not linked to Square transaction'
            })
            missing_in_square += 1
            continue
        
        # Check if Square has a refund record
        sq_refund = check_square_refund_exists(
            cur,
            sq_txn.get('square_transaction_id'),
            sq_txn.get('square_payment_id'),
            neg_amount,
            neg_date
        )
        
        if sq_refund:
            # Validate amounts and dates
            sq_refund_amt = float(sq_refund.get('amount', 0))
            sq_refund_date = sq_refund.get('transaction_date')
            amount_diff = abs(abs(sq_refund_amt) - abs(neg_amount))
            date_diff = abs((sq_refund_date - neg_date).days) if sq_refund_date and neg_date else None
            
            status = 'VALIDATED'
            notes = 'Square refund found and matches'
            
            if amount_diff > 0.02:
                status = 'AMOUNT_MISMATCH'
                notes = f'Amount differs by ${amount_diff:.2f}'
                amount_mismatch += 1
            elif date_diff and date_diff > 3:
                status = 'DATE_MISMATCH'
                notes = f'Date differs by {date_diff} days'
                date_mismatch += 1
            else:
                validated += 1
            
            results.append({
                **c,
                'validation_status': status,
                'square_refund_found': 'YES',
                'square_refund_amount': f"{sq_refund_amt:.2f}",
                'square_refund_date': sq_refund_date.isoformat() if sq_refund_date else '',
                'amount_diff': f"{amount_diff:.2f}",
                'date_diff_days': str(date_diff) if date_diff else '',
                'notes': notes
            })
        else:
            # Refund in payments but not in Square
            results.append({
                **c,
                'validation_status': 'MISSING_IN_SQUARE',
                'square_refund_found': 'NO',
                'square_refund_amount': '',
                'square_refund_date': '',
                'amount_diff': '',
                'date_diff_days': '',
                'notes': 'Refund in payments table but no matching Square refund record'
            })
            missing_in_square += 1
    
    # Write results
    out_path = 'reports/square_refund_validation.csv'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    if results:
        fieldnames = list(results[0].keys())
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
    
    # Summary
    print(f"\n[OK] Square refund validation complete")
    print(f"   Total Square refunds analyzed: {len(square_candidates)}")
    print(f"   ✓ Validated (match found): {validated}")
    print(f"   ⚠ Missing in Square: {missing_in_square}")
    print(f"   ⚠ Amount mismatch: {amount_mismatch}")
    print(f"   ⚠ Date mismatch: {date_mismatch}")
    print(f"\n📄 Full report: {out_path}")
    
    # Sample some missing ones
    missing = [r for r in results if r['validation_status'] == 'MISSING_IN_SQUARE']
    if missing:
        print(f"\n🔍 Sample refunds missing in Square (first 10):")
        for r in missing[:10]:
            print(f"   • Payment {r['negative_payment_id']}: ${r['negative_amount']} on {r.get('negative_date', 'unknown date')}")
            print(f"     Reserve: {r.get('negative_reserve', 'none')}, Matched to payment {r.get('matched_positive_id', 'none')}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    validate_square_refunds()
