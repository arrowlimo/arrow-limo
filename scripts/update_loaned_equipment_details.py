#!/usr/bin/env python3
"""
Update Loaned Office Equipment Details
Update details for 5 computer desktops and 1 AC unit when information is available
"""
import os
import psycopg2
from datetime import datetime
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def update_computer_desktop(
    desktop_number,
    owner_name=None,
    make=None,
    model=None,
    serial_number=None,
    borrowing_date=None,
    condition=None,
    loan_terms=None
):
    """Update individual computer desktop details"""
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        asset_id = 30 + desktop_number  # Asset IDs 31-35 for desktops 1-5
        
        notes = f"""[LOANED EQUIPMENT - NOT OWNED]
Computer Desktop Unit {desktop_number}
Type: Desktop Computer
Location: Office
Status: Loaned to Arrow Limousine

OWNERSHIP:
- Legal Owner: {owner_name or '[pending]'}
- Borrowing Date: {borrowing_date.strftime('%Y-%m-%d') if borrowing_date else '[pending]'}
- Loan Agreement: {loan_terms or '[pending]'}
- Equipment Condition: {condition or '[pending]'}

DETAILS:
- Make: {make or '[pending]'}
- Model: {model or '[pending]'}
- Serial Number: {serial_number or '[pending]'}

AUDIT TRAIL:
- This is NOT a business asset
- Equipment is loaned from external source
- NOT depreciable by business
- NOT a business expense
- Owner and loan terms documented"""
        
        cur.execute("""
            UPDATE assets
            SET 
                make = COALESCE(%s, make),
                model = COALESCE(%s, model),
                serial_number = COALESCE(%s, serial_number),
                legal_owner = COALESCE(%s, legal_owner),
                notes = %s,
                updated_at = %s
            WHERE asset_id = %s
        """, (make, model, serial_number, owner_name, notes, datetime.now(), asset_id))
        
        conn.commit()
        print(f"✅ Updated Desktop {desktop_number} (Asset ID: {asset_id})")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating Desktop {desktop_number}: {e}")
    finally:
        cur.close()
        conn.close()


def update_ac_unit(
    owner_name=None,
    make=None,
    model=None,
    serial_number=None,
    capacity=None,
    borrowing_date=None,
    condition=None,
    maintenance_responsibility=None,
    loan_terms=None
):
    """Update AC unit details"""
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        asset_id = 36  # AC unit is asset ID 36
        
        notes = f"""[LOANED EQUIPMENT - NOT OWNED]
Upright Air Conditioning Unit
Type: HVAC/Climate Control
Location: Office
Status: Loaned to Arrow Limousine

OWNERSHIP:
- Legal Owner: {owner_name or '[pending]'}
- Borrowing Date: {borrowing_date.strftime('%Y-%m-%d') if borrowing_date else '[pending]'}
- Loan Agreement: {loan_terms or '[pending]'}
- Equipment Condition: {condition or '[pending]'}
- Maintenance Responsibility: {maintenance_responsibility or '[pending]'}

DETAILS:
- Make: {make or '[pending]'}
- Model: {model or '[pending]'}
- Serial Number: {serial_number or '[pending]'}
- Capacity/Specifications: {capacity or '[pending]'}

AUDIT TRAIL:
- This is NOT a business asset
- Equipment is loaned from external source
- NOT depreciable by business
- NOT a business expense
- Owner and loan terms documented"""
        
        cur.execute("""
            UPDATE assets
            SET 
                make = COALESCE(%s, make),
                model = COALESCE(%s, model),
                serial_number = COALESCE(%s, serial_number),
                legal_owner = COALESCE(%s, legal_owner),
                notes = %s,
                updated_at = %s
            WHERE asset_id = %s
        """, (make, model, serial_number, owner_name, notes, datetime.now(), asset_id))
        
        conn.commit()
        print(f"✅ Updated AC Unit (Asset ID: {asset_id})")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating AC Unit: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    from datetime import datetime
    
    # Example of how to call when you have the information:
    print("Script ready for updating loaned equipment details.")
    print("\nExample calls:")
    print("\nFor computer desktop:")
    print("from datetime import datetime")
    print("from scripts.update_loaned_equipment_details import update_computer_desktop")
    print("update_computer_desktop(")
    print("    desktop_number=1,")
    print("    owner_name='John Doe',")
    print("    make='Dell',")
    print("    model='OptiPlex 7090',")
    print("    serial_number='ABC123XYZ',")
    print("    borrowing_date=datetime(2023, 6, 15),")
    print("    condition='Good',")
    print("    loan_terms='Indefinite loan, return at borrower discretion'")
    print(")")
    print("\nFor AC unit:")
    print("from scripts.update_loaned_equipment_details import update_ac_unit")
    print("update_ac_unit(")
    print("    owner_name='Facilities Corp',")
    print("    make='LG',")
    print("    model='AQ48UBJ',")
    print("    serial_number='SN789456',")
    print("    capacity='48000 BTU',")
    print("    borrowing_date=datetime(2022, 1, 1),")
    print("    condition='Good',")
    print("    maintenance_responsibility='Owner maintains',")
    print("    loan_terms='Indefinite loan'")
    print(")")
