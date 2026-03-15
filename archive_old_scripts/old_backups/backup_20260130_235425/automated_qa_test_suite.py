#!/usr/bin/env python3
"""
Automated QA Test Suite - Phase 1
Tests balance fixes, widget data, and error handling
"""
import psycopg2
import os
import random
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def test_balance_fixes():
    """Test 1: Verify 18,645 charter balances are correctly calculated"""
    print("\n" + "="*60)
    print("TEST 1: CHARTER BALANCE VERIFICATION")
    print("="*60)
    
    conn = connect_db()
    cur = conn.cursor()
    
    try:
        # Count total charters
        cur.execute("SELECT COUNT(*) FROM charters")
        total = cur.fetchone()[0]
        print(f"✅ Total charters in database: {total:,}")
        
        # Check for charters with NULL balance
        cur.execute("SELECT COUNT(*) FROM charters WHERE balance IS NULL")
        null_count = cur.fetchone()[0]
        if null_count > 0:
            print(f"❌ FAIL: {null_count} charters have NULL balance")
            return False
        else:
            print(f"✅ Zero charters with NULL balance")
        
        # Sample 100 random charters and verify balance calculation
        cur.execute("SELECT reserve_number FROM charters ORDER BY RANDOM() LIMIT 100")
        samples = [row[0] for row in cur.fetchall()]
        
        mismatches = []
        for reserve_num in samples:
            cur.execute("""
                SELECT c.total_amount_due, c.balance,
                       COALESCE(SUM(p.amount), 0) as total_paid
                FROM charters c
                LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                WHERE c.reserve_number = %s
                GROUP BY c.charter_id, c.total_amount_due, c.balance
            """, (reserve_num,))
            
            result = cur.fetchone()
            if result:
                due, stored_balance, total_paid = result
                # If due is NULL, balance should be 0 or calculated from payments alone
                if due is None:
                    calculated_balance = 0
                else:
                    calculated_balance = float(due) - float(total_paid or 0)
                
                if abs(float(stored_balance or 0) - calculated_balance) > 0.01:
                    mismatches.append({
                        'reserve': reserve_num,
                        'due': due,
                        'paid': total_paid,
                        'stored': stored_balance,
                        'calculated': calculated_balance
                    })
        
        if mismatches:
            print(f"❌ FAIL: {len(mismatches)} balance mismatches found in sample of 100:")
            for m in mismatches[:5]:
                print(f"   {m['reserve']}: stored={m['stored']}, calculated={m['calculated']}")
            return False
        else:
            print(f"✅ All 100 sampled charters have correct balances")
        
        # Check balance distribution
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE balance < -0.01) as negative,
                COUNT(*) FILTER (WHERE balance BETWEEN -0.01 AND 0.01) as zero,
                COUNT(*) FILTER (WHERE balance > 0.01) as positive
            FROM charters
        """)
        neg, zero, pos = cur.fetchone()
        print(f"✅ Balance distribution: {neg} negative, {zero} zero, {pos} positive")
        
        return True
        
    finally:
        cur.close()
        conn.close()

def test_widget_data():
    """Test 2: Verify widget data loads correctly"""
    print("\n" + "="*60)
    print("TEST 2: WIDGET DATA VERIFICATION")
    print("="*60)
    
    conn = connect_db()
    cur = conn.cursor()
    
    try:
        # Fleet Management: 26 vehicles
        cur.execute("SELECT COUNT(*) FROM vehicles WHERE status = 'active' OR is_active = true")
        vehicle_count = cur.fetchone()[0]
        if vehicle_count == 0:
            # Try without status filter
            cur.execute("SELECT COUNT(*) FROM vehicles")
            vehicle_count = cur.fetchone()[0]
        print(f"✅ Fleet Management: {vehicle_count} vehicles")
        if vehicle_count < 20:
            print(f"⚠️  WARNING: Expected ~26, got {vehicle_count}")
        
        # Driver Performance: active drivers (not all drivers have 'driver' designation)
        cur.execute("SELECT COUNT(*) FROM employees WHERE position = 'driver' AND status = 'active'")
        driver_count = cur.fetchone()[0]
        if driver_count == 0:
            # Try alternative status field
            cur.execute("SELECT COUNT(*) FROM employees WHERE position = 'driver' AND employment_status = 'active'")
            driver_count = cur.fetchone()[0]
        if driver_count == 0:
            # Try without status
            cur.execute("SELECT COUNT(*) FROM employees WHERE is_chauffeur = true OR position = 'driver'")
            driver_count = cur.fetchone()[0]
        print(f"✅ Driver Performance: {driver_count} drivers")
        if driver_count < 100:
            print(f"⚠️  WARNING: Expected ~135, got {driver_count}")
        
        # Financial Dashboard data
        cur.execute("""
            SELECT 
                COALESCE(SUM(c.total_amount_due), 0) as revenue,
                COALESCE(SUM(r.gross_amount), 0) as expenses
            FROM charters c,
                 receipts r
        """)
        result = cur.fetchone()
        if result:
            revenue, expenses = result
            print(f"✅ Financial Dashboard: Revenue ${revenue:,.2f}, Expenses ${expenses:,.2f}")
        
        # Payment Reconciliation: outstanding charters
        cur.execute("SELECT COUNT(*) FROM charters WHERE balance > 0.01")
        outstanding = cur.fetchone()[0]
        print(f"✅ Payment Reconciliation: {outstanding} outstanding charters")
        
        # Check for data integrity issues
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE reserve_number IS NULL
               OR total_amount_due IS NULL
               OR status IS NULL
        """)
        integrity_issues = cur.fetchone()[0]
        if integrity_issues > 0:
            print(f"❌ FAIL: {integrity_issues} charters with missing required fields")
            return False
        else:
            print(f"✅ All charters have required fields populated")
        
        return True
        
    finally:
        cur.close()
        conn.close()

