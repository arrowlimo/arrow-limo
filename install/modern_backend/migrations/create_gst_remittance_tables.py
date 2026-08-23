"""
GST Remittance Payment Table Creation
Supports multi-bank and manual payment entry for GST remittance tracking
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def migrate_up(conn):
    """Create GST remittance payment tables"""
    cur = conn.cursor()
    try:
        # GST Remittance Payment Table
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

        # Create indexes
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

        # GST Collected by Period staging table
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

        conn.commit()
        logger.info("Created GST remittance payment tables")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create GST remittance payment tables: {e}")
        raise


def migrate_down(conn):
    """Drop GST remittance payment tables"""
    cur = conn.cursor()
    try:
        cur.execute("DROP TABLE IF EXISTS gst_remittance_payments CASCADE")
        cur.execute("DROP TABLE IF EXISTS gst_collected_by_period CASCADE")
        conn.commit()
        logger.info("Dropped GST remittance payment tables")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to drop GST remittance payment tables: {e}")
        raise


def calculate_gst_by_period(conn, year: int, month: int) -> float:
    """
    Calculate total GST collected in a given period from receipts
    """
    cur = conn.cursor()
    try:
        # Sum GST from receipts for the given month
        cur.execute(
            """
            SELECT COALESCE(SUM(gst_amount), 0)
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            AND EXTRACT(MONTH FROM receipt_date) = %s
            """,
            (year, month),
        )
        gst_collected = cur.fetchone()[0]
        return float(gst_collected) if gst_collected else 0.0
    finally:
        cur.close()


def populate_historical_gst(conn):
    """
    Calculate and populate historical GST collected by period
    """
    cur = conn.cursor()
    try:
        # Get all distinct year/month combinations from receipts
        cur.execute(
            """
            SELECT DISTINCT 
                EXTRACT(YEAR FROM receipt_date)::INT as year,
                EXTRACT(MONTH FROM receipt_date)::INT as month
            FROM receipts
            WHERE gst_amount IS NOT NULL AND gst_amount > 0
            ORDER BY year DESC, month DESC
            """
        )
        periods = cur.fetchall()

        for year, month in periods:
            gst_amount = calculate_gst_by_period(conn, year, month)
            if gst_amount > 0:
                cur.execute(
                    """
                    INSERT INTO gst_collected_by_period 
                    (tax_year, gst_period_month, gst_amount_collected, receipt_count, last_calculated)
                    SELECT %s, %s, 
                        COALESCE(SUM(gst_amount), 0),
                        COUNT(*),
                        NOW()
                    FROM receipts
                    WHERE EXTRACT(YEAR FROM receipt_date) = %s
                    AND EXTRACT(MONTH FROM receipt_date) = %s
                    ON CONFLICT (tax_year, gst_period_month) 
                    DO UPDATE SET 
                        gst_amount_collected = EXCLUDED.gst_amount_collected,
                        receipt_count = EXCLUDED.receipt_count,
                        last_calculated = NOW()
                    """,
                    (year, month, year, month),
                )

        conn.commit()
        logger.info(f"Populated historical GST for {len(periods)} periods")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to populate historical GST: {e}")
        raise
    finally:
        cur.close()
