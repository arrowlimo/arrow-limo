#!/usr/bin/env python3
"""
Create staging tables for GST calculations before inserting into receipts table.
This provides better control over tax calculations and data validation.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def create_gst_staging_tables(dry_run=True):
    """Create staging tables for GST calculations"""
    print("📊 CREATING GST CALCULATION STAGING TABLES")
    print("=" * 50)
    print("Mode:", "DRY RUN (preview only)" if dry_run else "APPLY CHANGES")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Define staging table structure
        staging_sql = """
        CREATE TABLE IF NOT EXISTS receipts_gst_staging (
            staging_id SERIAL PRIMARY KEY,
            
            -- Source data
            source_system TEXT NOT NULL,
            source_reference TEXT NOT NULL,
            source_file TEXT,
            source_row INTEGER,
            
            -- Receipt core data
            receipt_date DATE NOT NULL,
            vendor_name TEXT,
            description TEXT,
            currency CHAR(3) DEFAULT 'CAD',
            
            -- Financial amounts (raw from source)
            raw_amount NUMERIC NOT NULL,
            raw_tax NUMERIC DEFAULT 0,
            
            -- Calculated GST fields
            province_code CHAR(2) DEFAULT 'AB',
            gst_rate DECIMAL(6,4) DEFAULT 0.0500,
            tax_included BOOLEAN DEFAULT TRUE,
            
            -- Calculated results
            gross_amount NUMERIC,
            gst_amount NUMERIC,
            net_amount NUMERIC,
            
            -- Categorization
            category TEXT,
            expense_account TEXT,
            
            -- Processing status
            validation_status TEXT DEFAULT 'pending',
            validation_errors TEXT,
            processed_at TIMESTAMP,
            receipt_id BIGINT, -- Links to final receipts table record
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Constraints
            UNIQUE(source_system, source_reference)
        )
        """
        
        gst_rates_sql = """
        CREATE TABLE IF NOT EXISTS gst_rates_lookup (
            province_code CHAR(2) PRIMARY KEY,
            province_name TEXT NOT NULL,
            gst_rate DECIMAL(6,4) NOT NULL,
            pst_rate DECIMAL(6,4) DEFAULT 0,
            hst_rate DECIMAL(6,4) DEFAULT 0,
            total_rate DECIMAL(6,4) NOT NULL,
            effective_date DATE NOT NULL,
            notes TEXT
        )
        """
        
        # Insert GST rates for all Canadian provinces
        rates_insert_sql = """
        INSERT INTO gst_rates_lookup (province_code, province_name, gst_rate, pst_rate, hst_rate, total_rate, effective_date, notes) 
        VALUES 
            ('AB', 'Alberta', 0.0500, 0, 0, 0.0500, '2023-01-01', '5% GST only'),
            ('BC', 'British Columbia', 0.0500, 0.0700, 0, 0.1200, '2023-01-01', '5% GST + 7% PST'),
            ('SK', 'Saskatchewan', 0.0500, 0.0600, 0, 0.1100, '2023-01-01', '5% GST + 6% PST'),
            ('MB', 'Manitoba', 0.0500, 0.0700, 0, 0.1200, '2023-01-01', '5% GST + 7% PST'),
            ('ON', 'Ontario', 0, 0, 0.1300, 0.1300, '2023-01-01', '13% HST (harmonized)'),
            ('QC', 'Quebec', 0.0500, 0.09975, 0, 0.14975, '2023-01-01', '5% GST + 9.975% QST'),
            ('NB', 'New Brunswick', 0, 0, 0.1500, 0.1500, '2023-01-01', '15% HST'),
            ('NS', 'Nova Scotia', 0, 0, 0.1500, 0.1500, '2023-01-01', '15% HST'),
            ('PE', 'Prince Edward Island', 0, 0, 0.1500, 0.1500, '2023-01-01', '15% HST'),
            ('NL', 'Newfoundland', 0, 0, 0.1500, 0.1500, '2023-01-01', '15% HST'),
            ('YT', 'Yukon', 0.0500, 0, 0, 0.0500, '2023-01-01', '5% GST only'),
            ('NT', 'Northwest Territories', 0.0500, 0, 0, 0.0500, '2023-01-01', '5% GST only'),
            ('NU', 'Nunavut', 0.0500, 0, 0, 0.0500, '2023-01-01', '5% GST only')
        ON CONFLICT (province_code) DO NOTHING
        """
        
        # GST calculation function
        calc_function_sql = """
        CREATE OR REPLACE FUNCTION calculate_gst_amounts(
            p_raw_amount NUMERIC,
            p_province_code CHAR(2) DEFAULT 'AB',
            p_tax_included BOOLEAN DEFAULT TRUE
        ) RETURNS TABLE(
            gross_amount NUMERIC,
            gst_amount NUMERIC, 
            net_amount NUMERIC
        ) AS $$
        DECLARE
            v_rate DECIMAL(6,4);
        BEGIN
            -- Get tax rate for province
            SELECT total_rate INTO v_rate 
            FROM gst_rates_lookup 
            WHERE province_code = p_province_code;
            
            -- Default to Alberta rate if province not found
            IF v_rate IS NULL THEN
                v_rate := 0.0500;
            END IF;
            
            IF p_tax_included THEN
                -- Tax is included in the raw amount
                gross_amount := p_raw_amount;
                gst_amount := ROUND(p_raw_amount * v_rate / (1 + v_rate), 2);
                net_amount := gross_amount - gst_amount;
            ELSE
                -- Tax is additional to raw amount
                net_amount := p_raw_amount;
                gst_amount := ROUND(p_raw_amount * v_rate, 2);
                gross_amount := net_amount + gst_amount;
            END IF;
            
            RETURN NEXT;
        END;
        $$ LANGUAGE plpgsql;
        """
        
        if dry_run:
            print("📋 PLANNED STAGING TABLE STRUCTURE:")
            print("\n1. receipts_gst_staging:")
            print("   - Holds raw receipt data before GST calculations")
            print("   - Supports multiple provinces and tax rates")
            print("   - Tracks validation status and errors")
            print("   - Links to final receipts table records")
            
            print("\n2. gst_rates_lookup:")
            print("   - GST/PST/HST rates for all Canadian provinces")
            print("   - Supports rate changes over time")
            print("   - Includes calculation notes")
            
            print("\n3. calculate_gst_amounts() function:")
            print("   - Handles tax-included vs tax-additional calculations")
            print("   - Province-specific rate lookup")
            print("   - Returns gross, GST, and net amounts")
            
            print(f"\n📊 WORKFLOW:")
            print(f"   1. Import raw data → receipts_gst_staging")
            print(f"   2. Run GST calculations using function")
            print(f"   3. Validate and review in staging")
            print(f"   4. Promote to receipts table")
            
            print(f"\n📋 To create tables, run: python {__file__} --apply")
            return
        
        # Apply changes
        print("🔧 CREATING STAGING TABLES...")
        
        print("  1. Creating receipts_gst_staging table...")
        cur.execute(staging_sql)
        
        print("  2. Creating gst_rates_lookup table...")
        cur.execute(gst_rates_sql)
        
        print("  3. Inserting Canadian GST/PST/HST rates...")
        cur.execute(rates_insert_sql)
        
        print("  4. Creating GST calculation function...")
        cur.execute(calc_function_sql)
        
        conn.commit()
        
        # Verify creation
        print("\n[OK] STAGING TABLES CREATED - VERIFYING...")
        
        cur.execute("SELECT COUNT(*) FROM gst_rates_lookup")
        rates_count = cur.fetchone()[0]
        print(f"  GST rates loaded: {rates_count} provinces")
        
        cur.execute("SELECT province_code, province_name, total_rate FROM gst_rates_lookup ORDER BY province_code")
        print(f"  Sample rates:")
        for code, name, rate in cur.fetchall()[:5]:
            print(f"    {code}: {name} = {rate:.1%}")
        
        # Test the calculation function
        print(f"\n🧪 TESTING GST CALCULATION FUNCTION:")
        cur.execute("SELECT * FROM calculate_gst_amounts(105.00, 'AB', TRUE)")
        gross, gst, net = cur.fetchone()
        print(f"  Alberta $105 tax-included: gross=${gross:.2f}, gst=${gst:.2f}, net=${net:.2f}")
        
        cur.execute("SELECT * FROM calculate_gst_amounts(100.00, 'ON', FALSE)")
        gross, gst, net = cur.fetchone()
        print(f"  Ontario $100 tax-additional: gross=${gross:.2f}, gst=${gst:.2f}, net=${net:.2f}")
        
        print(f"\n🎯 BENEFITS:")
        print(f"   [OK] GST calculations handled in staging before final insert")
        print(f"   [OK] Support for all Canadian provinces")
        print(f"   [OK] Validation and error tracking")
        print(f"   [OK] No more generated column import issues")
        print(f"   [OK] Easy to review and correct before promotion")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        conn.rollback()
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create GST calculation staging tables')
    parser.add_argument('--apply', action='store_true', help='Create the tables (default is dry-run)')
    
    args = parser.parse_args()
    
    create_gst_staging_tables(dry_run=not args.apply)

if __name__ == "__main__":
    main()