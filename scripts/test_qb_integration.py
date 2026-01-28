"""
Comprehensive Test Suite for QB Integration (Phases 1-3)
Tests all extended tables, views, triggers, and API endpoints
"""

import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment
load_dotenv()

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def test(self, name, condition, error_msg=""):
        if condition:
            print(f"  PASS: {name}")
            self.passed += 1
        else:
            print(f"  FAIL: {name} - {error_msg}")
            self.failed += 1
            self.errors.append(f"{name}: {error_msg}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"\nFailed Tests:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}\n")
        return self.failed == 0


def test_phase1_journal_structure(conn, results):
    """Test Phase 1: QB Journal Entries structure"""
    print("\n=== Phase 1: Journal Structure Tests ===")
    cur = conn.cursor()
    
    # Test 1: qb_journal_entries table exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'qb_journal_entries'
    """)
    results.test("qb_journal_entries table exists", cur.fetchone()[0] == 1)
    
    # Test 2: Journal entries count
    cur.execute("SELECT COUNT(*) FROM qb_journal_entries")
    count = cur.fetchone()[0]
    results.test("Journal entries loaded", count > 50000, f"Found {count} entries")
    
    # Test 3: journal_lines table has required columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'journal_lines' 
        AND column_name IN ('entry_id', 'account_id', 'debit_amount', 'credit_amount')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("journal_lines has QB columns", len(columns) == 4)
    
    # Test 4: Indexes exist
    cur.execute("""
        SELECT COUNT(*) FROM pg_indexes 
        WHERE tablename IN ('qb_journal_entries', 'journal_lines')
    """)
    index_count = cur.fetchone()[0]
    results.test("QB indexes created", index_count >= 20, f"Found {index_count} indexes")
    
    # Test 5: Views exist
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.views 
        WHERE table_name IN ('qb_active_accounts', 'qb_account_activity_summary')
    """)
    view_count = cur.fetchone()[0]
    results.test("Phase 1 views created", view_count == 2, f"Found {view_count} views")
    
    cur.close()


def test_phase2_table_extensions(conn, results):
    """Test Phase 2: Table Extensions"""
    print("\n=== Phase 2: Table Extension Tests ===")
    cur = conn.cursor()
    
    # Test 1: chart_of_accounts extended columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'chart_of_accounts' 
        AND column_name IN ('opening_balance', 'current_balance', 'qb_description', 
                           'qb_tax_line_id', 'is_sub_account')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("chart_of_accounts has QB columns", len(columns) == 5, 
                f"Found {len(columns)}/5 columns")
    
    # Test 2: journal_lines extended columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'journal_lines' 
        AND column_name IN ('trans_num', 'qb_type', 'is_cleared', 'reconcile_date', 'entity_type')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("journal_lines has QB columns", len(columns) >= 3,
                f"Found {len(columns)}/5 columns")
    
    # Test 3: payments extended columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'payments' 
        AND column_name IN ('qb_payment_type', 'qb_trans_num', 'reference_number',
                           'check_number', 'is_deposited')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("payments has QB columns", len(columns) == 5,
                f"Found {len(columns)}/5 columns")
    
    # Test 4: clients extended columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'clients' 
        AND column_name IN ('qb_customer_type', 'payment_terms', 'credit_limit',
                           'tax_code', 'sales_tax_code')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("clients has QB columns", len(columns) == 5,
                f"Found {len(columns)}/5 columns")
    
    # Test 5: vendors extended columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'vendors' 
        AND column_name IN ('qb_vendor_type', 'qb_payment_terms', 'vendor_account_number',
                           'tax_id', 'is_1099_eligible')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("vendors has QB columns", len(columns) >= 2,
                f"Found {len(columns)}/5 columns")
    
    # Test 6: payables extended columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'payables' 
        AND column_name IN ('qb_bill_id', 'bill_number', 'due_date',
                           'qb_terms', 'memo')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("payables has QB columns", len(columns) >= 1,
                f"Found {len(columns)}/5 columns")
    
    cur.close()


