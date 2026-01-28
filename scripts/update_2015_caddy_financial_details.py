#!/usr/bin/env python3
"""
Update 2015 Caddy with financial details
Acquisition: $130,000
Repossession/Auction: 2024 - sold for $20,000
Loss: $110,000
Outstanding balance owed to owner: ~$130,000
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
        # Update 2015 Caddy asset with financial details
        cur.execute("""
            UPDATE assets
            SET 
                acquisition_cost = %s,
                acquisition_date = %s,
                current_book_value = %s,
                salvage_value = %s,
                cca_class = %s,
                cca_rate = %s,
                notes = %s,
                legal_owner = %s
            WHERE asset_id = 27
        """, (
            Decimal('130000.00'),  # Original purchase price
            datetime(2024, 1, 1),  # Approx repossession date (user can refine)
            Decimal('0.00'),  # No book value (loss)
            Decimal('20000.00'),  # Auction sale proceeds
            '10',  # Vehicle CCA Class 10
            Decimal('0.30'),  # 30% declining balance
            """[STOLEN/REPOSSESSED - TOTAL LOSS DOCUMENTED]
2015 Cadillac vehicle - Original purchase: $130,000
Repossessed in 2024 and sold at auction for $20,000
Loss on sale: $110,000

FINANCIAL DETAILS:
- Acquisition Cost: $130,000.00
- Auction Sale Proceeds: $20,000.00
- Net Loss: $110,000.00
- Company retains: ~$18,000 of auction proceeds for payment toward debt
- Outstanding Balance to Owner: ~$130,000.00

DOCUMENTATION:
- Auction sale receipt: [pending upload]
- Payment details: [pending from user]
- Insurance claim: [status pending]
- CRA Loss Deduction: Eligible for write-off as capital loss

This asset is recorded for audit trail, insurance documentation, and CRA loss deduction purposes.
No depreciation claimed. Asset removed from active inventory.""",
            "Repossessed - No Longer Owned"
        ))
        
        conn.commit()
        
        print(f"✅ Updated Asset ID 27 - 2015 Cadillac with Financial Details:")
        print(f"\n💰 FINANCIAL SUMMARY:")
        print(f"   Original Purchase Price: $130,000.00")
        print(f"   Repossession Date: 2024 (approx)")
        print(f"   Auction Sale Price: $20,000.00")
        print(f"   Loss on Sale: $110,000.00")
        print(f"   Company Retains: ~$18,000.00")
        print(f"   Outstanding Balance to Owner: ~$130,000.00")
        print(f"\n📊 CRA TAX IMPACT:")
        print(f"   CCA Class: 10 (Vehicle)")
        print(f"   Depreciation Rate: 30% declining balance")
        print(f"   Capital Loss Available: $110,000.00")
        print(f"   Treatment: Write-off as loss on disposition")
        print(f"\n📋 NEXT STEPS:")
        print(f"   1. Obtain exact repossession date from lender")
        print(f"   2. Obtain auction sale receipt with final amounts")
        print(f"   3. Collect payment allocation details")
        print(f"   4. File insurance claim if applicable")
        print(f"   5. Prepare CRA loss documentation package")
        print(f"\n💡 NOTE: Once you have exact numbers, we can update:")
        print(f"   - Exact acquisition date")
        print(f"   - Exact loss amount")
        print(f"   - Exact outstanding balance owed")
        print(f"   - Payment allocation details")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating asset: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
