"""Final summary: Square refund validation for suspicious batches.

Since square_transactions table is archived, we validate Square negatives by:
  1. Confirming the payment has Square IDs (square_transaction_id, square_payment_id)
  2. Checking if there's a corresponding positive payment with same Square IDs
  3. Reporting on batch patterns

Outputs:
  reports/square_refund_summary.md
"""

import os
import psycopg2
import psycopg2.extras
from collections import Counter, defaultdict


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    print("🔍 Analyzing Square-linked refunds...")
    
    # Get all Square negative payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_key,
            reserve_number,
            charter_id,
            COALESCE(payment_amount, amount, 0) as amount,
            payment_date,
            square_transaction_id,
            square_payment_id
        FROM payments
        WHERE COALESCE(payment_amount, amount, 0) < 0
          AND (square_transaction_id IS NOT NULL OR square_payment_id IS NOT NULL)
        ORDER BY payment_date DESC
    """)
    
    square_negs = cur.fetchall()
    
    # For each negative, find matching positive
    results = []
    for neg in square_negs:
        cur.execute("""
            SELECT 
                payment_id,
                COALESCE(payment_amount, amount, 0) as amount,
                payment_date,
                reserve_number
            FROM payments
            WHERE (square_transaction_id = %s OR square_payment_id = %s)
              AND COALESCE(payment_amount, amount, 0) > 0
            ORDER BY payment_date
            LIMIT 1
        """, (neg['square_transaction_id'], neg['square_payment_id']))
        
        pos = cur.fetchone()
        
        results.append({
            'neg_payment_id': neg['payment_id'],
            'neg_amount': neg['amount'],
            'neg_date': neg['payment_date'],
            'neg_reserve': neg['reserve_number'],
            'payment_key': neg['payment_key'],
            'pos_payment_id': pos['payment_id'] if pos else None,
            'pos_amount': pos['amount'] if pos else None,
            'pos_date': pos['payment_date'] if pos else None,
            'pos_reserve': pos['reserve_number'] if pos else None,
            'matched': 'YES' if pos else 'NO',
            'same_reserve': (neg['reserve_number'] == pos['reserve_number']) if pos and neg['reserve_number'] and pos['reserve_number'] else 'N/A'
        })
    
    # Group by payment_key
    by_key = defaultdict(list)
    for r in results:
        if r['payment_key']:
            by_key[r['payment_key']].append(r)
    
    # Summary stats
    total = len(results)
    matched = sum(1 for r in results if r['matched'] == 'YES')
    unmatched = total - matched
    batches_with_square = len(by_key)
    
    # Write markdown report
    out_path = 'reports/square_refund_summary.md'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("# Square Refund Validation Summary\n\n")
        f.write(f"**Analysis Date:** {os.popen('date /T').read().strip()}\n\n")
        f.write("## Overview\n\n")
        f.write(f"- **Total Square-linked negative payments:** {total}\n")
        f.write(f"- **Matched to positive payment:** {matched} ({matched/total*100:.1f}%)\n")
        f.write(f"- **Unmatched (no corresponding positive):** {unmatched}\n")
        f.write(f"- **Batches containing Square negatives:** {batches_with_square}\n\n")
        
        f.write("## Validation Method\n\n")
        f.write("Since `square_transactions` table is archived, validation is performed by:\n")
        f.write("1. Identifying payments with `square_transaction_id` or `square_payment_id` populated\n")
        f.write("2. Matching negative amounts to positive payments with same Square IDs\n")
        f.write("3. Verifying reserve number consistency\n\n")
        
        f.write("## Key Findings\n\n")
        
        same_reserve = sum(1 for r in results if r['same_reserve'] == True)
        if same_reserve:
            f.write(f"- **{same_reserve} matched refunds** have same reserve_number as original payment\n")
        
        diff_reserve = sum(1 for r in results if r['matched'] == 'YES' and r['same_reserve'] == False)
        if diff_reserve:
            f.write(f"- **{diff_reserve} matched refunds** have DIFFERENT reserve_number (cross-charter refunds)\n")
        
        f.write(f"\n### Batches with Multiple Square Refunds\n\n")
        multi_batches = [(k, v) for k, v in by_key.items() if len(v) > 1]
        multi_batches.sort(key=lambda x: len(x[1]), reverse=True)
        
        if multi_batches:
            for key, items in multi_batches[:15]:
                f.write(f"- **{key}**: {len(items)} Square refunds\n")
                for item in items[:3]:
                    f.write(f"  - Payment {item['neg_payment_id']}: ${item['neg_amount']:.2f}, Reserve: {item['neg_reserve']}\n")
                if len(items) > 3:
                    f.write(f"  - ...and {len(items)-3} more\n")
        else:
            f.write("*No batches with multiple Square refunds found.*\n")
        
        f.write(f"\n### Unmatched Square Negatives (sample)\n\n")
        unmatched_items = [r for r in results if r['matched'] == 'NO']
        if unmatched_items:
            f.write("These negative payments have Square IDs but no corresponding positive payment was found:\n\n")
            for item in unmatched_items[:10]:
                f.write(f"- Payment {item['neg_payment_id']}: ${item['neg_amount']:.2f} on {item['neg_date']}\n")
                f.write(f"  - Reserve: {item['neg_reserve']}, Batch: {item['payment_key']}\n")
        else:
            f.write("*All Square negative payments matched to positive payments.*\n")
        
        f.write("\n## Recommendations\n\n")
        f.write("1. **Validated Refunds:** Square negatives matched to positives with same reserve are legitimate\n")
        f.write("2. **Cross-Charter Refunds:** Review refunds with different reserve numbers for misposting\n")
        f.write("3. **Unmatched Negatives:** Investigate why these have Square IDs but no original payment\n")
        f.write("4. **Square Archive:** Consider restoring square_transactions table for full audit trail\n")
    
    print(f"\n[OK] Square refund summary complete")
    print(f"   Total Square negatives: {total}")
    print(f"   Matched: {matched} ({matched/total*100:.1f}%)")
    print(f"   Unmatched: {unmatched}")
    print(f"   Batches with Square refunds: {batches_with_square}")
    print(f"\n📄 Report: {out_path}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
