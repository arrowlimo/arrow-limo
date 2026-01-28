#!/usr/bin/env python3
"""
Tweak existing database tables to support Advanced Quoting, Beverage Ordering, 
and Vehicle Incident Tracking systems.

Run: python l:\limo\migrations\tweak_tables_for_quotes_beverages_incidents.py
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def column_exists(cur, table_name, column_name):
    """Check if column already exists."""
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_name = %s AND column_name = %s
    """, (table_name, column_name))
    return cur.fetchone()[0] > 0

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*70)
    print("TWEAKING DATABASE TABLES FOR QUOTES/BEVERAGES/INCIDENTS")
    print("="*70)
    
    try:
        # ===== BEVERAGES TABLE TWEAKS =====
        print("\n[1/3] BEVERAGES TABLE")
        print("-" * 70)
        
        tweaks_beverages = [
            ("our_cost", "NUMERIC(10,2)", "our_purchase_price"),
            ("marked_up_price_gst_included", "NUMERIC(10,2)", "retail_price_with_gst"),
            ("gst_deposit_amount", "NUMERIC(10,2)", "for tracking GST portion"),
            ("ice_charge", "NUMERIC(10,2)", "additional charge for ice"),
            ("is_charter_eligible", "BOOLEAN DEFAULT TRUE", "can be added to charter orders"),
        ]
        
        for new_col, col_type, description in tweaks_beverages:
            if not column_exists(cur, 'beverages', new_col):
                # Check if alternate name exists
                alt_names = {
                    'our_cost': ['cost_price', 'cost'],
                    'marked_up_price_gst_included': ['retail_price', 'price'],
                }
                
                found_alt = False
                if new_col in alt_names:
                    for alt in alt_names[new_col]:
                        if column_exists(cur, 'beverages', alt):
                            print(f"  ✓ {new_col}: Using existing column '{alt}' ({description})")
                            found_alt = True
                            break
                
                if not found_alt:
                    cur.execute(f"ALTER TABLE beverages ADD COLUMN {new_col} {col_type}")
                    print(f"  ✓ Added {new_col} {col_type}")
            else:
                print(f"  ✓ {new_col} already exists")
        
        conn.commit()
        print("  ✅ Beverages table updated successfully")
        
        # ===== INCIDENTS TABLE TWEAKS =====
        print("\n[2/3] INCIDENTS TABLE")
        print("-" * 70)
        
        tweaks_incidents = [
            ("charter_id", "INTEGER", "link to affected charter"),
            ("incident_start_time", "TIMESTAMP", "when incident occurred"),
            ("replacement_vehicle_id", "INTEGER", "replacement vehicle used"),
            ("replacement_arrival_time", "TIMESTAMP", "when replacement arrived"),
            ("downtime_minutes", "INTEGER", "calculated downtime"),
            ("total_incident_cost", "NUMERIC(10,2)", "sum of all incident costs"),
            ("guest_compensation_flag", "BOOLEAN DEFAULT FALSE", "guest compensation provided"),
            ("guest_compensation_amount", "NUMERIC(10,2)", "amount rebated to guest"),
        ]
        
        for new_col, col_type, description in tweaks_incidents:
            if not column_exists(cur, 'incidents', new_col):
                cur.execute(f"ALTER TABLE incidents ADD COLUMN {new_col} {col_type}")
                print(f"  ✓ Added {new_col} {col_type}")
            else:
                print(f"  ✓ {new_col} already exists")
        
        conn.commit()
        print("  ✅ Incidents table updated successfully")
        
        # ===== CREATE SUPPORTING TABLES =====
        print("\n[3/3] CREATING SUPPORTING TABLES")
        print("-" * 70)
        
        # Agreement Terms table
        if not table_exists(cur, 'agreement_terms'):
            cur.execute("""
                CREATE TABLE agreement_terms (
                    term_id SERIAL PRIMARY KEY,
                    term_name VARCHAR(200) NOT NULL,
                    description TEXT,
                    term_text TEXT NOT NULL,
                    category VARCHAR(50),  -- payment, cancellation, damage, other
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created agreement_terms table")
            conn.commit()
        else:
            print("  ✓ agreement_terms table already exists")
        
        # Beverage Cart table
        if not table_exists(cur, 'beverage_cart'):
            cur.execute("""
                CREATE TABLE beverage_cart (
                    cart_id SERIAL PRIMARY KEY,
                    charter_id INTEGER,
                    beverage_id INTEGER REFERENCES beverages(beverage_id),
                    quantity INTEGER DEFAULT 1,
                    ice_requested BOOLEAN DEFAULT FALSE,
                    our_cost_total NUMERIC(10,2),
                    marked_up_total NUMERIC(10,2),
                    free_flag BOOLEAN DEFAULT FALSE,
                    cost_only_flag BOOLEAN DEFAULT FALSE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created beverage_cart table")
            conn.commit()
        else:
            print("  ✓ beverage_cart table already exists")
        
        # Incident Costs table
        if not table_exists(cur, 'incident_costs'):
            cur.execute("""
                CREATE TABLE incident_costs (
                    cost_id SERIAL PRIMARY KEY,
                    incident_id INTEGER REFERENCES incidents(incident_id),
                    cost_type VARCHAR(100),  -- taxi, meal, rental, other
                    description TEXT,
                    amount NUMERIC(10,2) NOT NULL,
                    rebate_percentage NUMERIC(5,2) DEFAULT 0,  -- 0-100%
                    rebate_amount NUMERIC(10,2),  -- calculated
                    net_cost NUMERIC(10,2),  -- amount - rebate_amount
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created incident_costs table")
            conn.commit()
        else:
            print("  ✓ incident_costs table already exists")
        
        # Quotations table
        if not table_exists(cur, 'quotations'):
            cur.execute("""
                CREATE TABLE quotations (
                    quote_id SERIAL PRIMARY KEY,
                    charter_id INTEGER,
                    reserve_number VARCHAR(20),
                    client_id INTEGER,
                    quote_date DATE NOT NULL,
                    pickup_location VARCHAR(200),
                    dropoff_location VARCHAR(200),
                    pax_count INTEGER,
                    
                    hourly_hours NUMERIC(8,2),
                    hourly_rate NUMERIC(10,2),
                    hourly_total NUMERIC(12,2),
                    
                    package_description VARCHAR(200),
                    package_price NUMERIC(12,2),
                    
                    split_run_json TEXT,
                    split_run_total NUMERIC(12,2),
                    
                    gst_rate NUMERIC(5,4) DEFAULT 0.05,
                    gratuity_rate NUMERIC(5,4) DEFAULT 0.18,
                    extra_charges_json TEXT,
                    
                    selected_option VARCHAR(20),  -- hourly, package, split_run
                    total_quote NUMERIC(12,2),
                    
                    status VARCHAR(50) DEFAULT 'pending',  -- pending, accepted, declined, expired
                    sent_to_client BOOLEAN DEFAULT FALSE,
                    sent_date TIMESTAMP,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created quotations table")
            conn.commit()
        else:
            print("  ✓ quotations table already exists")
        
        print("\n" + "="*70)
        print("✅ ALL TABLES TWEAKED SUCCESSFULLY")
        print("="*70)
        print("\nYou can now use:")
        print("  - desktop_app/quotes_engine.py")
        print("  - desktop_app/beverage_ordering.py")
        print("  - desktop_app/red_deer_bylaw_and_incidents.py")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        conn.rollback()
        cur.close()
        conn.close()
        return 1
    
    return 0

def table_exists(cur, table_name):
    """Check if table exists."""
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = %s
    """, (table_name,))
    return cur.fetchone()[0] > 0

if __name__ == '__main__':
    exit(main())
