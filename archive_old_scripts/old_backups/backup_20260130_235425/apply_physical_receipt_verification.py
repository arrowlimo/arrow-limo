#!/usr/bin/env python3
"""
Apply physical receipt verification schema.

Matches receipts to banking transactions = they have been physically verified.
"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def apply_migration():
    """Apply the physical verification schema migration."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        print("📋 PHYSICAL RECEIPT VERIFICATION SCHEMA")
        print("=" * 70)
        
        # Step 1: Add columns
        print("\n1️⃣ Adding verification columns...")
        cur.execute("""
            ALTER TABLE receipts
            ADD COLUMN IF NOT EXISTS is_paper_verified BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS paper_verification_date TIMESTAMP DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS verified_by_user VARCHAR(255) DEFAULT NULL;
        """)
        print("   ✅ Columns added")
        
        # Step 2: Auto-populate based on banking links
        print("\n2️⃣ Auto-verifying receipts linked to banking...")
        cur.execute("""
            UPDATE receipts
            SET 
              is_paper_verified = TRUE,
              paper_verification_date = COALESCE(paper_verification_date, created_at)
            WHERE banking_transaction_id IS NOT NULL 
              AND is_paper_verified = FALSE
            RETURNING receipt_id;
        """)
        updated = cur.rowcount
        print(f"   ✅ Auto-verified {updated:,} receipts (matched to banking)")
        
        # Step 3: Create index
        print("\n3️⃣ Creating verification index...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_receipts_paper_verified 
            ON receipts(is_paper_verified, paper_verification_date);
        """)
        print("   ✅ Index created")
        
        # Step 4: Create views
        print("\n4️⃣ Creating verification views...")
        cur.execute("DROP VIEW IF EXISTS receipt_verification_summary;")
        cur.execute("""
            CREATE VIEW receipt_verification_summary AS
            SELECT 
              COUNT(*) as total_receipts,
              SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) as physically_verified_count,
              SUM(CASE WHEN NOT is_paper_verified THEN 1 ELSE 0 END) as unverified_count,
              ROUND(100.0 * SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) / 
                    NULLIF(COUNT(*), 0), 1) as verification_percentage
            FROM receipts
            WHERE business_personal != 'personal' 
              AND is_personal_purchase = FALSE;
        """)
        print("   ✅ receipt_verification_summary view created")
        
        cur.execute("DROP VIEW IF EXISTS verified_receipts_detail;")
        cur.execute("""
            CREATE VIEW verified_receipts_detail AS
            SELECT 
              r.receipt_id,
              r.receipt_date,
              r.vendor_name,
              r.gross_amount,
              r.category,
              r.is_paper_verified,
              r.paper_verification_date,
              bt.transaction_id as banking_id,
              bt.transaction_date as banking_date,
              bt.description as banking_description
            FROM receipts r
            LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
            WHERE r.is_paper_verified = TRUE
            ORDER BY r.receipt_date DESC;
        """)
        print("   ✅ verified_receipts_detail view created")
        
        # Step 5: Show stats
        print("\n5️⃣ VERIFICATION STATUS")
        print("-" * 70)
        cur.execute("SELECT * FROM receipt_verification_summary;")
        stats = cur.fetchone()
        if stats:
            total, verified, unverified, percentage = stats
            print(f"   📦 Total Business Receipts:     {total:,}")
            print(f"   ✅ Physically Verified:         {verified:,}")
            print(f"   ❌ Unverified:                  {unverified:,}")
            print(f"   📊 Verification Rate:          {percentage:.1f}%")
        
        # Year breakdown
        print("\n6️⃣ VERIFICATION BY YEAR")
        print("-" * 70)
        cur.execute("""
            SELECT 
              EXTRACT(YEAR FROM receipt_date)::INT as year,
              COUNT(*) as total,
              SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) as verified,
              ROUND(100.0 * SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) / 
                    NULLIF(COUNT(*), 0), 1) as percent
            FROM receipts
            WHERE business_personal != 'personal' 
              AND is_personal_purchase = FALSE
            GROUP BY EXTRACT(YEAR FROM receipt_date)
            ORDER BY year;
        """)
        for year, total, verified, percent in cur.fetchall():
            year = int(year) if year else 'NULL'
            print(f"   {year} | {total:6,} receipts | {verified:6,} verified ({percent:5.1f}%)")
        
        # Commit
        conn.commit()
        print("\n✅ SCHEMA MIGRATION COMPLETE")
        print("\nUsage:")
        print("  - SELECT * FROM receipt_verification_summary;")
        print("  - SELECT * FROM verified_receipts_detail WHERE receipt_date > '2025-01-01';")
        print("  - UPDATE receipts SET is_paper_verified=TRUE WHERE receipt_id=123;")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    apply_migration()
