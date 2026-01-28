#!/usr/bin/env python3
"""
Import compliance data from CSV into employees table
Usage: python import_compliance_data.py --file compliance_data.csv [--dry-run] [--write]
"""
import csv
import sys
import psycopg2
from datetime import datetime
from pathlib import Path

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def import_compliance_csv(csv_file, dry_run=True):
    """Import compliance data from CSV"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            
            updated = 0
            errors = 0
            
            for row in reader:
                try:
                    employee_number = row.get('employee_number', '').strip()
                    proserve_number = row.get('proserve_number', '').strip() or None
                    proserve_expiry = row.get('proserve_expiry', '').strip() or None
                    vsc_date = row.get('vulnerable_sector_check_date', '').strip() or None
                    abstract_date = row.get('drivers_abstract_date', '').strip() or None
                    license_class = row.get('driver_license_class', '').strip() or None
                    permit_number = row.get('chauffeur_permit_number', '').strip() or None
                    permit_expiry = row.get('chauffeur_permit_expiry', '').strip() or None
                    medical_fitness = row.get('medical_fitness_expiry', '').strip() or None
                    
                    if not employee_number:
                        print(f"⚠️  Skipping row: missing employee_number")
                        errors += 1
                        continue
                    
                    # Find employee by employee_number
                    cur.execute("SELECT employee_id FROM employees WHERE employee_number = %s", (employee_number,))
                    result = cur.fetchone()
                    
                    if not result:
                        print(f"❌ Employee not found: {employee_number}")
                        errors += 1
                        continue
                    
                    employee_id = result[0]
                    
                    if dry_run:
                        print(f"DRY RUN: {employee_number} -> ProServe: {proserve_expiry}, VSC: {vsc_date}")
                    else:
                        # Update employee record
                        cur.execute("""
                            UPDATE employees SET
                                proserve_number = COALESCE(%s, proserve_number),
                                proserve_expiry = COALESCE(%s::date, proserve_expiry),
                                vulnerable_sector_check_date = COALESCE(%s::date, vulnerable_sector_check_date),
                                drivers_abstract_date = COALESCE(%s::date, drivers_abstract_date),
                                driver_license_class = COALESCE(%s, driver_license_class),
                                chauffeur_permit_number = COALESCE(%s, chauffeur_permit_number),
                                chauffeur_permit_expiry = COALESCE(%s::date, chauffeur_permit_expiry),
                                medical_fitness_expiry = COALESCE(%s::date, medical_fitness_expiry),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE employee_id = %s
                        """, (proserve_number, proserve_expiry, vsc_date, abstract_date, 
                              license_class, permit_number, permit_expiry, medical_fitness, employee_id))
                        
                        print(f"✅ {employee_number}: Updated")
                        updated += 1
                except Exception as e:
                    print(f"❌ Error processing {employee_number}: {e}")
                    errors += 1
            
            if not dry_run:
                conn.commit()
            
            print(f"\nSummary: {updated} updated, {errors} errors")
            cur.close()
            conn.close()
            return updated > 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="CSV file with compliance data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--write", action="store_true", help="Save changes to database")
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.write:
        print("Usage: python import_compliance_data.py --file <csv> [--dry-run|--write]")
        sys.exit(1)
    
    csv_path = Path(args.file)
    if not csv_path.exists():
        print(f"❌ File not found: {args.file}")
        sys.exit(1)
    
    dry_run = args.dry_run
    if dry_run:
        print("🔍 DRY RUN MODE: Preview only, no changes saved\n")
    elif args.write:
        print("⚠️  WRITE MODE: Changes will be saved\n")
    
    success = import_compliance_csv(csv_path, dry_run=dry_run)
    sys.exit(0 if success else 1)
