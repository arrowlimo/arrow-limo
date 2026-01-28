"""
Complete Fibrenew reconciliation report:
- Statement entries (rent_debt_ledger)
- Receipt PDFs (from audit_records)
- Database receipts (receipts table)
- Banking transactions
"""
import psycopg2
from datetime import datetime
import os

os.environ['DB_HOST'] = 'localhost'
os.environ['DB_NAME'] = 'almsdata'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = '***REMOVED***'

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("FIBRENEW COMPLETE RECONCILIATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # 1. Rent Debt Ledger (Statement data)
    print("1. RENT DEBT LEDGER (Statement entries):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            transaction_type,
            COUNT(*) as count,
            SUM(charge_amount) as charges,
            SUM(payment_amount) as payments
        FROM rent_debt_ledger
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
        GROUP BY EXTRACT(YEAR FROM transaction_date), transaction_type
        ORDER BY year, transaction_type
    """)
    
    ledger_data = cur.fetchall()
    if ledger_data:
        print(f"{'Year':<6} {'Type':<10} {'Count':<8} {'Charges':<15} {'Payments':<15}")
        print("-" * 80)
        for year, txn_type, count, charges, payments in ledger_data:
            charges_str = f"${charges:,.2f}" if charges else ""
            payments_str = f"${payments:,.2f}" if payments else ""
            print(f"{int(year):<6} {txn_type:<10} {count:<8} {charges_str:<15} {payments_str:<15}")
        
        # Get current balance
        cur.execute("""
            SELECT running_balance
            FROM rent_debt_ledger
            WHERE LOWER(vendor_name) LIKE '%fibrenew%'
            ORDER BY transaction_date DESC, id DESC
            LIMIT 1
        """)
        balance = cur.fetchone()
        if balance:
            print()
            print(f"Current Balance Owed: ${balance[0]:,.2f}")
    else:
        print("  No entries found in rent_debt_ledger")
    print()
    
    # 2. Receipts Table
    print("2. RECEIPTS TABLE (Payments recorded):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as count,
            SUM(gross_amount) as total,
            COUNT(CASE WHEN created_from_banking THEN 1 END) as auto_created
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    receipt_data = cur.fetchall()
    total_receipts = 0
    total_amount = 0
    
    print(f"{'Year':<6} {'Count':<8} {'Total':<15} {'Auto-Created':<12}")
    print("-" * 80)
    for year, count, total, auto in receipt_data:
        print(f"{int(year):<6} {count:<8} ${total:,.2f}{'':<6} {auto:<12}")
        total_receipts += count
        total_amount += total or 0
    
    print("-" * 80)
    print(f"TOTAL  {total_receipts:<8} ${total_amount:,.2f}")
    print()
    
    # 3. Banking Transactions
    print("3. BANKING TRANSACTIONS (Fibrenew payments):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as count,
            SUM(debit_amount) as debits,
            SUM(credit_amount) as credits
        FROM banking_transactions
        WHERE LOWER(description) LIKE '%fibrenew%'
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    
    banking_data = cur.fetchall()
    if banking_data:
        print(f"{'Year':<6} {'Count':<8} {'Debits':<15} {'Credits':<15}")
        print("-" * 80)
        for year, count, debits, credits in banking_data:
            debit_str = f"${debits:,.2f}" if debits else ""
            credit_str = f"${credits:,.2f}" if credits else ""
            print(f"{int(year):<6} {count:<8} {debit_str:<15} {credit_str:<15}")
    else:
        print("  No Fibrenew transactions found in banking")
    print()
    
    # 4. Reconciliation Summary
    print("=" * 80)
    print("RECONCILIATION SUMMARY:")
    print("=" * 80)
    
    # Compare statement charges vs receipts payments
    cur.execute("""
        SELECT 
            COALESCE(SUM(charge_amount), 0) as total_charges,
            COALESCE(SUM(payment_amount), 0) as total_payments
        FROM rent_debt_ledger
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
    """)
    ledger_totals = cur.fetchone()
    
    print(f"Statement (rent_debt_ledger):")
    print(f"  Total Charges: ${ledger_totals[0]:,.2f}")
    print(f"  Total Payments: ${ledger_totals[1]:,.2f}")
    print(f"  Net Balance: ${ledger_totals[0] - ledger_totals[1]:,.2f}")
    print()
    
    print(f"Receipts Table (payments recorded):")
    print(f"  Total: ${total_amount:,.2f}")
    print()
    
    # Variance
    variance = total_amount - ledger_totals[1]
    print(f"Variance (Receipts vs Statement Payments): ${variance:,.2f}")
    
    if abs(variance) > 0.01:
        print()
        print("⚠️  VARIANCE ANALYSIS:")
        if variance > 0:
            print(f"   Receipts table shows ${variance:,.2f} MORE than statement")
            print("   Likely due to duplicates in receipts table")
        else:
            print(f"   Receipts table shows ${abs(variance):,.2f} LESS than statement")
            print("   Some statement payments may not have receipts")
    else:
        print("✅ Perfect reconciliation!")
    
    print()
    print("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
