"""
Enhance charges infrastructure to support percentage-based charges (gratuity, fuel surcharge).
Adds:
1. charge_catalog: calculation_type, percentage_rate columns
2. clients: gst_exempt flag
3. New catalog entries: FUEL_SURCHARGE
4. Updated GRATUITY to use 18% default
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
        print("Adding percentage support to charge_catalog...")
        
        # Add calculation_type and percentage_rate columns
        cur.execute("""
            ALTER TABLE charge_catalog
            ADD COLUMN IF NOT EXISTS calculation_type VARCHAR(20) DEFAULT 'fixed',
            ADD COLUMN IF NOT EXISTS percentage_rate DECIMAL(5,2) DEFAULT 0.00,
            ADD CONSTRAINT chk_calculation_type 
                CHECK (calculation_type IN ('fixed', 'percentage', 'quantity'))
        """)
        print("✅ Added calculation_type and percentage_rate columns")
        
        # Update GRATUITY to use 18% percentage calculation
        cur.execute("""
            UPDATE charge_catalog
            SET calculation_type = 'percentage',
                percentage_rate = 18.00,
                charge_name = 'Gratuity (18% default, adjustable)'
            WHERE charge_code = 'GRATUITY'
        """)
        print("✅ Updated GRATUITY to 18% percentage-based")
        
        # Add FUEL_SURCHARGE to catalog
        cur.execute("""
            INSERT INTO charge_catalog (
                charge_code, charge_name, charge_type, 
                calculation_type, percentage_rate, default_amount,
                is_taxable, is_active, display_order
            )
            VALUES (
                'FUEL_SURCHARGE', 'Fuel Surcharge', 'additional',
                'percentage', 0.00, 0.00,
                true, false, 25
            )
            ON CONFLICT (charge_code) DO NOTHING
        """)
        print("✅ Added FUEL_SURCHARGE to catalog (inactive by default)")
        
        # Add CUSTOM_RATE to catalog for custom charter pricing
        cur.execute("""
            INSERT INTO charge_catalog (
                charge_code, charge_name, charge_type,
                calculation_type, default_amount,
                is_taxable, is_active, display_order
            )
            VALUES (
                'BASE_CUSTOM', 'Custom Rate', 'base_rate',
                'fixed', 0.00,
                true, true, 3
            )
            ON CONFLICT (charge_code) DO NOTHING
        """)
        print("✅ Added BASE_CUSTOM for custom charter pricing")
        
        print("\nAdding GST exemption support to clients...")
        
        # Add gst_exempt flag to clients table
        cur.execute("""
            ALTER TABLE clients
            ADD COLUMN IF NOT EXISTS gst_exempt BOOLEAN DEFAULT false
        """)
        print("✅ Added gst_exempt column to clients table")
        
        # Create index for GST-exempt clients
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_gst_exempt 
            ON clients(gst_exempt) WHERE gst_exempt = true
        """)
        print("✅ Created index on gst_exempt clients")
        
        print("\nAdding customer printout preference to charters...")
        
        # Add separate_customer_printout flag to charters
        cur.execute("""
            ALTER TABLE charters
            ADD COLUMN IF NOT EXISTS separate_customer_printout BOOLEAN DEFAULT false
        """)
        print("✅ Added separate_customer_printout to charters")
        
        conn.commit()
        print("\n✅ DONE: Charges infrastructure enhanced")
        print("\nCatalog now supports:")
        print("  - Fixed amounts (base rates, airport fees)")
        print("  - Percentage-based (gratuity 18%, fuel surcharge)")
        print("  - Client GST exemption flag")
        print("  - Custom charter pricing")
        print("  - Separate customer printout option")
        
        # Show updated catalog
        print("\nUpdated charge catalog:")
        cur.execute("""
            SELECT charge_code, charge_name, calculation_type, 
                   default_amount, percentage_rate, is_taxable, is_active
            FROM charge_catalog
            ORDER BY display_order
        """)
        for row in cur.fetchall():
            calc_info = f"${row[3]}" if row[2] == 'fixed' else f"{row[4]}%"
            tax_info = "taxable" if row[5] else "non-taxable"
            active_info = "ACTIVE" if row[6] else "inactive"
            print(f"  {row[0]:20s} | {row[1]:35s} | {row[2]:10s} {calc_info:10s} | {tax_info:12s} | {active_info}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
