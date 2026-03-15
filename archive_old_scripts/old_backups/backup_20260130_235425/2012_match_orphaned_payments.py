"""
Match 2012 positive orphaned payments to charters by amount and date proximity.
- Uses ±7 day window for date matching
- Matches by exact amount or close amount (within $1)
- Reports confidence scores
- Allows dry-run and batch application
"""
import os
import psycopg2
from datetime import date, timedelta
import argparse

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REDACTED***'),
}

YEAR = 2012

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply matches')
    parser.add_argument('--limit', type=int, default=50, help='Limit matches to apply')
    args = parser.parse_args()
    
    s, e = date(YEAR, 1, 1), date(YEAR + 1, 1, 1)
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    
    # Get positive orphaned payments
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_method, notes
        FROM payments
        WHERE payment_date >= %s AND payment_date < %s
          AND reserve_number IS NULL
          AND amount > 0
        ORDER BY payment_date
    """, (s, e))
    
    orphans = cur.fetchall()
    print(f"=== Match 2012 Positive Orphaned Payments to Charters ===")
    print(f"Found {len(orphans)} orphaned payments to match\n")
    
    if not orphans:
        cur.close()
        conn.close()
        return
    
    matches = []
    
    # For each orphaned payment, find candidate charters
    for payment_id, pmt_date, amount, method, notes in orphans:
        # Look for charters within ±7 days with matching or close amount
        date_start = pmt_date - timedelta(days=7)
        date_end = pmt_date + timedelta(days=7)
        
        cur.execute("""
            SELECT 
                c.reserve_number,
                c.charter_date,
                c.total_amount_due,
                c.paid_amount,
                c.balance,
                ABS(c.total_amount_due - %s) AS amount_diff,
                ABS(c.charter_date - %s::date) AS days_diff
            FROM charters c
            WHERE c.charter_date >= %s AND c.charter_date < %s
              AND c.charter_date BETWEEN %s AND %s
              AND ABS(c.total_amount_due - %s) <= 1.00
            ORDER BY 
                ABS(c.total_amount_due - %s) ASC,
                ABS(c.charter_date - %s::date) ASC
            LIMIT 3
        """, (amount, pmt_date, s, e, date_start, date_end, amount, amount, pmt_date))
        
        candidates = cur.fetchall()
        
        if candidates:
            best = candidates[0]
            reserve = best[0]
            charter_date = best[1]
            total_due = best[2]
            amount_diff = float(best[5])
            days_diff = float(best[6])
            
            # Confidence scoring
            confidence = 0
            if amount_diff < 0.01:
                confidence += 50  # Exact amount match
            elif amount_diff < 0.50:
                confidence += 30  # Very close
            else:
                confidence += 10  # Within $1
            
            if days_diff == 0:
                confidence += 50  # Same day
            elif days_diff <= 1:
                confidence += 30  # Next/prev day
            elif days_diff <= 3:
                confidence += 20  # Within 3 days
            else:
                confidence += 10  # Within week
            
            matches.append({
                'payment_id': payment_id,
                'pmt_date': pmt_date,
                'amount': float(amount),
                'reserve': reserve,
                'charter_date': charter_date,
                'total_due': float(total_due),
                'amount_diff': amount_diff,
                'days_diff': days_diff,
                'confidence': confidence,
                'method': method,
                'notes': notes
            })
    
    print(f"Found {len(matches)} potential matches\n")
    
    if not matches:
        print("No matches found")
        cur.close()
        conn.close()
        return
    
    # Show matches by confidence
    high_conf = [m for m in matches if m['confidence'] >= 80]
    med_conf = [m for m in matches if 50 <= m['confidence'] < 80]
    low_conf = [m for m in matches if m['confidence'] < 50]
    
    print(f"High confidence (≥80): {len(high_conf)}")
    print(f"Medium confidence (50-79): {len(med_conf)}")
    print(f"Low confidence (<50): {len(low_conf)}\n")
    
    # Show sample
    print("Sample top 20 matches:")
    print(f"{'Conf':>4} {'PmtDate':<12} {'Amount':>10} {'Reserve':<8} {'CharterDate':<12} {'TotalDue':>10} {'$Diff':>7} {'Days':>4}")
    print('-' * 95)
    
    for m in sorted(matches, key=lambda x: x['confidence'], reverse=True)[:20]:
        print(f"{m['confidence']:>4} {m['pmt_date']} ${m['amount']:>9,.2f} {m['reserve']:<8} "
              f"{m['charter_date']} ${m['total_due']:>9,.2f} ${m['amount_diff']:>6,.2f} {int(m['days_diff']):>4}")
    
    if not args.write:
        print(f"\n[WARN]  DRY RUN - Use --write to apply (--limit {args.limit} by default)")
        cur.close()
        conn.close()
        return
    
    # Apply matches (high confidence first, respect limit)
    to_apply = sorted(matches, key=lambda x: x['confidence'], reverse=True)[:args.limit]
    
    print(f"\n🔄 Applying {len(to_apply)} matches...")
    
    updated = 0
    for m in to_apply:
        cur.execute("""
            UPDATE payments
            SET reserve_number = %s,
                notes = COALESCE(notes || ' | ', '') || 
                        'AUTO-MATCHED: Amount $' || %s::text || 
                        ' to charter ' || %s || 
                        ' (confidence=' || %s::text || ')'
            WHERE payment_id = %s
        """, (m['reserve'], m['amount'], m['reserve'], m['confidence'], m['payment_id']))
        updated += 1
    
    conn.commit()
    
    print(f"\n{'='*80}")
    print("[OK] MATCHING COMPLETE")
    print("=" * 80)
    print(f"Matched: {updated} payments")
    print(f"Avg confidence: {sum(m['confidence'] for m in to_apply) / len(to_apply):.1f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
