#!/usr/bin/env python3
"""
Add L-4 Lincoln Navigator - Personally Owned, Leased to Business
Owner: User (personal ownership)
Lender: TD Bank
Status: On lease to Arrow Limousine
"""
import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # Check if L-4 already exists
        cur.execute("""
            SELECT asset_id FROM assets 
            WHERE asset_name ILIKE '%L-4%' OR asset_name ILIKE '%Navigator%L-4%'
        """)
        
        existing = cur.fetchone()
        
        if existing:
            print(f"⚠️  L-4 (Asset ID: {existing[0]}) already exists in database")
            print(f"   Skipping creation. You can update it with details when found.")
            return
        
        # Create L-4 asset
        cur.execute("""
            INSERT INTO assets (
                asset_name, asset_category, make, model,
                ownership_status, legal_owner, lender_contact,
                status, notes, created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            ) RETURNING asset_id
        """, (
            "L-4 Lincoln Navigator (Personal - Leased to Business)",
            "vehicle",
            "Lincoln",
            "Navigator",
            "loaned_in",  # Not owned by business - personal ownership
            "User (Personal Ownership)",
            "TD Bank",
            "active",
            """[PERSONALLY OWNED - LEASED TO BUSINESS]
Lincoln Navigator L-4
Owned by: User (personal, not business)
Financed by: TD Bank
Current Use: Leased to Arrow Limousine business
Vehicle Assignment: L-4

OWNERSHIP STRUCTURE:
- Legal Owner: User (personal)
- Lender: TD Bank
- Business Use: Leased to Arrow Limousine
- Lease Status: Active

FINANCIAL DETAILS:
- Purchase Price: [pending - user to provide]
- Loan Balance (TD Bank): [pending - user to provide]
- Monthly Lease Payment to User: [pending - user to provide]
- TD Bank Monthly Payment: [pending - user to provide]
- Loan Term: [pending - user to provide]
- TD Bank Loan Details: [pending - user to provide]

DOCUMENTATION NEEDED:
- ⏳ TD Bank loan agreement
- ⏳ Vehicle registration/title
- ⏳ Lease agreement between owner and business
- ⏳ Insurance details
- ⏳ Maintenance responsibility documentation

AUDIT TRAIL:
- This is NOT a business asset - it's personally owned
- It is ON LOAN to the business via lease agreement
- Lease payments to owner are personal income
- TD Bank loan is personal debt
- Demonstrates clear separation of personal and business assets""",
            datetime.now()
        ))
        
        asset_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"✅ Created Asset - L-4 Lincoln Navigator (Asset ID: {asset_id})")
        print(f"\n📋 OWNERSHIP STRUCTURE:")
        print(f"   Owner: User (Personal)")
        print(f"   Lender: TD Bank")
        print(f"   Current Use: Leased to Arrow Limousine Business")
        print(f"   Status: Active")
        print(f"\n⏳ PENDING DOCUMENTATION:")
        print(f"   - TD Bank loan details")
        print(f"   - Purchase price and loan balance")
        print(f"   - Monthly payments (business lease + bank)")
        print(f"   - Lease agreement details")
        print(f"   - Insurance and maintenance terms")
        print(f"\n💡 AUDIT TRAIL:")
        print(f"   This asset demonstrates:")
        print(f"   - Clear personal vs business asset separation")
        print(f"   - Legitimate business lease arrangement")
        print(f"   - CRA compliance for asset classification")
        print(f"\n📝 NEXT STEP:")
        print(f"   When you find the paperwork, run:")
        print(f"   python scripts/update_l4_navigator_details.py")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
