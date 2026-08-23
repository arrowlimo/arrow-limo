#!/usr/bin/env python3
"""
Database Migration Runner
Applies GST remittance payment infrastructure to the database

Usage:
    python run_gst_migration.py --up       # Apply migration
    python run_gst_migration.py --down     # Rollback migration
"""

import os
import sys
from datetime import date, timedelta

# Add modern_backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "modern_backend"))

from app.db import get_connection, return_connection


def apply_gst_migration():
    """Apply GST remittance payment tables"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        print("Creating gst_remittance_payments table...")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS gst_remittance_payments (
                gst_payment_id BIGSERIAL PRIMARY KEY,
                tax_year INT NOT NULL,
                gst_period_month INT NOT NULL,
                gst_amount_collected DECIMAL(12, 2) NOT NULL,
                payment_amount DECIMAL(12, 2) NOT NULL,
                payment_date DATE NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                banking_institution VARCHAR(100),
                reference_number VARCHAR(100),
                banking_transaction_id BIGINT,
                remittance_status VARCHAR(50) NOT NULL DEFAULT 'pending',
                notes TEXT,
                created_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_by VARCHAR(100),
                updated_at TIMESTAMP DEFAULT NOW(),
                retained_until DATE NOT NULL,
                audit_verified BOOLEAN DEFAULT FALSE,
                audit_verified_by VARCHAR(100),
                audit_verified_date TIMESTAMP,
                UNIQUE (tax_year, gst_period_month)
            )
            """
        )

        print("Creating indexes on gst_remittance_payments...")
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gst_payment_year_month 
            ON gst_remittance_payments(tax_year, gst_period_month)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gst_payment_status 
            ON gst_remittance_payments(remittance_status)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gst_payment_date 
            ON gst_remittance_payments(payment_date)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gst_payment_retained_until 
            ON gst_remittance_payments(retained_until)
            """
        )

        print("Creating gst_collected_by_period table...")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS gst_collected_by_period (
                gst_period_id BIGSERIAL PRIMARY KEY,
                tax_year INT NOT NULL,
                gst_period_month INT NOT NULL,
                gst_amount_collected DECIMAL(12, 2) NOT NULL DEFAULT 0,
                receipt_count INT DEFAULT 0,
                last_calculated TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (tax_year, gst_period_month)
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_gst_collected_period 
            ON gst_collected_by_period(tax_year, gst_period_month)
            """
        )

        print("Populating historical GST by period from receipts...")
        cur.execute(
            """
            INSERT INTO gst_collected_by_period 
            (tax_year, gst_period_month, gst_amount_collected, receipt_count, last_calculated)
            SELECT 
                EXTRACT(YEAR FROM receipt_date)::INT,
                EXTRACT(MONTH FROM receipt_date)::INT,
                COALESCE(SUM(gst_amount), 0),
                COUNT(*),
                NOW()
            FROM receipts
            WHERE gst_amount IS NOT NULL AND gst_amount > 0
            GROUP BY EXTRACT(YEAR FROM receipt_date), EXTRACT(MONTH FROM receipt_date)
            ON CONFLICT (tax_year, gst_period_month)
            DO UPDATE SET 
                gst_amount_collected = EXCLUDED.gst_amount_collected,
                receipt_count = EXCLUDED.receipt_count,
                last_calculated = NOW()
            """
        )

        conn.commit()
        print("[OK] GST remittance payment tables created successfully")
        print("[OK] Historical GST periods populated from receipts")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] Error applying GST migration: {e}")
        return False
    finally:
        if conn:
            return_connection(conn)


def rollback_gst_migration():
    """Rollback GST remittance payment tables"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        print("Dropping gst_remittance_payments table...")
        cur.execute("DROP TABLE IF NOT EXISTS gst_remittance_payments CASCADE")

        print("Dropping gst_collected_by_period table...")
        cur.execute("DROP TABLE IF NOT EXISTS gst_collected_by_period CASCADE")

        conn.commit()
        print("[OK] GST remittance payment tables dropped successfully")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] Error rolling back GST migration: {e}")
        return False
    finally:
        if conn:
            return_connection(conn)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_gst_migration.py [--up|--down]")
        sys.exit(1)

    action = sys.argv[1]

    if action == "--up":
        success = apply_gst_migration()
    elif action == "--down":
        success = rollback_gst_migration()
    else:
        print(f"Unknown action: {action}")
        print("Usage: python run_gst_migration.py [--up|--down]")
        sys.exit(1)

    sys.exit(0 if success else 1)
