#!/usr/bin/env python3
"""
CRA Asset Compliance Report
Generates comprehensive asset inventory for CRA audits.
"""
import os
import csv
import psycopg2
from datetime import datetime, date
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

REPORT_DIR = os.path.join("l:\\limo", "reports", "assets")
CSV_PATH = os.path.join(REPORT_DIR, "CRA_ASSET_INVENTORY.csv")
OWNED_CSV = os.path.join(REPORT_DIR, "CRA_OWNED_ASSETS.csv")
LEASED_CSV = os.path.join(REPORT_DIR, "CRA_LEASED_ASSETS.csv")
LOANED_CSV = os.path.join(REPORT_DIR, "CRA_LOANED_IN_ASSETS.csv")
TXT_PATH = os.path.join(REPORT_DIR, "CRA_ASSET_SUMMARY.txt")


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Get all active assets with depreciation info
    cur.execute("""
        SELECT 
            a.asset_id,
            a.asset_name,
            a.asset_category,
            a.ownership_status,
            a.make,
            a.model,
            a.year,
            a.vin,
            a.serial_number,
            a.acquisition_date,
            a.acquisition_cost,
            a.current_book_value,
            a.salvage_value,
            a.depreciation_method,
            a.useful_life_years,
            a.cca_class,
            a.cca_rate,
            a.legal_owner,
            a.lender_contact,
            a.lease_start_date,
            a.lease_end_date,
            a.lease_monthly_payment,
            a.location,
            a.status,
            a.notes,
            a.created_at
        FROM assets a
        WHERE a.status IN ('active', 'stolen')
        ORDER BY a.ownership_status, a.asset_category, a.asset_name
    """)
    
    assets = cur.fetchall()
    
    # Group by ownership status
    owned = [a for a in assets if a[3] == 'owned']
    leased = [a for a in assets if a[3] == 'leased']
    loaned = [a for a in assets if a[3] == 'loaned_in']
    rental = [a for a in assets if a[3] == 'rental']
    
    # CSV headers
    headers = [
        'asset_id', 'asset_name', 'category', 'ownership_status', 'make', 'model', 'year',
        'vin', 'serial_number', 'acquisition_date', 'acquisition_cost', 'current_book_value',
        'salvage_value', 'depreciation_method', 'useful_life_years', 'cca_class', 'cca_rate',
        'legal_owner', 'lender_contact', 'lease_start', 'lease_end', 'monthly_payment',
        'location', 'status', 'notes'
    ]
    
    # Write full inventory
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in assets:
            writer.writerow([str(v) if v is not None else '' for v in row[:-1]])  # Exclude created_at
    
    # Write owned assets (CRA depreciation schedule)
    with open(OWNED_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in owned:
            writer.writerow([str(v) if v is not None else '' for v in row[:-1]])
    
    # Write leased assets
    with open(LEASED_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in leased:
            writer.writerow([str(v) if v is not None else '' for v in row[:-1]])
    
    # Write loaned-in assets
    with open(LOANED_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in loaned:
            writer.writerow([str(v) if v is not None else '' for v in row[:-1]])
    
    # Write summary TXT
    with open(TXT_PATH, 'w', encoding='utf-8') as f:
        f.write("CRA ASSET COMPLIANCE REPORT\n")
        f.write("=" * 100 + "\n")
        f.write(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("ASSET SUMMARY BY OWNERSHIP STATUS\n")
        f.write("-" * 100 + "\n\n")
        
        # Owned assets
        f.write(f"OWNED ASSETS (Depreciable for Tax Purposes): {len(owned)}\n")
        if owned:
            total_cost = sum(Decimal(str(a[10])) for a in owned if a[10])
            total_book = sum(Decimal(str(a[11])) for a in owned if a[11])
            f.write(f"  Total Acquisition Cost: ${total_cost:,.2f}\n")
            f.write(f"  Current Book Value: ${total_book:,.2f}\n")
            f.write(f"  Accumulated Depreciation: ${total_cost - total_book:,.2f}\n\n")
            
            # Group by CCA class
            cca_groups = {}
            for asset in owned:
                cca_class = asset[15] or 'Unclassified'
                if cca_class not in cca_groups:
                    cca_groups[cca_class] = []
                cca_groups[cca_class].append(asset)
            
            f.write("  By CCA Class:\n")
            for cca_class in sorted(cca_groups.keys()):
                assets_in_class = cca_groups[cca_class]
                class_cost = sum(Decimal(str(a[10])) for a in assets_in_class if a[10])
                f.write(f"    {cca_class}: {len(assets_in_class)} assets, ${class_cost:,.2f}\n")
        f.write("\n")
        
        # Leased assets
        f.write(f"LEASED ASSETS (Monthly Expenses, Not Owned): {len(leased)}\n")
        if leased:
            total_monthly = sum(Decimal(str(a[21])) for a in leased if a[21])
            f.write(f"  Total Monthly Lease Payments: ${total_monthly:,.2f}\n")
            f.write(f"  Annual Lease Expense: ${total_monthly * 12:,.2f}\n\n")
            
            f.write("  Leased Asset Details:\n")
            for asset in leased[:20]:  # Top 20
                name = asset[1]
                owner = asset[17] or 'Unknown'
                monthly = Decimal(str(asset[21])) if asset[21] else Decimal('0.00')
                f.write(f"    {name:<50} {owner:<30} ${monthly:>10,.2f}/month\n")
        f.write("\n")
        
        # Loaned-in assets
        f.write(f"LOANED-IN ASSETS (Borrowed from Others, Not Owned): {len(loaned)}\n")
        if loaned:
            f.write("  IMPORTANT: These are NOT business assets. Document ownership clearly.\n\n")
            f.write("  Loaned Asset Details:\n")
            for asset in loaned:
                name = asset[1]
                owner = asset[17] or 'Unknown Owner'
                status = asset[23] or 'loaned'
                f.write(f"    {name:<50} Owned by: {owner} (Status: {status})\n")
        f.write("\n")
        
        # Stolen/repossessed assets
        stolen = [a for a in assets if a[23] == 'stolen']
        if stolen:
            f.write(f"STOLEN/REPOSSESSED ASSETS (Not in Inventory): {len(stolen)}\n")
            f.write("  IMPORTANT: These are documented losses for CRA audit trail.\n\n")
            f.write("  Loss Documentation:\n")
            for asset in stolen:
                name = asset[1]
                year = asset[6]
                acquisition_date = asset[9]
                notes = asset[24]
                f.write(f"    {year} {name}:\n")
                f.write(f"      Acquisition Date: {acquisition_date}\n")
                f.write(f"      Documentation: {notes}\n\n")
        f.write("\n")
        
        # Rental assets
        if rental:
            f.write(f"RENTAL ASSETS (Short-term Rentals): {len(rental)}\n\n")
        
        f.write("\n" + "=" * 100 + "\n")
        f.write("CRA COMPLIANCE NOTES:\n")
        f.write("-" * 100 + "\n")
        f.write("1. OWNED ASSETS: Depreciate using CCA (Capital Cost Allowance) classes\n")
        f.write("2. LEASED ASSETS: Deduct monthly payments as operating expenses\n")
        f.write("3. LOANED-IN ASSETS: NOT depreciable, NOT deductible, document to prove non-ownership\n")
        f.write("4. Keep receipts, loan agreements, and lease contracts for all assets\n")
        f.write("5. Update asset register annually for CRA audit readiness\n\n")
        
        f.write("COMMON CCA CLASSES (Vehicles):\n")
        f.write("  Class 10: Passenger vehicles ($30,000+ cost) - 30% declining balance\n")
        f.write("  Class 10.1: Luxury vehicles ($30,000+ cost) - 30% declining balance, no terminal loss\n")
        f.write("  Class 16: Taxis, buses - 40% declining balance\n")
    
    cur.close()
    conn.close()
    
    print(f"✅ CRA Asset Compliance Report Generated:")
    print(f"   Full Inventory: {CSV_PATH}")
    print(f"   Owned Assets: {OWNED_CSV}")
    print(f"   Leased Assets: {LEASED_CSV}")
    print(f"   Loaned-In Assets: {LOANED_CSV}")
    print(f"   Summary: {TXT_PATH}")
    print(f"\n   Total Active Assets: {len(assets)}")
    print(f"   - Owned (Depreciable): {len(owned)}")
    print(f"   - Leased (Expense): {len(leased)}")
    print(f"   - Loaned-In (Not Owned): {len(loaned)}")


if __name__ == "__main__":
    main()
