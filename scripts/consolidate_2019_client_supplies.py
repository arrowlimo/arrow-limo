"""
Find and consolidate 2019 CLIENT SUPPLIES, WATER, ICE receipts
Move to appropriate GL codes:
- Client supplies → 5116 (Client Amenities)
- Client water → 4115 (Client Beverage Service Charges) 
- Client ice → 5116 (Client Amenities)
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def consolidate_client_supplies():
    """Find and consolidate client supplies, water, ice"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("2019 CLIENT SUPPLIES, WATER, ICE ANALYSIS")
    print("=" * 100)
    
    # Find receipts (exact patterns from 2019 data - client-related only)
    categories = [
        ('CLIENT SUPPLIES', r'^client supplies$', '5116', 'Client Amenities - Food, Coffee, Supplies'),
        ('WATER', r'^water$', '4115', 'Client Beverage Service Charges'),
        ('ICE', r'^ice$|^ICE$', '5116', 'Client Amenities - Food, Coffee, Supplies'),
        ('CLIENT BEVERAGE', r'^Client Beverage$', '4115', 'Client Beverage Service Charges'),
        ('BUSINESS MEAL', r'^Business meal$', '5700', 'Travel and Entertainment'),
    ]
    
    all_updates = []
    
    for cat_name, pattern, target_code, target_name in categories:
        print(f"\n{'=' * 100}")
        print(f"📦 {cat_name}")
        print('=' * 100)
        
        cur.execute("""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                gl_account_code,
                gl_account_name,
                description
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2019
              AND description ~* %s
            ORDER BY receipt_date
        """, (pattern,))
        
        receipts = cur.fetchall()
        print(f"Found {len(receipts)} receipts\n")
        
        if receipts:
            # Show current GL distribution
            from collections import defaultdict
            gl_dist = defaultdict(lambda: {'count': 0, 'total': 0})
            
            for rid, date, vendor, amount, code, name, desc in receipts:
                gl_key = f"{code or 'NULL'} — {name or 'No Name'}"
                gl_dist[gl_key]['count'] += 1
                gl_dist[gl_key]['total'] += amount
            
            print("Current GL Distribution:")
            for gl_key, data in sorted(gl_dist.items()):
                print(f"   {gl_key}: {data['count']} receipts, ${data['total']:,.2f}")
            
            print(f"\nSample Receipts:")
            for rid, date, vendor, amount, code, name, desc in receipts[:15]:
                needs_update = (code != target_code)
                marker = "→" if needs_update else "✓"
                print(f"   {marker} #{rid} | {date} | {vendor[:30]:30s} | ${amount:>8,.2f}")
                print(f"      Current: {code or 'NULL'} — {name or 'No Name'}")
                print(f"      Description: {(desc or '')[:80]}")
                
                if needs_update:
                    all_updates.append((rid, code, target_code, target_name, vendor, amount, desc))
            
            if len(receipts) > 15:
                print(f"   ... and {len(receipts) - 15} more")
            
            print(f"\n   Target GL: {target_code} — {target_name}")
            needs_update_count = sum(1 for r in receipts if r[4] != target_code)
            print(f"   Receipts needing update: {needs_update_count}")
    
    # Summary
    print("\n" + "=" * 100)
    print(f"📊 SUMMARY - {len(all_updates)} RECEIPTS TO UPDATE")
    print("=" * 100)
    
    if all_updates:
        # Group by target code
        by_target = defaultdict(list)
        for rid, old_code, target_code, target_name, vendor, amount, desc in all_updates:
            by_target[target_code].append((rid, old_code, vendor, amount))
        
        for target_code in sorted(by_target.keys()):
            items = by_target[target_code]
            total = sum(item[3] for item in items)
            print(f"\nMove to {target_code}:")
            print(f"   {len(items)} receipts, ${total:,.2f} total")
        
        response = input("\n⚠️  Proceed with updates? (yes/no): ").strip().lower()
        
        if response == 'yes':
            print("\n🔄 UPDATING RECEIPTS...")
            
            updated_count = 0
            for cat_name, pattern, target_code, target_name in categories:
                cur.execute("""
                    UPDATE receipts
                    SET gl_account_code = %s,
                        gl_account_name = %s
                    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
                      AND description ~* %s
                      AND COALESCE(gl_account_code, '') != %s
                    RETURNING receipt_id
                """, (target_code, target_name, pattern, target_code))
                
                updated = cur.fetchall()
                count = len(updated)
                updated_count += count
                print(f"   {cat_name}: Updated {count} receipts to {target_code}")
            
            conn.commit()
            print(f"\n✅ Total updated: {updated_count} receipts")
            print("✅ Changes committed")
            
            # Show final state
            print("\n" + "=" * 100)
            print("📊 FINAL STATE")
            print("=" * 100)
            
            for cat_name, pattern, target_code, target_name in categories:
                cur.execute("""
                    SELECT COUNT(*), SUM(gross_amount)
                    FROM receipts
                    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
                      AND description ~* %s
                      AND gl_account_code = %s
                """, (pattern, target_code))
                
                count, total = cur.fetchone()
                print(f"{cat_name}: {count or 0} receipts in {target_code}, ${total or 0:,.2f}")
        else:
            print("\n❌ Update cancelled")
    else:
        print("\n✅ All receipts already have correct GL codes")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    consolidate_client_supplies()