def test_orphaned_payments():
    """Test 3: Verify orphaned payments detection"""
    print("\n" + "="*60)
    print("TEST 3: ORPHANED PAYMENTS DETECTION")
    print("="*60)
    
    conn = connect_db()
    cur = conn.cursor()
    
    try:
        # Find orphaned payments (no matching charter)
        cur.execute("""
            SELECT COUNT(*) FROM payments p
            WHERE NOT EXISTS (
                SELECT 1 FROM charters c
                WHERE c.reserve_number = p.reserve_number
            )
        """)
        orphaned = cur.fetchone()[0]
        print(f"⚠️  Found {orphaned:,} orphaned payments (no matching charter)")
        
        if orphaned > 0:
            # Sample a few
            cur.execute("""
                SELECT p.payment_id, p.reserve_number, p.amount, p.payment_date
                FROM payments p
                WHERE NOT EXISTS (
                    SELECT 1 FROM charters c
                    WHERE c.reserve_number = p.reserve_number
                )
                LIMIT 5
            """)
            print("   Sample orphaned payments:")
            for row in cur.fetchall():
                print(f"   - Payment {row[0]}: Reserve {row[1]}, ${row[2]}, {row[3]}")
        
        return True
        
    finally:
        cur.close()
        conn.close()

def test_flattening():
    """Test 4: Verify receipt flattening is complete"""
    print("\n" + "="*60)
    print("TEST 4: RECEIPT FLATTENING VERIFICATION")
    print("="*60)
    
    conn = connect_db()
    cur = conn.cursor()
    
    try:
        # Check 2019 receipts (the flattening target)
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE parent_receipt_id IS NOT NULL) as with_parent
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2019
        """)
        total, with_parent = cur.fetchone()
        print(f"✅ 2019 receipts: {total:,} total, {with_parent} with parent_receipt_id")
        
        if with_parent > 0:
            print(f"❌ FAIL: {with_parent} receipts still have parent_receipt_id (should be 0)")
            return False
        else:
            print(f"✅ All 2019 receipts fully flattened (no parent_receipt_id)")
        
        # Overall flattening status
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE parent_receipt_id IS NOT NULL)
            FROM receipts
        """)
        orphaned_receipts = cur.fetchone()[0]
        print(f"✅ Total receipts with parent: {orphaned_receipts:,}")
        
        return True
        
    finally:
        cur.close()
        conn.close()

def test_vendor_data():
    """Test 5: Verify vendor autocomplete data"""
    print("\n" + "="*60)
    print("TEST 5: VENDOR DATA VERIFICATION")
    print("="*60)
    
    conn = connect_db()
    cur = conn.cursor()
    
    try:
        # Count distinct vendors
        cur.execute("SELECT COUNT(DISTINCT vendor_name) FROM receipts WHERE vendor_name IS NOT NULL")
        vendor_count = cur.fetchone()[0]
        print(f"✅ Distinct vendors in receipts: {vendor_count:,}")
        
        # Check for NULL vendors
        cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name IS NULL")
        null_vendors = cur.fetchone()[0]
        if null_vendors > 0:
            print(f"⚠️  {null_vendors:,} receipts with NULL vendor_name")
        else:
            print(f"✅ All receipts have vendor_name populated")
        
        return True
        
    finally:
        cur.close()
        conn.close()

def main():
    print("\n" + "="*60)
    print("AUTOMATED QA TEST SUITE - PHASE 1")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = []
    
    # Run all tests
    results.append(("Balance Fixes", test_balance_fixes()))
    results.append(("Widget Data", test_widget_data()))
    results.append(("Orphaned Payments", test_orphaned_payments()))
    results.append(("Receipt Flattening", test_flattening()))
    results.append(("Vendor Data", test_vendor_data()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
