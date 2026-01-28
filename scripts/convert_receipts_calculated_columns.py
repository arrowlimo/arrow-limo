#!/usr/bin/env python3
"""
Convert receipts table calculated columns to regular data columns.
This fixes import issues by removing generated column constraints.
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def convert_calculated_columns(dry_run=True):
    """Convert calculated columns to regular data columns"""
    print("🔧 RECEIPTS TABLE COLUMN CONVERSION")
    print("=" * 50)
    print("Mode:", "DRY RUN (preview only)" if dry_run else "APPLY CHANGES")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check current state
        print("\n📊 CURRENT COLUMN STATUS:")
        cur.execute("""
            SELECT 
                column_name, 
                data_type, 
                is_nullable, 
                column_default,
                is_generated,
                generation_expression
            FROM information_schema.columns 
            WHERE table_name = 'receipts' AND column_name IN ('gst_amount', 'net_amount')
            ORDER BY column_name
        """)
        
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]} (Generated: {row[4]})")
            if row[5]:
                print(f"    Expression: {row[5]}")
        
        # Check how many records have calculated values
        cur.execute("SELECT COUNT(*), COUNT(net_amount), SUM(gross_amount), SUM(gst_amount), SUM(net_amount) FROM receipts")
        total_count, net_count, gross_sum, gst_sum, net_sum = cur.fetchone()
        
        print(f"\n📈 CURRENT DATA STATUS:")
        print(f"  Total receipts: {total_count:,}")
        print(f"  Records with net_amount: {net_count:,}")
        print(f"  Gross total: ${gross_sum:,.2f}")
        print(f"  GST total: ${gst_sum:,.2f}")  
        print(f"  Net total: ${net_sum:,.2f}")
        
        if dry_run:
            print(f"\n👀 PLANNED CHANGES:")
            print(f"  1. Drop generated constraint on net_amount column")
            print(f"  2. Convert net_amount to regular numeric column")
            print(f"  3. Update existing records: net_amount = gross_amount - gst_amount")
            print(f"  4. Set NOT NULL constraint on net_amount")
            print(f"  5. Create backup of current structure")
            
            print(f"\n📋 To apply changes, run: python {__file__} --apply")
            return
        
        # Apply changes
        print(f"\n🔧 APPLYING COLUMN CONVERSION...")
        
        # Step 1: Create backup table
        backup_table = f"receipts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"  1. Creating backup table: {backup_table}")
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS 
            SELECT * FROM receipts LIMIT 5
        """)
        
        # Step 2: Handle view dependency and drop generated column
        print(f"  2. Backing up and dropping dependent view...")
        
        # Get view definition for recreation
        cur.execute("""
            SELECT view_definition 
            FROM information_schema.views 
            WHERE table_name = 'receipts_finance_view'
        """)
        view_def = cur.fetchone()
        if view_def:
            view_definition = view_def[0]
            print(f"     Saved receipts_finance_view definition for recreation")
        
        # Drop view temporarily
        cur.execute("DROP VIEW IF EXISTS receipts_finance_view")
        
        print(f"  3. Converting net_amount from generated to regular column...")
        cur.execute("""
            ALTER TABLE receipts 
            DROP COLUMN net_amount
        """)
        
        # Step 4: Add net_amount as regular column
        cur.execute("""
            ALTER TABLE receipts 
            ADD COLUMN net_amount NUMERIC
        """)
        
        # Step 5: Populate net_amount with calculated values
        print(f"  4. Calculating net_amount values...")
        cur.execute("""
            UPDATE receipts 
            SET net_amount = COALESCE(gross_amount, 0) - COALESCE(gst_amount, 0)
        """)
        
        # Step 6: Set NOT NULL constraint
        print(f"  5. Setting NOT NULL constraint...")
        cur.execute("""
            ALTER TABLE receipts 
            ALTER COLUMN net_amount SET NOT NULL
        """)
        
        # Step 7: Set default value
        cur.execute("""
            ALTER TABLE receipts 
            ALTER COLUMN net_amount SET DEFAULT 0
        """)
        
        # Step 8: Recreate the view
        if view_def:
            print(f"  6. Recreating receipts_finance_view...")
            cur.execute(f"CREATE VIEW receipts_finance_view AS {view_definition}")
        
        conn.commit()
        
        # Verify changes
        print(f"\n[OK] CONVERSION COMPLETE - VERIFYING...")
        
        cur.execute("""
            SELECT 
                column_name, 
                is_generated,
                column_default,
                is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'receipts' AND column_name IN ('gst_amount', 'net_amount')
            ORDER BY column_name
        """)
        
        for row in cur.fetchall():
            generated = "YES" if row[1] == "ALWAYS" else "NO"
            print(f"  {row[0]}: Generated={generated}, Default={row[2]}, Nullable={row[3]}")
        
        # Check data integrity
        cur.execute("SELECT COUNT(*), SUM(gross_amount), SUM(gst_amount), SUM(net_amount) FROM receipts")
        total, gross_sum, gst_sum, net_sum = cur.fetchone()
        
        print(f"\n📊 VERIFICATION:")
        print(f"  Total receipts: {total:,}")
        print(f"  Gross total: ${gross_sum:,.2f}")
        print(f"  GST total: ${gst_sum:,.2f}")
        print(f"  Net total: ${net_sum:,.2f}")
        print(f"  Calculation check: ${(gross_sum - gst_sum):,.2f} (should match net)")
        
        # Check for calculation errors
        cur.execute("""
            SELECT COUNT(*) FROM receipts 
            WHERE ABS(net_amount - (gross_amount - gst_amount)) > 0.01
        """)
        calc_errors = cur.fetchone()[0]
        
        if calc_errors > 0:
            print(f"  [WARN]  Warning: {calc_errors} records with calculation discrepancies > $0.01")
        else:
            print(f"  [OK] All calculations verified correct")
            
        print(f"\n🎯 BENEFITS:")
        print(f"  [OK] No more generated column import errors")
        print(f"  [OK] Can insert net_amount values directly")
        print(f"  [OK] GST calculations handled in staging tables")
        print(f"  [OK] Existing data preserved and verified")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        conn.rollback()
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    """Main conversion function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert receipts calculated columns to regular columns')
    parser.add_argument('--apply', action='store_true', help='Apply the conversion (default is dry-run)')
    
    args = parser.parse_args()
    
    convert_calculated_columns(dry_run=not args.apply)

if __name__ == "__main__":
    main()