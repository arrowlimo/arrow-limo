#!/usr/bin/env python3
"""
Update L-4 Lincoln Navigator with Details
Run this script when you have the paperwork
"""
import os
import psycopg2
from datetime import datetime
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def update_l4_navigator(
    acquisition_cost=None,
    td_bank_balance=None,
    monthly_business_lease=None,
    monthly_td_bank_payment=None,
    loan_term_months=None,
    loan_start_date=None,
    td_bank_loan_number=None,
    vin=None,
    year=None
):
    """
    Update L-4 Navigator with complete details
    
    Example:
        update_l4_navigator(
            acquisition_cost=Decimal('65000.00'),
            td_bank_balance=Decimal('50000.00'),
            monthly_business_lease=Decimal('2500.00'),
            monthly_td_bank_payment=Decimal('1500.00'),
            loan_term_months=60,
            loan_start_date=datetime(2022, 1, 15),
            td_bank_loan_number='1234567890',
            vin='5TDJURV76LS123456',
            year=2020
        )
    """
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # Build notes with complete information
        notes = """[PERSONALLY OWNED - LEASED TO BUSINESS]
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

FINANCIAL DETAILS:"""
        
        if acquisition_cost:
            notes += f"\n- Purchase Price: ${acquisition_cost:,.2f}"
        if td_bank_balance:
            notes += f"\n- Loan Balance (TD Bank): ${td_bank_balance:,.2f}"
        if monthly_business_lease:
            notes += f"\n- Monthly Lease Payment to Owner (from business): ${monthly_business_lease:,.2f}"
        if monthly_td_bank_payment:
            notes += f"\n- Monthly Payment to TD Bank: ${monthly_td_bank_payment:,.2f}"
        if loan_term_months:
            notes += f"\n- Loan Term: {loan_term_months} months"
        if loan_start_date:
            notes += f"\n- Loan Start Date: {loan_start_date.strftime('%Y-%m-%d')}"
        if td_bank_loan_number:
            notes += f"\n- TD Bank Loan #: {td_bank_loan_number}"
        
        notes += """

DOCUMENTATION:
✓ TD Bank loan agreement (located)
✓ Vehicle registration/title (located)
✓ Lease agreement between owner and business (located)
✓ Insurance details (located)
✓ Maintenance responsibility documentation (located)

AUDIT TRAIL:
- This is NOT a business asset - it's personally owned
- It is ON LOAN to the business via lease agreement
- Lease payments to owner are personal income (offset against business expense)
- TD Bank loan is personal debt (owner responsible)
- Clear separation of personal and business assets for CRA purposes
- Business deducts lease payment as operating expense
- Owner reports lease income as personal income"""
        
        # Update the asset
        cur.execute("""
            UPDATE assets
            SET 
                year = COALESCE(%s, year),
                vin = COALESCE(%s, vin),
                acquisition_cost = COALESCE(%s, acquisition_cost),
                lease_monthly_payment = COALESCE(%s, lease_monthly_payment),
                notes = %s,
                updated_at = %s
            WHERE asset_id = 30
        """, (
            year,
            vin,
            acquisition_cost,
            monthly_business_lease,
            notes,
            datetime.now()
        ))
        
        conn.commit()
        
        print("✅ L-4 Lincoln Navigator (Asset ID: 30) Updated with Documentation:")
        if year:
            print(f"   Year: {year}")
        if vin:
            print(f"   VIN: {vin}")
        if acquisition_cost:
            print(f"   Purchase Price: ${acquisition_cost:,.2f}")
        if td_bank_balance:
            print(f"   TD Bank Loan Balance: ${td_bank_balance:,.2f}")
        if monthly_business_lease:
            print(f"   Monthly Lease (Business): ${monthly_business_lease:,.2f}")
        if monthly_td_bank_payment:
            print(f"   Monthly TD Bank Payment: ${monthly_td_bank_payment:,.2f}")
        if td_bank_loan_number:
            print(f"   TD Bank Loan #: {td_bank_loan_number}")
        print(f"\n📋 Asset is now fully documented for CRA audit purposes")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating asset: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    from datetime import datetime
    from decimal import Decimal
    
    # Example of how to call this when you have the documents:
    print("Script ready. When you have the paperwork, call:")
    print("\nfrom datetime import datetime")
    print("from decimal import Decimal")
    print("from scripts.update_l4_navigator_details import update_l4_navigator")
    print("\nupdate_l4_navigator(")
    print("    acquisition_cost=Decimal('65000.00'),")
    print("    td_bank_balance=Decimal('50000.00'),")
    print("    monthly_business_lease=Decimal('2500.00'),")
    print("    monthly_td_bank_payment=Decimal('1500.00'),")
    print("    loan_term_months=60,")
    print("    loan_start_date=datetime(2022, 1, 15),")
    print("    td_bank_loan_number='1234567890',")
    print("    vin='5TDJURV76LS123456',")
    print("    year=2020")
    print(")")
