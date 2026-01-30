"""
Check Square and Loan Payment Integration Status
- Verify if Square is connected and payments are synced
- Check loan payment records (vehicle loans, payday loans, Square capital loans)
- Confirm if payments are linked to charters
"""
import os
import psycopg2
from datetime import datetime
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

def connect():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def check_square_status():
    """Check Square integration status"""
    print("=" * 120)
    print("SQUARE INTEGRATION STATUS")
    print("=" * 120)
    
    conn = connect()
    cur = conn.cursor()
    
    # Check Square transactions in staging
    cur.execute("SELECT COUNT(*) FROM square_transactions_staging")
    staging_count = cur.fetchone()[0]
    
    # Check if any payments have square_transaction_id
    cur.execute("SELECT COUNT(*) FROM payments WHERE square_transaction_id IS NOT NULL")
    payments_with_square = cur.fetchone()[0]
    
    # Check Square customers
    cur.execute("SELECT COUNT(*) FROM square_customers")
    square_customers = cur.fetchone()[0]
    
    # Check Square deposits staging
    cur.execute("SELECT COUNT(*) FROM square_deposits_staging")
    square_deposits = cur.fetchone()[0]
    
    print(f"\n📊 SQUARE CONFIGURATION STATUS:")
    print(f"  Square Transactions (Staging): {staging_count:,}")
    print(f"  Payments with Square TX ID: {payments_with_square:,}")
    print(f"  Square Customers: {square_customers:,}")
    print(f"  Square Deposits (Staging): {square_deposits:,}")
    
    if staging_count > 0:
        print(f"\n✅ Square data exists in staging tables but NOT YET synced to payments table")
    elif payments_with_square > 0:
        print(f"\n✅ Square is connected and {payments_with_square:,} payments have Square transaction IDs")
    else:
        print(f"\n⚠️  Square appears to be configured but NO payments have Square transaction IDs")
        print(f"    Staging tables: {staging_count:,} transactions")
        print(f"    This suggests Square data exists but hasn't been imported to payments table")
    
    conn.close()

def check_loan_payments():
    """Check loan payment records"""
    print("\n" + "=" * 120)
    print("LOAN PAYMENT INTEGRATION STATUS")
    print("=" * 120)
    
    conn = connect()
    cur = conn.cursor()
    
    # Vehicle loans
    cur.execute("SELECT COUNT(*), SUM(balance_remaining) FROM vehicle_loans WHERE balance_remaining > 0")
    row = cur.fetchone()
    active_vehicle_loans = row[0]
    vehicle_balance = row[1] if row[1] else 0.0
    
    cur.execute("SELECT COUNT(*), SUM(amount) FROM vehicle_loan_payments")
    row = cur.fetchone()
    vehicle_loan_payments = row[0]
    vehicle_payments_total = row[1] if row[1] else 0.0
    
    # Payday loans
    cur.execute("SELECT COUNT(*), SUM(balance_remaining) FROM payday_loans WHERE balance_remaining > 0")
    row = cur.fetchone()
    active_payday_loans = row[0]
    payday_balance = row[1] if row[1] else 0.0
    
    cur.execute("SELECT COUNT(*) FROM payday_loan_payments")
    payday_loan_payments = cur.fetchone()[0]
    
    # Square Capital loans
    cur.execute("SELECT COUNT(*), SUM(balance) FROM square_capital_loans WHERE balance > 0")
    row = cur.fetchone()
    square_capital_loans = row[0]
    square_capital_balance = row[1] if row[1] else 0.0
    
    cur.execute("SELECT COUNT(*) FROM square_loan_payments")
    square_loan_payments = cur.fetchone()[0]
    
    # Loan transactions (general)
    cur.execute("SELECT COUNT(*), SUM(amount) FROM loan_transactions")
    row = cur.fetchone()
    loan_transactions = row[0]
    loan_transactions_total = row[1] if row[1] else 0.0
    
    print(f"\n📊 VEHICLE LOANS:")
    print(f"  Active Loans: {active_vehicle_loans:,}")
    print(f"  Outstanding Balance: ${vehicle_balance:,.2f}")
    print(f"  Payments Recorded: {vehicle_loan_payments:,}")
    print(f"  Total Paid: ${vehicle_payments_total:,.2f}")
    
    print(f"\n📊 PAYDAY LOANS:")
    print(f"  Active Loans: {active_payday_loans:,}")
    print(f"  Outstanding Balance: ${payday_balance:,.2f}")
    print(f"  Payments Recorded: {payday_loan_payments:,}")
    
    print(f"\n📊 SQUARE CAPITAL LOANS:")
    print(f"  Active Loans: {square_capital_loans:,}")
    print(f"  Outstanding Balance: ${square_capital_balance:,.2f}")
    print(f"  Payments Recorded: {square_loan_payments:,}")
    
    print(f"\n📊 GENERAL LOAN TRANSACTIONS:")
    print(f"  Total Transactions: {loan_transactions:,}")
    print(f"  Total Amount: ${loan_transactions_total:,.2f}")
    
    # Check if loan payments are linked to charters
    cur.execute("""
        SELECT COUNT(DISTINCT charter_id)
        FROM vehicle_loan_payments
        WHERE charter_id IS NOT NULL
    """)
    charters_with_vehicle_loans = cur.fetchone()[0]
    
    print(f"\n📊 CHARTER LINKAGE:")
    print(f"  Charters with Vehicle Loan Payments: {charters_with_vehicle_loans:,}")
    
    conn.close()

