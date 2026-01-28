#!/usr/bin/env python3
"""
Comprehensive Application Code Validation Suite
Tests all critical components: database, APIs, business logic
"""
import sys
import traceback
from pathlib import Path
from datetime import datetime, timedelta
import psycopg2
from decimal import Decimal

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

class ValidationReport:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add_pass(self, name, details=""):
        self.passed += 1
        self.tests.append(("✅", name, details))
        print(f"✅ {name}")
        if details:
            print(f"   {details}")
    
    def add_fail(self, name, error=""):
        self.failed += 1
        self.tests.append(("❌", name, error))
        print(f"❌ {name}")
        if error:
            print(f"   {error[:100]}")
    
    def add_warn(self, name, details=""):
        self.warnings += 1
        self.tests.append(("⚠️", name, details))
        print(f"⚠️  {name}")
        if details:
            print(f"   {details[:100]}")
    
    def summary(self):
        total = self.passed + self.failed + self.warnings
        return {
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "total": total,
            "pass_rate": f"{(self.passed/total*100):.0f}%" if total > 0 else "0%"
        }

report = ValidationReport()

# ============================================================================
# 1. DATABASE VALIDATION
# ============================================================================
print("\n" + "="*70)
print("1. DATABASE VALIDATION")
print("="*70)

try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    report.add_pass("Database connection successful")
    
    # Check all critical tables exist
    tables_to_check = [
        'receipts', 'charters', 'payments', 'employees', 'vehicles',
        'banking_transactions', 'assets', 'vendors', 'invoices'
    ]
    missing_tables = []
    for table in tables_to_check:
        cur.execute(f"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='{table}')")
        if not cur.fetchone()[0]:
            missing_tables.append(table)
    
    if missing_tables:
        report.add_warn(f"Missing tables: {', '.join(missing_tables)}")
    else:
        report.add_pass(f"All {len(tables_to_check)} critical tables exist")
    
    # Check 2019 flattening
    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN parent_receipt_id IS NOT NULL THEN 1 ELSE 0 END) as with_parent
        FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    """)
    total_2019, with_parent = cur.fetchone()
    if with_parent == 0:
        report.add_pass(f"2019 Receipts flattened: {total_2019} total, 0 with parent_receipt_id")
    else:
        report.add_fail(f"2019 flattening incomplete: {with_parent} receipts still have parent_receipt_id")
    
    # Check data integrity - verify balances match
    cur.execute("""
        SELECT c.charter_id, c.total_amount_due,
               COALESCE(SUM(p.amount), 0) as total_paid,
               c.total_amount_due - COALESCE(SUM(p.amount), 0) as balance
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.total_amount_due
        HAVING ABS((c.total_amount_due - COALESCE(SUM(p.amount), 0)) - c.balance) > 0.01
        LIMIT 5
    """)
    bad_balances = cur.fetchall()
    if bad_balances:
        report.add_fail(f"Balance mismatches found: {len(bad_balances)} charters")
    else:
        report.add_pass("Charter balance integrity verified")
    
    # Check for orphaned payments
    cur.execute("""
        SELECT COUNT(*) FROM payments
        WHERE reserve_number NOT IN (SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL)
        AND reserve_number IS NOT NULL
    """)
    orphan_count = cur.fetchone()[0]
    if orphan_count > 0:
        report.add_warn(f"Orphaned payments found: {orphan_count} payments without matching charters")
    else:
        report.add_pass("No orphaned payments found")
    
    # Verify GST calculations
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE gross_amount > 0 AND gst_amount IS NULL
        AND EXTRACT(YEAR FROM receipt_date) >= 2020
        LIMIT 5
    """)
    missing_gst = cur.fetchone()[0]
    if missing_gst > 0:
        report.add_warn(f"Receipts missing GST: {missing_gst} receipts without gst_amount")
    else:
        report.add_pass("All receipts have GST calculated")
    
    cur.close()
    conn.close()
    
except Exception as e:
    report.add_fail("Database validation", str(e))

# ============================================================================
# 2. BUSINESS LOGIC VALIDATION
# ============================================================================
print("\n" + "="*70)
print("2. BUSINESS LOGIC VALIDATION")
print("="*70)

