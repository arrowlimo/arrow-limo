#!/usr/bin/env python3
"""
Add/Update Mercedes L-1 - Written Off, CRA Took Insurance Proceeds
"""
import os
import psycopg2
from datetime import datetime
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # First, check if Mercedes L-1 exists
        cur.execute("""
            SELECT asset_id FROM assets 
            WHERE asset_name ILIKE '%Mercedes%L-1%' OR asset_name ILIKE '%L-1%Mercedes%'
        """)
        
        existing = cur.fetchone()
        
        notes = """[WRITTEN OFF - CRA TOOK INSURANCE PROCEEDS]
Mercedes L-1 - Written off/totaled
Vehicle declared total loss
Insurance claim filed and processed
CRA took/seized insurance proceeds

FINANCIAL DETAILS:
- Original Purchase: [pending - user to provide]
- Insurance Claim Amount: [pending - user to provide]
- CRA Seizure: [pending - user to provide]
- Outstanding Balance: [pending - user to provide]

DOCUMENTATION STATUS:
- ⏳ Insurance claim documents (pending)
- ⏳ Insurance payout details (pending)
- ⏳ CRA seizure documentation (pending)
- ⏳ Write-off/total loss assessment (pending)

AUDIT TRAIL:
- Asset removed from service (total loss)
- Insurance proceeds seized by CRA
- Demonstrates CRA debt collection history
- Financial impact to be quantified when documents located"""
        
        if existing:
            # Update existing
            asset_id = existing[0]
            cur.execute("""
                UPDATE assets
                SET status = %s, notes = %s
                WHERE asset_id = %s
            """, ('disposed', notes, asset_id))
            print(f"✅ Updated existing Mercedes L-1 (Asset ID: {asset_id})")
        else:
            # Create new asset
            cur.execute("""
                INSERT INTO assets (
                    asset_name, asset_category, make, model,
                    ownership_status, status, notes, created_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                ) RETURNING asset_id
            """, (
                "Mercedes L-1 (Written Off - Total Loss)",
                "vehicle",
                "Mercedes-Benz",
                "L-1",
                "loaned_in",  # Not owned - written off
                "disposed",
                notes,
                datetime.now()
            ))
            asset_id = cur.fetchone()[0]
            print(f"✅ Created new asset - Mercedes L-1 (Asset ID: {asset_id})")
        
        conn.commit()
        
        print(f"\n📋 ASSET RECORD READY FOR DOCUMENTATION:")
        print(f"   Status: Disposed (Written Off - Total Loss)")
        print(f"   Issue: Insurance proceeds seized by CRA")
        print(f"\n⏳ PENDING USER DOCUMENTATION:")
        print(f"   - Insurance claim documents")
        print(f"   - Insurance payout amount")
        print(f"   - CRA seizure amount/documentation")
        print(f"   - Original vehicle cost")
        print(f"   - Outstanding financing balance")
        print(f"\n💡 NEXT STEP:")
        print(f"   Once you find the files, run:")
        print(f"   python scripts/update_mercedes_l1_details.py")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