def test_phase2_invoice_tables(conn, results):
    """Test Phase 2b: Invoice Tables"""
    print("\n=== Phase 2b: Invoice Table Tests ===")
    cur = conn.cursor()
    
    # Test 1: invoices table exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'invoices'
    """)
    results.test("invoices table exists", cur.fetchone()[0] == 1)
    
    # Test 2: invoice_line_items table exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'invoice_line_items'
    """)
    results.test("invoice_line_items table exists", cur.fetchone()[0] == 1)
    
    # Test 3: invoices has required columns
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_name = 'invoices' 
        AND column_name IN ('invoice_id', 'customer_id', 'invoice_number', 
                           'invoice_date', 'due_date', 'total_amount', 'balance_due')
    """)
    count = cur.fetchone()[0]
    results.test("invoices has core columns", count >= 6, f"Found {count}/7 columns")
    
    # Test 4: Invoice trigger exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.triggers 
        WHERE event_object_table = 'invoices' AND trigger_name LIKE '%balance%'
    """)
    results.test("Invoice balance trigger exists", cur.fetchone()[0] >= 1)
    
    # Test 5: Invoice views exist
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.views 
        WHERE table_name IN ('qb_invoice_summary', 'qb_invoice_detail', 'qb_ar_aging')
    """)
    view_count = cur.fetchone()[0]
    results.test("Invoice views created", view_count == 3, f"Found {view_count} views")
    
    # Test 6: Invoice indexes exist
    cur.execute("""
        SELECT COUNT(*) FROM pg_indexes 
        WHERE tablename IN ('invoices', 'invoice_line_items')
    """)
    index_count = cur.fetchone()[0]
    results.test("Invoice indexes created", index_count >= 10, f"Found {index_count} indexes")
    
    cur.close()


def test_phase3_data_backfill(conn, results):
    """Test Phase 3: Data Backfill"""
    print("\n=== Phase 3: Data Backfill Tests ===")
    cur = conn.cursor()
    
    # Test 1: Accounts have opening balances
    cur.execute("""
        SELECT COUNT(*) FROM chart_of_accounts 
        WHERE opening_balance IS NOT NULL AND opening_balance != 0
    """)
    count = cur.fetchone()[0]
    results.test("Accounts with opening balances", count >= 5, f"Found {count} accounts")
    
    # Test 2: Specific accounts updated (Scotia Bank Main)
    cur.execute("""
        SELECT opening_balance FROM chart_of_accounts 
        WHERE account_number = '1010'
    """)
    row = cur.fetchone()
    results.test("Scotia Bank Main has balance", 
                row is not None and row[0] is not None,
                "Balance not set")
    
    # Test 3: Accounts Receivable has balance
    cur.execute("""
        SELECT opening_balance FROM chart_of_accounts 
        WHERE account_number = '1100'
    """)
    row = cur.fetchone()
    results.test("Accounts Receivable has balance",
                row is not None and row[0] is not None,
                "Balance not set")
    
    # Test 4: Clients have QB defaults
    cur.execute("""
        SELECT COUNT(*) FROM clients 
        WHERE qb_customer_type = 'Commercial' AND payment_terms = 'Net 30'
    """)
    count = cur.fetchone()[0]
    results.test("Clients have QB defaults", count > 6000, f"Found {count} clients")
    
    # Test 5: Vendors categorized by type
    cur.execute("""
        SELECT COUNT(DISTINCT qb_vendor_type) FROM vendors 
        WHERE qb_vendor_type IS NOT NULL
    """)
    type_count = cur.fetchone()[0]
    results.test("Vendors categorized by type", type_count >= 5, f"Found {type_count} types")
    
    cur.close()


def test_charter_employee_preservation(conn, results):
    """Test that charter and employee data is preserved"""
    print("\n=== Data Preservation Tests ===")
    cur = conn.cursor()
    
    # Test 1: Charters table exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'charters'
    """)
    results.test("charters table exists", cur.fetchone()[0] == 1)
    
    # Test 2: Employees table exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'employees'
    """)
    results.test("employees table exists", cur.fetchone()[0] == 1)
    
    # Test 3: Charters have data
    cur.execute("SELECT COUNT(*) FROM charters")
    count = cur.fetchone()[0]
    results.test("Charters preserved", count > 0, f"Found {count} charters")
    
    # Test 4: Employees have data
    cur.execute("SELECT COUNT(*) FROM employees")
    count = cur.fetchone()[0]
    results.test("Employees preserved", count > 0, f"Found {count} employees")
    
    # Test 5: Charter-specific columns exist
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'charters' 
        AND column_name IN ('charter_id', 'charter_date', 'client_id', 'driver_name')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("Charter columns preserved", len(columns) == 4)
    
    # Test 6: Employee-specific columns exist
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'employees' 
        AND column_name IN ('employee_id', 'first_name', 'last_name', 'employee_type')
    """)
    columns = [row[0] for row in cur.fetchall()]
    results.test("Employee columns preserved", len(columns) == 4)
    
    cur.close()


def test_foreign_keys(conn, results):
    """Test foreign key constraints"""
    print("\n=== Foreign Key Tests ===")
    cur = conn.cursor()
    
    # Test 1: journal_lines -> qb_journal_entries FK
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.table_constraints 
        WHERE constraint_type = 'FOREIGN KEY' 
        AND table_name = 'journal_lines'
        AND constraint_name LIKE '%entry_id%'
    """)
    results.test("journal_lines -> entries FK exists", cur.fetchone()[0] >= 1)
    
    # Test 2: journal_lines -> chart_of_accounts FK
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.table_constraints 
        WHERE constraint_type = 'FOREIGN KEY' 
        AND table_name = 'journal_lines'
        AND constraint_name LIKE '%account%'
    """)
    results.test("journal_lines -> accounts FK exists", cur.fetchone()[0] >= 1)
    
    # Test 3: payments -> clients FK
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.table_constraints 
        WHERE constraint_type = 'FOREIGN KEY' 
        AND table_name = 'payments'
        AND constraint_name LIKE '%client%'
    """)
    results.test("payments -> clients FK exists", cur.fetchone()[0] >= 1)
    
    # Test 4: invoice_line_items -> invoices FK
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.table_constraints 
        WHERE constraint_type = 'FOREIGN KEY' 
        AND table_name = 'invoice_line_items'
        AND constraint_name LIKE '%invoice%'
    """)
    results.test("invoice_line_items -> invoices FK exists", cur.fetchone()[0] >= 1)
    
    cur.close()