def check_charter_payment_reconciliation():
    """Check if charter payments include loan payments"""
    print("\n" + "=" * 120)
    print("CHARTER PAYMENT RECONCILIATION")
    print("=" * 120)
    
    conn = connect()
    cur = conn.cursor()
    
    # Check if charter paid_amount includes all payment types
    cur.execute("""
        SELECT 
            COUNT(DISTINCT c.reserve_number) as charters_with_data,
            SUM(c.total_amount_due) as total_due,
            SUM(c.paid_amount) as recorded_paid,
            SUM(p_payments.total_payments) as payments_table_total,
            SUM(c.balance) as total_balance
        FROM charters c
        LEFT JOIN (
            SELECT reserve_number, SUM(amount) as total_payments
            FROM payments
            GROUP BY reserve_number
        ) p_payments ON p_payments.reserve_number = c.reserve_number
    """)
    
    row = cur.fetchone()
    charters = row[0]
    total_due = row[1] if row[1] else 0.0
    recorded_paid = row[2] if row[2] else 0.0
    payments_total = row[3] if row[3] else 0.0
    total_balance = row[4] if row[4] else 0.0
    
    print(f"\n📊 CHARTER PAYMENT STATUS:")
    print(f"  Total Charters: {charters:,}")
    print(f"  Total Amount Due: ${total_due:,.2f}")
    print(f"  Total Recorded Paid: ${recorded_paid:,.2f}")
    print(f"  Payments Table Total: ${payments_total:,.2f}")
    print(f"  Total Balance: ${total_balance:,.2f}")
    
    # Check if paid_amount matches payments table sum
    if abs(float(recorded_paid - (payments_total or 0))) > 100:
        print(f"\n⚠️  DISCREPANCY DETECTED:")
        print(f"    Charter.paid_amount: ${recorded_paid:,.2f}")
        print(f"    SUM(payments): ${payments_total:,.2f}")
        print(f"    Difference: ${abs(recorded_paid - (payments_total or 0)):,.2f}")
    else:
        print(f"\n✅ Charter paid_amount matches payments table total")
    
    conn.close()

def main():
    print("=" * 120)
    print("SQUARE & LOAN PAYMENT INTEGRATION AUDIT")
    print("=" * 120)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    check_square_status()
    check_loan_payments()
    check_charter_payment_reconciliation()
    
    print("\n" + "=" * 120)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 120)
    print("""
1. SQUARE INTEGRATION:
   - If staging tables have data but payments table doesn't: Need to run Square import
   - If no square_transaction_id in payments: Square data not synced yet
   
2. LOAN PAYMENTS:
   - Vehicle loans, payday loans, Square Capital loans tracked separately
   - Check if loan payments should be included in charter.paid_amount calculation
   
3. PAYMENT RECONCILIATION:
   - Verify charter.paid_amount = SUM(payments) + loan_payments
   - If discrepancy exists, may need to reconcile or update payment sources
""")

if __name__ == "__main__":
    main()
