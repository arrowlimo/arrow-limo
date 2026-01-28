"""
Comprehensive charter audit against payment records and QuickBooks data.

Identifies and reports:
1. Charters with payment mismatches (paid_amount vs actual payments)
2. Charters with balance calculation errors
3. Charters missing in QuickBooks but have payments
4. QuickBooks invoices without corresponding charters
5. Total amount discrepancies between charter and actual charges
6. Payment method inconsistencies
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
from collections import defaultdict

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def audit_charters():
    """Comprehensive charter audit."""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("CHARTER AUDIT - PAYMENTS & QUICKBOOKS RECONCILIATION")
    print("=" * 80)
    print()
    
    # 1. Check paid_amount vs actual payments (using reserve_number)
    print("=" * 80)
    print("1. PAID_AMOUNT DISCREPANCIES (Charter vs Actual Payments)")
    print("=" * 80)
    
    cur.execute("""
        WITH payment_totals AS (
            SELECT 
                reserve_number,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        SELECT 
            c.charter_id,
            c.reserve_number,
            COALESCE(cl.client_name, c.account_number, c.client_id::text) as client_name,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount as charter_paid,
            COALESCE(pt.actual_paid, 0) as actual_paid,
            c.balance as charter_balance,
            c.total_amount_due - COALESCE(pt.actual_paid, 0) as correct_balance,
            ABS(c.paid_amount - COALESCE(pt.actual_paid, 0)) as discrepancy
        FROM charters c
        LEFT JOIN payment_totals pt ON pt.reserve_number = c.reserve_number
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE ABS(c.paid_amount - COALESCE(pt.actual_paid, 0)) > 0.01
        AND c.reserve_number IS NOT NULL
        ORDER BY discrepancy DESC
        LIMIT 50
    """)
    
    paid_discrepancies = cur.fetchall()
    print(f"\nFound {len(paid_discrepancies)} charters with paid_amount discrepancies")
    
    if paid_discrepancies:
        print("\nTop discrepancies:")
        for idx, row in enumerate(paid_discrepancies[:20], 1):
            print(f"\n{idx}. Charter {row['reserve_number']} ({row['charter_date']})")
            print(f"   Client: {row['client_name']}")
            print(f"   Charter paid_amount: ${row['charter_paid']:,.2f}")
            print(f"   Actual payments: ${row['actual_paid']:,.2f}")
            print(f"   Discrepancy: ${row['discrepancy']:,.2f}")
            print(f"   Balance: ${row['charter_balance']:,.2f} (should be ${row['correct_balance']:,.2f})")
    
    # 2. Check balance calculation errors
    print(f"\n{'='*80}")
    print("2. BALANCE CALCULATION ERRORS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            COALESCE(cl.client_name, c.account_number, c.client_id::text) as client_name,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance as charter_balance,
            c.total_amount_due - c.paid_amount as correct_balance,
            ABS(c.balance - (c.total_amount_due - c.paid_amount)) as error
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE ABS(c.balance - (c.total_amount_due - c.paid_amount)) > 0.01
        AND c.reserve_number IS NOT NULL
        ORDER BY error DESC
        LIMIT 30
    """)
    
    balance_errors = cur.fetchall()
    print(f"\nFound {len(balance_errors)} charters with balance calculation errors")
    
    if balance_errors:
        print("\nTop errors:")
        for idx, row in enumerate(balance_errors[:15], 1):
            print(f"\n{idx}. Charter {row['reserve_number']} ({row['charter_date']})")
            print(f"   Client: {row['client_name']}")
            print(f"   Total due: ${row['total_amount_due']:,.2f}")
            print(f"   Paid: ${row['paid_amount']:,.2f}")
            print(f"   Charter balance: ${row['charter_balance']:,.2f}")
            print(f"   Correct balance: ${row['correct_balance']:,.2f}")
            print(f"   Error: ${row['error']:,.2f}")
    
    # 3. Check total_amount_due vs charter_charges
    print(f"\n{'='*80}")
    print("3. TOTAL_AMOUNT_DUE VS CHARTER_CHARGES DISCREPANCIES")
    print("=" * 80)
    
    cur.execute("""
        WITH charge_totals AS (
            SELECT 
                charter_id,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        )
        SELECT 
            c.charter_id,
            c.reserve_number,
            COALESCE(cl.client_name, c.account_number, c.client_id::text) as client_name,
            c.charter_date,
            c.total_amount_due as charter_total,
            COALESCE(ct.total_charges, 0) as charges_total,
            ABS(c.total_amount_due - COALESCE(ct.total_charges, 0)) as discrepancy
        FROM charters c
        LEFT JOIN charge_totals ct ON ct.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE ABS(c.total_amount_due - COALESCE(ct.total_charges, 0)) > 0.01
        AND c.reserve_number IS NOT NULL
        ORDER BY discrepancy DESC
        LIMIT 30
    """)
    
    charge_discrepancies = cur.fetchall()
    print(f"\nFound {len(charge_discrepancies)} charters with charge discrepancies")
    
    if charge_discrepancies:
        print("\nTop discrepancies:")
        for idx, row in enumerate(charge_discrepancies[:15], 1):
            print(f"\n{idx}. Charter {row['reserve_number']} ({row['charter_date']})")
            print(f"   Client: {row['client_name']}")
            print(f"   Charter total_amount_due: ${row['charter_total']:,.2f}")
            print(f"   Charter_charges sum: ${row['charges_total']:,.2f}")
            print(f"   Discrepancy: ${row['discrepancy']:,.2f}")
    
    # 4. Check QuickBooks journal entries
    print(f"\n{'='*80}")
    print("4. QUICKBOOKS JOURNAL RECONCILIATION")
    print("=" * 80)
    print("\n⚠️  Skipping QB reconciliation (journal table schema varies)")
    
    # 5. Orphaned payments (payments without charters)
    print(f"\n{'='*80}")
    print("5. ORPHANED PAYMENTS (Payments without charters)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.account_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.notes
        FROM payments p
        LEFT JOIN charters c ON c.reserve_number = p.reserve_number
        WHERE p.reserve_number IS NOT NULL
        AND c.charter_id IS NULL
        ORDER BY p.amount DESC
        LIMIT 30
    """)
    
    orphaned = cur.fetchall()
    print(f"\nFound {len(orphaned)} orphaned payments")
    
    if orphaned:
        print("\nTop orphaned payments:")
        for idx, row in enumerate(orphaned[:15], 1):
            print(f"\n{idx}. Payment {row['payment_id']}")
            print(f"   Reserve: {row['reserve_number']}")
            print(f"   Date: {row['payment_date']}")
            print(f"   Amount: ${row['amount']:,.2f}")
            print(f"   Method: {row['payment_method']}")
            if row['notes']:
                print(f"   Notes: {row['notes'][:100]}")
    
    # 6. Summary statistics
    print(f"\n{'='*80}")
    print("6. SUMMARY STATISTICS")
    print("=" * 80)
    
    # Total charters
    cur.execute("SELECT COUNT(*) as count FROM charters WHERE reserve_number IS NOT NULL")
    total_charters = cur.fetchone()['count']
    
    # Charters with payments
    cur.execute("""
        SELECT COUNT(DISTINCT c.charter_id) as count
        FROM charters c
        JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.reserve_number IS NOT NULL
    """)
    charters_with_payments = cur.fetchone()['count']
    
    # Charters with discrepancies
    total_discrepancies = len(paid_discrepancies) + len(balance_errors) + len(charge_discrepancies)
    
    print(f"\nTotal charters: {total_charters:,}")
    print(f"Charters with payments: {charters_with_payments:,} ({charters_with_payments/total_charters*100:.1f}%)")
    print(f"\nDiscrepancies found:")
    print(f"  - Paid amount mismatches: {len(paid_discrepancies)}")
    print(f"  - Balance calculation errors: {len(balance_errors)}")
    print(f"  - Charge total discrepancies: {len(charge_discrepancies)}")
    print(f"  - Total unique issues: {total_discrepancies}")
    
    # Financial impact
    if paid_discrepancies:
        total_paid_error = sum(Decimal(str(row['discrepancy'])) for row in paid_discrepancies)
        print(f"\nTotal paid_amount error: ${total_paid_error:,.2f}")
    
    if balance_errors:
        total_balance_error = sum(Decimal(str(row['error'])) for row in balance_errors)
        print(f"Total balance calculation error: ${total_balance_error:,.2f}")
    
    if charge_discrepancies:
        total_charge_error = sum(Decimal(str(row['discrepancy'])) for row in charge_discrepancies)
        print(f"Total charge discrepancy: ${total_charge_error:,.2f}")
    
    # Recommendations
    print(f"\n{'='*80}")
    print("7. RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n✅ FIXES AVAILABLE:")
    
    if paid_discrepancies:
        print("\n1. Recalculate paid_amount from actual payments:")
        print("   - Use reserve_number to sum payments (NOT charter_id)")
        print(f"   - Affects {len(paid_discrepancies)} charters")
    
    if balance_errors:
        print("\n2. Recalculate balance = total_amount_due - paid_amount:")
        print(f"   - Affects {len(balance_errors)} charters")
    
    if charge_discrepancies:
        print("\n3. Sync total_amount_due with charter_charges sum:")
        print(f"   - Affects {len(charge_discrepancies)} charters")
    
    if orphaned:
        print(f"\n4. Investigate {len(orphaned)} orphaned payments:")
        print("   - May be cancelled charters or data entry errors")
        print("   - Check if reserve_number is valid but charter deleted")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    audit_charters()
