"""
Deep investigation of duplicate payment imports across all years (2016-2024).
Distinguishes between:
- Legitimate duplicates: Multiple vehicles prepaid at same time (fuel)
- True duplicates: Accidental re-imports or data errors
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def investigate_year_duplicates(cur, year):
    """Investigate duplicate groups for a specific year."""
    print(f"\n{'='*80}")
    print(f"DUPLICATE INVESTIGATION FOR {year}")
    print(f"{'='*80}\n")
    
    # Find duplicate groups
    cur.execute("""
        SELECT 
            payment_date,
            amount,
            COUNT(*) as dup_count,
            ARRAY_AGG(payment_id ORDER BY payment_id) as payment_ids,
            ARRAY_AGG(payment_method ORDER BY payment_id) as payment_methods,
            ARRAY_AGG(reserve_number ORDER BY payment_id) as reserve_numbers,
            ARRAY_AGG(SUBSTRING(notes, 1, 100) ORDER BY payment_id) as note_samples
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND (
            notes ILIKE '%%Import%%' 
            OR notes ILIKE '%%QBO%%' 
            OR notes ILIKE '%%Square%%'
            OR square_transaction_id IS NOT NULL
        )
        GROUP BY payment_date, amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, amount DESC
    """, (year,))
    
    duplicate_groups = cur.fetchall()
    
    if not duplicate_groups:
        print(f"  ✅ No duplicate groups found in {year}")
        return {'year': year, 'duplicate_groups': 0, 'fuel_prepays': 0, 'true_duplicates': 0}
    
    print(f"Found {len(duplicate_groups)} duplicate groups:\n")
    
    results = {
        'year': year,
        'duplicate_groups': len(duplicate_groups),
        'fuel_prepays': 0,
        'true_duplicates': 0,
        'details': []
    }
    
    for idx, group in enumerate(duplicate_groups, 1):
        print(f"Group {idx}: {group['payment_date']} - ${group['amount']:.2f} ({group['dup_count']} occurrences)")
        print(f"  Payment IDs: {group['payment_ids']}")
        print(f"  Payment methods: {group['payment_methods']}")
        print(f"  Reserve numbers: {group['reserve_numbers']}")
        
        # Analyze pattern
        is_fuel_prepay = False
        is_true_duplicate = False
        
        # Check if all have different reserve numbers (legitimate multi-vehicle)
        reserve_nums = [r for r in group['reserve_numbers'] if r]
        unique_reserves = len(set(reserve_nums))
        
        # Check payment methods and notes
        methods = group['payment_methods']
        notes = group['note_samples']
        
        # Fuel prepay indicators
        fuel_keywords = ['fuel', 'gas', 'prepay', 'centex', 'fas gas', 'shell', 'esso']
        has_fuel_keyword = any(
            any(keyword in (note or '').lower() for keyword in fuel_keywords)
            for note in notes
        )
        
        # Check if amounts are common fuel prepay values
        common_fuel_amounts = [50.00, 100.00, 150.00, 200.00, 212.75]
        is_common_fuel_amount = group['amount'] in common_fuel_amounts
        
        # Determine classification
        if unique_reserves == group['dup_count'] and unique_reserves > 1:
            # Different charters = likely legitimate multi-vehicle
            is_fuel_prepay = True
            classification = "✅ LEGITIMATE (Multi-vehicle prepay)"
            results['fuel_prepays'] += 1
        elif unique_reserves == 1 and group['dup_count'] > 1:
            # Same charter, multiple payments = likely duplicate
            is_true_duplicate = True
            classification = "⚠️ TRUE DUPLICATE (Same charter)"
            results['true_duplicates'] += 1
        elif has_fuel_keyword and is_common_fuel_amount:
            # Fuel-related with common amount
            is_fuel_prepay = True
            classification = "✅ LIKELY LEGITIMATE (Fuel prepay pattern)"
            results['fuel_prepays'] += 1
        else:
            # Unclear - needs manual review
            classification = "❓ NEEDS REVIEW"
        
        print(f"  Classification: {classification}")
        
        # Show note samples
        print(f"  Note samples:")
        for pid, note in zip(group['payment_ids'], notes):
            print(f"    [{pid}] {note[:80]}...")
        
        # Get full details for true duplicates
        if is_true_duplicate:
            cur.execute("""
                SELECT 
                    payment_id,
                    payment_date,
                    amount,
                    payment_method,
                    reserve_number,
                    charter_id,
                    client_id,
                    notes,
                    square_transaction_id,
                    created_at
                FROM payments
                WHERE payment_id = ANY(%s)
                ORDER BY payment_id
            """, (group['payment_ids'],))
            
            details = cur.fetchall()
            print(f"\n  DETAILED ANALYSIS (TRUE DUPLICATE):")
            for detail in details:
                print(f"    Payment {detail['payment_id']}:")
                print(f"      Created: {detail['created_at']}")
                print(f"      Charter: {detail['charter_id']} (Reserve: {detail['reserve_number']})")
                print(f"      Square ID: {detail['square_transaction_id']}")
                print(f"      Full note: {detail['notes']}")
        
        results['details'].append({
            'date': str(group['payment_date']),
            'amount': float(group['amount']),
            'count': group['dup_count'],
            'payment_ids': group['payment_ids'],
            'classification': classification,
            'is_fuel_prepay': is_fuel_prepay,
            'is_true_duplicate': is_true_duplicate
        })
        
        print()
    
    return results

def generate_summary(all_results):
    """Generate summary of duplicate investigation."""
    print(f"\n{'='*80}")
    print(f"DUPLICATE INVESTIGATION SUMMARY (2016-2024)")
    print(f"{'='*80}\n")
    
    total_groups = sum(r['duplicate_groups'] for r in all_results if r['duplicate_groups'] > 0)
    total_fuel = sum(r['fuel_prepays'] for r in all_results if r['fuel_prepays'] > 0)
    total_true = sum(r['true_duplicates'] for r in all_results if r['true_duplicates'] > 0)
    total_review = total_groups - total_fuel - total_true
    
    print(f"Total duplicate groups found: {total_groups}")
    print(f"  ✅ Legitimate (fuel prepays): {total_fuel}")
    print(f"  ⚠️ True duplicates: {total_true}")
    print(f"  ❓ Needs review: {total_review}")
    
    print(f"\nYear-by-Year Breakdown:")
    print("-" * 60)
    print(f"{'Year':<6} {'Groups':<8} {'Fuel':<8} {'Duplicate':<10} {'Review':<8}")
    print("-" * 60)
    
    for year in sorted(r['year'] for r in all_results):
        r = next(res for res in all_results if res['year'] == year)
        if r['duplicate_groups'] > 0:
            review = r['duplicate_groups'] - r['fuel_prepays'] - r['true_duplicates']
            print(f"{year:<6} {r['duplicate_groups']:<8} {r['fuel_prepays']:<8} {r['true_duplicates']:<10} {review:<8}")
    
    # Highlight true duplicates needing action
    print(f"\n{'='*80}")
    print(f"ACTION REQUIRED: TRUE DUPLICATES")
    print(f"{'='*80}\n")
    
    if total_true > 0:
        print(f"Found {total_true} true duplicate groups requiring remediation:")
        for year in sorted(r['year'] for r in all_results):
            r = next(res for res in all_results if res['year'] == year)
            if r['true_duplicates'] > 0:
                print(f"\n{year}:")
                true_dups = [d for d in r.get('details', []) if d['is_true_duplicate']]
                for dup in true_dups:
                    print(f"  • {dup['date']} ${dup['amount']:.2f} - IDs: {dup['payment_ids']}")
    else:
        print("✅ No true duplicates requiring action!")
    
    # Fuel prepay confirmation
    print(f"\n{'='*80}")
    print(f"CONFIRMED: LEGITIMATE FUEL PREPAYS")
    print(f"{'='*80}\n")
    
    if total_fuel > 0:
        print(f"Confirmed {total_fuel} legitimate multi-vehicle fuel prepay groups:")
        for year in sorted(r['year'] for r in all_results):
            r = next(res for res in all_results if res['year'] == year)
            if r['fuel_prepays'] > 0:
                fuel_groups = [d for d in r.get('details', []) if d['is_fuel_prepay']]
                if fuel_groups:
                    print(f"\n{year}: {len(fuel_groups)} groups")
                    for fuel in fuel_groups[:3]:  # Show first 3
                        print(f"  • {fuel['date']} ${fuel['amount']:.2f} ({fuel['count']} vehicles)")
    else:
        print("No multi-vehicle fuel prepays detected (all singles or different amounts)")

def main():
    """Main execution."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    years = range(2016, 2025)
    all_results = []
    
    try:
        for year in years:
            result = investigate_year_duplicates(cur, year)
            all_results.append(result)
        
        generate_summary(all_results)
        
        print(f"\n{'='*80}")
        print(f"INVESTIGATION COMPLETE")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        cur.close()
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
