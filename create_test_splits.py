#!/usr/bin/env python3
"""
Create test split receipts in database to test the UI
"""

import psycopg2
import os
from datetime import datetime, timedelta

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("\n" + "=" * 80)
print("CREATING TEST SPLIT RECEIPTS FOR UI TESTING")
print("=" * 80)

try:
    # Find some existing receipts to base test data on
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, payment_method, gl_account_code
        FROM receipts 
        WHERE gross_amount > 1000 AND receipt_date >= '2025-01-01'
        ORDER BY RANDOM() LIMIT 5
    """)
    
    source_receipts = cur.fetchall()
    
    if not source_receipts:
        print("\n⚠️  No suitable receipts found to base test splits on")
        print("Looking for older receipts...")
        
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, payment_method, gl_account_code
            FROM receipts 
            WHERE gross_amount > 1000
            ORDER BY receipt_date DESC LIMIT 5
        """)
        source_receipts = cur.fetchall()
    
    if not source_receipts:
        print("❌ No receipts found in database")
        cur.close()
        conn.close()
        exit(1)
    
    print(f"\n✅ Found {len(source_receipts)} receipts to test with\n")
    
    test_count = 0
    
    # Create splits for each test receipt
    for receipt in source_receipts[:3]:  # Test with first 3
        receipt_id, receipt_date, vendor_name, gross_amount, payment_method, gl_code = receipt
        
        # Skip if already has splits
        cur.execute("SELECT COUNT(*) FROM receipt_splits WHERE receipt_id = %s", (receipt_id,))
        if cur.fetchone()[0] > 0:
            print(f"⏭️  Receipt #{receipt_id} already has splits, skipping")
            continue
        
        amount = float(gross_amount)
        
        # Create 2-part split
        part1_amount = amount * 0.6
        part2_amount = amount * 0.4
        
        print(f"\n📦 Creating 2-part split for Receipt #{receipt_id}")
        print(f"   Original: ${amount:,.2f}")
        print(f"   Part 1: ${part1_amount:,.2f} (60%)")
        print(f"   Part 2: ${part2_amount:,.2f} (40%)")
        
        # Insert split parts
        cur.execute("""
            INSERT INTO receipt_splits 
            (receipt_id, split_order, gl_code, amount, payment_method, notes, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (receipt_id, 1, gl_code or '4100', part1_amount, payment_method, 
              f"Part 1 of 2-part split", 'admin'))
        
        cur.execute("""
            INSERT INTO receipt_splits 
            (receipt_id, split_order, gl_code, amount, payment_method, notes, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (receipt_id, 2, '4200', part2_amount, payment_method, 
              f"Part 2 of 2-part split", 'admin'))
        
        # Add cash portion for some receipts
        if test_count % 2 == 0:
            cash_amount = amount * 0.1
            
            # Find a driver
            cur.execute("""
                SELECT employee_id FROM employees 
                WHERE status = 'active' AND employee_type IN ('Driver', 'employee')
                LIMIT 1
            """)
            driver_result = cur.fetchone()
            driver_id = driver_result[0] if driver_result else None
            
            if driver_id:
                print(f"   Cash Portion: ${cash_amount:,.2f}")
                
                cur.execute("""
                    INSERT INTO receipt_cashbox_links 
                    (receipt_id, cashbox_amount, float_reimbursement_type, driver_id, 
                     driver_notes, confirmed_by, confirmed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (receipt_id, cash_amount, 'cash_received', driver_id, 
                      'Test cash portion', 'admin'))
        
        # Update receipt split_status
        cur.execute("""
            UPDATE receipts SET split_status = 'split_reconciled' WHERE receipt_id = %s
        """, (receipt_id,))
        
        # Add audit log entries
        cur.execute("""
            INSERT INTO audit_log 
            (entity_type, entity_id, field_changed, old_value, new_value, changed_by, changed_at, reason)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
        """, ('receipt', receipt_id, 'split_status', 'single', 'split_reconciled', 'admin', 
              'Test split creation via UI testing script'))
        
        test_count += 1
        print(f"   ✅ Created test split")
    
    conn.commit()
    
    print("\n" + "=" * 80)
    print(f"✅ CREATED {test_count} TEST SPLIT RECEIPTS")
    print("=" * 80)
    
    if test_count > 0:
        # Show what was created
        cur.execute("""
            SELECT DISTINCT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
                   COUNT(rs.split_id) as split_count
            FROM receipts r
            LEFT JOIN receipt_splits rs ON rs.receipt_id = r.receipt_id
            WHERE rs.split_id IS NOT NULL
            GROUP BY r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount
            ORDER BY r.receipt_id DESC LIMIT 5
        """)
        
        print("\n📊 TEST DATA CREATED:\n")
        for r in cur.fetchall():
            print(f"  Receipt #{r[0]}: ${r[3]:,.2f} ({r[2]}) - {r[4]} parts")
        
        # Store test IDs
        cur.execute("""
            SELECT receipt_id FROM receipt_splits
            GROUP BY receipt_id ORDER BY receipt_id DESC LIMIT 5
        """)
        test_ids = [r[0] for r in cur.fetchall()]
        
        print("\n" + "=" * 80)
        print("🚀 READY FOR UI TESTING")
        print("=" * 80)
        
        print("""
1. Launch the desktop app:
   $env:RECEIPT_WIDGET_WRITE_ENABLED = "true"
   python -X utf8 desktop_app/main.py

2. Go to Receipts tab

3. Load these test receipt IDs:
""")
        
        for test_id in test_ids:
            print(f"   - #{test_id}")
        
        print("""
4. For each receipt, verify:
   ✓ Red banner appears: "📦 Split into X receipt(s)..."
   ✓ Side-by-side panels show below search table
   ✓ Each panel shows correct amount
   ✓ [👁️ View Split Details] shows summary
   ✓ [🔗 Open] buttons work to jump between parts
   ✓ Cash portion panel visible (if added)
   ✓ [🔽 Collapse] hides split view
   ✓ Amounts displayed correctly

5. Test on non-split receipts:
   ✓ No banner should appear
   ✓ Can click [✂️ Create Split] button
   ✓ Dialog opens with side-by-side panels
   ✓ Auto-fill works (enter part 1, part 2 fills automatically)
   
6. Document any issues or UI improvements needed
""")
    else:
        print("\n⚠️  No test splits were created")
        print("All receipts already had splits")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()

finally:
    cur.close()
    conn.close()
