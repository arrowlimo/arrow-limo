#!/usr/bin/env python3
"""
Test Arrow Limousine Desktop App - Feature Verification
Tests all major UI components and database interactions
"""

import sys
import psycopg2
from decimal import Decimal
from datetime import datetime, date
import os

# Set up environment
os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "almsdata"
os.environ["DB_USER"] = "postgres"
os.environ["DB_PASSWORD"] = "***REMOVED***"

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def test_database_connection():
    """Verify database connection works"""
    print("✅ Testing database connection...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        print("  ✅ Database connection successful")
        return True
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False

def test_data_availability():
    """Check if sample data exists for testing"""
    print("\n✅ Checking sample data...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Check clients
        cur.execute("SELECT COUNT(*) FROM clients")
        client_count = cur.fetchone()[0]
        print(f"  ✅ Clients: {client_count}")
        
        # Check charters
        cur.execute("SELECT COUNT(*) FROM charters")
        charter_count = cur.fetchone()[0]
        print(f"  ✅ Charters: {charter_count}")
        
        # Check payments
        cur.execute("SELECT COUNT(*) FROM payments")
        payment_count = cur.fetchone()[0]
        print(f"  ✅ Payments: {payment_count}")
        
        # Check vehicles
        cur.execute("SELECT COUNT(*) FROM vehicles")
        vehicle_count = cur.fetchone()[0]
        print(f"  ✅ Vehicles: {vehicle_count}")
        
        # Check employees
        cur.execute("SELECT COUNT(*) FROM employees")
        employee_count = cur.fetchone()[0]
        print(f"  ✅ Employees: {employee_count}")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Data check failed: {e}")
        return False

def test_fleet_management_queries():
    """Test Fleet Management tab queries"""
    print("\n✅ Testing Fleet Management queries...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Fleet summary
        cur.execute("""
            SELECT COUNT(*), SUM(CAST(purchase_price AS DECIMAL(12,2)))
            FROM vehicles
        """)
        result = cur.fetchone()
        if result:
            vehicle_count, total_value = result
            print(f"  ✅ Fleet Summary: {vehicle_count} vehicles, ${total_value or 0:.2f} total value")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Fleet Management queries failed: {e}")
        return False

def test_driver_performance_queries():
    """Test Driver Performance tab queries"""
    print("\n✅ Testing Driver Performance queries...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Driver stats
        cur.execute("""
            SELECT COUNT(DISTINCT e.employee_id) as active_drivers
            FROM employees e
            LEFT JOIN charters c ON e.employee_id = c.employee_id
            GROUP BY e.employee_id
        """)
        rows = cur.fetchall()
        print(f"  ✅ Driver Performance: {len(rows)} active drivers")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Driver Performance queries failed: {e}")
        return False

def test_charter_queries():
    """Test charter-related queries"""
    print("\n✅ Testing charter queries...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Sample charter with related data
        cur.execute("""
            SELECT c.charter_id, c.reserve_number, c.charter_date, c.client_id, c.total_amount_due,
                   COUNT(p.payment_id) as payment_count,
                   COALESCE(SUM(p.amount), 0) as total_paid
            FROM charters c
            LEFT JOIN payments p ON c.reserve_number = p.reserve_number
            GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.client_id, c.total_amount_due
            LIMIT 1
        """)
        charter = cur.fetchone()
        if charter:
            charter_id, res_num, charter_date, client_id, amount_due, payment_count, total_paid = charter
            print(f"  ✅ Sample Charter: {res_num}, {charter_date}, ${amount_due:.2f} (${total_paid:.2f} paid)")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Charter queries failed: {e}")
        return False

def test_client_drill_down_queries():
    """Test Client Drill Down dialog queries"""
    print("\n✅ Testing Client Drill Down queries...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Get first client
        cur.execute("SELECT client_id FROM clients LIMIT 1")
        result = cur.fetchone()
        if not result:
            print("  ⚠️  No clients available for testing")
            return True
        
        client_id = result[0]
        
        # Test charter history query
        cur.execute("""
            SELECT c.charter_date, c.reserve_number, c.pickup_address, c.dropoff_address,
                   e.full_name, v.license_plate, c.total_amount_due
            FROM charters c
            LEFT JOIN employees e ON c.employee_id = e.employee_id
            LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
            WHERE c.client_id = %s
            ORDER BY c.charter_date DESC
            LIMIT 5
        """, (client_id,))
        charters = cur.fetchall()
        print(f"  ✅ Client {client_id} Charter History: {len(charters)} records")
        
        # Test payment history query
        cur.execute("""
            SELECT p.payment_date, p.reserve_number, p.amount, p.payment_method
            FROM payments p
            JOIN charters c ON p.reserve_number = c.reserve_number
            WHERE c.client_id = %s
            ORDER BY p.payment_date DESC
            LIMIT 5
        """, (client_id,))
        payments = cur.fetchall()
        print(f"  ✅ Client {client_id} Payment History: {len(payments)} records")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Client Drill Down queries failed: {e}")
        return False

def main():
    print("=" * 60)
    print("Arrow Limousine Desktop App - Feature Verification")
    print("=" * 60)
    
    tests = [
        test_database_connection,
        test_data_availability,
        test_fleet_management_queries,
        test_driver_performance_queries,
        test_charter_queries,
        test_client_drill_down_queries,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
