#!/usr/bin/env python3
"""
Migration: Add split receipt management schema
Includes: receipt_splits, receipt_banking_links, receipt_cashbox_links, audit_log
Safe: Checks for existing tables, idempotent, no data loss
"""

import psycopg2
import sys
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def log_migration(conn, migration_name, status, details=""):
    """Log migration execution for audit trail."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO migration_log (migration_name, status, details, executed_at)
        VALUES (%s, %s, %s, NOW())
    """, (migration_name, status, details))
    conn.commit()
    cur.close()

def table_exists(conn, table_name):
    """Check if table exists."""
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
    """, (table_name,))
    exists = cur.fetchone()[0]
    cur.close()
    return exists

def run_migration():
    """Execute the migration."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        print("🔄 Starting split receipt schema migration...")
        
        # Create migration_log table if needed
        if not table_exists(conn, 'migration_log'):
            print("  → Creating migration_log table...")
            cur.execute("""
                CREATE TABLE migration_log (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    details TEXT,
                    executed_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
        
        # 1. Add split_status column to receipts if missing
        if not table_exists(conn, 'receipts'):
            print("❌ receipts table does not exist! Exiting.")
            return False
        
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'receipts' AND column_name = 'split_status'
        """)
        if not cur.fetchone():
            print("  → Adding split_status to receipts...")
            cur.execute("""
                ALTER TABLE receipts 
                ADD COLUMN split_status VARCHAR(50) DEFAULT 'single'
                CHECK (split_status IN ('single', 'split_pending', 'split_reconciled'))
            """)
            conn.commit()
        
        # 2. Create receipt_splits table
        if not table_exists(conn, 'receipt_splits'):
            print("  → Creating receipt_splits table...")
            cur.execute("""
                CREATE TABLE receipt_splits (
                    split_id SERIAL PRIMARY KEY,
                    receipt_id INTEGER NOT NULL REFERENCES receipts(receipt_id) ON DELETE CASCADE,
                    split_order INTEGER NOT NULL,
                    gl_code VARCHAR(50) NOT NULL REFERENCES gl_accounts(gl_code),
                    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
                    payment_method VARCHAR(50) NOT NULL 
                        CHECK (payment_method IN ('debit_card', 'credit_card', 'cash', 'check', 'bank_transfer', 'other')),
                    notes TEXT,
                    created_by INTEGER REFERENCES employees(employee_id),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(receipt_id, split_order)
                )
            """)
            cur.execute("CREATE INDEX idx_receipt_splits_receipt_id ON receipt_splits(receipt_id)")
            conn.commit()
        
        # 3. Create receipt_banking_links table
        if not table_exists(conn, 'receipt_banking_links'):
            print("  → Creating receipt_banking_links table...")
            cur.execute("""
                CREATE TABLE receipt_banking_links (
                    link_id SERIAL PRIMARY KEY,
                    receipt_id INTEGER NOT NULL REFERENCES receipts(receipt_id) ON DELETE CASCADE,
                    transaction_id INTEGER NOT NULL REFERENCES banking_transactions(transaction_id),
                    linked_amount NUMERIC(12, 2) NOT NULL CHECK (linked_amount > 0),
                    link_status VARCHAR(50) DEFAULT 'matched' 
                        CHECK (link_status IN ('matched', 'partial', 'unmatched')),
                    linked_by INTEGER REFERENCES employees(employee_id),
                    linked_at TIMESTAMP DEFAULT NOW(),
                    notes TEXT,
                    UNIQUE(receipt_id, transaction_id)
                )
            """)
            cur.execute("CREATE INDEX idx_receipt_banking_links_receipt_id ON receipt_banking_links(receipt_id)")
            cur.execute("CREATE INDEX idx_receipt_banking_links_transaction_id ON receipt_banking_links(transaction_id)")
            conn.commit()
        
        # 4. Create receipt_cashbox_links table
        if not table_exists(conn, 'receipt_cashbox_links'):
            print("  → Creating receipt_cashbox_links table...")
            cur.execute("""
                CREATE TABLE receipt_cashbox_links (
                    link_id SERIAL PRIMARY KEY,
                    receipt_id INTEGER NOT NULL REFERENCES receipts(receipt_id) ON DELETE CASCADE,
                    cashbox_amount NUMERIC(12, 2) NOT NULL CHECK (cashbox_amount > 0),
                    float_reimbursement_type VARCHAR(50) DEFAULT 'other'
                        CHECK (float_reimbursement_type IN ('float_out', 'reimbursed', 'cash_received', 'other')),
                    driver_id INTEGER REFERENCES employees(employee_id),
                    driver_notes TEXT,
                    confirmed_by INTEGER REFERENCES employees(employee_id),
                    confirmed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(receipt_id)
                )
            """)
            cur.execute("CREATE INDEX idx_receipt_cashbox_links_receipt_id ON receipt_cashbox_links(receipt_id)")
            cur.execute("CREATE INDEX idx_receipt_cashbox_links_driver_id ON receipt_cashbox_links(driver_id)")
            conn.commit()
        
        # 5. Create audit_log table
        if not table_exists(conn, 'audit_log'):
            print("  → Creating audit_log table...")
            cur.execute("""
                CREATE TABLE audit_log (
                    audit_id BIGSERIAL PRIMARY KEY,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id INTEGER NOT NULL,
                    field_changed VARCHAR(100),
                    old_value TEXT,
                    new_value TEXT,
                    changed_by INTEGER REFERENCES employees(employee_id),
                    changed_at TIMESTAMP DEFAULT NOW(),
                    reason TEXT,
                    ip_address INET,
                    CONSTRAINT audit_entity CHECK (entity_type IN ('receipt', 'split', 'banking_link', 'cashbox_link'))
                )
            """)
            cur.execute("CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id)")
            cur.execute("CREATE INDEX idx_audit_log_changed_at ON audit_log(changed_at)")
            conn.commit()
        
        # 6. Create stored procedure for split amount validation
        print("  → Creating split amount validation function...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION validate_receipt_split_amounts(p_receipt_id INTEGER)
            RETURNS TABLE (
                is_valid BOOLEAN,
                split_total NUMERIC,
                receipt_total NUMERIC,
                variance NUMERIC
            ) AS $$
            DECLARE
                v_split_total NUMERIC;
                v_receipt_total NUMERIC;
            BEGIN
                SELECT COALESCE(SUM(amount), 0) INTO v_split_total
                FROM receipt_splits WHERE receipt_id = p_receipt_id;
                
                SELECT gross_amount INTO v_receipt_total
                FROM receipts WHERE receipt_id = p_receipt_id;
                
                RETURN QUERY SELECT 
                    (ABS(v_split_total - v_receipt_total) < 0.01)::BOOLEAN,
                    v_split_total,
                    v_receipt_total,
                    ABS(v_split_total - v_receipt_total);
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        
        # 7. Create stored procedure for banking link validation
        print("  → Creating banking link validation function...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION validate_receipt_banking_amounts(p_receipt_id INTEGER)
            RETURNS TABLE (
                is_valid BOOLEAN,
                banking_total NUMERIC,
                receipt_total NUMERIC,
                variance NUMERIC
            ) AS $$
            DECLARE
                v_banking_total NUMERIC;
                v_receipt_total NUMERIC;
            BEGIN
                SELECT COALESCE(SUM(linked_amount), 0) INTO v_banking_total
                FROM receipt_banking_links WHERE receipt_id = p_receipt_id;
                
                SELECT gross_amount INTO v_receipt_total
                FROM receipts WHERE receipt_id = p_receipt_id;
                
                RETURN QUERY SELECT 
                    (ABS(v_banking_total - v_receipt_total) < 0.01)::BOOLEAN,
                    v_banking_total,
                    v_receipt_total,
                    ABS(v_banking_total - v_receipt_total);
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        
        print("✅ Migration completed successfully!")
        print("\n📋 Summary:")
        print("   • receipt_splits - stores GL allocations per split")
        print("   • receipt_banking_links - links receipts to bank transactions")
        print("   • receipt_cashbox_links - tracks cash, floats, reimbursements")
        print("   • audit_log - immutable change tracking")
        print("   • Validation functions for amount reconciliation")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