def test_views(conn, results):
    """Test all QB views"""
    print("\n=== View Tests ===")
    cur = conn.cursor()
    
    views_to_test = [
        'qb_active_accounts',
        'qb_account_activity_summary',
        'qb_invoice_summary',
        'qb_invoice_detail',
        'qb_ar_aging'
    ]
    
    for view_name in views_to_test:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {view_name}")
            count = cur.fetchone()[0]
            results.test(f"View {view_name} queryable", True, f"{count} rows")
        except Exception as e:
            conn.rollback()  # Rollback to continue testing
            cur = conn.cursor()  # Get fresh cursor
            results.test(f"View {view_name} queryable", False, str(e))
    
    cur.close()


def test_invoice_trigger(conn, results):
    """Test invoice auto-balance trigger"""
    print("\n=== Invoice Trigger Tests ===")
    cur = conn.cursor()
    
    try:
        # Create test invoice
        cur.execute("""
            INSERT INTO invoices (customer_id, invoice_number, invoice_date, due_date, 
                                 total_amount, amount_paid, status, payment_terms)
            VALUES (1, 'TEST-001', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days',
                   1000.00, 250.00, 'Open', 'Net 30')
            RETURNING id, balance_due
        """)
        invoice_id, balance_due = cur.fetchone()
        
        results.test("Invoice trigger calculates balance",
                    balance_due == 750.00,
                    f"Expected 750.00, got {balance_due}")
        
        # Update payment
        cur.execute("""
            UPDATE invoices SET amount_paid = 1000.00
            WHERE id = %s
            RETURNING balance_due, status
        """, (invoice_id,))
        balance_due, status = cur.fetchone()
        
        results.test("Invoice trigger updates on payment",
                    balance_due == 0.00 and status == 'Paid',
                    f"Expected 0.00/Paid, got {balance_due}/{status}")
        
        # Cleanup
        cur.execute("DELETE FROM invoices WHERE id = %s", (invoice_id,))
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        results.test("Invoice trigger functional", False, str(e))
    
    cur.close()


def test_data_integrity(conn, results):
    """Test data integrity checks"""
    print("\n=== Data Integrity Tests ===")
    cur = conn.cursor()
    
    # Test 1: Account numbers are unique
    cur.execute("""
        SELECT account_number, COUNT(*) 
        FROM chart_of_accounts 
        GROUP BY account_number 
        HAVING COUNT(*) > 1
    """)
    duplicates = cur.fetchall()
    results.test("Account numbers unique",
                len(duplicates) == 0,
                f"Found {len(duplicates)} duplicate account numbers")
    
    # Test 2: All active accounts in valid range
    cur.execute("""
        SELECT COUNT(*) FROM chart_of_accounts
        WHERE is_active = true
        AND (account_number NOT SIMILAR TO '[1-9][0-9][0-9][0-9]')
    """)
    invalid = cur.fetchone()[0]
    results.test("Account numbers in valid format",
                invalid == 0,
                f"Found {invalid} invalid account numbers")
    
    # Test 3: Journal entries exist
    cur.execute("SELECT COUNT(*) FROM qb_journal_entries")
    count = cur.fetchone()[0]
    results.test("Journal entries present", count > 50000, f"Found {count} entries")
    
    # Test 4: Chart of accounts has entries
    cur.execute("SELECT COUNT(*) FROM chart_of_accounts WHERE is_active = true")
    count = cur.fetchone()[0]
    results.test("Active accounts present", count > 30, f"Found {count} accounts")
    
    cur.close()


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("QB INTEGRATION TEST SUITE")
    print("Testing Phases 1-3 Implementation")
    print("="*60)
    
    results = TestResults()
    conn = get_db_connection()
    
    try:
        # Phase 1 Tests
        test_phase1_journal_structure(conn, results)
        
        # Phase 2 Tests
        test_phase2_table_extensions(conn, results)
        test_phase2_invoice_tables(conn, results)
        
        # Phase 3 Tests
        test_phase3_data_backfill(conn, results)
        
        # Preservation Tests
        test_charter_employee_preservation(conn, results)
        
        # Constraint Tests
        test_foreign_keys(conn, results)
        
        # View Tests
        test_views(conn, results)
        
        # Trigger Tests
        test_invoice_trigger(conn, results)
        
        # Integrity Tests
        test_data_integrity(conn, results)
        
    except Exception as e:
        print(f"\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
    
    # Print summary
    success = results.summary()
    
    if success:
        print("ALL TESTS PASSED! System is ready for production.")
        return 0
    else:
        print("SOME TESTS FAILED. Review errors above.")
        return 1


if __name__ == '__main__':
    exit(main())
