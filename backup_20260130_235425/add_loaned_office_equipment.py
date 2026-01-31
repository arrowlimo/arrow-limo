#!/usr/bin/env python3
"""
Add Loaned Office Equipment - 5 Computer Desktops + 1 AC Unit
Loaned to business, not owned
"""
import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # Add 5 computer desktops
        for i in range(1, 6):
            cur.execute("""
                INSERT INTO assets (
                    asset_name, asset_category, make, model,
                    ownership_status, legal_owner, location,
                    status, notes, created_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                ) RETURNING asset_id
            """, (
                f"Computer Desktop {i} (Loaned)",
                "electronics",
                "Unknown",
                "Desktop Computer",
                "loaned_in",
                "Unknown Owner (Pending)",
                "Office",
                "active",
                f"""[LOANED EQUIPMENT - NOT OWNED]
Computer Desktop Unit {i}
Type: Desktop Computer
Location: Office
Status: Loaned to Arrow Limousine

OWNERSHIP:
- Legal Owner: [pending - user to provide]
- Borrowing Date: [pending - user to provide]
- Loan Agreement: [pending - user to provide]
- Return Condition: [pending - user to provide]

DETAILS:
- Make/Model: [pending]
- Serial Number: [pending]
- Condition: [pending]
- Original Owner: [pending]

AUDIT TRAIL:
- This is NOT a business asset
- Equipment is loaned from external source
- NOT depreciable by business
- NOT a business expense
- Must document owner and loan terms""",
                datetime.now()
            ))
            asset_id = cur.fetchone()[0]
            print(f"✅ Created Desktop {i} (Asset ID: {asset_id})")
        
        # Add upright AC unit
        cur.execute("""
            INSERT INTO assets (
                asset_name, asset_category, make, model,
                ownership_status, legal_owner, location,
                status, notes, created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            ) RETURNING asset_id
        """, (
            "Upright AC Unit (Loaned)",
            "equipment",
            "Unknown",
            "Air Conditioning Unit",
            "loaned_in",
            "Unknown Owner (Pending)",
            "Office",
            "active",
            """[LOANED EQUIPMENT - NOT OWNED]
Upright Air Conditioning Unit
Type: HVAC/Climate Control
Location: Office
Status: Loaned to Arrow Limousine

OWNERSHIP:
- Legal Owner: [pending - user to provide]
- Borrowing Date: [pending - user to provide]
- Loan Agreement: [pending - user to provide]
- Return Condition: [pending - user to provide]

DETAILS:
- Make/Model: [pending]
- Serial Number: [pending]
- Capacity/Specifications: [pending]
- Condition: [pending]
- Original Owner: [pending]
- Maintenance Responsibility: [pending]

AUDIT TRAIL:
- This is NOT a business asset
- Equipment is loaned from external source
- NOT depreciable by business
- NOT a business expense (unless lease payment to owner)
- Must document owner and loan terms""",
            datetime.now()
        ))
        ac_asset_id = cur.fetchone()[0]
        print(f"✅ Created AC Unit (Asset ID: {ac_asset_id})")
        
        conn.commit()
        
        print(f"\n📋 LOANED OFFICE EQUIPMENT ADDED:")
        print(f"   - 5x Computer Desktops (Asset IDs: in system)")
        print(f"   - 1x Upright AC Unit (Asset ID: {ac_asset_id})")
        print(f"\n⏳ PENDING DETAILS FOR EACH ITEM:")
        print(f"   - Legal owner name")
        print(f"   - Borrowing/loan agreement date")
        print(f"   - Loan agreement terms and conditions")
        print(f"   - Equipment make/model and serial numbers")
        print(f"   - Original condition documentation")
        print(f"   - Return/disposal conditions")
        print(f"   - Maintenance responsibility")
        print(f"\n💡 IMPORTANT FOR CRA:")
        print(f"   - These are NOT business assets (not depreciable)")
        print(f"   - These are NOT business expenses (unless paid lease fee)")
        print(f"   - Must clearly document lender/owner")
        print(f"   - Demonstrates proper asset classification")
        print(f"\n📝 NEXT STEP:")
        print(f"   When you have details, run:")
        print(f"   python scripts/update_loaned_equipment_details.py")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
