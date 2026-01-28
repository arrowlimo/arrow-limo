"""
Analyze whether duplicate payments are matched to same or different charters.

This will help determine the deduplication strategy:
- If duplicates match same charter: Simple deduplication (keep one)
- If duplicates match different charters: Data integrity issue (investigate why)
- If some matched, some not: Need careful merge strategy
"""

import psycopg2
import os
from collections import defaultdict

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_duplicate_charter_assignments():
    """Analyze charter_id assignments for duplicate payment_keys."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("DUPLICATE PAYMENT CHARTER ASSIGNMENT ANALYSIS")
    print("=" * 80)
    print()
    
    # Get payment keys with duplicates and their charter assignments
    print("Analyzing payment_keys with multiple records...")
    cur.execute("""
        SELECT 
            payment_key,
            COUNT(*) as duplicate_count,
            COUNT(DISTINCT charter_id) as unique_charters,
            COUNT(DISTINCT CASE WHEN charter_id IS NOT NULL THEN charter_id END) as matched_charters,
            MIN(payment_id) as min_payment_id,
            MAX(payment_id) as max_payment_id,
            MIN(payment_date) as payment_date,
            MIN(amount) as amount,
            STRING_AGG(DISTINCT CAST(charter_id AS TEXT), ', ' ORDER BY CAST(charter_id AS TEXT)) as charter_ids,
            STRING_AGG(DISTINCT CAST(payment_id AS TEXT), ', ') as payment_ids
        FROM payments
        WHERE payment_key IS NOT NULL 
          AND payment_key != ''
        GROUP BY payment_key
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, payment_key
        LIMIT 30
    """)
    
    duplicates = cur.fetchall()
    print(f"Found {len(duplicates)} payment_keys with duplicates (showing top 30)")
    print()
    
    # Categorize duplicates
    same_charter = []
    different_charters = []
    mixed_matching = []
    all_unmatched = []
    
    for row in duplicates:
        payment_key, dup_count, unique_charters, matched_charters, min_id, max_id, pdate, amount, charter_ids, payment_ids = row
        
        if matched_charters == 0:
            # All duplicates are unmatched
            all_unmatched.append(row)
        elif matched_charters == 1 and unique_charters == 1:
            # All duplicates matched to same charter (including NULLs)
            same_charter.append(row)
        elif matched_charters > 1 and unique_charters > 1:
            # Duplicates matched to different charters
            different_charters.append(row)
        else:
            # Some matched, some not (or multiple of same charter)
            mixed_matching.append(row)
    
    print("\n" + "=" * 80)
    print("CATEGORIZATION SUMMARY")
    print("=" * 80)
    print(f"Same Charter (all duplicates → 1 charter):     {len(same_charter)}")
    print(f"Different Charters (duplicates → 2+ charters): {len(different_charters)}")
    print(f"Mixed (some matched, some not):                {len(mixed_matching)}")
    print(f"All Unmatched (all duplicates have NULL):      {len(all_unmatched)}")
    print()
    
    # Show examples of each category
    if same_charter:
        print("\n" + "=" * 80)
        print("SAME CHARTER - Safe to deduplicate (keep 1st payment_id)")
        print("=" * 80)
        for i, row in enumerate(same_charter[:5], 1):
            payment_key, dup_count, unique_charters, matched_charters, min_id, max_id, pdate, amount, charter_ids, payment_ids = row
            print(f"{i}. Payment Key: {payment_key}")
            print(f"   Duplicates: {dup_count} copies")
            print(f"   Charter ID: {charter_ids if charter_ids else 'NULL'}")
            print(f"   Payment IDs: {payment_ids[:100]}..." if len(payment_ids) > 100 else f"   Payment IDs: {payment_ids}")
            print(f"   Date: {pdate}, Amount: ${amount if amount else 0:.2f}")
            print()
    
    if different_charters:
        print("\n" + "=" * 80)
        print("DIFFERENT CHARTERS - [WARN] DATA INTEGRITY ISSUE!")
        print("Same payment matched to multiple charters - need investigation")
        print("=" * 80)
        for i, row in enumerate(different_charters[:5], 1):
            payment_key, dup_count, unique_charters, matched_charters, min_id, max_id, pdate, amount, charter_ids, payment_ids = row
            print(f"{i}. Payment Key: {payment_key}")
            print(f"   Duplicates: {dup_count} copies")
            print(f"   Charter IDs: {charter_ids}")
            print(f"   Payment IDs: {payment_ids[:100]}..." if len(payment_ids) > 100 else f"   Payment IDs: {payment_ids}")
            print(f"   Date: {pdate}, Amount: ${amount if amount else 0:.2f}")
            print()
            
            # Show details for this payment_key
            cur.execute("""
                SELECT payment_id, charter_id, reserve_number, account_number, 
                       amount, payment_method, notes
                FROM payments
                WHERE payment_key = %s
                ORDER BY payment_id
            """, (payment_key,))
            details = cur.fetchall()
            for detail in details:
                pid, cid, reserve, account, amt, method, notes = detail
                print(f"     Payment {pid}: Charter {cid if cid else 'NULL'}, "
                      f"Reserve {reserve if reserve else 'NULL'}, "
                      f"Account {account if account else 'NULL'}, "
                      f"${amt if amt else 0:.2f} {method if method else 'NULL'}")
                if notes:
                    print(f"       Notes: {notes[:80]}...")
            print()
    
    if mixed_matching:
        print("\n" + "=" * 80)
        print("MIXED MATCHING - Some matched, some unmatched")
        print("=" * 80)
        for i, row in enumerate(mixed_matching[:5], 1):
            payment_key, dup_count, unique_charters, matched_charters, min_id, max_id, pdate, amount, charter_ids, payment_ids = row
            print(f"{i}. Payment Key: {payment_key}")
            print(f"   Duplicates: {dup_count} copies")
            print(f"   Matched: {matched_charters} to charter(s), Unmatched: {dup_count - matched_charters}")
            print(f"   Charter IDs: {charter_ids}")
            print(f"   Payment IDs: {payment_ids[:100]}..." if len(payment_ids) > 100 else f"   Payment IDs: {payment_ids}")
            print(f"   Date: {pdate}, Amount: ${amount if amount else 0:.2f}")
            print()
    
    if all_unmatched:
        print("\n" + "=" * 80)
        print("ALL UNMATCHED - All duplicates have NULL charter_id")
        print("Safe to deduplicate (keep 1st payment_id)")
        print("=" * 80)
        for i, row in enumerate(all_unmatched[:5], 1):
            payment_key, dup_count, unique_charters, matched_charters, min_id, max_id, pdate, amount, charter_ids, payment_ids = row
            print(f"{i}. Payment Key: {payment_key}")
            print(f"   Duplicates: {dup_count} copies (all unmatched)")
            print(f"   Payment IDs: {payment_ids[:100]}..." if len(payment_ids) > 100 else f"   Payment IDs: {payment_ids}")
            print(f"   Date: {pdate}, Amount: ${amount if amount else 0:.2f}")
            print()
    
    # Overall statistics
    print("\n" + "=" * 80)
    print("DEDUPLICATION STRATEGY RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    safe_to_delete = len(same_charter) + len(all_unmatched)
    needs_review = len(different_charters)
    needs_merge = len(mixed_matching)
    
    print(f"[OK] SAFE TO DEDUPLICATE: {safe_to_delete} payment_keys")
    print(f"   - Same charter: {len(same_charter)}")
    print(f"   - All unmatched: {len(all_unmatched)}")
    print(f"   Strategy: Keep payment with lowest payment_id, delete duplicates")
    print()
    
    if needs_review > 0:
        print(f"[WARN]  NEEDS INVESTIGATION: {needs_review} payment_keys")
        print(f"   - Different charters matched")
        print(f"   Strategy: Manual review - determine which charter is correct")
        print()
    
    if needs_merge > 0:
        print(f"🔄 NEEDS MERGE LOGIC: {needs_merge} payment_keys")
        print(f"   - Some matched, some unmatched")
        print(f"   Strategy: Keep matched payment, delete unmatched duplicates")
        print()
    
    # Calculate total duplicates to remove
    cur.execute("""
        SELECT 
            COUNT(*) - COUNT(DISTINCT payment_key) as total_duplicates_to_remove
        FROM payments
        WHERE payment_key IS NOT NULL 
          AND payment_key != ''
          AND payment_key IN (
              SELECT payment_key
              FROM payments
              WHERE payment_key IS NOT NULL AND payment_key != ''
              GROUP BY payment_key
              HAVING COUNT(*) > 1
          )
    """)
    total_to_remove = cur.fetchone()[0]
    
    print(f"\nTOTAL DUPLICATE PAYMENTS TO REMOVE: {total_to_remove}")
    print(f"(Keeping 1 payment per payment_key)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_duplicate_charter_assignments()
