"""Extract reserve numbers from suspicious R7 batches for manual review.

For each R7 batch, shows:
- Which reserve numbers appear multiple times
- All payments in the batch with their reserves
- Charter IDs if available

Outputs a focused CSV for manual charter review.
"""

import csv
import psycopg2
import psycopg2.extras
import os
from collections import Counter


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def main():
    # Load R7 batches
    r7_batches = []
    with open('reports/refund_batch_audit.csv', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        r7_batches = [row for row in reader if 'R7' in row.get('reason_codes', '')]
    
    print(f"🔍 Analyzing {len(r7_batches)} R7 batches for related charters...")
    
    # Get top batches by repeat count
    r7_batches.sort(key=lambda x: int(x.get('repeat_reserve_count', 0)), reverse=True)
    
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    results = []
    
    # Analyze top 100 batches
    for batch in r7_batches[:100]:
        payment_key = batch['payment_key']
        
        # Get all payments in this batch
        cur.execute("""
            SELECT 
                payment_id,
                payment_key,
                reserve_number,
                charter_id,
                COALESCE(payment_amount, amount, 0) as amount,
                payment_date,
                payment_method
            FROM payments
            WHERE payment_key = %s
            ORDER BY payment_id
        """, (payment_key,))
        
        payments = cur.fetchall()
        
        # Count reserve occurrences
        reserves = [p['reserve_number'] for p in payments if p['reserve_number']]
        reserve_counts = Counter(reserves)
        repeated = {r: c for r, c in reserve_counts.items() if c > 1}
        
        if repeated:
            for reserve, count in repeated.items():
                # Get payments for this reserve
                reserve_payments = [p for p in payments if p['reserve_number'] == reserve]
                
                for p in reserve_payments:
                    results.append({
                        'payment_key': payment_key,
                        'reserve_number': reserve,
                        'occurrences_in_batch': count,
                        'payment_id': p['payment_id'],
                        'charter_id': p['charter_id'] or '',
                        'amount': f"{p['amount']:.2f}",
                        'payment_date': p['payment_date'],
                        'payment_method': p['payment_method'] or '',
                        'batch_payment_count': len(payments),
                        'batch_distinct_reserves': len(set(reserves)),
                        'reason_codes': batch['reason_codes']
                    })
    
    # Write results
    out_path = 'reports/r7_related_charters_for_review.csv'
    if results:
        fieldnames = list(results[0].keys())
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
    
    print(f"\n[OK] Extracted {len(results)} payment records from top R7 batches")
    print(f"📄 Review file: {out_path}")
    
    # Show sample
    print(f"\n🔍 Sample batches with repeated reserves (top 10):")
    seen_batches = set()
    count = 0
    for r in results:
        if r['payment_key'] not in seen_batches:
            seen_batches.add(r['payment_key'])
            print(f"\n  Batch {r['payment_key']}: {r['batch_payment_count']} payments, {r['batch_distinct_reserves']} distinct reserves")
            batch_reserves = [res for res in results if res['payment_key'] == r['payment_key']]
            unique_repeats = set((b['reserve_number'], b['occurrences_in_batch']) for b in batch_reserves)
            for reserve, occ in sorted(unique_repeats):
                print(f"    • Reserve {reserve}: appears {occ} times")
            count += 1
            if count >= 10:
                break
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
