"""
Create/Update GL 5116 for Client Amenities
- Create or update 5116 "Client Amenities - Food, Coffee, Supplies"
- Move client food/amenities receipts to 5116
- Show before/after stats
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def setup_client_amenities():
    """Setup 5116 for client amenities"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("SETUP GL 5116 - CLIENT AMENITIES")
    print("=" * 80)
    
    # 1. Check if 5116 exists
    print("\n📊 CHECKING GL CODE 5116...")
    cur.execute("""
        SELECT account_code, account_name, account_type
        FROM chart_of_accounts
        WHERE account_code = '5116'
    """)
    
    existing = cur.fetchone()
    if existing:
        print(f"   Found: {existing[0]} — {existing[1]} ({existing[2]})")
    else:
        print("   Not found - will create new")
    
    # 2. Create or update 5116
    print("\n📝 SETTING UP GL ACCOUNT 5116...")
    cur.execute("""
        INSERT INTO chart_of_accounts (account_code, account_name, account_type, description)
        VALUES ('5116', 'Client Amenities - Food, Coffee, Supplies', 'Expense', 
                'Food, coffee, balloons, and other amenities provided to charter clients')
        ON CONFLICT (account_code) 
        DO UPDATE SET 
            account_name = 'Client Amenities - Food, Coffee, Supplies',
            description = 'Food, coffee, balloons, and other amenities provided to charter clients'
        RETURNING account_code, account_name
    """)
    
    result = cur.fetchone()
    if result:
        print(f"   ✅ {result[0]} — {result[1]}")
    
    # 3. Find client food/amenity receipts from 2019
    print("\n🔍 FINDING CLIENT FOOD/AMENITY RECEIPTS (2019 patterns)...")
    cur.execute("""
        SELECT 
            r.vendor_name,
            COUNT(*) as count,
            SUM(r.gross_amount) as total,
            STRING_AGG(DISTINCT r.gl_account_code, ', ') as current_codes
        FROM receipts r
        WHERE EXTRACT(YEAR FROM r.receipt_date) = 2019
          AND (r.description ~* 'client food|client amenity|amenities|balloon|coffee.*client|snack.*client'
               OR r.vendor_name ~* 'superstore|safeway|sobeys|walmart|costco|save.*on|pizza|subway|tim horton|starbucks')
        GROUP BY r.vendor_name
        HAVING COUNT(*) >= 2
        ORDER BY count DESC
    """)
    
    vendors_2019 = cur.fetchall()
    print(f"   Found {len(vendors_2019)} vendor patterns from 2019:")
    for vendor, count, total, codes in vendors_2019[:15]:
        print(f"   {vendor}: {count} receipts, ${total:,.2f} (currently: {codes or 'NULL'})")
    
    # 4. Find all receipts to move to 5116
    print("\n🔍 FINDING ALL CLIENT AMENITY RECEIPTS TO MOVE...")
    cur.execute("""
        SELECT 
            receipt_id,
            vendor_name,
            receipt_date,
            gross_amount,
            gl_account_code,
            gl_account_name,
            description
        FROM receipts
        WHERE (description ~* 'client food|client amenity|amenities|balloon|coffee.*client|snack.*client'
               OR (vendor_name ~* 'superstore|safeway|sobeys|walmart|costco|save.*on|pizza|subway|tim horton|starbucks'
                   AND description ~* 'client|charter|amenity'))
          AND COALESCE(gl_account_code, '') != '5116'
        ORDER BY receipt_date
    """)
    
    to_update = cur.fetchall()
    print(f"   Found {len(to_update)} receipts to move to 5116")
    
    if to_update:
        print("\n   Sample receipts to update:")
        for rid, vendor, date, amount, old_code, old_name, desc in to_update[:15]:
            print(f"   #{rid}: {vendor} ({date}) ${amount:,.2f}")
            print(f"      {old_code or 'NULL'} → 5116 | {(desc or '')[:60]}")
    
    # 5. Show current state before update
    print("\n📊 CURRENT STATE (before consolidation):")
    cur.execute("""
        SELECT 
            gl_account_code,
            gl_account_name,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE description ~* 'client food|client amenity|amenities|balloon|coffee.*client|snack.*client'
           OR (vendor_name ~* 'superstore|safeway|sobeys|walmart|costco|save.*on|pizza|subway|tim horton|starbucks'
               AND description ~* 'client|charter|amenity')
        GROUP BY gl_account_code, gl_account_name
        ORDER BY gl_account_code
    """)
    
    current = cur.fetchall()
    for code, name, count, total in current:
        print(f"   {code or 'NULL'} — {name or 'No Name'}: {count} receipts, ${total:,.2f}")
    
    # 6. Ask for confirmation
    if to_update:
        print(f"\n⚠️  READY TO UPDATE {len(to_update)} RECEIPTS")
        print("   This will move client food/amenity receipts to 5116")
        response = input("\n   Proceed? (yes/no): ").strip().lower()
        
        if response == 'yes':
            print("\n🔄 UPDATING RECEIPTS...")
            cur.execute("""
                UPDATE receipts
                SET gl_account_code = '5116',
                    gl_account_name = 'Client Amenities - Food, Coffee, Supplies'
                WHERE (description ~* 'client food|client amenity|amenities|balloon|coffee.*client|snack.*client'
                       OR (vendor_name ~* 'superstore|safeway|sobeys|walmart|costco|save.*on|pizza|subway|tim horton|starbucks'
                           AND description ~* 'client|charter|amenity'))
                  AND COALESCE(gl_account_code, '') != '5116'
            """)
            
            updated_count = cur.rowcount
            print(f"   ✅ Updated {updated_count} receipts")
            
            # Commit changes
            conn.commit()
            print("   ✅ Changes committed")
            
            # 7. Show final state
            print("\n📊 FINAL STATE (after consolidation):")
            cur.execute("""
                SELECT 
                    gl_account_code,
                    gl_account_name,
                    COUNT(*) as count,
                    SUM(gross_amount) as total
                FROM receipts
                WHERE gl_account_code = '5116'
                   OR description ~* 'client food|client amenity|amenities|balloon|coffee.*client|snack.*client'
                   OR (vendor_name ~* 'superstore|safeway|sobeys|walmart|costco|save.*on|pizza|subway|tim horton|starbucks'
                       AND description ~* 'client|charter|amenity')
                GROUP BY gl_account_code, gl_account_name
                ORDER BY gl_account_code
            """)
            
            final = cur.fetchall()
            for code, name, count, total in final:
                print(f"   {code or 'NULL'} — {name or 'No Name'}: {count} receipts, ${total:,.2f}")
        else:
            print("\n❌ Update cancelled")
    else:
        conn.commit()
        print("\n✅ GL account 5116 created/updated (no receipts to move)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Setup Complete")
    print("=" * 80)
    print("\nSUMMARY:")
    print("   • 5116 'Client Amenities - Food, Coffee, Supplies' ready")
    print("   • Use for: client food, coffee, balloons, snacks, supplies")
    print("   • Distinct from 4115 (beverages/drinks)")
    print("=" * 80)


if __name__ == "__main__":
    setup_client_amenities()
