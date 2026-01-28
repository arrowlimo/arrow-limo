#!/usr/bin/env python3
"""
Create Missing Receipt Staging System
====================================

Manual entry system for accountant cash receipts that are missing from digital records.
Provides staging table and batch processing workflow.

Based on spot check findings:
- Liquor Barn receipts (4 checked, 4 missing) = $442.44 total
- Pattern suggests significant missing receipt population
- Need systematic manual entry and validation process

Author: AI Agent
Date: October 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from decimal import Decimal
from datetime import datetime
import json

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def create_receipt_staging_schema(conn):
    """Create staging table for manual receipt entry."""
    cur = conn.cursor()
    
    # Drop existing staging table if needed
    cur.execute("DROP TABLE IF EXISTS staging_accountant_receipts CASCADE")
    
    # Create staging table
    cur.execute("""
        CREATE TABLE staging_accountant_receipts (
            id SERIAL PRIMARY KEY,
            entry_date DATE NOT NULL,
            vendor_name VARCHAR(200) NOT NULL,
            gross_amount DECIMAL(12,2) NOT NULL,
            gst_amount DECIMAL(12,2) NOT NULL,
            net_amount DECIMAL(12,2) GENERATED ALWAYS AS (gross_amount - gst_amount) STORED,
            receipt_date DATE NOT NULL,
            description TEXT,
            category VARCHAR(100) DEFAULT 'business_expense',
            payment_method VARCHAR(50) DEFAULT 'cash',
            source_reference VARCHAR(100) DEFAULT 'accountant_manual_entry',
            notes TEXT,
            entered_by VARCHAR(100) DEFAULT 'manual_entry',
            entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            validated BOOLEAN DEFAULT FALSE,
            validation_notes TEXT,
            promoted_to_receipts BOOLEAN DEFAULT FALSE,
            promoted_at TIMESTAMP,
            receipt_id INTEGER, -- Link to main receipts table after promotion
            
            -- Audit fields
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add indexes
    cur.execute("""
        CREATE INDEX idx_staging_receipts_date ON staging_accountant_receipts(receipt_date);
        CREATE INDEX idx_staging_receipts_vendor ON staging_accountant_receipts(vendor_name);
        CREATE INDEX idx_staging_receipts_amount ON staging_accountant_receipts(gross_amount);
        CREATE INDEX idx_staging_receipts_validated ON staging_accountant_receipts(validated);
        CREATE INDEX idx_staging_receipts_promoted ON staging_accountant_receipts(promoted_to_receipts);
    """)
    
    # Create validation trigger
    cur.execute("""
        CREATE OR REPLACE FUNCTION validate_gst_calculation()
        RETURNS TRIGGER AS $$
        DECLARE
            calculated_gst DECIMAL(12,2);
            gst_rate DECIMAL(5,4) := 0.05; -- Alberta 2012: 5% GST
        BEGIN
            -- Calculate GST (included in gross amount)
            calculated_gst := NEW.gross_amount * gst_rate / (1 + gst_rate);
            
            -- Check if GST is within reasonable tolerance (5 cents)
            IF ABS(NEW.gst_amount - calculated_gst) > 0.05 THEN
                NEW.validation_notes := COALESCE(NEW.validation_notes, '') || 
                    ' GST_WARNING: Expected ' || calculated_gst::TEXT || 
                    ', got ' || NEW.gst_amount::TEXT || ';';
            END IF;
            
            -- Validate amount is positive
            IF NEW.gross_amount <= 0 THEN
                RAISE EXCEPTION 'Gross amount must be positive';
            END IF;
            
            IF NEW.gst_amount < 0 THEN
                RAISE EXCEPTION 'GST amount cannot be negative';
            END IF;
            
            -- Update timestamp
            NEW.updated_at := CURRENT_TIMESTAMP;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    cur.execute("""
        CREATE TRIGGER validate_receipt_entry
        BEFORE INSERT OR UPDATE ON staging_accountant_receipts
        FOR EACH ROW EXECUTE FUNCTION validate_gst_calculation();
    """)
    
    conn.commit()
    cur.close()
    
    print("[OK] Created staging_accountant_receipts table with validation")

def insert_sample_liquor_barn_receipts(conn):
    """Insert the 4 Liquor Barn receipts we've been checking."""
    cur = conn.cursor()
    
    liquor_receipts = [
        ('2012-12-06', 'Liquor Barn', 41.18, 1.93, 'Liquor purchase - business entertainment/gifts'),
        ('2012-12-07', 'Liquor Barn', 44.90, 2.10, 'Liquor purchase - business entertainment/gifts'),
        ('2012-12-31', 'Liquor Barn', 60.32, 2.75, 'Liquor purchase #1 - year-end business entertainment'),
        ('2012-12-31', 'Liquor Barn', 296.04, 13.65, 'Liquor purchase #2 - year-end business entertainment')
    ]
    
    print("🍷 INSERTING SAMPLE LIQUOR BARN RECEIPTS")
    print("=" * 40)
    
    total_gross = Decimal('0')
    total_gst = Decimal('0')
    
    for receipt_date, vendor, gross, gst, description in liquor_receipts:
        cur.execute("""
            INSERT INTO staging_accountant_receipts 
            (receipt_date, vendor_name, gross_amount, gst_amount, description, 
             category, notes, source_reference)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, net_amount, validation_notes
        """, (
            receipt_date, vendor, gross, gst, description,
            'business_entertainment', 
            f'Spot check receipt - confirmed missing from digital records',
            'accountant_cash_records_manual_entry'
        ))
        
        result = cur.fetchone()
        staging_id, net_amount, validation_notes = result
        
        total_gross += Decimal(str(gross))
        total_gst += Decimal(str(gst))
        
        status = "[OK] VALID" if not validation_notes else f"[WARN] {validation_notes}"
        print(f"#{staging_id}: {receipt_date} ${gross:.2f} (${gst:.2f} GST, ${net_amount:.2f} net) {status}")
    
    conn.commit()
    cur.close()
    
    print("-" * 40)
    print(f"Total Staged: ${total_gross:.2f} gross, ${total_gst:.2f} GST, ${total_gross - total_gst:.2f} net")
    print("[OK] Sample receipts staged for validation")

def create_manual_entry_template(conn):
    """Create a template for manual receipt entry."""
    
    template = {
        "manual_receipt_entry_template": {
            "instructions": "Copy this template for each new receipt",
            "receipt_date": "YYYY-MM-DD",
            "vendor_name": "Exact vendor name from receipt",
            "gross_amount": "Total amount including GST/HST",
            "gst_amount": "GST/HST amount (5% for Alberta 2012)",
            "description": "Description of purchase/service",
            "category": "business_expense|fuel|maintenance|office|communication|etc",
            "notes": "Additional context or receipt details"
        },
        "sample_entries": [
            {
                "receipt_date": "2012-12-06",
                "vendor_name": "Liquor Barn",
                "gross_amount": 41.18,
                "gst_amount": 1.93,
                "description": "Business entertainment supplies",
                "category": "business_entertainment",
                "notes": "Year-end client appreciation"
            }
        ],
        "gst_calculation_help": {
            "alberta_2012_rate": "5% GST included in total",
            "formula": "GST = gross_amount × 0.05 ÷ 1.05",
            "example": "$41.18 → GST = $41.18 × 0.05 ÷ 1.05 = $1.96 ≈ $1.93"
        },
        "common_categories": [
            "fuel", "maintenance", "office_supplies", "communication",
            "insurance", "licensing", "business_entertainment", 
            "professional_services", "bank_fees", "equipment"
        ]
    }
    
    with open('manual_receipt_entry_template.json', 'w') as f:
        json.dump(template, f, indent=2)
    
    print("📝 Created manual_receipt_entry_template.json")

def create_batch_insert_function(conn):
    """Create function for batch inserting receipts."""
    cur = conn.cursor()
    
    cur.execute("""
        CREATE OR REPLACE FUNCTION batch_insert_receipts(receipt_data JSON)
        RETURNS TABLE(
            staging_id INTEGER,
            receipt_date DATE,
            vendor_name VARCHAR(200),
            gross_amount DECIMAL(12,2),
            net_amount DECIMAL(12,2),
            status TEXT
        ) AS $$
        DECLARE
            receipt_record JSON;
            new_id INTEGER;
            calc_net DECIMAL(12,2);
        BEGIN
            FOR receipt_record IN SELECT json_array_elements(receipt_data)
            LOOP
                INSERT INTO staging_accountant_receipts (
                    receipt_date, vendor_name, gross_amount, gst_amount,
                    description, category, notes, source_reference
                ) VALUES (
                    (receipt_record->>'receipt_date')::DATE,
                    receipt_record->>'vendor_name',
                    (receipt_record->>'gross_amount')::DECIMAL(12,2),
                    (receipt_record->>'gst_amount')::DECIMAL(12,2),
                    receipt_record->>'description',
                    COALESCE(receipt_record->>'category', 'business_expense'),
                    receipt_record->>'notes',
                    'batch_manual_entry'
                ) RETURNING id, net_amount INTO new_id, calc_net;
                
                RETURN QUERY SELECT 
                    new_id,
                    (receipt_record->>'receipt_date')::DATE,
                    receipt_record->>'vendor_name',
                    (receipt_record->>'gross_amount')::DECIMAL(12,2),
                    calc_net,
                    'INSERTED'::TEXT;
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    conn.commit()
    cur.close()
    
    print("⚡ Created batch_insert_receipts() function")

def create_promotion_workflow(conn):
    """Create workflow to promote staging receipts to main receipts table."""
    cur = conn.cursor()
    
    cur.execute("""
        CREATE OR REPLACE FUNCTION promote_validated_receipts()
        RETURNS TABLE(
            promoted_count INTEGER,
            total_gross_amount DECIMAL(12,2),
            total_gst_amount DECIMAL(12,2)
        ) AS $$
        DECLARE
            promotion_count INTEGER := 0;
            total_gross DECIMAL(12,2) := 0;
            total_gst DECIMAL(12,2) := 0;
            staging_record RECORD;
            new_receipt_id INTEGER;
        BEGIN
            FOR staging_record IN 
                SELECT * FROM staging_accountant_receipts 
                WHERE validated = TRUE AND promoted_to_receipts = FALSE
            LOOP
                -- Insert into main receipts table
                INSERT INTO receipts (
                    receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                    description, category, source_system, source_reference, notes,
                    is_business_expense, created_at
                ) VALUES (
                    staging_record.receipt_date,
                    staging_record.vendor_name,
                    staging_record.gross_amount,
                    staging_record.gst_amount,
                    staging_record.net_amount,
                    staging_record.description,
                    staging_record.category,
                    'manual_entry_staging',
                    staging_record.source_reference,
                    COALESCE(staging_record.notes, '') || ' [Promoted from staging #' || staging_record.id || ']',
                    TRUE,
                    CURRENT_TIMESTAMP
                ) RETURNING receipt_id INTO new_receipt_id;
                
                -- Update staging record
                UPDATE staging_accountant_receipts 
                SET promoted_to_receipts = TRUE,
                    promoted_at = CURRENT_TIMESTAMP,
                    receipt_id = new_receipt_id
                WHERE id = staging_record.id;
                
                promotion_count := promotion_count + 1;
                total_gross := total_gross + staging_record.gross_amount;
                total_gst := total_gst + staging_record.gst_amount;
            END LOOP;
            
            RETURN QUERY SELECT promotion_count, total_gross, total_gst;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    conn.commit()
    cur.close()
    
    print("🚀 Created promote_validated_receipts() function")

def create_staging_summary_views(conn):
    """Create summary views for staging management."""
    cur = conn.cursor()
    
    cur.execute("""
        CREATE OR REPLACE VIEW v_staging_receipt_summary AS
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(*) FILTER (WHERE validated) as validated_receipts,
            COUNT(*) FILTER (WHERE promoted_to_receipts) as promoted_receipts,
            COUNT(*) FILTER (WHERE NOT validated) as pending_validation,
            SUM(gross_amount) as total_gross,
            SUM(gst_amount) as total_gst,
            SUM(net_amount) as total_net,
            MIN(receipt_date) as earliest_date,
            MAX(receipt_date) as latest_date,
            COUNT(DISTINCT vendor_name) as unique_vendors
        FROM staging_accountant_receipts;
    """)
    
    cur.execute("""
        CREATE OR REPLACE VIEW v_staging_by_vendor AS
        SELECT 
            vendor_name,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_gross,
            SUM(gst_amount) as total_gst,
            SUM(net_amount) as total_net,
            COUNT(*) FILTER (WHERE validated) as validated_count,
            COUNT(*) FILTER (WHERE promoted_to_receipts) as promoted_count
        FROM staging_accountant_receipts
        GROUP BY vendor_name
        ORDER BY total_gross DESC;
    """)
    
    cur.execute("""
        CREATE OR REPLACE VIEW v_staging_by_category AS
        SELECT 
            category,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_gross,
            SUM(gst_amount) as total_gst,
            SUM(net_amount) as total_net,
            AVG(gross_amount) as avg_amount
        FROM staging_accountant_receipts
        GROUP BY category
        ORDER BY total_gross DESC;
    """)
    
    conn.commit()
    cur.close()
    
    print("📊 Created staging summary views")

def show_staging_status(conn):
    """Show current staging table status."""
    cur = conn.cursor()
    
    # Get summary
    cur.execute("SELECT * FROM v_staging_receipt_summary")
    summary = cur.fetchone()
    
    if summary:
        total, validated, promoted, pending, gross, gst, net, earliest, latest, vendors = summary
        
        print()
        print("📋 STAGING TABLE CURRENT STATUS")
        print("=" * 32)
        print(f"Total Receipts: {total}")
        print(f"├─ Validated: {validated}")
        print(f"├─ Promoted: {promoted}")
        print(f"└─ Pending Validation: {pending}")
        print()
        print(f"Financial Summary:")
        print(f"├─ Total Gross: ${gross or 0:.2f}")
        print(f"├─ Total GST: ${gst or 0:.2f}")
        print(f"└─ Total Net: ${net or 0:.2f}")
        print()
        print(f"Date Range: {earliest} to {latest}")
        print(f"Unique Vendors: {vendors}")
        
        # Show by vendor
        cur.execute("SELECT * FROM v_staging_by_vendor LIMIT 10")
        vendors = cur.fetchall()
        
        if vendors:
            print()
            print("🏪 TOP VENDORS IN STAGING")
            print("=" * 25)
            print(f"{'Vendor':<20} {'Count':<6} {'Gross':<10} {'Status'}")
            print("-" * 50)
            
            for vendor, count, gross, gst, net, validated, promoted in vendors:
                status = f"{validated}/{count} val, {promoted}/{count} prom"
                print(f"{vendor[:18]:<20} {count:<6} ${gross:<8.2f} {status}")
    else:
        print("📋 Staging table is empty")
    
    cur.close()

def main():
    print("🏗️  MISSING RECEIPT STAGING SYSTEM SETUP")
    print("=" * 45)
    print("Setting up manual entry system for missing accountant cash receipts")
    print()
    
    conn = get_db_connection()
    
    try:
        # Create staging infrastructure
        print("1️⃣  Creating staging schema...")
        create_receipt_staging_schema(conn)
        
        print("\n2️⃣  Creating batch processing functions...")
        create_batch_insert_function(conn)
        create_promotion_workflow(conn)
        
        print("\n3️⃣  Creating summary views...")
        create_staging_summary_views(conn)
        
        print("\n4️⃣  Creating manual entry template...")
        create_manual_entry_template(conn)
        
        print("\n5️⃣  Inserting sample Liquor Barn receipts...")
        insert_sample_liquor_barn_receipts(conn)
        
        print("\n6️⃣  Current staging status...")
        show_staging_status(conn)
        
        print()
        print("[OK] STAGING SYSTEM READY")
        print("=" * 23)
        print("📝 Next Steps:")
        print("1. Review manual_receipt_entry_template.json")
        print("2. Use staging table for manual receipt entry")
        print("3. Validate entries before promotion")
        print("4. Promote validated receipts to main system")
        print()
        print("💡 Manual Entry Process:")
        print("INSERT INTO staging_accountant_receipts")
        print("(receipt_date, vendor_name, gross_amount, gst_amount, description)")
        print("VALUES ('2012-XX-XX', 'Vendor Name', XX.XX, X.XX, 'Description');")
        print()
        print("🎯 Current Status: 4 Liquor Barn receipts staged ($442.44 total)")
        print("   Ready for validation and promotion to main receipts table")
        
    except Exception as e:
        print(f"[FAIL] Error setting up staging system: {e}")
        return 1
    
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())