"""
Create vehicle pricing defaults and charter type infrastructure.

Adds:
1. charter_types table - Valid charter types (hourly, package, airport, split_run, etc.)
2. vehicle_pricing_defaults table - Default rates by vehicle type
3. charters.charter_type column
4. charters.quoted_hours column
5. charters.extra_time_rate column
6. Split run calculation support
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        print("Creating charter_types reference table...")
        
        # Create charter_types lookup table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS charter_types (
                charter_type_id SERIAL PRIMARY KEY,
                type_code VARCHAR(50) UNIQUE NOT NULL,
                type_name VARCHAR(100) NOT NULL,
                description TEXT,
                requires_hours BOOLEAN DEFAULT true,
                is_active BOOLEAN DEFAULT true,
                display_order INTEGER DEFAULT 0
            )
        """)
        print("✅ charter_types table created")
        
        # Seed charter types
        charter_types_data = [
            ('hourly', 'Hourly Rate', 'Standard hourly charter with minimum hours', True, True, 1),
            ('package', 'Package Rate', 'Fixed package pricing (e.g., 6hr package)', True, True, 2),
            ('airport', 'Airport Transfer', 'Airport pickup/dropoff flat rate', False, True, 3),
            ('split_run', 'Split Run', 'Before/after event with standby time', True, True, 4),
            ('discount', 'Discounted Rate', 'Special discount pricing', True, True, 5),
            ('trade_of_service', 'Trade of Service', 'Non-cash trade arrangement', False, True, 6),
            ('donation', 'Donation/Charity', 'Donated service (no charge)', False, True, 7),
            ('custom', 'Custom Quote', 'Custom negotiated pricing', False, True, 8),
        ]
        
        for code, name, desc, req_hrs, active, order in charter_types_data:
            cur.execute("""
                INSERT INTO charter_types (type_code, type_name, description, requires_hours, is_active, display_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (type_code) DO NOTHING
            """, (code, name, desc, req_hrs, active, order))
        
        print(f"✅ Seeded {len(charter_types_data)} charter types")
        
        print("\nCreating vehicle_pricing_defaults table...")
        
        # Create vehicle pricing defaults table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_pricing_defaults (
                pricing_id SERIAL PRIMARY KEY,
                vehicle_type VARCHAR(50) NOT NULL,
                charter_type_code VARCHAR(50) NOT NULL,
                hourly_rate DECIMAL(10,2) DEFAULT 0.00,
                package_rate DECIMAL(10,2) DEFAULT 0.00,
                package_hours DECIMAL(5,2) DEFAULT 0.00,
                minimum_hours DECIMAL(5,2) DEFAULT 0.00,
                extra_time_rate DECIMAL(10,2) DEFAULT 0.00,
                standby_rate DECIMAL(10,2) DEFAULT 25.00,
                split_run_before_hours DECIMAL(5,2) DEFAULT 1.5,
                split_run_after_hours DECIMAL(5,2) DEFAULT 1.5,
                is_active BOOLEAN DEFAULT true,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(vehicle_type, charter_type_code)
            )
        """)
        print("✅ vehicle_pricing_defaults table created")
        
        # Seed default pricing by vehicle type
        # Format: (vehicle_type, charter_type, hourly, package, pkg_hrs, min_hrs, extra, standby, split_before, split_after)
        pricing_defaults = [
            # Sedan
            ('Sedan', 'hourly', 150.00, 0, 0, 2.0, 150.00, 25.00, 1.5, 1.5),
            ('Sedan', 'package', 0, 750.00, 6.0, 6.0, 150.00, 25.00, 1.5, 1.5),
            ('Sedan', 'airport', 75.00, 0, 0, 0, 0, 0, 0, 0),
            ('Sedan', 'split_run', 150.00, 0, 0, 0, 150.00, 25.00, 1.5, 1.5),
            
            # SUV
            ('SUV', 'hourly', 175.00, 0, 0, 2.0, 175.00, 30.00, 1.5, 1.5),
            ('SUV', 'package', 0, 900.00, 6.0, 6.0, 175.00, 30.00, 1.5, 1.5),
            ('SUV', 'airport', 95.00, 0, 0, 0, 0, 0, 0, 0),
            ('SUV', 'split_run', 175.00, 0, 0, 0, 175.00, 30.00, 1.5, 1.5),
            
            # Stretch Limo
            ('Stretch Limo', 'hourly', 195.00, 0, 0, 3.0, 195.00, 35.00, 1.5, 1.5),
            ('Stretch Limo', 'package', 0, 1170.00, 6.0, 6.0, 150.00, 35.00, 1.5, 1.5),
            ('Stretch Limo', 'airport', 125.00, 0, 0, 0, 0, 0, 0, 0),
            ('Stretch Limo', 'split_run', 195.00, 0, 0, 0, 150.00, 25.00, 1.5, 1.5),
            
            # Party Bus
            ('Party Bus', 'hourly', 225.00, 0, 0, 4.0, 225.00, 40.00, 1.5, 1.5),
            ('Party Bus', 'package', 0, 1350.00, 6.0, 6.0, 225.00, 40.00, 1.5, 1.5),
            ('Party Bus', 'airport', 0, 0, 0, 0, 0, 0, 0, 0),  # Not typically used for airport
            ('Party Bus', 'split_run', 225.00, 0, 0, 0, 225.00, 40.00, 1.5, 1.5),
        ]
        
        for vtype, ctype, hourly, pkg, pkg_hrs, min_hrs, extra, standby, split_b, split_a in pricing_defaults:
            cur.execute("""
                INSERT INTO vehicle_pricing_defaults (
                    vehicle_type, charter_type_code, hourly_rate, package_rate,
                    package_hours, minimum_hours, extra_time_rate, standby_rate,
                    split_run_before_hours, split_run_after_hours
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (vehicle_type, charter_type_code) DO NOTHING
            """, (vtype, ctype, hourly, pkg, pkg_hrs, min_hrs, extra, standby, split_b, split_a))
        
        print(f"✅ Seeded {len(pricing_defaults)} pricing defaults")
        
        print("\nAdding charter_type columns to charters table...")
        
        # Add charter type and pricing columns to charters
        cur.execute("""
            ALTER TABLE charters
            ADD COLUMN IF NOT EXISTS charter_type VARCHAR(50) DEFAULT 'hourly',
            ADD COLUMN IF NOT EXISTS quoted_hours DECIMAL(5,2) DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS extra_time_rate DECIMAL(10,2) DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS standby_rate DECIMAL(10,2) DEFAULT 25.00,
            ADD COLUMN IF NOT EXISTS split_run_before_hours DECIMAL(5,2) DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS split_run_after_hours DECIMAL(5,2) DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS split_run_standby_hours DECIMAL(5,2) DEFAULT 0.00
        """)
        print("✅ Added charter_type columns to charters")
        
        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_charters_charter_type ON charters(charter_type);
            CREATE INDEX IF NOT EXISTS idx_vehicle_pricing_vehicle_type ON vehicle_pricing_defaults(vehicle_type);
            CREATE INDEX IF NOT EXISTS idx_vehicle_pricing_charter_type ON vehicle_pricing_defaults(charter_type_code);
        """)
        print("✅ Created indexes")
        
        conn.commit()
        print("\n✅ DONE: Charter type infrastructure created")
        
        # Display pricing summary
        print("\n" + "="*80)
        print("VEHICLE PRICING DEFAULTS SUMMARY")
        print("="*80)
        cur.execute("""
            SELECT vehicle_type, charter_type_code, hourly_rate, package_rate, 
                   package_hours, extra_time_rate, standby_rate
            FROM vehicle_pricing_defaults
            ORDER BY vehicle_type, charter_type_code
        """)
        
        current_vehicle = None
        for row in cur.fetchall():
            if current_vehicle != row[0]:
                current_vehicle = row[0]
                print(f"\n{current_vehicle}:")
            
            if row[2] > 0:  # hourly_rate
                print(f"  {row[1]:15s} | ${row[2]:.2f}/hr | Extra: ${row[5]:.2f}/hr | Standby: ${row[6]:.2f}/hr")
            elif row[3] > 0:  # package_rate
                print(f"  {row[1]:15s} | ${row[3]:.2f} ({row[4]:.1f}hrs) | Extra: ${row[5]:.2f}/hr")
            else:
                print(f"  {row[1]:15s} | Flat rate")
        
        print("\n" + "="*80)
        print("\nCHARTER TYPES:")
        cur.execute("SELECT type_code, type_name, requires_hours FROM charter_types ORDER BY display_order")
        for row in cur.fetchall():
            req = "requires hours" if row[2] else "no hours required"
            print(f"  {row[0]:20s} - {row[1]:30s} ({req})")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
