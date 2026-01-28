#!/usr/bin/env python3
"""
COMPREHENSIVE MIGRATION: Add All Missing Components to Arrow Limousine System

Features Added:
- CVIP Inspection Tracking (Alberta compliance)
- Vehicle Lifecycle Management (purchase, sale, writeoff, repossession)
- Driver Internal Notes (hidden from drivers)
- Pre-Trip Inspection System
- Scheduled Maintenance Alerts
- CRA Event Tracking
- Driver Mobile App Support Tables

Run: python l:\limo\migrations\add_all_missing_components.py
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

def table_exists(cur, table_name):
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = %s
    """, (table_name,))
    return cur.fetchone()[0] > 0

def column_exists(cur, table_name, column_name):
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_name = %s AND column_name = %s
    """, (table_name, column_name))
    return cur.fetchone()[0] > 0

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("ARROW LIMOUSINE - COMPREHENSIVE SYSTEM UPGRADE")
    print("="*80)
    print(f"Migration Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    try:
        # ========================================================================
        # SECTION 1: CVIP INSPECTION TRACKING
        # ========================================================================
        print("\n[1/9] CVIP INSPECTION TRACKING")
        print("-" * 80)
        
        # Add CVIP columns to vehicles table
        cvip_columns = [
            ("cvip_expiry_date", "DATE"),
            ("cvip_inspection_number", "VARCHAR(50)"),
            ("last_cvip_date", "DATE"),
            ("next_cvip_due", "DATE"),
            ("cvip_compliance_status", "VARCHAR(50)")
        ]
        
        for col_name, col_type in cvip_columns:
            if not column_exists(cur, 'vehicles', col_name):
                cur.execute(f"ALTER TABLE vehicles ADD COLUMN {col_name} {col_type}")
                print(f"  ✓ Added vehicles.{col_name}")
        
        conn.commit()
        
        # CVIP Inspections table
        if not table_exists(cur, 'cvip_inspections'):
            cur.execute("""
                CREATE TABLE cvip_inspections (
                    inspection_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    inspection_date DATE NOT NULL,
                    inspection_number VARCHAR(50) UNIQUE,
                    inspection_location VARCHAR(200),
                    inspector_name VARCHAR(100),
                    inspection_station VARCHAR(200),
                    
                    passed BOOLEAN,
                    inspection_result VARCHAR(50),
                    defect_count INTEGER DEFAULT 0,
                    critical_defects INTEGER DEFAULT 0,
                    
                    valid_until DATE,
                    is_current BOOLEAN DEFAULT TRUE,
                    renewal_due_date DATE,
                    days_remaining INTEGER,
                    
                    defects_json TEXT,
                    cost NUMERIC(10,2),
                    receipt_id INTEGER,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created cvip_inspections table")
            conn.commit()
        
        # CVIP Defects table
        if not table_exists(cur, 'cvip_defects'):
            cur.execute("""
                CREATE TABLE cvip_defects (
                    defect_id SERIAL PRIMARY KEY,
                    inspection_id INTEGER REFERENCES cvip_inspections(inspection_id),
                    defect_code VARCHAR(20),
                    defect_description TEXT,
                    severity VARCHAR(20),
                    remediation_required BOOLEAN,
                    remediation_deadline DATE,
                    remediated_date DATE,
                    remediation_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created cvip_defects table")
            conn.commit()
        
        # CVIP Compliance Alerts
        if not table_exists(cur, 'cvip_compliance_alerts'):
            cur.execute("""
                CREATE TABLE cvip_compliance_alerts (
                    alert_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    alert_type VARCHAR(50),
                    alert_date DATE,
                    due_date DATE,
                    days_until_due INTEGER,
                    severity VARCHAR(20),
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_date DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created cvip_compliance_alerts table")
            conn.commit()
        
        # ========================================================================
        # SECTION 2: VEHICLE LIFECYCLE MANAGEMENT
        # ========================================================================
        print("\n[2/9] VEHICLE LIFECYCLE MANAGEMENT")
        print("-" * 80)
        
        # Add lifecycle columns to vehicles
        lifecycle_columns = [
            ("purchase_date", "DATE"),
            ("purchase_price", "NUMERIC(12,2)"),
            ("purchase_vendor", "VARCHAR(200)"),
            ("finance_partner", "VARCHAR(200)"),
            ("financing_amount", "NUMERIC(12,2)"),
            ("monthly_payment", "NUMERIC(10,2)"),
            ("sale_date", "DATE"),
            ("sale_price", "NUMERIC(12,2)"),
            ("writeoff_date", "DATE"),
            ("writeoff_reason", "VARCHAR(200)"),
            ("repossession_date", "DATE"),
            ("lifecycle_status", "VARCHAR(50)")
        ]
        
        for col_name, col_type in lifecycle_columns:
            if not column_exists(cur, 'vehicles', col_name):
                cur.execute(f"ALTER TABLE vehicles ADD COLUMN {col_name} {col_type}")
                print(f"  ✓ Added vehicles.{col_name}")
        
        conn.commit()
        
        # Vehicle Purchases
        if not table_exists(cur, 'vehicle_purchases'):
            cur.execute("""
                CREATE TABLE vehicle_purchases (
                    purchase_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    purchase_date DATE NOT NULL,
                    vendor_name VARCHAR(200),
                    purchase_price NUMERIC(12,2),
                    down_payment NUMERIC(12,2),
                    financing_partner VARCHAR(200),
                    financing_amount NUMERIC(12,2),
                    financing_term_months INTEGER,
                    interest_rate NUMERIC(5,4),
                    monthly_payment NUMERIC(10,2),
                    invoice_number VARCHAR(50),
                    po_number VARCHAR(50),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created vehicle_purchases table")
            conn.commit()
        
        # Vehicle Sales
        if not table_exists(cur, 'vehicle_sales'):
            cur.execute("""
                CREATE TABLE vehicle_sales (
                    sale_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    sale_date DATE NOT NULL,
                    buyer_name VARCHAR(200),
                    sale_price NUMERIC(12,2),
                    sale_status VARCHAR(50),
                    auction_company VARCHAR(200),
                    auction_date DATE,
                    lot_number VARCHAR(50),
                    hammer_price NUMERIC(12,2),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created vehicle_sales table")
            conn.commit()
        
        # Vehicle Writeoffs
        if not table_exists(cur, 'vehicle_writeoffs'):
            cur.execute("""
                CREATE TABLE vehicle_writeoffs (
                    writeoff_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    writeoff_date DATE NOT NULL,
                    writeoff_reason VARCHAR(100),
                    insurance_claim_number VARCHAR(50),
                    insurance_company VARCHAR(200),
                    claim_amount NUMERIC(12,2),
                    claim_status VARCHAR(50),
                    book_value NUMERIC(12,2),
                    salvage_value NUMERIC(12,2),
                    loss_amount NUMERIC(12,2),
                    deduction_claimed BOOLEAN,
                    deduction_amount NUMERIC(12,2),
                    cra_class VARCHAR(20),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created vehicle_writeoffs table")
            conn.commit()
        
        # Vehicle Repossessions
        if not table_exists(cur, 'vehicle_repossessions'):
            cur.execute("""
                CREATE TABLE vehicle_repossessions (
                    repossession_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    repossession_date DATE NOT NULL,
                    lender_name VARCHAR(200),
                    reason VARCHAR(200),
                    recovery_location VARCHAR(200),
                    recovery_cost NUMERIC(10,2),
                    sold_to_lender BOOLEAN,
                    auction_date DATE,
                    final_amount_owed NUMERIC(12,2),
                    reportable_event BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created vehicle_repossessions table")
            conn.commit()
        
        # CRA Vehicle Events
        if not table_exists(cur, 'cra_vehicle_events'):
            cur.execute("""
                CREATE TABLE cra_vehicle_events (
                    event_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    event_type VARCHAR(50),
                    event_date DATE NOT NULL,
                    police_report_number VARCHAR(50),
                    insurance_claim_number VARCHAR(50),
                    reported_to_cra BOOLEAN DEFAULT FALSE,
                    report_date DATE,
                    cra_reference_number VARCHAR(50),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created cra_vehicle_events table")
            conn.commit()
        
        # ========================================================================
        # SECTION 3: DRIVER INTERNAL NOTES
        # ========================================================================
        print("\n[3/9] DRIVER INTERNAL NOTES (MANAGER ONLY)")
        print("-" * 80)
        
        if not table_exists(cur, 'driver_internal_notes'):
            cur.execute("""
                CREATE TABLE driver_internal_notes (
                    note_id SERIAL PRIMARY KEY,
                    driver_id INTEGER REFERENCES employees(employee_id),
                    note_date DATE NOT NULL,
                    note_type VARCHAR(50),
                    created_by VARCHAR(100),
                    visibility VARCHAR(50),
                    title VARCHAR(200),
                    content TEXT NOT NULL,
                    is_warning BOOLEAN DEFAULT FALSE,
                    warning_level VARCHAR(20),
                    follow_up_required BOOLEAN DEFAULT FALSE,
                    follow_up_date DATE,
                    attached_document_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created driver_internal_notes table")
            conn.commit()
        
        if not table_exists(cur, 'driver_disciplinary_actions'):
            cur.execute("""
                CREATE TABLE driver_disciplinary_actions (
                    action_id SERIAL PRIMARY KEY,
                    driver_id INTEGER REFERENCES employees(employee_id),
                    action_date DATE NOT NULL,
                    action_type VARCHAR(50),
                    reason TEXT NOT NULL,
                    duration_days INTEGER,
                    issued_by VARCHAR(100),
                    acknowledged_date DATE,
                    acknowledged_by VARCHAR(100),
                    appeal_filed BOOLEAN DEFAULT FALSE,
                    appeal_notes TEXT,
                    appeal_resolved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created driver_disciplinary_actions table")
            conn.commit()
        
        if not table_exists(cur, 'driver_performance_private'):
            cur.execute("""
                CREATE TABLE driver_performance_private (
                    metric_id SERIAL PRIMARY KEY,
                    driver_id INTEGER REFERENCES employees(employee_id),
                    measurement_period DATE,
                    accident_count INTEGER DEFAULT 0,
                    incident_count INTEGER DEFAULT 0,
                    citation_count INTEGER DEFAULT 0,
                    hos_violation_count INTEGER DEFAULT 0,
                    customer_complaint_count INTEGER DEFAULT 0,
                    on_time_delivery_rate NUMERIC(5,2),
                    vehicle_condition_rating NUMERIC(3,2),
                    overall_rating NUMERIC(3,2),
                    manager_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created driver_performance_private table")
            conn.commit()
        
        # ========================================================================
        # SECTION 4: PRE-TRIP INSPECTION SYSTEM
        # ========================================================================
        print("\n[4/9] PRE-TRIP INSPECTION SYSTEM")
        print("-" * 80)
        
        if not table_exists(cur, 'pre_inspection_templates'):
            cur.execute("""
                CREATE TABLE pre_inspection_templates (
                    template_id SERIAL PRIMARY KEY,
                    template_name VARCHAR(200),
                    vehicle_type VARCHAR(100),
                    is_active BOOLEAN DEFAULT TRUE,
                    checklist_json JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created pre_inspection_templates table")
            conn.commit()
        
        if not table_exists(cur, 'vehicle_pre_inspections'):
            cur.execute("""
                CREATE TABLE vehicle_pre_inspections (
                    inspection_id SERIAL PRIMARY KEY,
                    charter_id INTEGER REFERENCES charters(charter_id),
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    driver_id INTEGER REFERENCES employees(employee_id),
                    inspection_date DATE NOT NULL,
                    inspection_time TIME,
                    inspection_type VARCHAR(50),
                    completed BOOLEAN DEFAULT FALSE,
                    completed_time TIMESTAMP,
                    pass_fail VARCHAR(20),
                    issues_found INTEGER DEFAULT 0,
                    critical_issues INTEGER DEFAULT 0,
                    issues_json JSONB,
                    cleared_to_operate BOOLEAN DEFAULT FALSE,
                    clearance_time TIMESTAMP,
                    clearance_notes TEXT,
                    previous_inspection_id INTEGER REFERENCES vehicle_pre_inspections(inspection_id),
                    carryover_issues TEXT,
                    notes TEXT,
                    signature VARCHAR(200),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created vehicle_pre_inspections table")
            conn.commit()
        
        if not table_exists(cur, 'pre_inspection_issues'):
            cur.execute("""
                CREATE TABLE pre_inspection_issues (
                    issue_id SERIAL PRIMARY KEY,
                    inspection_id INTEGER REFERENCES vehicle_pre_inspections(inspection_id),
                    category VARCHAR(100),
                    issue_description TEXT NOT NULL,
                    severity VARCHAR(20),
                    photo_url TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_date DATE,
                    resolved_by VARCHAR(100),
                    resolution_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created pre_inspection_issues table")
            conn.commit()
        
        # ========================================================================
        # SECTION 5: SCHEDULED MAINTENANCE ENHANCEMENTS
        # ========================================================================
        print("\n[5/9] SCHEDULED MAINTENANCE AUTOMATION")
        print("-" * 80)
        
        # Add columns to maintenance_records
        maint_columns = [
            ("scheduled_date", "DATE"),
            ("maintenance_status", "VARCHAR(50)"),
            ("alert_sent", "BOOLEAN DEFAULT FALSE"),
            ("alert_sent_date", "DATE"),
            ("alert_days_before", "INTEGER DEFAULT 14"),
            ("next_service_date", "DATE"),
            ("recurring_interval_days", "INTEGER"),
            ("recurring_interval_km", "INTEGER"),
            ("required_by_regulation", "BOOLEAN"),
            ("compliance_category", "VARCHAR(50)"),
            ("estimated_cost", "NUMERIC(10,2)"),
            ("actual_cost", "NUMERIC(10,2)"),
            ("scheduled_with_vendor", "VARCHAR(200)"),
            ("vendor_confirmed", "BOOLEAN DEFAULT FALSE"),
            ("service_order_number", "VARCHAR(50)")
        ]
        
        for col_name, col_type in maint_columns:
            if not column_exists(cur, 'maintenance_records', col_name):
                cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col_name} {col_type}")
                print(f"  ✓ Added maintenance_records.{col_name}")
        
        conn.commit()
        
        if not table_exists(cur, 'maintenance_schedules_auto'):
            cur.execute("""
                CREATE TABLE maintenance_schedules_auto (
                    schedule_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    maintenance_type VARCHAR(100),
                    due_date DATE,
                    due_mileage INTEGER,
                    days_until_due INTEGER,
                    km_until_due INTEGER,
                    status VARCHAR(50),
                    last_completed_date DATE,
                    next_due_date DATE,
                    alert_threshold_days INTEGER DEFAULT 14,
                    alert_threshold_km INTEGER DEFAULT 500,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created maintenance_schedules_auto table")
            conn.commit()
        
        if not table_exists(cur, 'maintenance_alerts'):
            cur.execute("""
                CREATE TABLE maintenance_alerts (
                    alert_id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
                    maintenance_type VARCHAR(100),
                    alert_date DATE,
                    alert_level VARCHAR(20),
                    due_date DATE,
                    days_overdue INTEGER,
                    recipient_email VARCHAR(100),
                    sent_date TIMESTAMP,
                    acknowledged BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created maintenance_alerts table")
            conn.commit()
        
        # ========================================================================
        # SECTION 6: DRIVER MOBILE APP SUPPORT
        # ========================================================================
        print("\n[6/9] DRIVER MOBILE APP BACKEND")
        print("-" * 80)
        
        if not table_exists(cur, 'driver_app_sessions'):
            cur.execute("""
                CREATE TABLE driver_app_sessions (
                    session_id SERIAL PRIMARY KEY,
                    driver_id INTEGER REFERENCES employees(employee_id),
                    device_id VARCHAR(100),
                    device_type VARCHAR(50),
                    device_name VARCHAR(100),
                    app_version VARCHAR(20),
                    os_version VARCHAR(20),
                    last_login TIMESTAMP,
                    login_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    push_token VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created driver_app_sessions table")
            conn.commit()
        
        if not table_exists(cur, 'driver_location_history'):
            cur.execute("""
                CREATE TABLE driver_location_history (
                    location_id SERIAL PRIMARY KEY,
                    driver_id INTEGER REFERENCES employees(employee_id),
                    charter_id INTEGER REFERENCES charters(charter_id),
                    latitude NUMERIC(10,8),
                    longitude NUMERIC(11,8),
                    accuracy NUMERIC(6,2),
                    altitude NUMERIC(8,2),
                    speed NUMERIC(6,2),
                    heading NUMERIC(5,2),
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created driver_location_history table")
            conn.commit()
        
        if not table_exists(cur, 'driver_app_actions'):
            cur.execute("""
                CREATE TABLE driver_app_actions (
                    action_id SERIAL PRIMARY KEY,
                    driver_id INTEGER REFERENCES employees(employee_id),
                    charter_id INTEGER REFERENCES charters(charter_id),
                    action_type VARCHAR(50),
                    action_timestamp TIMESTAMP NOT NULL,
                    action_data JSONB,
                    synced BOOLEAN DEFAULT FALSE,
                    synced_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created driver_app_actions table")
            conn.commit()
        
        # ========================================================================
        # SECTION 7: CHARTER TIME UPDATES
        # ========================================================================
        print("\n[7/9] CHARTER TIME TRACKING")
        print("-" * 80)
        
        charter_time_columns = [
            ("actual_pickup_time", "TIMESTAMP"),
            ("actual_dropoff_time", "TIMESTAMP"),
            ("eta_pickup", "TIMESTAMP"),
            ("eta_dropoff", "TIMESTAMP"),
            ("driver_reported_delay", "BOOLEAN DEFAULT FALSE"),
            ("delay_reason", "TEXT"),
            ("delay_minutes", "INTEGER"),
            ("time_updated_by_driver", "BOOLEAN DEFAULT FALSE"),
            ("last_time_update", "TIMESTAMP")
        ]
        
        for col_name, col_type in charter_time_columns:
            if not column_exists(cur, 'charters', col_name):
                cur.execute(f"ALTER TABLE charters ADD COLUMN {col_name} {col_type}")
                print(f"  ✓ Added charters.{col_name}")
        
        conn.commit()
        
        if not table_exists(cur, 'charter_time_updates'):
            cur.execute("""
                CREATE TABLE charter_time_updates (
                    update_id SERIAL PRIMARY KEY,
                    charter_id INTEGER REFERENCES charters(charter_id),
                    driver_id INTEGER REFERENCES employees(employee_id),
                    update_type VARCHAR(50),
                    old_time TIMESTAMP,
                    new_time TIMESTAMP,
                    reason TEXT,
                    location_lat NUMERIC(10,8),
                    location_lon NUMERIC(11,8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created charter_time_updates table")
            conn.commit()
        
        # ========================================================================
        # SECTION 8: DIGITAL RECEIPTS
        # ========================================================================
        print("\n[8/9] DIGITAL RECEIPT DELIVERY")
        print("-" * 80)
        
        if not table_exists(cur, 'receipt_deliveries'):
            cur.execute("""
                CREATE TABLE receipt_deliveries (
                    delivery_id SERIAL PRIMARY KEY,
                    charter_id INTEGER REFERENCES charters(charter_id),
                    client_email VARCHAR(200),
                    receipt_type VARCHAR(50),
                    delivery_method VARCHAR(50),
                    pdf_url TEXT,
                    sent_date TIMESTAMP,
                    opened_date TIMESTAMP,
                    downloaded_date TIMESTAMP,
                    sent_by VARCHAR(100),
                    status VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("  ✓ Created receipt_deliveries table")
            conn.commit()
        
        # ========================================================================
        # SECTION 9: REPORTING VIEWS
        # ========================================================================
        print("\n[9/9] CREATING REPORTING VIEWS")
        print("-" * 80)
        
        # CVIP Compliance View
        cur.execute("""
            CREATE OR REPLACE VIEW v_cvip_compliance AS
            SELECT 
                v.vehicle_id,
                v.vehicle_number,
                v.make,
                v.model,
                v.year,
                v.license_plate,
                v.cvip_expiry_date,
                v.cvip_inspection_number,
                v.cvip_compliance_status,
                CASE 
                    WHEN v.cvip_expiry_date IS NULL THEN 'NO_RECORD'
                    WHEN v.cvip_expiry_date < CURRENT_DATE THEN 'EXPIRED'
                    WHEN v.cvip_expiry_date < CURRENT_DATE + INTERVAL '30 days' THEN 'EXPIRING_SOON'
                    ELSE 'CURRENT'
                END as alert_status,
                v.cvip_expiry_date - CURRENT_DATE as days_remaining
            FROM vehicles v
            WHERE v.is_active = TRUE
            ORDER BY v.cvip_expiry_date NULLS FIRST
        """)
        print("  ✓ Created v_cvip_compliance view")
        
        # Maintenance Due View
        cur.execute("""
            CREATE OR REPLACE VIEW v_maintenance_due AS
            SELECT 
                v.vehicle_id,
                v.vehicle_number,
                v.make,
                v.model,
                ms.maintenance_type,
                ms.due_date,
                ms.due_mileage,
                v.odometer as current_mileage,
                ms.days_until_due,
                ms.km_until_due,
                ms.status,
                CASE 
                    WHEN ms.status = 'OVERDUE' THEN 'CRITICAL'
                    WHEN ms.days_until_due < 7 THEN 'WARNING'
                    WHEN ms.days_until_due < 30 THEN 'INFO'
                    ELSE 'OK'
                END as alert_level
            FROM vehicles v
            LEFT JOIN maintenance_schedules_auto ms ON v.vehicle_id = ms.vehicle_id
            WHERE v.is_active = TRUE
            AND (ms.status = 'OVERDUE' OR ms.days_until_due < 30)
            ORDER BY ms.days_until_due NULLS FIRST
        """)
        print("  ✓ Created v_maintenance_due view")
        
        # Driver Performance Summary View
        cur.execute("""
            CREATE OR REPLACE VIEW v_driver_performance_summary AS
            SELECT 
                e.employee_id,
                e.full_name,
                e.employee_number,
                e.position,
                COUNT(DISTINCT c.charter_id) as total_charters,
                COUNT(DISTINCT i.incident_id) as total_incidents,
                COUNT(DISTINCT din.note_id) as warning_count,
                AVG(dpp.overall_rating) as avg_rating,
                MAX(dpp.measurement_period) as last_review_date
            FROM employees e
            LEFT JOIN charters c ON e.employee_id = c.assigned_driver_id
            LEFT JOIN incidents i ON e.employee_id = i.involved_employee::INTEGER
            LEFT JOIN driver_internal_notes din ON e.employee_id = din.driver_id AND din.is_warning = TRUE
            LEFT JOIN driver_performance_private dpp ON e.employee_id = dpp.driver_id
            WHERE e.is_chauffeur = TRUE
            GROUP BY e.employee_id, e.full_name, e.employee_number, e.position
            ORDER BY e.full_name
        """)
        print("  ✓ Created v_driver_performance_summary view")
        
        conn.commit()
        
        # ========================================================================
        # FINAL SUMMARY
        # ========================================================================
        print("\n" + "="*80)
        print("✅ MIGRATION COMPLETE - ALL COMPONENTS ADDED")
        print("="*80)
        
        # Count tables created
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN (
                'cvip_inspections', 'cvip_defects', 'cvip_compliance_alerts',
                'vehicle_purchases', 'vehicle_sales', 'vehicle_writeoffs', 'vehicle_repossessions',
                'cra_vehicle_events', 'driver_internal_notes', 'driver_disciplinary_actions',
                'driver_performance_private', 'pre_inspection_templates', 'vehicle_pre_inspections',
                'pre_inspection_issues', 'maintenance_schedules_auto', 'maintenance_alerts',
                'driver_app_sessions', 'driver_location_history', 'driver_app_actions',
                'charter_time_updates', 'receipt_deliveries'
            )
        """)
        table_count = cur.fetchone()[0]
        
        print(f"\n📊 STATISTICS:")
        print(f"   - New tables created: {table_count}")
        print(f"   - Views created: 3")
        print(f"   - Columns added to existing tables: ~50+")
        
        print(f"\n🎯 FEATURES NOW AVAILABLE:")
        print(f"   ✅ CVIP Inspection Tracking (Alberta compliance)")
        print(f"   ✅ Vehicle Lifecycle Management (purchase → disposal)")
        print(f"   ✅ Driver Internal Notes (hidden from drivers)")
        print(f"   ✅ Pre-Trip Inspection System")
        print(f"   ✅ Scheduled Maintenance Automation")
        print(f"   ✅ CRA Event Tracking")
        print(f"   ✅ Driver Mobile App Backend")
        print(f"   ✅ Charter Time Updates")
        print(f"   ✅ Digital Receipt Delivery")
        
        print(f"\n📝 NEXT STEPS:")
        print(f"   1. Populate CVIP inspection data from historical records")
        print(f"   2. Import vehicle purchase/sale history")
        print(f"   3. Create pre-inspection checklist templates")
        print(f"   4. Configure maintenance alert thresholds")
        print(f"   5. Build driver mobile app UI")
        print(f"   6. Create dashboard widgets for new features")
        
        print("\n" + "="*80)
        
        cur.close()
        conn.close()
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        cur.close()
        conn.close()
        return 1

if __name__ == '__main__':
    exit(main())
