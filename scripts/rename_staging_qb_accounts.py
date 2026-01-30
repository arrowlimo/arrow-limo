#!/usr/bin/env python3
"""
Rename staging_qb_accounts to staging_qb_gl_transactions (accurate naming).
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

conn = get_db_connection()
cur = conn.cursor()

try:
    print("="*80)
    print("RENAMING MISNAMED STAGING TABLE")
    print("="*80)
    
    print("\n⚠️  staging_qb_accounts (262,884 rows) is MISNAMED")
    print("   • Contains transaction-level QuickBooks General Ledger entries")
    print("   • NOT account definitions (that's in qb_accounts_staging)")
    print("   • Identified in November 7, 2025 staging remediation")
    
    print("\n✓ Renaming to: staging_qb_gl_transactions")
    
    cur.execute("""
        ALTER TABLE staging_qb_accounts 
        RENAME TO staging_qb_gl_transactions
    """)
    
    conn.commit()
    
    print("  ✓ Table renamed successfully")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*) FROM staging_qb_gl_transactions
    """)
    
    count = cur.fetchone()[0]
    print(f"\n✓ Verification: staging_qb_gl_transactions has {count:,} rows")
    
    print("\n📋 Next Steps:")
    print("   1. Create cleansing workflow to validate transaction data")
    print("   2. Promote to general_ledger or journal tables")
    print("   3. See STAGING_REMEDIATION_FINAL_REPORT.md for guidelines")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
