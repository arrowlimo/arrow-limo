#!/usr/bin/env python3
"""Apply receipt verification tracking migration."""
import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

def apply_migration():
    print("🔧 Applying Receipt Verification Tracking Migration")
    print("=" * 60)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Add verification columns
        print("\n1. Adding verification columns...")
        cur.execute("""
            ALTER TABLE receipts
            ADD COLUMN IF NOT EXISTS verified_by_edit BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS verified_by_user VARCHAR(255) DEFAULT NULL
        """)
        print("   ✅ Columns added")
        
        # Create index
        print("\n2. Creating index...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_receipts_verified_by_edit 
            ON receipts(verified_by_edit, verified_at)
        """)
        print("   ✅ Index created")
        
        # Add comments
        print("\n3. Adding column comments...")
        cur.execute("""
            COMMENT ON COLUMN receipts.verified_by_edit IS 
            'Auto-set to TRUE when receipt is manually edited, indicating it has been reviewed during audit'
        """)
        cur.execute("""
            COMMENT ON COLUMN receipts.verified_at IS 
            'Timestamp when receipt was last edited/verified'
        """)
        cur.execute("""
            COMMENT ON COLUMN receipts.verified_by_user IS 
            'Username or system that performed the verification'
        """)
        print("   ✅ Comments added")
        
        # Create verification summary view
        print("\n4. Creating verification summary view...")
        cur.execute("""
            DROP VIEW IF EXISTS receipt_verification_audit_summary CASCADE
        """)
        cur.execute("""
            CREATE VIEW receipt_verification_audit_summary AS
            SELECT 
              COUNT(*) as total_receipts,
              SUM(CASE WHEN verified_by_edit THEN 1 ELSE 0 END) as verified_count,
              SUM(CASE WHEN NOT verified_by_edit OR verified_by_edit IS NULL THEN 1 ELSE 0 END) as unverified_count,
              ROUND(100.0 * SUM(CASE WHEN verified_by_edit THEN 1 ELSE 0 END) / 
                    NULLIF(COUNT(*), 0), 1) as verification_percentage,
              MIN(verified_at) as first_verification_date,
              MAX(verified_at) as last_verification_date,
              COUNT(DISTINCT verified_by_user) as unique_verifiers
            FROM receipts
            WHERE business_personal != 'personal' 
              OR business_personal IS NULL
        """)
        print("   ✅ Summary view created")
        
        # Create detailed view
        print("\n5. Creating detailed verification view...")
        cur.execute("""
            DROP VIEW IF EXISTS verified_receipts_audit_detail CASCADE
        """)
        cur.execute("""
            CREATE VIEW verified_receipts_audit_detail AS
            SELECT 
              r.receipt_id,
              r.receipt_date,
              r.vendor_name,
              r.gross_amount,
              r.category,
              r.gl_account_code,
              r.verified_by_edit,
              r.verified_at,
              r.verified_by_user,
              r.created_at,
              CASE 
                WHEN r.verified_by_edit THEN 'Manually Verified'
                WHEN r.banking_transaction_id IS NOT NULL THEN 'Banking Linked'
                ELSE 'Unverified'
              END as verification_status
            FROM receipts r
            WHERE r.business_personal != 'personal' OR r.business_personal IS NULL
            ORDER BY r.verified_at DESC NULLS LAST, r.receipt_date DESC
        """)
        print("   ✅ Detail view created")
        
        conn.commit()
        
        # Show summary
        print("\n6. Current verification status:")
        cur.execute("SELECT * FROM receipt_verification_audit_summary")
        row = cur.fetchone()
        if row:
            total, verified, unverified, pct, first, last, users = row
            print(f"   Total receipts: {total:,}")
            print(f"   Verified: {verified:,} ({pct}%)")
            print(f"   Unverified: {unverified:,}")
            print(f"   Unique verifiers: {users or 0}")
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    apply_migration()
