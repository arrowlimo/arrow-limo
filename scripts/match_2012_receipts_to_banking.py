"""
Match receipts to verified 2012 CIBC banking transactions.
Links receipts (expenses) to banking debits (withdrawals).
"""

import os
import psycopg2
from datetime import timedelta

def get_db_connection():
    """Get PostgreSQL connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def match_receipts_to_banking():
    """Match receipts to banking transactions using amount, date, and vendor."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Find 2012 receipts without banking_transaction_id
        print("🔍 Finding unmatched 2012 receipts...")
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, category
            FROM receipts
            WHERE (banking_transaction_id IS NULL OR banking_transaction_id NOT IN (
                SELECT transaction_id FROM banking_transactions WHERE account_number = '0228362'
            ))
            AND receipt_date >= '2012-01-01'
            AND receipt_date <= '2012-12-31'
            ORDER BY receipt_date, gross_amount
        """)
        
        unmatched_receipts = cur.fetchall()
        print(f"   Found {len(unmatched_receipts)} unmatched receipts")
        
        if len(unmatched_receipts) == 0:
            print("[OK] No unmatched receipts found!")
            return
        
        matched_count = 0
        fuzzy_matched = 0
        manual_review = []
        
        for receipt_id, receipt_date, vendor_name, gross_amount, description, category in unmatched_receipts:
            matched = False
            
            # Try exact match: amount and date within ±3 days
            cur.execute("""
                SELECT transaction_id, transaction_date, description, debit_amount
                FROM banking_transactions
                WHERE account_number = '0228362'
                AND transaction_date BETWEEN %s AND %s
                AND debit_amount = %s
                AND transaction_id NOT IN (
                    SELECT banking_transaction_id FROM receipts WHERE banking_transaction_id IS NOT NULL
                )
                ORDER BY ABS(EXTRACT(EPOCH FROM (transaction_date - %s::timestamp)))
                LIMIT 1
            """, (
                receipt_date - timedelta(days=3),
                receipt_date + timedelta(days=3),
                gross_amount,
                receipt_date
            ))
            
            match = cur.fetchone()
            
            if match:
                transaction_id, trans_date, trans_desc, debit_amount = match
                
                # Update receipt with banking_transaction_id
                cur.execute("""
                    UPDATE receipts
                    SET banking_transaction_id = %s
                    WHERE receipt_id = %s
                """, (transaction_id, receipt_id))
                
                matched_count += 1
                print(f"   [OK] Matched receipt {receipt_id} ({vendor_name} ${gross_amount:.2f} on {receipt_date}) → banking {transaction_id}")
                matched = True
            
            # Try fuzzy match: vendor name in description
            if not matched and vendor_name:
                # Extract key words from vendor name
                vendor_words = vendor_name.upper().split()
                if len(vendor_words) > 0:
                    # Look for vendor name in banking description
                    search_pattern = '%' + vendor_words[0] + '%'
                    
                    cur.execute("""
                        SELECT transaction_id, transaction_date, description, debit_amount
                        FROM banking_transactions
                        WHERE account_number = '0228362'
                        AND transaction_date BETWEEN %s AND %s
                        AND debit_amount BETWEEN %s AND %s
                        AND UPPER(description) LIKE %s
                        AND transaction_id NOT IN (
                            SELECT banking_transaction_id FROM receipts WHERE banking_transaction_id IS NOT NULL
                        )
                        ORDER BY ABS(debit_amount - %s), ABS(EXTRACT(EPOCH FROM (transaction_date - %s::timestamp)))
                        LIMIT 1
                    """, (
                        receipt_date - timedelta(days=5),
                        receipt_date + timedelta(days=5),
                        gross_amount * 0.95,  # Allow 5% variance
                        gross_amount * 1.05,
                        search_pattern,
                        gross_amount,
                        receipt_date
                    ))
                    
                    fuzzy_match = cur.fetchone()
                    
                    if fuzzy_match:
                        transaction_id, trans_date, trans_desc, debit_amount = fuzzy_match
                        
                        # Update receipt with banking_transaction_id
                        cur.execute("""
                            UPDATE receipts
                            SET banking_transaction_id = %s
                            WHERE receipt_id = %s
                        """, (transaction_id, receipt_id))
                        
                        fuzzy_matched += 1
                        print(f"   🔍 Fuzzy matched receipt {receipt_id} ({vendor_name} ${gross_amount:.2f}) → banking {transaction_id} ({trans_desc} ${debit_amount:.2f})")
                        matched = True
            
            if not matched:
                manual_review.append({
                    'receipt_id': receipt_id,
                    'date': receipt_date,
                    'vendor': vendor_name,
                    'amount': gross_amount,
                    'category': category,
                    'description': description
                })
        
        conn.commit()
        
        # Summary
        print(f"\n" + "="*60)
        print(f"[OK] RECEIPT MATCHING COMPLETE")
        print(f"="*60)
        print(f"Exact matches: {matched_count}")
        print(f"Fuzzy matches: {fuzzy_matched}")
        print(f"Total matched: {matched_count + fuzzy_matched}")
        print(f"Require manual review: {len(manual_review)}")
        print(f"="*60)
        
        if manual_review:
            print(f"\n[WARN]  Receipts requiring manual review:")
            # Group by category
            by_category = {}
            for r in manual_review:
                cat = r['category'] or 'Unknown'
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(r)
            
            for category, receipts in sorted(by_category.items()):
                print(f"\n  {category}: {len(receipts)} receipts")
                for r in receipts[:3]:  # Show first 3 per category
                    print(f"    Receipt {r['receipt_id']}: {r['vendor']} ${r['amount']:.2f} on {r['date']}")
                if len(receipts) > 3:
                    print(f"    ... and {len(receipts) - 3} more")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    print("="*60)
    print("2012 Receipt-Banking Matching")
    print("="*60)
    print()
    
    match_receipts_to_banking()
    
    print("\n[OK] Receipt matching complete!")
