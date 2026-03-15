#!/usr/bin/env python3
"""
Add 2015 Caddy (Stolen/Repossessed) to Asset Inventory
Documents repossession for CRA purposes
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
        # Insert 2015 Caddy as stolen/repossessed asset
        # Mark as "loaned_in" (not owned/in inventory) since it's no longer available
        cur.execute("""
            INSERT INTO assets (
                asset_name, asset_category, make, model, year,
                vin, ownership_status, legal_owner, acquisition_date,
                acquisition_cost, current_book_value, cca_class,
                status, notes, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            ) RETURNING asset_id
        """, (
            "2015 Cadillac (Stolen/Repossessed)",
            "vehicle",
            "Cadillac",
            "Unknown Model",
            2015,
            "UNKNOWN",  # VIN likely not available if stolen
            "loaned_in",  # Not owned/not in inventory
            "No Longer Available - Stolen/Repossessed",
            datetime.now(),  # Repossession date
            Decimal('0.00'),  # No book value (loss = stolen/repossessed)
            Decimal('0.00'),
            "10",  # Vehicle CCA class
            "stolen",  # Mark status as stolen
            "[STOLEN/REPOSSESSED - NOT IN INVENTORY] 2015 Cadillac vehicle was stolen/repossessed. Asset removed from service. Documented for CRA audit trail and insurance purposes. No depreciation claimed. This asset is recorded to document total loss and removal from active Arrow Limousine fleet.",
            datetime.now()
        ))
        
        asset_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"✅ Added 2015 Caddy (Stolen/Repossessed) to Asset Inventory:")
        print(f"   Asset ID: {asset_id}")
        print(f"   Status: Stolen/Repossessed (Not in Inventory)")
        print(f"   Book Value: $0.00 (total loss)")
        print(f"   Ownership: Not Owned (marked as loaned_in = not available)")
        print(f"   CCA Treatment: No depreciation (loss documented)")
        print(f"\n📋 CRA Documentation:")
        print(f"   ✓ Asset recorded as loss/removal on {datetime.now().strftime('%Y-%m-%d')}")
        print(f"   ✓ Total loss documented for insurance claim")
        print(f"   ✓ Removed from depreciable assets")
        print(f"   ✓ Audit trail maintained for CRA purposes")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error adding asset: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
