"""
Consolidate Client Beverage GL Codes to 4115
- Move all client beverage receipts to 4115 "Beverage Service Charges"
- Update GL account name to make it clearer
- Show before/after stats
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def consolidate_beverage():
    """Consolidate beverage codes to 4115"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("CONSOLIDATE CLIENT BEVERAGE TO 4115")
    print("=" * 80)
    
    # 1. Check current beverage receipts
    print("\n📊 CURRENT BEVERAGE RECEIPTS:")
    cur.execute("""
        SELECT 
            gl_account_code,
            gl_account_name,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE vendor_name ~* 'beverage|curvy|bottle|liquor|wine|beer'
           OR gl_account_code IN ('4115', '5310', '5315')
           OR gl_account_name ~* 'beverage|bev'
        GROUP BY gl_account_code, gl_account_name
        ORDER BY gl_account_code
    """)
    
    current = cur.fetchall()
    for code, name, count, total in current:
        print(f"   {code or 'NULL'} — {name or 'No Name'}: {count} receipts, ${total:,.2f}")
    
    # 2. Update chart_of_accounts to clarify 4115
    print("\n📝 UPDATING GL ACCOUNT 4115...")
    cur.execute("""
        UPDATE chart_of_accounts
        SET account_name = 'Client Beverage Service Charges',
            description = 'Beverages provided to charter clients (water, soft drinks, alcohol) - billable service'
        WHERE account_code = '4115'
        RETURNING account_code, account_name
    """)
    
    updated = cur.fetchone()
    if updated:
        print(f"   ✅ Updated: {updated[0]} — {updated[1]}")
    
    # 3. Find receipts to consolidate
    print("\n🔍 FINDING RECEIPTS TO CONSOLIDATE...")
    cur.execute("""
        SELECT 
            receipt_id,
            vendor_name,
            receipt_date,
            gross_amount,
            gl_account_code,
            gl_account_name
        FROM receipts
        WHERE (vendor_name ~* 'curvy|bottle' 
               OR gl_account_code IN ('5310', '5315'))
          AND gl_account_code != '4115'
        ORDER BY receipt_date
    """)
    
    to_update = cur.fetchall()
    print(f"   Found {len(to_update)} receipts to move to 4115")
    
    if to_update:
        print("\n   Sample receipts to update:")
        for rid, vendor, date, amount, old_code, old_name in to_update[:10]:
            print(f"   #{rid}: {vendor} ({date}) ${amount:,.2f} | {old_code} → 4115")
    
    # 4. Update receipts
    if to_update:
        print(f"\n🔄 UPDATING {len(to_update)} RECEIPTS...")
        cur.execute("""
            UPDATE receipts
            SET gl_account_code = '4115',
                gl_account_name = 'Client Beverage Service Charges'
            WHERE (vendor_name ~* 'curvy|bottle' 
                   OR gl_account_code IN ('5310', '5315'))
              AND gl_account_code != '4115'
        """)
        
        updated_count = cur.rowcount
        print(f"   ✅ Updated {updated_count} receipts")
        
        # Commit changes
        conn.commit()
        print("   ✅ Changes committed")
    else:
        print("   ℹ️  No receipts need updating")
    
    # 5. Show final state
    print("\n📊 FINAL BEVERAGE RECEIPTS (after consolidation):")
    cur.execute("""
        SELECT 
            gl_account_code,
            gl_account_name,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE vendor_name ~* 'beverage|curvy|bottle|liquor|wine|beer'
           OR gl_account_code IN ('4115', '5310', '5315')
           OR gl_account_name ~* 'beverage|bev'
        GROUP BY gl_account_code, gl_account_name
        ORDER BY gl_account_code
    """)
    
    final = cur.fetchall()
    for code, name, count, total in final:
        print(f"   {code or 'NULL'} — {name or 'No Name'}: {count} receipts, ${total:,.2f}")
    
    # 6. Check if old codes can be deleted
    print("\n🗑️  OLD BEVERAGE CODES STATUS:")
    for old_code in ['5310', '5315']:
        cur.execute("""
            SELECT COUNT(*) 
            FROM receipts 
            WHERE gl_account_code = %s
        """, (old_code,))
        count = cur.fetchone()[0]
        
        if count == 0:
            print(f"   {old_code} — Safe to delete (0 receipts)")
        else:
            print(f"   {old_code} — Still in use ({count} receipts)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Consolidation Complete")
    print("=" * 80)
    print("\nRECOMMENDATION:")
    print("   • 4115 is now 'Client Beverage Service Charges'")
    print("   • All client beverage receipts consolidated")
    print("   • Consider deleting unused 5310/5315 if count = 0")
    print("=" * 80)


if __name__ == "__main__":
    consolidate_beverage()
