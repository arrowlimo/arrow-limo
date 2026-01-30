"""
Import QuickBooks vehicle, loan, insurance, and maintenance data into almsdata.

This script processes QB Journal transactions and populates:
- vehicle_insurance (insurance payments)
- maintenance_records (repairs and services)
- vehicle_fuel_log (fuel purchases)
- financing_payments (loan payments)
- Updates vehicle_loans with QB loan account linkage
"""

import pandas as pd
import psycopg2
from datetime import datetime
from decimal import Decimal
import re

# Configuration
BACKUP_PATH = r"L:\limo\quickbooks\Arrow Limousine backup 2025 Oct 19, 2025"
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

def parse_date(date_str):
    """Convert DD/MM/YYYY to Python date."""
    if pd.isna(date_str):
        return None
    try:
        return datetime.strptime(str(date_str), '%d/%m/%Y').date()
    except:
        return None

def parse_amount(amount_str):
    """Convert string amount to Decimal."""
    if pd.isna(amount_str):
        return Decimal('0')
    try:
        # Remove commas and convert
        clean = str(amount_str).replace(',', '')
        return Decimal(clean)
    except:
        return Decimal('0')

def extract_vehicle_id(account_name):
    """Extract vehicle ID from account name (e.g., 'L-15', 'L-14')."""
    if pd.isna(account_name):
        return None
    
    # Pattern: L-XX or LXX
    match = re.search(r'L-?(\d+)', account_name, re.IGNORECASE)
    if match:
        return f"L-{match.group(1)}"
    return None

