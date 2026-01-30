#!/usr/bin/env python3
"""
Driver ID Relationship Repair Implementation
Fixes the broken driver-employee-charter relationships
"""

import psycopg2
import sys

def main():
    # Check for dry-run vs apply mode
    dry_run = '--apply' not in sys.argv
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("Use --apply to execute repairs")
    else:
        print("⚡ APPLY MODE - Making actual database changes")
    
    print("=" * 50)

    conn = psycopg2.connect(
        host='localhost',
        database='almsdata', 
        user='postgres',
        password='***REDACTED***'
    )
    
    try:
        # Phase 1: Create driver-employee mapping
        print("🎯 PHASE 1: CREATING DRIVER-EMPLOYEE MAPPING")
        print("=" * 45)
        
        cur = conn.cursor()
        
        # Check if mapping table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'driver_employee_mapping'
            )
        """)
        
        table_exists = cur.fetchone()[0]
        
        if not table_exists and not dry_run:
            print("Creating driver_employee_mapping table...")
            cur.execute("""
                CREATE TABLE driver_employee_mapping (
                    driver_id VARCHAR(50) PRIMARY KEY,
                    employee_id INTEGER REFERENCES employees(employee_id),
                    employee_number VARCHAR(50),
                    full_name VARCHAR(200),
                    confidence_score INTEGER DEFAULT 100,
                    mapping_source VARCHAR(100) DEFAULT 'employee_number_match',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("[OK] Created driver_employee_mapping table")
        elif table_exists:
            print("ℹ️  driver_employee_mapping table already exists")
        else:
            print("📝 Would create driver_employee_mapping table")
        
        # Find employee_number matches
        cur.execute("""
            SELECT dp.driver_id, e.employee_id, e.employee_number, e.full_name,
                   COUNT(dp.id) as payroll_records
            FROM driver_payroll dp
            JOIN employees e ON CAST(dp.driver_id AS TEXT) = CAST(e.employee_number AS TEXT)
            WHERE dp.driver_id IS NOT NULL 
              AND e.employee_number IS NOT NULL
            GROUP BY dp.driver_id, e.employee_id, e.employee_number, e.full_name
            ORDER BY COUNT(dp.id) DESC
        """)
        
        matches = cur.fetchall()
        print(f"Found {len(matches)} driver_id → employee matches:")
        
        for driver_id, emp_id, emp_num, name, records in matches:
            print(f"  {driver_id} → {name} ({records} payroll records)")
            
            if not dry_run:
                # Insert mapping (or update if exists)
                cur.execute("""
                    INSERT INTO driver_employee_mapping 
                    (driver_id, employee_id, employee_number, full_name, confidence_score)
                    VALUES (%s, %s, %s, %s, 100)
                    ON CONFLICT (driver_id) DO UPDATE SET
                        employee_id = EXCLUDED.employee_id,
                        employee_number = EXCLUDED.employee_number,
                        full_name = EXCLUDED.full_name,
                        confidence_score = EXCLUDED.confidence_score
                """, (driver_id, emp_id, emp_num, name))
        
        if not dry_run:
            conn.commit()
            print(f"[OK] Inserted {len(matches)} driver mappings")
        
        # Phase 2: Update driver_payroll.employee_id
        print(f"\n🔄 PHASE 2: UPDATING PAYROLL EMPLOYEE_ID")
        print("=" * 40)
        
        if not dry_run:
            cur.execute("""
                UPDATE driver_payroll 
                SET employee_id = dem.employee_id
                FROM driver_employee_mapping dem
                WHERE driver_payroll.driver_id = dem.driver_id
                  AND driver_payroll.employee_id IS NULL
            """)
            updated_payroll = cur.rowcount
            conn.commit()
            print(f"[OK] Updated {updated_payroll:,} payroll records with employee_id")
        else:
            # In dry-run, calculate potential updates using the matches we found
            payroll_updates = sum(records for _, _, _, _, records in matches)
            print(f"📝 Would update approximately {payroll_updates:,} payroll records with employee_id")
        
        # Phase 3: Update charters.assigned_driver_id via reserve_number
        print(f"\n🎯 PHASE 3: UPDATING CHARTER DRIVER ASSIGNMENTS")
        print("=" * 45)
        
        if not dry_run:
            cur.execute("""
                UPDATE charters 
                SET assigned_driver_id = dem.employee_id
                FROM driver_payroll dp
                JOIN driver_employee_mapping dem ON dp.driver_id = dem.driver_id
                WHERE CAST(charters.reserve_number AS TEXT) = CAST(dp.reserve_number AS TEXT)
                  AND charters.assigned_driver_id IS NULL
                  AND dp.employee_id IS NOT NULL
            """)
            updated_charters = cur.rowcount
            conn.commit()
            print(f"[OK] Updated {updated_charters:,} charter driver assignments")
        else:
            # Estimate charter updates based on reserve_number linkage
            cur.execute("""
                SELECT COUNT(*) FROM charters c
                JOIN driver_payroll dp ON CAST(c.reserve_number AS TEXT) = CAST(dp.reserve_number AS TEXT)
                WHERE c.assigned_driver_id IS NULL
            """)
            charter_updates = cur.fetchone()[0]
            print(f"📝 Would update approximately {charter_updates:,} charter driver assignments")
        
        # Phase 4: Validation Report
        print(f"\n📊 VALIDATION REPORT:")
        print("=" * 25)
        
        # Check final linkage statistics
        cur.execute("""
            SELECT 
                COUNT(*) as total_payroll,
                COUNT(employee_id) as with_employee_id,
                ROUND(COUNT(employee_id) * 100.0 / COUNT(*), 1) as employee_id_pct
            FROM driver_payroll
        """)
        payroll_stats = cur.fetchone()
        total_pay, with_emp, emp_pct = payroll_stats
        print(f"Payroll employee_id coverage: {with_emp:,}/{total_pay:,} ({emp_pct}%)")
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                COUNT(assigned_driver_id) as with_driver_id,
                ROUND(COUNT(assigned_driver_id) * 100.0 / COUNT(*), 1) as driver_id_pct
            FROM charters
        """)
        charter_stats = cur.fetchone()
        total_ch, with_drv, drv_pct = charter_stats  
        print(f"Charter driver_id coverage: {with_drv:,}/{total_ch:,} ({drv_pct}%)")
        
        cur.close()
        
        print(f"\n[OK] REPAIR COMPLETE!")
        if dry_run:
            print("🔧 Run with --apply to execute these changes")
            
    except Exception as e:
        print(f"[FAIL] Error during repair: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()