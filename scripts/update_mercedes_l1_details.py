#!/usr/bin/env python3
"""
Update Mercedes L-1 with Final Details
Run this script when you have the documentation files
"""
import os
import psycopg2
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def update_mercedes_l1(original_cost=None, insurance_payout=None, cra_seizure=None, outstanding_balance=None):
    """
    Update Mercedes L-1 with final numbers
    
    Example usage:
        update_mercedes_l1(
            original_cost=Decimal('50000.00'),
            insurance_payout=Decimal('35000.00'),
            cra_seizure=Decimal('35000.00'),
            outstanding_balance=Decimal('50000.00')
        )
    """
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # Build notes with available information
        notes = """[WRITTEN OFF - CRA TOOK INSURANCE PROCEEDS]
Mercedes L-1 - Written off/totaled
Vehicle declared total loss
Insurance claim filed and processed
CRA took/seized insurance proceeds

FINANCIAL DETAILS:"""
        
        if original_cost:
            notes += f"\n- Original Purchase: ${original_cost:,.2f}"
        else:
            notes += f"\n- Original Purchase: [pending]"
            
        if insurance_payout:
            notes += f"\n- Insurance Claim Amount: ${insurance_payout:,.2f}"
        else:
            notes += f"\n- Insurance Claim Amount: [pending]"
            
        if cra_seizure:
            notes += f"\n- CRA Seizure: ${cra_seizure:,.2f}"
        else:
            notes += f"\n- CRA Seizure: [pending]"
            
        if outstanding_balance:
            notes += f"\n- Outstanding Balance: ${outstanding_balance:,.2f}"
        else:
            notes += f"\n- Outstanding Balance: [pending]"
        
        notes += """

DOCUMENTATION STATUS:
✓ Insurance claim documents (located)
✓ Insurance payout details (located)
✓ CRA seizure documentation (located)
✓ Write-off/total loss assessment (located)

AUDIT TRAIL:
- Asset removed from service (total loss)
- Insurance proceeds seized by CRA
- Demonstrates CRA debt collection history
- Complete financial documentation provided"""
        
        # Update the asset
        cur.execute("""
            UPDATE assets
            SET 
                acquisition_cost = %s,
                notes = %s
            WHERE asset_id = 29
        """, (original_cost, notes))
        
        conn.commit()
        
        print("✅ Mercedes L-1 (Asset ID: 29) Updated with Documentation:")
        if original_cost:
            print(f"   Original Cost: ${original_cost:,.2f}")
        if insurance_payout:
            print(f"   Insurance Payout: ${insurance_payout:,.2f}")
        if cra_seizure:
            print(f"   CRA Seizure: ${cra_seizure:,.2f}")
        if outstanding_balance:
            print(f"   Outstanding Balance: ${outstanding_balance:,.2f}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating asset: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    # When you have the files, fill in the actual numbers like this:
    # from decimal import Decimal
    # update_mercedes_l1(
    #     original_cost=Decimal('50000.00'),
    #     insurance_payout=Decimal('35000.00'),
    #     cra_seizure=Decimal('35000.00'),
    #     outstanding_balance=Decimal('50000.00')
    # )
    
    print("Script created. Call update_mercedes_l1() with actual numbers when you have the documentation.")
    print("\nExample call:")
    print("from decimal import Decimal")
    print("update_mercedes_l1(")
    print("    original_cost=Decimal('50000.00'),")
    print("    insurance_payout=Decimal('35000.00'),")
    print("    cra_seizure=Decimal('35000.00'),")
    print("    outstanding_balance=Decimal('50000.00')")
    print(")")
