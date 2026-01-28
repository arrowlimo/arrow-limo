#!/usr/bin/env python3
"""
Add gratuity_type column to charters table for CRA audit compliance.

Creates:
- gratuity_type VARCHAR(20) - 'direct' or 'invoiced'
- gratuity_documentation TEXT - audit notes

Defaults all existing gratuities to 'direct' (non-taxable) based on analysis
showing gratuities were excluded from payroll.
"""
import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("=" * 80)
    print("ADDING GRATUITY AUDIT COLUMNS")
    print("=" * 80)
    
    # 1. Add gratuity_type column
    print("\n1. Adding gratuity_type column...")
    try:
        cur.execute("""
            ALTER TABLE charters 
            ADD COLUMN IF NOT EXISTS gratuity_type VARCHAR(20) 
            CHECK (gratuity_type IN ('direct', 'invoiced', NULL))
        """)
        print("   ✓ gratuity_type column added (values: 'direct', 'invoiced', NULL)")
    except Exception as e:
        print(f"   Note: {e}")
    
    # 2. Add gratuity_documentation column
    print("\n2. Adding gratuity_documentation column...")
    try:
        cur.execute("""
            ALTER TABLE charters 
            ADD COLUMN IF NOT EXISTS gratuity_documentation TEXT
        """)
        print("   ✓ gratuity_documentation column added")
    except Exception as e:
        print(f"   Note: {e}")
    
    # 3. Default all existing gratuities to 'direct' based on payroll analysis
    print("\n3. Setting default gratuity_type to 'direct' for existing records...")
    cur.execute("""
        UPDATE charters 
        SET gratuity_type = 'direct',
            gratuity_documentation = 'Default classification based on payroll analysis showing gratuities excluded from gross pay (direct tips treatment per CRA guidelines). Set ' || NOW()::date
        WHERE driver_gratuity > 0 
        AND gratuity_type IS NULL
    """)
    updated = cur.rowcount
    print(f"   ✓ Updated {updated:,} charters with gratuity_type='direct'")
    
    # 4. Verify changes
    print("\n4. Verification:")
    cur.execute("""
        SELECT 
            gratuity_type,
            COUNT(*) as count,
            SUM(driver_gratuity) as total_gratuity
        FROM charters
        WHERE driver_gratuity > 0
        GROUP BY gratuity_type
        ORDER BY gratuity_type
    """)
    print(f"   {'Type':<15} {'Count':<10} {'Total Gratuity':<20}")
    print("   " + "-" * 45)
    for row in cur.fetchall():
        gtype = row[0] or 'NULL'
        print(f"   {gtype:<15} {row[1]:<10,} ${row[2]:<19,.2f}")
    
    conn.commit()
    print("\n✓ Database schema updated successfully")
    print("\nNext steps:")
    print("  1. Run: python scripts/classify_gratuities_for_audit.py")
    print("  2. Review flagged charters that may need reclassification")
    print("  3. Generate audit defense report")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
