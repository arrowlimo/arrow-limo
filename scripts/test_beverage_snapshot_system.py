#!/usr/bin/env python3
"""
Test Suite: Beverage Snapshot System
Validates that charter_beverages table properly locks prices at time of charter creation
Ensures price changes to master beverage_products do NOT affect historical charters
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def connect_db():
    """Create database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def test_1_table_structure():
    """Test 1: Verify charter_beverages table exists with correct structure"""
    print("\n" + "="*80)
    print("TEST 1: Verify charter_beverages table structure")
    print("="*80)
    
    conn = None
    cur = None
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Get table structure
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'charter_beverages'
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        if not columns:
            print("❌ FAILED: charter_beverages table does not exist!")
            return False
        
        print(f"✅ Table exists with {len(columns)} columns")
        print("\nColumns:")
        print("─" * 80)
        for col_name, col_type, nullable in columns:
            nullable_str = "NULLABLE" if nullable == 'YES' else "NOT NULL"
            print(f"  {col_name:<25} {col_type:<20} {nullable_str}")
        
        # Check required columns
        required_columns = {
            'id', 'charter_id', 'beverage_item_id', 'item_name', 'quantity',
            'unit_price_charged', 'unit_our_cost', 'deposit_per_unit',
            'line_amount_charged', 'line_cost', 'notes', 'created_at', 'updated_at'
        }
        existing_columns = {col[0] for col in columns}
        
        missing = required_columns - existing_columns
        if missing:
            print(f"\n❌ FAILED: Missing columns: {missing}")
            return False
        
        print(f"\n✅ PASSED: All required columns present")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def test_2_save_beverages():
    """Test 2: Save beverages to an existing test charter"""
    print("\n" + "="*80)
    print("TEST 2: Save beverages to existing charter and verify snapshot")
    print("="*80)
    
    conn = None
    cur = None
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Use an existing charter for testing  
        print("\n1️⃣ Finding an existing charter to test with...")
        cur.execute("""
            SELECT charter_id FROM charters WHERE reserve_number IS NOT NULL LIMIT 1
        """)
        
        result = cur.fetchone()
        if not result:
            print("⚠️  No existing charters available to test with")
            return None
        
        test_charter_id = result[0]
        print(f"   ✓ Using existing charter_id: {test_charter_id}")
        
        # Get beverages from master list
        print("\n2️⃣ Fetching beverages from master list...")
        cur.execute("""
            SELECT item_id, item_name, unit_price, our_cost, deposit_amount
            FROM beverage_products
            WHERE item_name NOT LIKE '%TEST%'
            ORDER BY RANDOM()
            LIMIT 2
        """)
        
        beverages = cur.fetchall()
        if not beverages:
            print("⚠️  No beverages available to test")
            return None
        
        print(f"   Found {len(beverages)} beverages")
        
        # Save to charter_beverages
        print("\n3️⃣ Saving beverages to charter_beverages...")
        for item_id, item_name, unit_price, our_cost, deposit in beverages:
            qty = 12
            unit_price = float(unit_price) if unit_price else 5.00
            unit_cost = float(our_cost) if our_cost else unit_price * 0.6
            deposit = float(deposit) if deposit else 0
            
            cur.execute("""
                INSERT INTO charter_beverages
                (charter_id, beverage_item_id, item_name, quantity, 
                 unit_price_charged, unit_our_cost, deposit_per_unit, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                test_charter_id, item_id, item_name, qty,
                unit_price, unit_cost, deposit,
                "SNAPSHOT_TEST"
            ))
            print(f"   ✓ Saved {item_name} to charter_beverages")
        
        conn.commit()
        print(f"\n✅ PASSED: {len(beverages)} beverages saved to charter {test_charter_id}")
        return test_charter_id
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def test_3_price_snapshot(test_charter_id):
    """Test 3: Verify master price changes don't affect snapshot"""
    print("\n" + "="*80)
    print("TEST 3: Verify price snapshot integrity")
    print("="*80)
    
    if not test_charter_id:
        print("⏭️  SKIPPED: No test charter")
        return False
    
    conn = None
    cur = None
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Get first saved beverage
        print("\n1️⃣ Getting first saved beverage...")
        cur.execute("""
            SELECT beverage_item_id, item_name, unit_price_charged
            FROM charter_beverages
            WHERE charter_id = %s
            LIMIT 1
        """, (test_charter_id,))
        
        item = cur.fetchone()
        if not item:
            print("❌ FAILED: No beverages found")
            return False
        
        item_id, item_name, snapshot_price = item
        print(f"   Item: {item_name}")
        print(f"   Snapshot price: ${snapshot_price:.2f}")
        
        # Change master price
        new_price = round(float(snapshot_price) + 2.0, 2)
        print(f"\n2️⃣ Changing master price to ${new_price:.2f}...")
        
        cur.execute("""
            UPDATE beverage_products
            SET unit_price = %s
            WHERE item_id = %s
        """, (new_price, item_id))
        conn.commit()
        print("   ✓ Master price updated")
        
        # Verify charter snapshot unchanged
        print(f"\n3️⃣ Verifying charter snapshot...")
        cur.execute("""
            SELECT unit_price_charged
            FROM charter_beverages
            WHERE charter_id = %s AND beverage_item_id = %s
        """, (test_charter_id, item_id))
        
        snapshot_after = cur.fetchone()[0]
        
        if snapshot_after == snapshot_price:
            print(f"   ✓ Snapshot UNCHANGED: ${snapshot_after:.2f}")
            print(f"\n✅ PASSED: Master changes don't affect charter snapshot")
            return True
        else:
            print(f"   ❌ Snapshot CHANGED: ${snapshot_after:.2f}")
            return False
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def test_4_load_beverages(test_charter_id):
    """Test 4: Load charter beverages"""
    print("\n" + "="*80)
    print("TEST 4: Load charter beverages")
    print("="*80)
    
    if not test_charter_id:
        print("⏭️  SKIPPED: No test charter")
        return False
    
    conn = None
    cur = None
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        print(f"\n1️⃣ Loading beverages for charter {test_charter_id}...")
        cur.execute("""
            SELECT item_name, quantity, unit_price_charged, line_amount_charged
            FROM charter_beverages
            WHERE charter_id = %s
            ORDER BY created_at
        """, (test_charter_id,))
        
        beverages = cur.fetchall()
        if not beverages:
            print("❌ FAILED: No beverages loaded")
            return False
        
        print(f"✅ Loaded {len(beverages)} beverages:")
        print("─" * 80)
        print(f"{'Item':<35} {'Qty':<5} {'Unit Price':<15} {'Total':<12}")
        print("─" * 80)
        
        total = 0
        for item_name, qty, unit_price, line_amount in beverages:
            total += float(line_amount)
            print(f"{item_name:<35} {qty:<5} ${unit_price:<14.2f} ${line_amount:<11.2f}")
        
        print("─" * 80)
        print(f"{'TOTAL':<50} ${total:<11.2f}")
        print(f"\n✅ PASSED: Successfully loaded beverages")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def cleanup(test_charter_id):
    """Clean up test data"""
    print("\n" + "="*80)
    print("CLEANUP: Removing test beverages")
    print("="*80)
    
    if not test_charter_id:
        return
    
    conn = None
    cur = None
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM charter_beverages WHERE charter_id = %s AND notes = 'SNAPSHOT_TEST'", (test_charter_id,))
        
        conn.commit()
        print(f"✅ Cleaned up test beverages from charter {test_charter_id}")
        
    except Exception as e:
        print(f"⚠️  Cleanup error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def main():
    """Run all tests"""
    print("\n╔" + "="*78 + "╗")
    print("║" + " "*20 + "BEVERAGE SNAPSHOT SYSTEM TEST SUITE" + " "*24 + "║")
    print("╚" + "="*78 + "╝")
    
    results = {}
    test_charter_id = None
    
    # Run tests
    results['table_structure'] = test_1_table_structure()
    test_charter_id = test_2_save_beverages()
    results['save_beverages'] = bool(test_charter_id)
    
    if test_charter_id:
        results['price_snapshot'] = test_3_price_snapshot(test_charter_id)
        results['load_beverages'] = test_4_load_beverages(test_charter_id)
    else:
        results['price_snapshot'] = False
        results['load_beverages'] = False
    
    # Cleanup
    cleanup(test_charter_id)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {test_name}")
    
    print("="*80)
    print(f"RESULT: {passed}/{total} tests passed\n")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