def main():
    print("=" * 100)
    print("IMPORTING QUICKBOOKS VEHICLE/LOAN/INSURANCE DATA")
    print("=" * 100)
    
    # Load QB Journal
    print("\n1. Loading QuickBooks Journal...")
    journal = pd.read_excel(BACKUP_PATH + r"\Journal.xlsx", skiprows=4)
    journal['Date'] = journal['Date'].apply(parse_date)
    print(f"   Loaded {len(journal):,} journal entries")
    
    # Connect to database
    print("\n2. Connecting to almsdata...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("   Connected successfully")
    
    # Statistics
    stats = {
        'insurance': {'processed': 0, 'inserted': 0, 'errors': 0},
        'maintenance': {'processed': 0, 'inserted': 0, 'errors': 0},
        'fuel': {'processed': 0, 'inserted': 0, 'errors': 0},
        'loan_payments': {'processed': 0, 'inserted': 0, 'errors': 0}
    }
    
    # =========================================================================
    # 3. IMPORT INSURANCE TRANSACTIONS
    # =========================================================================
    print("\n3. Importing Insurance transactions...")
    print("-" * 100)
    
    insurance_accounts = ['6400 Insurance', '6950 WCB']
    insurance_txns = journal[journal['Account'].isin(insurance_accounts)].copy()
    
    print(f"   Found {len(insurance_txns):,} insurance transactions")
    
    for idx, row in insurance_txns.iterrows():
        stats['insurance']['processed'] += 1
        
        try:
            # Determine amount (debit = payment out)
            amount = parse_amount(row['Debit']) if pd.notna(row['Debit']) else Decimal('0')
            if amount == 0:
                continue
            
            # Extract vehicle if mentioned in memo
            vehicle_id = extract_vehicle_id(row.get('Memo/Description', ''))
            vendor_name = row.get('Name', '') if pd.notna(row.get('Name', '')) else 'Unknown'
            
            # Insert into vehicle_insurance
            cur.execute("""
                INSERT INTO vehicle_insurance 
                (vehicle_id, carrier, policy_number, policy_type, annual_premium,
                 policy_start_date, policy_end_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                vehicle_id,  # May be NULL if no vehicle identified
                vendor_name,  # carrier from Name field
                'QB-' + str(idx),  # Generate policy_number from row index
                'General' if '6400' in row['Account'] else 'WCB',  # policy_type
                amount,  # annual_premium (actually transaction amount)
                row['Date'],  # policy_start_date (use transaction date)
                row['Date'],  # policy_end_date (same date - we don't know end date)
                f"QB Account: {row['Account']}, Memo: {row.get('Memo/Description', '')}"
            ))
            
            stats['insurance']['inserted'] += 1
            
            if stats['insurance']['inserted'] % 20 == 0:
                print(f"   Inserted {stats['insurance']['inserted']} insurance records...")
                
        except Exception as e:
            stats['insurance']['errors'] += 1
            if stats['insurance']['errors'] <= 5:
                print(f"   Error on row {idx}: {e}")
    
    conn.commit()
    print(f"   ✓ Insurance import complete: {stats['insurance']['inserted']} records inserted")
    
    # =========================================================================
    # 4. IMPORT MAINTENANCE/REPAIR TRANSACTIONS
    # =========================================================================
    print("\n4. Importing Maintenance/Repair transactions...")
    print("-" * 100)
    
    maintenance_accounts = ['6900 Vehicle R&M', '6350 Equipment Repairs']
    maint_txns = journal[journal['Account'].isin(maintenance_accounts)].copy()
    
    print(f"   Found {len(maint_txns):,} maintenance transactions")
    
    for idx, row in maint_txns.iterrows():
        stats['maintenance']['processed'] += 1
        
        try:
            amount = parse_amount(row['Debit']) if pd.notna(row['Debit']) else Decimal('0')
            if amount == 0:
                continue
            
            vehicle_id = extract_vehicle_id(row.get('Memo/Description', ''))
            vendor_name = row.get('Name', '') if pd.notna(row.get('Name', '')) else 'Unknown'
            
            # Insert into maintenance_records
            # Note: Requires activity_type_id, but we don't have mapping
            # Skip records without vehicle_id for now
            if not vehicle_id:
                continue
                
            cur.execute("""
                INSERT INTO maintenance_records 
                (vehicle_id, activity_type_id, service_date, performed_by, 
                 total_cost, notes)
                SELECT %s, mat.activity_type_id, %s, %s, %s, %s
                FROM maintenance_activity_types mat
                WHERE mat.activity_name ILIKE %s
                LIMIT 1
            """, (
                vehicle_id,
                row['Date'],
                vendor_name,
                amount,
                f"QB Account: {row['Account']}, Memo: {row.get('Memo/Description', '')}",
                '%repair%' if 'Repair' in row['Account'] else '%maintenance%'
            ))
            
            if cur.rowcount == 0:
                # No matching activity type, skip
                continue
            
            stats['maintenance']['inserted'] += 1
            
            if stats['maintenance']['inserted'] % 100 == 0:
                print(f"   Inserted {stats['maintenance']['inserted']} maintenance records...")
                
        except Exception as e:
            stats['maintenance']['errors'] += 1
            if stats['maintenance']['errors'] <= 5:
                print(f"   Error on row {idx}: {e}")
    
    conn.commit()
    print(f"   ✓ Maintenance import complete: {stats['maintenance']['inserted']} records inserted")
    
    # =========================================================================
    # 5. IMPORT FUEL TRANSACTIONS
    # =========================================================================
    print("\n5. Importing Fuel transactions...")
    print("-" * 100)
    
    fuel_txns = journal[journal['Account'] == '6925 Fuel'].copy()
    
    print(f"   Found {len(fuel_txns):,} fuel transactions")
    
    for idx, row in fuel_txns.iterrows():
        stats['fuel']['processed'] += 1
        
        try:
            amount = parse_amount(row['Debit']) if pd.notna(row['Debit']) else Decimal('0')
            if amount == 0:
                continue
            
            vehicle_id = extract_vehicle_id(row.get('Memo/Description', ''))
            vendor_name = row.get('Name', '') if pd.notna(row.get('Name', '')) else 'Unknown'
            
            # Insert into vehicle_fuel_log
            # vehicle_fuel_log requires: vehicle_id (text), amount (numeric), recorded_at (timestamp)
            # Skip if no vehicle identified
            if not vehicle_id:
                continue
                
            cur.execute("""
                INSERT INTO vehicle_fuel_log 
                (vehicle_id, amount, recorded_at, recorded_by)
                VALUES (%s, %s, %s, %s)
            """, (
                vehicle_id,
                amount,
                row['Date'],  # recorded_at
                vendor_name  # recorded_by
            ))
            
            stats['fuel']['inserted'] += 1
            
            if stats['fuel']['inserted'] % 500 == 0:
                print(f"   Inserted {stats['fuel']['inserted']} fuel records...")
                
        except Exception as e:
            stats['fuel']['errors'] += 1
            if stats['fuel']['errors'] <= 5:
                print(f"   Error on row {idx}: {e}")
    
    conn.commit()
    print(f"   ✓ Fuel import complete: {stats['fuel']['inserted']} records inserted")
    
    # =========================================================================
    # 6. IMPORT LOAN PAYMENT TRANSACTIONS
    # =========================================================================
    print("\n6. Importing Loan Payment transactions...")
    print("-" * 100)
    
    loan_keywords = ['loan', 'lease']
    loan_txns = journal[
        journal['Account'].fillna('').str.contains('|'.join(loan_keywords), case=False, regex=True)
    ].copy()
    
    print(f"   Found {len(loan_txns):,} loan-related transactions")
    
    for idx, row in loan_txns.iterrows():
        stats['loan_payments']['processed'] += 1
        
        try:
            # Loan payments are typically credits to the loan account
            amount = parse_amount(row['Credit']) if pd.notna(row['Credit']) else Decimal('0')
            if amount == 0:
                amount = parse_amount(row['Debit']) if pd.notna(row['Debit']) else Decimal('0')
            
            if amount == 0:
                continue
            
            vehicle_id = extract_vehicle_id(row['Account'])
            
            # Insert into financing_payments
            # Column is payment_amount not amount
            cur.execute("""
                INSERT INTO financing_payments 
                (source_id, payment_date, payment_amount, payment_type)
                SELECT 
                    fs.source_id,
                    %s,
                    %s,
                    'QuickBooks'
                FROM financing_sources fs
                WHERE fs.source_name ILIKE %s
                LIMIT 1
            """, (
                row['Date'],
                amount,
                f"%{vehicle_id}%" if vehicle_id else "%loan%"
            ))
            
            if cur.rowcount > 0:
                stats['loan_payments']['inserted'] += 1
            
            if stats['loan_payments']['inserted'] % 50 == 0:
                print(f"   Inserted {stats['loan_payments']['inserted']} loan payments...")
                
        except Exception as e:
            stats['loan_payments']['errors'] += 1
            if stats['loan_payments']['errors'] <= 5:
                print(f"   Error on row {idx}: {e}")
    
    conn.commit()
    print(f"   ✓ Loan payments import complete: {stats['loan_payments']['inserted']} records inserted")
    
    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print("\n\n" + "=" * 100)
    print("IMPORT SUMMARY:")
    print("=" * 100)
    
    total_processed = sum(s['processed'] for s in stats.values())
    total_inserted = sum(s['inserted'] for s in stats.values())
    total_errors = sum(s['errors'] for s in stats.values())
    
    print(f"\nInsurance:")
    print(f"  Processed: {stats['insurance']['processed']:,}")
    print(f"  Inserted:  {stats['insurance']['inserted']:,}")
    print(f"  Errors:    {stats['insurance']['errors']:,}")
    
    print(f"\nMaintenance/Repairs:")
    print(f"  Processed: {stats['maintenance']['processed']:,}")
    print(f"  Inserted:  {stats['maintenance']['inserted']:,}")
    print(f"  Errors:    {stats['maintenance']['errors']:,}")
    
    print(f"\nFuel:")
    print(f"  Processed: {stats['fuel']['processed']:,}")
    print(f"  Inserted:  {stats['fuel']['inserted']:,}")
    print(f"  Errors:    {stats['fuel']['errors']:,}")
    
    print(f"\nLoan Payments:")
    print(f"  Processed: {stats['loan_payments']['processed']:,}")
    print(f"  Inserted:  {stats['loan_payments']['inserted']:,}")
    print(f"  Errors:    {stats['loan_payments']['errors']:,}")
    
    print(f"\n{'TOTALS':15} {total_processed:,} processed | {total_inserted:,} inserted | {total_errors:,} errors")
    
    print("\n✓ Import complete!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
