import sys, os
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from modern_backend.app.db import get_connection

SQL_CREATE_CHARGES = """
CREATE TABLE IF NOT EXISTS charges (
    charge_id SERIAL PRIMARY KEY,
    reserve_number VARCHAR(6) NOT NULL,
    charge_type VARCHAR(50) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_charges_reserve_number ON charges(reserve_number);
CREATE INDEX IF NOT EXISTS idx_charges_charge_type ON charges(charge_type);
"""

SQL_CREATE_CATALOG = """
CREATE TABLE IF NOT EXISTS charge_catalog (
    catalog_id SERIAL PRIMARY KEY,
    charge_code VARCHAR(50) UNIQUE NOT NULL,
    charge_name VARCHAR(100) NOT NULL,
    charge_type VARCHAR(50) NOT NULL,
    default_amount DECIMAL(12,2) DEFAULT 0.00,
    is_taxable BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_charge_catalog_code ON charge_catalog(charge_code);
CREATE INDEX IF NOT EXISTS idx_charge_catalog_active ON charge_catalog(is_active);
"""

SQL_SEED_CATALOG = """
INSERT INTO charge_catalog (charge_code, charge_name, charge_type, default_amount, is_taxable, display_order)
VALUES
    ('BASE_HOURLY', 'Base Hourly Rate', 'base_rate', 150.00, true, 1),
    ('BASE_PACKAGE', 'Package Rate', 'base_rate', 200.00, true, 2),
    ('AIRPORT_PICKUP', 'Airport Pickup Fee', 'airport_fee', 30.00, true, 10),
    ('AIRPORT_DROPOFF', 'Airport Dropoff Fee', 'airport_fee', 30.00, true, 11),
    ('EXTRA_TIME', 'Extra Time (per hour)', 'additional', 50.00, true, 20),
    ('TOLL', 'Toll Charges', 'additional', 0.00, true, 21),
    ('WAITING_TIME', 'Waiting Time', 'additional', 0.00, true, 22),
    ('CLEANUP', 'Cleanup Fee', 'additional', 100.00, true, 23),
    ('BEVERAGE_SERVICE', 'Beverage Service', 'additional', 0.00, true, 24),
    ('GRATUITY', 'Gratuity', 'additional', 0.00, false, 30)
ON CONFLICT (charge_code) DO NOTHING;
"""

def main():
    conn = get_connection()
    cur = conn.cursor()
    try:
        print("Creating charges table...")
        cur.execute(SQL_CREATE_CHARGES)
        print("✅ charges table created")
        
        print("Creating charge_catalog table...")
        cur.execute(SQL_CREATE_CATALOG)
        print("✅ charge_catalog table created")
        
        print("Seeding charge_catalog with default entries...")
        cur.execute(SQL_SEED_CATALOG)
        cur.execute("SELECT COUNT(*) FROM charge_catalog")
        count = cur.fetchone()[0]
        print(f"✅ charge_catalog seeded ({count} entries)")
        
        conn.commit()
        print("\n✅ DONE: charges infrastructure ready")
    except Exception as e:
        conn.rollback()
        print(f"❌ ERROR: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
