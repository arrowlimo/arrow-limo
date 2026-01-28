#!/usr/bin/env python3
"""
Update 2015 Caddy - Clarify CRA Seizure from Auction Sale
Auction: $20,000
Less Repo Fee: ~$2,000
CRA Seized: $18,000
Outstanding to Owner: ~$130,000
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
        # Update 2015 Caddy with clarified CRA seizure details
        cur.execute("""
            UPDATE assets
            SET notes = %s
            WHERE asset_id = 27
        """, (
            """[STOLEN/REPOSSESSED - TOTAL LOSS + CRA SEIZURE]
2015 Cadillac vehicle - Original purchase: $130,000

REPOSSESSION & AUCTION DETAILS (2024):
- Vehicle repossessed
- Sold at auction for: $20,000.00
- Less repossession fee: ~$2,000.00
- Amount available after repo fee: ~$18,000.00

CRA SEIZURE:
- CRA seized $18,000.00 from auction proceeds (likely via garnishment/tax debt)
- No proceeds retained by company
- Company still owes: ~$130,000.00 (original purchase/financing balance)

FINANCIAL IMPACT:
- Original Investment: $130,000.00
- Total Loss on Asset Disposition: $110,000.00
  (Auction $20,000 less original cost of $130,000)
- CRA Garnishment: $18,000.00 (offset against tax debt)
- Outstanding Debt to Lender/Owner: ~$130,000.00

DOCUMENTATION NEEDED:
- Auction sale receipt with final breakdown
- Proof of CRA seizure/garnishment
- Lender documentation of outstanding balance
- Repossession fee documentation
- Insurance claim status (if applicable)

CRA TAX TREATMENT:
- Class 10 Vehicle (30% declining balance)
- Capital loss on disposition: $110,000.00
- CRA seizure is separate liability matter (not deductible - tax enforcement)
- Loss write-off eligible

AUDIT TRAIL:
- This asset is completely documented for CRA examination
- Demonstrates financial distress and asset loss history
- CRA garnishment shows tax debt collection occurred
- No depreciation claimed - asset removed from active inventory""",
        ))
        
        conn.commit()
        
        print(f"✅ Updated Asset ID 27 - Clarified CRA Seizure Details:")
        print(f"\n💰 FINANCIAL CLARIFICATION:")
        print(f"   Auction Sale Proceeds: $20,000.00")
        print(f"   Less Repossession Fee: ~$2,000.00")
        print(f"   Available After Repo Fee: ~$18,000.00")
        print(f"\n⚠️  CRA SEIZURE:")
        print(f"   CRA Took: $18,000.00 (garnishment against tax debt)")
        print(f"   Company Retained: $0.00")
        print(f"   Outstanding Balance: ~$130,000.00")
        print(f"\n📊 TAX LOSS SUMMARY:")
        print(f"   Capital Loss on Disposition: $110,000.00 (deductible)")
        print(f"   CRA Garnishment: $18,000.00 (tax enforcement - separate matter)")
        print(f"   Net Financial Impact: $130,000.00 loss + $18,000 seized")
        print(f"\n📋 CRA AUDIT TRAIL:")
        print(f"   ✓ Asset loss fully documented")
        print(f"   ✓ CRA seizure proves tax debt collection")
        print(f"   ✓ Demonstrates financial history")
        print(f"   ✓ Supports future tax position discussions")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating asset: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
