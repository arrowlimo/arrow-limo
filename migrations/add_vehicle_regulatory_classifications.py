#!/usr/bin/env python3
"""
Add regulatory classification columns to vehicles table.

Separates the multi-dimensional "type" problem into distinct columns:
1. regulatory_class - Commercial vehicle regulation (bus vs non-bus)
2. license_class_required - Driver qualification requirement
3. capacity_group - Vehicle allocation/booking categories  
4. hos_category - Hours of service logging type

Keeps existing:
- vehicle_type (customer-facing description like "20 passenger party bus")
- passenger_capacity (actual number)
"""

import psycopg2
from datetime import datetime

def main():
    print(f"\n{'='*80}")
    print("ADD VEHICLE REGULATORY CLASSIFICATION COLUMNS")
    print(f"{'='*80}\n")
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    try:
        # Backup vehicles table
        backup_table = f"vehicles_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Creating backup: {backup_table}")
        cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM vehicles")
        conn.commit()
        print(f"✅ Backed up {cur.rowcount} vehicles\n")
        
        # Add new columns
        print("Adding new classification columns...")
        
        cur.execute("""
            ALTER TABLE vehicles
            ADD COLUMN IF NOT EXISTS regulatory_class VARCHAR(20),
            ADD COLUMN IF NOT EXISTS license_class_required VARCHAR(10),
            ADD COLUMN IF NOT EXISTS capacity_group VARCHAR(30),
            ADD COLUMN IF NOT EXISTS hos_category VARCHAR(40)
        """)
        conn.commit()
        print("✅ Columns added\n")
        
        # Populate regulatory_class (based on 11+ passenger threshold)
        print("Populating regulatory_class...")
        cur.execute("""
            UPDATE vehicles
            SET regulatory_class = CASE
                WHEN passenger_capacity >= 11 THEN 'commercial_bus'
                WHEN passenger_capacity < 11 THEN 'non_commercial'
                ELSE 'unknown'
            END
        """)
        conn.commit()
        print(f"✅ Updated {cur.rowcount} vehicles\n")
        
        # Populate license_class_required
        print("Populating license_class_required...")
        cur.execute("""
            UPDATE vehicles
            SET license_class_required = CASE
                WHEN passenger_capacity >= 24 THEN 'class_2'
                WHEN passenger_capacity BETWEEN 11 AND 23 THEN 'class_4'
                WHEN passenger_capacity <= 10 THEN 'class_5'
                ELSE 'unknown'
            END
        """)
        conn.commit()
        print(f"✅ Updated {cur.rowcount} vehicles\n")
        
        # Populate capacity_group (for allocation matching)
        print("Populating capacity_group...")
        cur.execute("""
            UPDATE vehicles
            SET capacity_group = CASE
                WHEN passenger_capacity <= 4 THEN 'sedan'
                WHEN passenger_capacity BETWEEN 5 AND 8 THEN 'small_suv'
                WHEN passenger_capacity BETWEEN 9 AND 13 THEN 'large_suv'
                WHEN passenger_capacity BETWEEN 14 AND 23 THEN 'small_bus'
                WHEN passenger_capacity >= 24 THEN 'large_bus'
                ELSE 'unknown'
            END
        """)
        conn.commit()
        print(f"✅ Updated {cur.rowcount} vehicles\n")
        
        # Populate hos_category (Hours of Service logging)
        print("Populating hos_category...")
        cur.execute("""
            UPDATE vehicles
            SET hos_category = CASE
                WHEN passenger_capacity >= 11 THEN 'commercial_bus_driving'
                WHEN passenger_capacity < 11 THEN 'on_duty_non_bus'
                ELSE 'unknown'
            END
        """)
        conn.commit()
        print(f"✅ Updated {cur.rowcount} vehicles\n")
        
        # Show results
        print(f"{'='*80}")
        print("VERIFICATION - Classification Distribution")
        print(f"{'='*80}\n")
        
        cur.execute("""
            SELECT 
                regulatory_class,
                license_class_required,
                capacity_group,
                hos_category,
                COUNT(*) as count,
                MIN(passenger_capacity) as min_pax,
                MAX(passenger_capacity) as max_pax
            FROM vehicles
            GROUP BY regulatory_class, license_class_required, capacity_group, hos_category
            ORDER BY min_pax NULLS FIRST
        """)
        
        print(f"{'Reg Class':<20} {'License':<15} {'Cap Group':<15} {'HOS Category':<25} {'Count':<8} {'Pax Range'}")
        print("-" * 110)
        for row in cur.fetchall():
            reg, lic, cap, hos, count, min_pax, max_pax = row
            pax_range = f"{min_pax or '?'}-{max_pax or '?'}" if min_pax or max_pax else "NULL"
            print(f"{reg:<20} {lic:<15} {cap:<15} {hos:<25} {count:<8} {pax_range}")
        
        # Show sample vehicles with all classifications
        print(f"\n{'='*80}")
        print("SAMPLE VEHICLES WITH NEW CLASSIFICATIONS")
        print(f"{'='*80}\n")
        
        cur.execute("""
            SELECT vehicle_number, passenger_capacity, 
                   regulatory_class, license_class_required,
                   capacity_group, hos_category
            FROM vehicles
            WHERE passenger_capacity IS NOT NULL
            ORDER BY passenger_capacity, vehicle_number
            LIMIT 15
        """)
        
        print(f"{'Vehicle':<10} {'Pax':<5} {'Reg Class':<20} {'License':<12} {'Cap Group':<15} {'HOS Category'}")
        print("-" * 95)
        for row in cur.fetchall():
            vnum, pax, reg, lic, cap, hos = row
            print(f"{vnum:<10} {pax:<5} {reg:<20} {lic:<12} {cap:<15} {hos}")
        
        print(f"\n{'='*80}")
        print("✅ MIGRATION COMPLETE")
        print(f"{'='*80}\n")
        print("New columns added to vehicles table:")
        print("  - regulatory_class (commercial_bus vs non_commercial)")
        print("  - license_class_required (class_2, class_4, class_5)")
        print("  - capacity_group (sedan, small_suv, large_suv, small_bus, large_bus)")
        print("  - hos_category (commercial_bus_driving vs on_duty_non_bus)")
        print()
        print("Existing columns preserved:")
        print("  - vehicle_type (customer-facing description)")
        print("  - passenger_capacity (actual number)")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
