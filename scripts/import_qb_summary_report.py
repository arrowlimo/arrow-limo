"""
Generate a summary report of QuickBooks data available for import into almsdata.
Shows what can be imported and identifies any schema/data issues.
"""

import pandas as pd
import psycopg2
from datetime import datetime

BACKUP_PATH = r"L:\limo\quickbooks\Arrow Limousine backup 2025 Oct 19, 2025"

def main():
    print("=" * 100)
    print("QUICKBOOKS DATA IMPORT READINESS REPORT")
    print("=" * 100)
    
    # Load data
    print("\nLoading QuickBooks data...")
    journal = pd.read_excel(BACKUP_PATH + r"\Journal.xlsx", skiprows=4)
    journal['Date'] = pd.to_datetime(journal['Date'], format='%d/%m/%Y', errors='coerce')
    
    # Connect to DB
    conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REDACTED***")
    cur = conn.cursor()
    
    # Report sections
    print("\n\n" + "=" * 100)
    print("1. INSURANCE DATA (190 transactions)")
    print("=" * 100)
    
    insurance = journal[journal['Account'].isin(['6400 Insurance', '6950 WCB'])].copy()
    insurance_with_dates = insurance[insurance['Date'].notna()]
    
    print(f"Total insurance transactions: {len(insurance):,}")
    print(f"With valid dates: {len(insurance_with_dates):,}")
    print(f"Date range: {insurance_with_dates['Date'].min()} to {insurance_with_dates['Date'].max()}")
    print(f"Total amount: ${insurance_with_dates['Debit'].sum():,.2f}")
    print(f"\nRECOMMENDATION: Can import {len(insurance_with_dates):,} insurance records")
    print(f"  - Populate vehicle_insurance table")
    print(f"  - Note: Vehicle linkage limited (most don't specify vehicle in memo)")
    
    print("\n\n" + "=" * 100)
    print("2. FUEL DATA (4,418 transactions)")
    print("=" * 100)
    
    fuel = journal[journal['Account'] == '6925 Fuel'].copy()
    fuel_with_dates = fuel[fuel['Date'].notna()]
    
    print(f"Total fuel transactions: {len(fuel):,}")
    print(f"With valid dates: {len(fuel_with_dates):,}")
    print(f"Date range: {fuel_with_dates['Date'].min()} to {fuel_with_dates['Date'].max()}")
    print(f"Total amount: ${fuel_with_dates['Debit'].sum():,.2f}")
    print(f"\nRECOMMENDATION: REQUIRES vehicle identification in transactions")
    print(f"  - vehicle_fuel_log needs vehicle_id (text) NOT NULL")
    print(f"  - Most QB transactions don't specify which vehicle")
    print(f"  - ACTION: Export Journal report with Vehicle/Asset column")
    
    print("\n\n" + "=" * 100)
    print("3. MAINTENANCE/REPAIR DATA (1,951 transactions)")
    print("=" * 100)
    
    maint = journal[journal['Account'].isin(['6900 Vehicle R&M', '6350 Equipment Repairs'])].copy()
    maint_with_dates = maint[maint['Date'].notna()]
    
    print(f"Total maintenance transactions: {len(maint):,}")
    print(f"With valid dates: {len(maint_with_dates):,}")
    print(f"Date range: {maint_with_dates['Date'].min()} to {maint_with_dates['Date'].max()}")
    print(f"Total amount: ${maint_with_dates['Debit'].sum():,.2f}")
    print(f"\nRECOMMENDATION: REQUIRES vehicle identification AND activity_type_id")
    print(f"  - maintenance_records needs vehicle_id (integer) NOT NULL")
    print(f"  - maintenance_records needs activity_type_id (integer) NOT NULL")
    print(f"  - Need to map QB accounts to maintenance_activity_types")
    
    # Check maintenance activity types
    cur.execute("SELECT activity_type_id, activity_name FROM maintenance_activity_types LIMIT 10")
    activity_types = cur.fetchall()
    print(f"\n  Available activity types in almsdata:")
    for at in activity_types[:5]:
        print(f"    - {at[1]} (ID: {at[0]})")
    
    print("\n\n" + "=" * 100)
    print("4. LOAN PAYMENT DATA (727 transactions)")
    print("=" * 100)
    
    loans = journal[journal['Account'].str.contains('loan|lease', case=False, na=False)].copy()
    loans_with_dates = loans[loans['Date'].notna()]
    
    print(f"Total loan transactions: {len(loans):,}")
    print(f"With valid dates: {len(loans_with_dates):,}")
    print(f"Date range: {loans_with_dates['Date'].min()} to {loans_with_dates['Date'].max()}")
    print(f"Total credits (payments): ${loans_with_dates['Credit'].sum():,.2f}")
    print(f"\nRECOMMENDATION: Can import loan payments")
    print(f"  - financing_payments table ready")
    print(f"  - Need to match QB loan accounts to financing_sources")
    
    # Check financing sources
    cur.execute("SELECT source_id, source_name FROM financing_sources")
    sources = cur.fetchall()
    print(f"\n  Existing financing sources in almsdata:")
    for src in sources:
        print(f"    - {src[1]} (ID: {src[0]})")
    
    print("\n\n" + "=" * 100)
    print("SUMMARY & NEXT STEPS")
    print("=" * 100)
    
    print("""
READY TO IMPORT (with current data):
✓ Insurance transactions (190) - just need to handle NULL vehicle_id
✓ Loan payments (727) - need QB account to financing_source mapping

REQUIRES ADDITIONAL QB DATA:
✗ Fuel (4,418) - need Vehicle/Asset column in QB export
✗ Maintenance (1,951) - need Vehicle/Asset column + activity type mapping

RECOMMENDED ACTION:
1. Create simple insurance import (ignore vehicle linkage for now)
2. Create loan payment import with manual account mapping
3. Request new QB Journal export with Vehicle/Asset column for fuel/maintenance
4. Build vehicle identification lookup from QB account names

Would you like me to proceed with importing insurance and loan data that's ready now?
    """)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
