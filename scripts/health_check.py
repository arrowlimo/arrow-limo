#!/usr/bin/env python3
"""
Quick Health Check - Tests core functionality without starting server
"""
import sys
from pathlib import Path

def test_imports():
    """Test all critical imports work"""
    print("\n🔍 Testing Imports...")
    try:
        from modern_backend.app.main import app
        print("   ✅ Backend app imports successfully")
        return True
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return False

def test_database():
    """Test database connectivity"""
    print("\n🔍 Testing Database...")
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost', database='almsdata', 
            user='postgres', password='***REMOVED***'
        )
        cur = conn.cursor()
        
        # Test core table access
        cur.execute("SELECT 1 FROM receipts LIMIT 1")
        cur.execute("SELECT 1 FROM charters LIMIT 1")
        cur.execute("SELECT 1 FROM payments LIMIT 1")
        
        # Verify 2019 flattening
        cur.execute("""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE parent_receipt_id IS NOT NULL)
            FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2019
        """)
        total, with_parent = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if with_parent == 0:
            print(f"   ✅ Database connected")
            print(f"   ✅ 2019 receipts flattened: {total} total, 0 with parent")
            return True
        else:
            print(f"   ❌ 2019 flattening incomplete: {with_parent} still have parent_receipt_id")
            return False
            
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False

def test_code_structure():
    """Verify code structure is sound"""
    print("\n🔍 Testing Code Structure...")
    
    router_dir = Path('modern_backend/app/routers')
    if not router_dir.exists():
        print("   ❌ Routers directory not found")
        return False
    
    router_files = list(router_dir.glob('*.py'))
    router_files = [f for f in router_files if not f.name.startswith('_')]
    
    if len(router_files) < 10:
        print(f"   ❌ Only {len(router_files)} routers found (expected 10+)")
        return False
    
    print(f"   ✅ Found {len(router_files)} router modules")
    return True

def main():
    print("╔════════════════════════════════════════════════════════╗")
    print("║          LIMO APP - HEALTH CHECK                       ║")
    print("╚════════════════════════════════════════════════════════╝")
    
    results = [
        ("Code Structure", test_code_structure()),
        ("Database Connection", test_database()),
        ("Backend Imports", test_imports()),
    ]
    
    print("\n" + "="*60)
    print("HEALTH CHECK RESULTS")
    print("="*60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    passed = sum(1 for _, r in results if r)
    
    print(f"\nStatus: {passed}/{len(results)} checks passed")
    
    if passed == len(results):
        print("\n✨ All systems operational!")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} issue(s) detected")
        return 1

if __name__ == '__main__':
    sys.exit(main())
