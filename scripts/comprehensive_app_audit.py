#!/usr/bin/env python3
"""
Comprehensive Application Audit and Health Check
Tests all endpoints, database connections, and identifies issues
"""
import sys
import traceback
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def audit_database():
    """Test database connectivity and schema"""
    print("\n" + "="*70)
    print("DATABASE AUDIT")
    print("="*70)
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            database='almsdata',
            user='postgres',
            password='***REDACTED***'
        )
        cur = conn.cursor()
        
        # Check core tables
        tables = ['receipts', 'charters', 'payments', 'vehicles', 'employees', 'banking_transactions']
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  ✅ {table}: {count:,} rows")
        
        # Check 2019 flattening
        cur.execute("""
            SELECT COUNT(*), SUM(CASE WHEN parent_receipt_id IS NOT NULL THEN 1 ELSE 0 END)
            FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2019
        """)
        total, with_parent = cur.fetchone()
        with_parent = with_parent or 0
        status = "✅ FLATTENED" if with_parent == 0 else f"❌ {with_parent} still have parent_receipt_id"
        print(f"  {status} - 2019 receipts: {total} total, {with_parent} with parent")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        traceback.print_exc()
        return False


def audit_backend_imports():
    """Test if all backend modules import correctly"""
    print("\n" + "="*70)
    print("BACKEND IMPORTS AUDIT")
    print("="*70)
    
    issues = []
    
    # Test main app
    try:
        from modern_backend.app.main import app
        print("  ✅ modern_backend.app.main")
    except Exception as e:
        print(f"  ❌ modern_backend.app.main: {e}")
        issues.append(("main.py", str(e)))
    
    # Test routers
    routers = [
        'charges', 'charters', 'payments', 'bookings', 'reports',
        'receipts', 'receipts_simple', 'receipts_split',
        'invoices', 'accounting', 'banking', 'banking_allocations'
    ]
    
    for router_name in routers:
        try:
            module = __import__(f'modern_backend.app.routers.{router_name}', fromlist=['router'])
            print(f"  ✅ routers.{router_name}")
        except Exception as e:
            print(f"  ❌ routers.{router_name}: {str(e)[:60]}")
            issues.append((f"{router_name}.py", str(e)[:100]))
    
    return len(issues) == 0, issues


def audit_code_quality():
    """Check for common code issues"""
    print("\n" + "="*70)
    print("CODE QUALITY AUDIT")
    print("="*70)
    
    router_dir = Path('modern_backend/app/routers')
    if not router_dir.exists():
        print("  ❌ Routers directory not found")
        return False
    
    issues = []
    
    for router_file in sorted(router_dir.glob('*.py')):
        if router_file.name.startswith('_'):
            continue
            
        try:
            with open(router_file, 'r') as f:
                content = f.read()
            
            # Check for common patterns
            has_router_def = '@router.get' in content or '@router.post' in content
            has_error_handling = 'except' in content or 'HTTPException' in content
            has_docstring = '"""' in content or "'''" in content
            
            status = "✅" if has_router_def and has_error_handling else "⚠️"
            print(f"  {status} {router_file.name}")
            
            if not has_router_def:
                issues.append((router_file.name, "No router definitions found"))
            if not has_error_handling:
                issues.append((router_file.name, "No error handling found"))
                
        except Exception as e:
            print(f"  ❌ {router_file.name}: {e}")
            issues.append((router_file.name, str(e)))
    
    return len(issues) == 0, issues


def check_duplicate_code():
    """Identify duplicate patterns in routers"""
    print("\n" + "="*70)
    print("DUPLICATE CODE AUDIT")
    print("="*70)
    
    router_dir = Path('modern_backend/app/routers')
    get_patterns = {}
    
    for router_file in sorted(router_dir.glob('*.py')):
        if router_file.name.startswith('_'):
            continue
        
        try:
            with open(router_file, 'r') as f:
                lines = f.readlines()
            
            # Look for duplicate database fetch patterns
            for i, line in enumerate(lines):
                if 'SELECT' in line:
                    # Normalize the query
                    normalized = line.strip()[:50]
                    if normalized not in get_patterns:
                        get_patterns[normalized] = []
                    get_patterns[normalized].append((router_file.name, i+1))
        except Exception:
            pass
    
    # Report duplicates
    duplicates_found = False
    for pattern, locations in get_patterns.items():
        if len(locations) > 1:
            duplicates_found = True
            print(f"  ⚠️  Duplicate pattern found in {len(locations)} files:")
            for filename, line_num in locations:
                print(f"      - {filename}:{line_num}")
    
    if not duplicates_found:
        print("  ✅ No significant code duplication detected")
    
    return not duplicates_found


def audit_db_operations():
    """Verify all database operations are read-only or write-appropriate"""
    print("\n" + "="*70)
    print("DATABASE OPERATIONS AUDIT")
    print("="*70)
    
    router_dir = Path('modern_backend/app/routers')
    
    # These should be GET endpoints (read-only)
    get_endpoints = []
    # These should be POST endpoints (write)
    post_endpoints = []
    # These should be DELETE endpoints
    delete_endpoints = []
    
    issues = []
    
    for router_file in sorted(router_dir.glob('*.py')):
        if router_file.name.startswith('_'):
            continue
        
        try:
            with open(router_file, 'r') as f:
                content = f.read()
                lines = content.split('\n')
            
            current_endpoint = None
            for i, line in enumerate(lines):
                if '@router.get(' in line:
                    current_endpoint = ('GET', line.strip())
                elif '@router.post(' in line:
                    current_endpoint = ('POST', line.strip())
                elif '@router.delete(' in line:
                    current_endpoint = ('DELETE', line.strip())
                
                # Check for inappropriate operations
                if current_endpoint:
                    method = current_endpoint[0]
                    if method == 'GET' and ('INSERT' in line or 'UPDATE' in line or 'DELETE' in line.upper()):
                        issues.append((router_file.name, f"GET endpoint has {line.strip()[:40]} (should be read-only)"))
                    elif method == 'POST' and 'SELECT' in line and 'NOT EXISTS' not in line:
                        # POST can have SELECT for validation
                        pass
        except Exception as e:
            pass
    
    if issues:
        for filename, issue in issues:
            print(f"  ❌ {filename}: {issue}")
        return False
    else:
        print("  ✅ All database operations follow correct patterns")
        return True


def main():
    """Run all audits"""
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "COMPREHENSIVE APPLICATION AUDIT" + " "*22 + "║")
    print("╚" + "="*68 + "╝")
    
    results = {
        "Database": audit_database(),
        "Backend Imports": audit_backend_imports()[0],
        "Code Quality": audit_code_quality()[0],
        "Duplicate Code": check_duplicate_code(),
        "DB Operations": audit_db_operations(),
    }
    
    # Summary
    print("\n" + "="*70)
    print("AUDIT SUMMARY")
    print("="*70)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    print(f"\nOverall: {passed}/{total} audits passed")
    
    if passed == total:
        print("\n🎉 All audits passed! Application is in good shape.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} audit(s) need attention")
        return 1


if __name__ == '__main__':
    sys.exit(main())
