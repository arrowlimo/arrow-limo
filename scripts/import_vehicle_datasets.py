"""
Import Vehicle Operational Datasets

Imports verified CSV exports for:
- vehicle_fuel_log (fuel_expenses.csv)
- maintenance_records (maintenance_records.csv)
- vehicle_documents (vehicle_documents.csv)
- vehicle_insurance (vehicle_insurance.csv)

Author: AI Agent
Date: November 13, 2025
"""

import psycopg2
import csv
import os
import sys
from datetime import datetime

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def import_fuel_expenses(conn, csv_path, dry_run=True):
    """Import fuel expenses into vehicle_fuel_log table"""
    cur = conn.cursor()
    
    print(f"\n{'='*60}")
    print("IMPORTING FUEL EXPENSES")
    print(f"{'='*60}")
    
    # Check existing data
    cur.execute("SELECT COUNT(*) FROM vehicle_fuel_log")
    existing_count = cur.fetchone()[0]
    print(f"Existing fuel log entries: {existing_count}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    print(f"Found {len(rows)} rows in {csv_path}")
    
    inserted = 0
    skipped = 0
    
    for row in rows:
        # Check for duplicate
        cur.execute("""
            SELECT COUNT(*) FROM vehicle_fuel_log
            WHERE vehicle_id = %s
            AND recorded_at::date = %s::date
            AND amount = %s
        """, (row['vehicle_code'], row['expense_date'], float(row['total_amount'])))
        
        if cur.fetchone()[0] > 0:
            skipped += 1
            continue
        
        if not dry_run:
            cur.execute("""
                INSERT INTO vehicle_fuel_log (
                    vehicle_id, recorded_at, amount, liters, 
                    odometer_reading
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                row['vehicle_code'],
                row['expense_date'],
                float(row['total_amount']),
                float(row['liters']) if row['liters'] else None,
                None,  # odometer not in source
            ))
        
        inserted += 1
    
    print(f"✓ Would insert: {inserted} fuel entries")
    print(f"⊘ Skipped (duplicates): {skipped}")
    
    if not dry_run:
        conn.commit()
        print("✓ Fuel expenses imported")
    else:
        conn.rollback()
        print("⚠ DRY RUN - no changes made")
    
    cur.close()

def import_maintenance_records(conn, csv_path, dry_run=True):
    """Import maintenance records"""
    cur = conn.cursor()
    
    print(f"\n{'='*60}")
    print("IMPORTING MAINTENANCE RECORDS")
    print(f"{'='*60}")
    
    # Get valid vehicle IDs
    cur.execute("SELECT vehicle_id FROM vehicles")
    valid_vehicle_ids = {row[0] for row in cur.fetchall()}
    print(f"Valid vehicle IDs: {sorted(valid_vehicle_ids)}")
    
    # Check existing data
    cur.execute("SELECT COUNT(*) FROM maintenance_records")
    existing_count = cur.fetchone()[0]
    print(f"Existing maintenance records: {existing_count}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Found {len(rows)} rows in {csv_path}")
    
    inserted = 0
    skipped = 0
    
    for row in rows:
        vehicle_id = int(row['vehicle_id']) if row.get('vehicle_id') else None
        
        # Skip if vehicle doesn't exist
        if vehicle_id not in valid_vehicle_ids:
            print(f"  ⊘ Skipping record for non-existent vehicle_id={vehicle_id}")
            skipped += 1
            continue
        
        # Check for duplicate by record_id (if unique in CSV)
        if row.get('record_id'):
            cur.execute("""
                SELECT COUNT(*) FROM maintenance_records
                WHERE vehicle_id = %s
                AND service_date = %s
                AND total_cost = %s
            """, (
                vehicle_id,
                row['service_date'],
                float(row['total_cost']) if row['total_cost'] else 0
            ))
            
            if cur.fetchone()[0] > 0:
                skipped += 1
                continue
        
        if not dry_run:
            cur.execute("""
                INSERT INTO maintenance_records (
                    vehicle_id, activity_type_id, service_date,
                    odometer_reading, performed_by, total_cost,
                    next_service_km, next_service_date, notes,
                    status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                vehicle_id,
                int(row['activity_type_id']) if row.get('activity_type_id') else None,
                row['service_date'],
                int(row['odometer_reading']) if row.get('odometer_reading') else None,
                row.get('performed_by'),
                float(row['total_cost']) if row.get('total_cost') else 0,
                int(row['next_service_km']) if row.get('next_service_km') else None,
                row.get('next_service_date') if row.get('next_service_date') else None,
                row.get('notes'),
                row.get('status', 'completed')
            ))
        
        inserted += 1
    
    print(f"✓ Would insert: {inserted} maintenance records")
    print(f"⊘ Skipped (duplicates): {skipped}")
    
    if not dry_run:
        conn.commit()
        print("✓ Maintenance records imported")
    else:
        conn.rollback()
        print("⚠ DRY RUN - no changes made")
    
    cur.close()

def import_vehicle_documents(conn, csv_path, dry_run=True):
    """Import vehicle documents"""
    cur = conn.cursor()
    
    print(f"\n{'='*60}")
    print("IMPORTING VEHICLE DOCUMENTS")
    print(f"{'='*60}")
    
    # Get valid vehicle IDs
    cur.execute("SELECT vehicle_id FROM vehicles")
    valid_vehicle_ids = {row[0] for row in cur.fetchall()}
    
    # Check existing data
    cur.execute("SELECT COUNT(*) FROM vehicle_documents")
    existing_count = cur.fetchone()[0]
    print(f"Existing vehicle documents: {existing_count}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Found {len(rows)} rows in {csv_path}")
    
    inserted = 0
    skipped = 0
    
    for row in rows:
        vehicle_id = int(row['vehicle_id']) if row.get('vehicle_id') else None
        
        # Skip if vehicle doesn't exist
        if vehicle_id not in valid_vehicle_ids:
            skipped += 1
            continue
        
        # Check for duplicate
        cur.execute("""
            SELECT COUNT(*) FROM vehicle_documents
            WHERE vehicle_id = %s
            AND doc_type_id = %s
            AND issue_date = %s
        """, (
            vehicle_id,
            int(row['doc_type_id']) if row.get('doc_type_id') else None,
            row.get('issue_date')
        ))
        
        if cur.fetchone()[0] > 0:
            skipped += 1
            continue
        
        if not dry_run:
            cur.execute("""
                INSERT INTO vehicle_documents (
                    vehicle_id, doc_type_id, document_number,
                    issue_date, expiry_date, issuing_authority,
                    file_path, notes, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                vehicle_id,
                int(row['doc_type_id']) if row.get('doc_type_id') else None,
                row.get('document_number') or None,
                row.get('issue_date') or None,
                row.get('expiry_date') or None,
                row.get('issuing_authority') or None,
                row.get('file_path') or None,
                row.get('notes') or None
            ))
        
        inserted += 1
    
    print(f"✓ Would insert: {inserted} vehicle documents")
    print(f"⊘ Skipped (duplicates): {skipped}")
    
    if not dry_run:
        conn.commit()
        print("✓ Vehicle documents imported")
    else:
        conn.rollback()
        print("⚠ DRY RUN - no changes made")
    
    cur.close()

def import_vehicle_insurance(conn, csv_path, dry_run=True):
    """Import vehicle insurance records"""
    cur = conn.cursor()
    
    print(f"\n{'='*60}")
    print("IMPORTING VEHICLE INSURANCE")
    print(f"{'='*60}")
    
    # Get valid vehicle IDs
    cur.execute("SELECT vehicle_id FROM vehicles")
    valid_vehicle_ids = {row[0] for row in cur.fetchall()}
    
    # Check existing data
    cur.execute("SELECT COUNT(*) FROM vehicle_insurance")
    existing_count = cur.fetchone()[0]
    print(f"Existing insurance records: {existing_count}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Found {len(rows)} rows in {csv_path}")
    
    inserted = 0
    skipped = 0
    
    for row in rows:
        vehicle_id = int(row['vehicle_id']) if row.get('vehicle_id') else None
        
        # Skip if vehicle doesn't exist
        if vehicle_id not in valid_vehicle_ids:
            skipped += 1
            continue
        
        # Check for duplicate
        cur.execute("""
            SELECT COUNT(*) FROM vehicle_insurance
            WHERE vehicle_id = %s
            AND policy_number = %s
            AND policy_start_date = %s
        """, (
            vehicle_id,
            row.get('policy_number'),
            row.get('policy_start_date')
        ))
        
        if cur.fetchone()[0] > 0:
            skipped += 1
            continue
        
        if not dry_run:
            cur.execute("""
                INSERT INTO vehicle_insurance (
                    vehicle_id, policy_number, carrier,
                    policy_start_date, policy_end_date, policy_type,
                    annual_premium, deductible_collision, notes,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                vehicle_id,
                row.get('policy_number') or None,
                row.get('carrier') or None,
                row.get('policy_start_date') or None,
                row.get('policy_end_date') or None,
                row.get('policy_type') or None,
                float(row['annual_premium']) if row.get('annual_premium') and row['annual_premium'].strip() else None,
                float(row['deductible_collision']) if row.get('deductible_collision') and row['deductible_collision'].strip() else None,
                row.get('notes') or None
            ))
        
        inserted += 1
    
    print(f"✓ Would insert: {inserted} insurance records")
    print(f"⊘ Skipped (duplicates): {skipped}")
    
    if not dry_run:
        conn.commit()
        print("✓ Vehicle insurance imported")
    else:
        conn.rollback()
        print("⚠ DRY RUN - no changes made")
    
    cur.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import vehicle operational datasets')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--fuel', action='store_true', help='Import fuel expenses')
    parser.add_argument('--maintenance', action='store_true', help='Import maintenance records')
    parser.add_argument('--documents', action='store_true', help='Import vehicle documents')
    parser.add_argument('--insurance', action='store_true', help='Import vehicle insurance')
    parser.add_argument('--all', action='store_true', help='Import all datasets')
    args = parser.parse_args()
    
    dry_run = not args.write
    base_path = r'l:\limo\qb_storage\exports_verified'
    
    if dry_run:
        print("\n⚠ DRY RUN MODE - No changes will be made")
        print("Use --write to apply changes\n")
    
    conn = get_db_connection()
    
    try:
        if args.fuel or args.all:
            fuel_path = os.path.join(base_path, 'fuel_expenses.csv')
            if os.path.exists(fuel_path):
                import_fuel_expenses(conn, fuel_path, dry_run)
            else:
                print(f"✗ Not found: {fuel_path}")
        
        if args.maintenance or args.all:
            maint_path = os.path.join(base_path, 'maintenance_records.csv')
            if os.path.exists(maint_path):
                import_maintenance_records(conn, maint_path, dry_run)
            else:
                print(f"✗ Not found: {maint_path}")
        
        if args.documents or args.all:
            docs_path = os.path.join(base_path, 'vehicle_documents.csv')
            if os.path.exists(docs_path):
                import_vehicle_documents(conn, docs_path, dry_run)
            else:
                print(f"✗ Not found: {docs_path}")
        
        if args.insurance or args.all:
            ins_path = os.path.join(base_path, 'vehicle_insurance.csv')
            if os.path.exists(ins_path):
                import_vehicle_insurance(conn, ins_path, dry_run)
            else:
                print(f"✗ Not found: {ins_path}")
        
        if not any([args.fuel, args.maintenance, args.documents, args.insurance, args.all]):
            print("No datasets selected. Use --all or specify individual datasets.")
            print("Available options: --fuel, --maintenance, --documents, --insurance")
    
    finally:
        conn.close()
    
    print(f"\n{'='*60}")
    print("IMPORT COMPLETE" if not dry_run else "DRY RUN COMPLETE")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
