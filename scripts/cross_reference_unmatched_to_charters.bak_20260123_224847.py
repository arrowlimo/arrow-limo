"""
Cross-reference remaining 2,282 unmatched payments to 64 unpaid charters.

Matching strategy:
1. Account number exact match
2. Date proximity (±30 days from charter date)
3. Amount similarity (±10% of charter total charges)
4. Client name fuzzy match
"""

import psycopg2
from datetime import timedelta
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("CROSS-REFERENCE: Unmatched Payments vs Charters Without Payments")
    print("=" * 100)
    print()
    
    # Get unmatched payments
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.account_number,
            p.reserve_number,
            p.amount,
            p.payment_method,
            p.check_number,
            p.square_transaction_id,
            p.notes,
            cl.client_name
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE (p.charter_id IS NULL OR p.charter_id = 0)
        AND EXTRACT(YEAR FROM p.payment_date) BETWEEN 2007 AND 2024
        ORDER BY p.payment_date DESC
    """)
    
    unmatched_payments = cur.fetchall()
    print(f"Total unmatched payments: {len(unmatched_payments)}")
    print()
    
    # Get charters without payments (non-excluded)
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.account_number,
            cl.client_name,
            COALESCE(cc.total_charges, 0) as total_charges,
            c.status
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND EXTRACT(YEAR FROM c.charter_date) BETWEEN 2007 AND 2024
        AND COALESCE(c.payment_excluded, FALSE) = FALSE
        AND COALESCE(cc.total_charges, 0) > 0
        ORDER BY total_charges DESC
    """)
    
    unpaid_charters = cur.fetchall()
    print(f"Charters with charges but no payments: {len(unpaid_charters)}")
    print()
    
    # Cross-reference matching
    matches = []
    
    print("Analyzing potential matches...")
    print("-" * 100)
    
    for charter in unpaid_charters:
        charter_id, charter_reserve, charter_date, charter_account, charter_client, total_charges, charter_status = charter
        
        for payment in unmatched_payments:
            payment_id, payment_date, payment_account, payment_reserve, payment_amount, payment_method, check_num, square_id, notes, payment_client = payment
            
            match_score = 0
            match_reasons = []
            
            # 1. Account number exact match (50 points)
            if charter_account and payment_account and str(charter_account).strip() == str(payment_account).strip():
                match_score += 50
                match_reasons.append("Account match")
            
            # 2. Reserve number match (100 points - very strong)
            if charter_reserve and payment_reserve and str(charter_reserve).strip() == str(payment_reserve).strip():
                match_score += 100
                match_reasons.append("Reserve# match")
            
            # 3. Date proximity (±30 days) (30 points)
            if charter_date and payment_date:
                date_diff = abs((charter_date - payment_date).days)
                if date_diff <= 30:
                    match_score += max(0, 30 - date_diff)  # Closer dates get higher scores
                    match_reasons.append(f"Date ±{date_diff}d")
            
            # 4. Amount similarity (±10%) (40 points)
            if total_charges > 0 and payment_amount:
                amount_diff_pct = abs(total_charges - payment_amount) / total_charges * 100
                if amount_diff_pct <= 10:
                    match_score += max(0, 40 - int(amount_diff_pct * 4))
                    match_reasons.append(f"Amount ±{amount_diff_pct:.1f}%")
            
            # 5. Client name fuzzy match (20 points)
            if charter_client and payment_client:
                charter_name_lower = charter_client.lower().strip()
                payment_name_lower = payment_client.lower().strip()
                
                # Simple fuzzy match - contains or starts with
                if charter_name_lower in payment_name_lower or payment_name_lower in charter_name_lower:
                    match_score += 20
                    match_reasons.append("Client name similar")
            
            # Record matches with score >= 60 (threshold for potential match)
            if match_score >= 60:
                matches.append({
                    'score': match_score,
                    'payment_id': payment_id,
                    'payment_date': payment_date,
                    'payment_amount': payment_amount,
                    'payment_method': payment_method,
                    'payment_client': payment_client,
                    'payment_notes': notes,
                    'charter_id': charter_id,
                    'charter_reserve': charter_reserve,
                    'charter_date': charter_date,
                    'charter_charges': total_charges,
                    'charter_client': charter_client,
                    'charter_status': charter_status,
                    'reasons': match_reasons
                })
    
    # Sort by score descending
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    print()
    print("=" * 100)
    print(f"POTENTIAL MATCHES FOUND: {len(matches)}")
    print("=" * 100)
    print()
    
    if matches:
        # Group by confidence
        high_confidence = [m for m in matches if m['score'] >= 100]
        medium_confidence = [m for m in matches if 80 <= m['score'] < 100]
        low_confidence = [m for m in matches if 60 <= m['score'] < 80]
        
        print(f"High confidence (score ≥100): {len(high_confidence)}")
        print(f"Medium confidence (80-99): {len(medium_confidence)}")
        print(f"Low confidence (60-79): {len(low_confidence)}")
        print()
        
        # Show high confidence matches
        if high_confidence:
            print("=" * 100)
            print("HIGH CONFIDENCE MATCHES (Score ≥100)")
            print("=" * 100)
            print()
            
            for i, match in enumerate(high_confidence[:50], 1):
                print(f"{i}. MATCH SCORE: {match['score']}")
                print(f"   Reasons: {', '.join(match['reasons'])}")
                print(f"   Payment {match['payment_id']}: {match['payment_date']} | ${match['payment_amount']:,.2f} | {match['payment_method'] or 'N/A'}")
                print(f"   Client: {match['payment_client'] or 'Unknown'}")
                if match['payment_notes']:
                    print(f"   Notes: {match['payment_notes'][:100]}")
                print(f"   ↓ MATCHES ↓")
                print(f"   Charter {match['charter_id']} (Reserve {match['charter_reserve']}): {match['charter_date']} | ${match['charter_charges']:,.2f}")
                print(f"   Client: {match['charter_client'] or 'Unknown'} | Status: {match['charter_status']}")
                print()
            
            if len(high_confidence) > 50:
                print(f"   ... and {len(high_confidence) - 50} more high confidence matches")
                print()
        
        # Show sample medium confidence
        if medium_confidence:
            print("=" * 100)
            print("MEDIUM CONFIDENCE MATCHES (Score 80-99) - Sample")
            print("=" * 100)
            print()
            
            for i, match in enumerate(medium_confidence[:10], 1):
                print(f"{i}. MATCH SCORE: {match['score']}")
                print(f"   Reasons: {', '.join(match['reasons'])}")
                print(f"   Payment {match['payment_id']}: ${match['payment_amount']:,.2f} | Charter {match['charter_id']}: ${match['charter_charges']:,.2f}")
                print()
        
        # Summary by charter
        print("=" * 100)
        print("MATCHES BY CHARTER")
        print("=" * 100)
        print()
        
        charter_match_count = {}
        for match in matches:
            charter_id = match['charter_id']
            if charter_id not in charter_match_count:
                charter_match_count[charter_id] = {
                    'count': 0,
                    'reserve': match['charter_reserve'],
                    'client': match['charter_client'],
                    'charges': match['charter_charges'],
                    'best_score': 0
                }
            charter_match_count[charter_id]['count'] += 1
            charter_match_count[charter_id]['best_score'] = max(
                charter_match_count[charter_id]['best_score'],
                match['score']
            )
        
        sorted_charters = sorted(
            charter_match_count.items(),
            key=lambda x: (x[1]['best_score'], x[1]['count']),
            reverse=True
        )
        
        for charter_id, info in sorted_charters[:20]:
            print(f"Charter {charter_id} (Reserve {info['reserve']}): {info['count']} potential match(es)")
            print(f"  Client: {info['client']} | Charges: ${info['charges']:,.2f} | Best score: {info['best_score']}")
            print()
        
        if len(sorted_charters) > 20:
            print(f"... and {len(sorted_charters) - 20} more charters with potential matches")
            print()
        
        # Export to CSV
        csv_file = "L:\\limo\\potential_payment_charter_matches.csv"
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write("Match Score,Payment ID,Payment Date,Payment Amount,Payment Method,Payment Client,")
            f.write("Charter ID,Charter Reserve,Charter Date,Charter Charges,Charter Client,Charter Status,Match Reasons\n")
            
            for match in matches:
                f.write(f"{match['score']},")
                f.write(f"{match['payment_id']},")
                f.write(f"{match['payment_date']},")
                f.write(f"{match['payment_amount']},")
                f.write(f"{match['payment_method'] or ''},")
                f.write(f"\"{match['payment_client'] or ''}\",")
                f.write(f"{match['charter_id']},")
                f.write(f"{match['charter_reserve']},")
                f.write(f"{match['charter_date']},")
                f.write(f"{match['charter_charges']},")
                f.write(f"\"{match['charter_client'] or ''}\",")
                f.write(f"{match['charter_status'] or ''},")
                f.write(f"\"{'; '.join(match['reasons'])}\"\n")
        
        print("=" * 100)
        print(f"[OK] Exported {len(matches)} potential matches to: {csv_file}")
        print("=" * 100)
    else:
        print("[WARN] No potential matches found with current criteria")
        print("   (Score threshold: 60+)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
