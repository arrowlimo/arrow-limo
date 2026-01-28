#!/usr/bin/env python3
"""
Populate vehicle_category and vehicle_class columns based on regulatory requirements.

Uses existing columns:
- vehicle_category → Capacity groups for allocation/booking
- vehicle_class → Regulatory/license requirements

Based on your definitions:
- Regulatory: 11+ pax = commercial bus (Class 2/4), <11 = non-commercial (Class 5)  
- License: 24+ pax = Class 2, 11-23 pax = Class 4, <11 = Class 5
- Category: Groups by size for customer booking
"""

import psycopg2
from datetime import datetime

def main():
    print(f"\n{'='*80}")
    print("POPULATE VEHICLE REGULATORY CLASSIFICATIONS")
    print(f"{'='*80}\n")
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    try:
        # Backup
        backup_table = f"vehicles_backup_class_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Creating backup: {backup_table}")
        cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM vehicles")
        conn.commit()
        print(f"✅ Backed up {cur.rowcount} vehicles\n")
        
        # Populate vehicle_class (regulatory/license requirement)
        print("Populating vehicle_class (license/regulatory)...")
        print("  - class_2: 24+ passengers (Class 2 license required)")
        print("  - class_4: 11-23 passengers (Class 4 license, commercial bus regs)")
        print("  - class_5: <11 passengers (Class 5 license, non-commercial)\n")
        
        cur.execute("""
            UPDATE vehicles
            SET vehicle_class = CASE
                WHEN passenger_capacity >= 24 THEN 'class_2'
                WHEN passenger_capacity BETWEEN 11 AND 23 THEN 'class_4'
                WHEN passenger_capacity <= 10 THEN 'class_5'
                ELSE 'unknown'
            END
        """)
        conn.commit()
        print(f"✅ Updated {cur.rowcount} vehicles\n")
        
        # Populate vehicle_category (booking/allocation groups)
        print("Populating vehicle_category (customer booking categories)...")
        print("  - sedan: 1-4 passengers")
        print("  - small_suv: 5-8 passengers")
        print("  - large_suv: 9-13 passengers (SUV bus)")
        print("  - small_bus: 14-23 passengers (shuttle/party bus)")
        print("  - large_bus: 24+ passengers (coach/limo bus)\n")
        
        cur.execute("""
            UPDATE vehicles
            SET vehicle_category = CASE
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
        
        # Verification
        print(f"{'='*80}")
        print("VERIFICATION - Classification Distribution")
        print(f"{'='*80}\n")
        
        cur.execute("""
            SELECT 
                vehicle_class,
                vehicle_category,
                COUNT(*) as count,
                MIN(passenger_capacity) as min_pax,
                MAX(passenger_capacity) as max_pax,
                STRING_AGG(DISTINCT vehicle_number, ', ' ORDER BY vehicle_number) as vehicles
            FROM vehicles
            WHERE passenger_capacity IS NOT NULL
            GROUP BY vehicle_class, vehicle_category
            ORDER BY min_pax
        """)
        
        print(f"{'Class':<12} {'Category':<15} {'Count':<7} {'Pax Range':<12} {'Sample Vehicles'}")
        print("-" * 95)
        for row in cur.fetchall():
            vclass, vcat, count, min_pax, max_pax, vehicles = row
            pax_range = f"{min_pax}-{max_pax}" if min_pax != max_pax else str(min_pax)
            sample = vehicles[:40] + "..." if len(vehicles) > 40 else vehicles
            print(f"{vclass:<12} {vcat:<15} {count:<7} {pax_range:<12} {sample}")
        
        # Show regulatory implications
        print(f"\n{'='*80}")
        print("REGULATORY IMPLICATIONS")
        print(f"{'='*80}\n")
        
        cur.execute("""
            SELECT 
                vehicle_class,
                CASE vehicle_class
                    WHEN 'class_2' THEN 'Class 2 license required, commercial bus HOS, 24+ pax'
                    WHEN 'class_4' THEN 'Class 4 license required, commercial bus HOS, 11-23 pax'
                    WHEN 'class_5' THEN 'Class 5 license OK, on-duty (non-bus) HOS, <11 pax'
                    ELSE 'Unknown'
                END as requirements,
                COUNT(*) as vehicle_count
            FROM vehicles
            WHERE vehicle_class IS NOT NULL
            GROUP BY vehicle_class
            ORDER BY vehicle_count DESC
        """)
        
        print(f"{'Class':<12} {'Regulatory Requirements':<60} {'Vehicles'}")
        print("-" * 80)
        for row in cur.fetchall():
            vclass, reqs, count = row
            print(f"{vclass:<12} {reqs:<60} {count}")
        
        print(f"\n{'='*80}")
        print("✅ POPULATION COMPLETE")
        print(f"{'='*80}\n")
        print("Columns now populated based on passenger_capacity:")
        print("  ✅ vehicle_class → License/regulatory class (class_2, class_4, class_5)")
        print("  ✅ vehicle_category → Booking/allocation group (sedan, suv, bus sizes)")
        print()
        print("Usage:")
        print("  - HOS logging: Use vehicle_class (class_4/class_2 = commercial bus driving)")
        print("  - Driver assignment: Check vehicle_class for license requirement")
        print("  - Customer booking: Show vehicle_category for size selection")
        print("  - Availability lookup: Group by vehicle_category for 'next size up'")
        
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