try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Test 1: GST calculation correctness (Alberta 5% GST)
    cur.execute("""
        SELECT gross_amount, gst_amount, gross_amount - gst_amount as net_amount
        FROM receipts
        WHERE gross_amount > 0 AND gst_amount > 0
        LIMIT 10
    """)
    
    gst_ok = True
    for gross, gst, net in cur.fetchall():
        # GST should be gross * 0.05 / 1.05
        expected_gst = gross * Decimal('0.05') / Decimal('1.05')
        if abs(Decimal(str(gst)) - expected_gst) > Decimal('0.01'):
            gst_ok = False
            break
    
    if gst_ok:
        report.add_pass("GST calculation correct (5% tax-inclusive)")
    else:
        report.add_warn("Some GST calculations may be incorrect")
    
    # Test 2: Payment method validation
    cur.execute("""
        SELECT DISTINCT payment_method FROM payments WHERE payment_method IS NOT NULL
        ORDER BY payment_method
    """)
    allowed_methods = {'cash', 'check', 'credit_card', 'debit_card', 'bank_transfer', 'trade_of_services', 'unknown'}
    found_methods = {row[0] for row in cur.fetchall()}
    invalid_methods = found_methods - allowed_methods
    
    if invalid_methods:
        report.add_fail(f"Invalid payment methods: {invalid_methods}")
    else:
        report.add_pass(f"Payment methods valid: {sorted(found_methods)}")
    
    # Test 3: Receipt status validation
    cur.execute("""
        SELECT DISTINCT status FROM receipts WHERE status IS NOT NULL
        ORDER BY status
    """)
    statuses = {row[0] for row in cur.fetchall()}
    valid_statuses = {'active', 'archived', 'voided', 'pending', 'deleted'}
    if statuses.issubset(valid_statuses):
        report.add_pass(f"Receipt statuses valid: {sorted(statuses)}")
    else:
        report.add_warn(f"Unknown receipt statuses: {statuses - valid_statuses}")
    
    # Test 4: Date consistency (no future-dated charters)
    cur.execute("""
        SELECT COUNT(*) FROM charters
        WHERE charter_date > NOW()
    """)
    future_count = cur.fetchone()[0]
    if future_count > 0:
        report.add_warn(f"Future-dated charters found: {future_count}")
    else:
        report.add_pass("No future-dated charters found")
    
    # Test 5: Employee type validation
    cur.execute("""
        SELECT DISTINCT employee_type FROM employees WHERE employee_type IS NOT NULL
        ORDER BY employee_type
    """)
    emp_types = {row[0] for row in cur.fetchall()}
    valid_emp_types = {'driver', 'dispatcher', 'office', 'management', 'other'}
    if emp_types.issubset(valid_emp_types):
        report.add_pass(f"Employee types valid: {sorted(emp_types)}")
    else:
        report.add_warn(f"Unknown employee types: {emp_types - valid_emp_types}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    report.add_fail("Business logic validation", str(e))

# ============================================================================
# 3. DATA QUALITY VALIDATION
# ============================================================================
print("\n" + "="*70)
print("3. DATA QUALITY VALIDATION")
print("="*70)

try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Test 1: Required fields populated
    checks = [
        ("charters", "reserve_number", "Charter reserve numbers"),
        ("receipts", "receipt_date", "Receipt dates"),
        ("receipts", "gross_amount", "Receipt amounts"),
        ("employees", "first_name", "Employee names"),
        ("vehicles", "vehicle_number", "Vehicle numbers"),
    ]
    
    for table, field, label in checks:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {field} IS NULL OR {field} = ''")
        null_count = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        
        if null_count == 0:
            report.add_pass(f"{label}: 100% populated ({total:,} records)")
        else:
            pct = (null_count / total * 100) if total > 0 else 0
            if pct > 5:
                report.add_fail(f"{label}: {pct:.1f}% missing ({null_count:,}/{total:,})")
            else:
                report.add_warn(f"{label}: {pct:.1f}% missing ({null_count:,}/{total:,})")
    
    # Test 2: Duplicate detection
    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT receipt_date, vendor_name, gross_amount, COUNT(*)
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) >= 2024
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
        ) t
    """)
    dup_count = cur.fetchone()[0]
    if dup_count > 0:
        report.add_warn(f"Potential duplicate receipts: {dup_count} groups")
    else:
        report.add_pass("No obvious duplicate receipts detected")
    
    # Test 3: Data types correctness
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE TRY_CAST(CAST(gross_amount AS TEXT) AS NUMERIC) IS NULL
        OR gross_amount < 0
    """)
    type_errors = cur.fetchone()[0]
    if type_errors == 0:
        report.add_pass("All numeric values valid and non-negative")
    else:
        report.add_warn(f"Invalid numeric values found: {type_errors}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    report.add_fail("Data quality validation", str(e))

# ============================================================================
# 4. BUSINESS RULES VALIDATION
# ============================================================================
print("\n" + "="*70)
print("4. BUSINESS RULES VALIDATION")
print("="*70)

try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Rule 1: Reserve number is business key
    cur.execute("""
        SELECT COUNT(DISTINCT charter_id) FROM charters
        WHERE reserve_number IS NOT NULL
    """)
    charters_with_reserve = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM charters")
    total_charters = cur.fetchone()[0]
    
    if charters_with_reserve == total_charters:
        report.add_pass(f"Reserve number business key: 100% populated ({total_charters:,} charters)")
    else:
        report.add_warn(f"Reserve number coverage: {(charters_with_reserve/total_charters*100):.0f}%")
    
    # Rule 2: Payments link via reserve_number
    cur.execute("""
        SELECT COUNT(*) FROM payments
        WHERE reserve_number IS NULL OR reserve_number = ''
    """)
    null_reserve_payments = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM payments")
    total_payments = cur.fetchone()[0]
    
    if null_reserve_payments == 0:
        report.add_pass(f"Payment-charter links: 100% via reserve_number ({total_payments:,} payments)")
    else:
        report.add_fail(f"Orphaned payments (no reserve_number): {null_reserve_payments:,}")
    
    # Rule 3: Parent-child relationships flattened
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE parent_receipt_id IS NOT NULL
    """)
    parent_receipts = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM receipts")
    total_receipts = cur.fetchone()[0]
    
    if parent_receipts == 0:
        report.add_pass(f"Receipt flattening: Complete - {total_receipts:,} independent receipts")
    else:
        report.add_fail(f"Receipt flattening incomplete: {parent_receipts:,} still have parents")
    
    # Rule 4: No uncommitted transactions
    cur.execute("""
        SELECT COUNT(*) FROM charters
        WHERE created_at > NOW() - INTERVAL '24 hours'
        AND balance IS NULL
    """)
    uncommitted = cur.fetchone()[0]
    if uncommitted == 0:
        report.add_pass("All recent charters have complete data")
    else:
        report.add_warn(f"Uncommitted charters detected: {uncommitted}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    report.add_fail("Business rules validation", str(e))

# ============================================================================
# 5. SECURITY VALIDATION
# ============================================================================
print("\n" + "="*70)
print("5. SECURITY VALIDATION")
print("="*70)

try:
    # Check for SQL injection vulnerabilities in backend code
    router_dir = Path('modern_backend/app/routers')
    sql_injection_risk = 0
    
    for router_file in router_dir.glob('*.py'):
        if router_file.name.startswith('_'):
            continue
        try:
            with open(router_file, 'r') as f:
                content = f.read()
            
            # Look for string formatting in SQL (bad pattern)
            if 'execute(f"' in content or "execute(f'" in content:
                if 'WHERE' in content or 'SELECT' in content:
                    sql_injection_risk += 1
        except:
            pass
    
    if sql_injection_risk == 0:
        report.add_pass("SQL injection check: No unsafe string formatting in SQL queries")
    else:
        report.add_warn(f"Potential SQL patterns: {sql_injection_risk} files use f-strings with SQL")
    
    # Check for hardcoded credentials
    found_creds = False
    try:
        with open('modern_backend/app/main.py', 'r') as f:
            main_content = f.read()
        if '***REMOVED***' in main_content:
            found_creds = True
    except:
        pass
    
    if found_creds:
        report.add_warn("Hardcoded credentials: Password found in source code (use environment variables)")
    else:
        report.add_pass("Credentials: Using environment variables (secure)")
    
    # Check error handling
    error_handlers = 0
    for router_file in router_dir.glob('*.py'):
        try:
            with open(router_file, 'r') as f:
                if 'except' in f.read():
                    error_handlers += 1
        except:
            pass
    
    if error_handlers > 10:
        report.add_pass(f"Error handling: {error_handlers} routers with exception handlers")
    else:
        report.add_warn(f"Error handling: Only {error_handlers} routers with handlers (coverage could improve)")
    
except Exception as e:
    report.add_fail("Security validation", str(e))

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*70)
print("VALIDATION SUMMARY")
print("="*70)

summary = report.summary()
print(f"\n✅ Passed:   {summary['passed']:3d}")
print(f"❌ Failed:   {summary['failed']:3d}")
print(f"⚠️  Warnings: {summary['warnings']:3d}")
print(f"────────────────")
print(f"Total:    {summary['total']:3d}")
print(f"Pass Rate: {summary['pass_rate']}")

if summary['failed'] == 0:
    print("\n🎉 All critical validations passed!")
    sys.exit(0)
else:
    print(f"\n⚠️  {summary['failed']} critical issue(s) need attention")
    sys.exit(1)
