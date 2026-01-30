"""
Rebuild Fibrenew rent debt ledger with opening balance integrated

This will:
1. Delete all existing CHARGE/PAYMENT entries (keep opening_balance)
2. Recalculate running_balance starting from opening_balance
3. Insert CHARGE/PAYMENT entries with correct cumulative balances

Usage:
  python -X utf8 scripts/rebuild_fibrenew_ledger_with_opening.py           # dry-run
  python -X utf8 scripts/rebuild_fibrenew_ledger_with_opening.py --write   # apply
"""
import argparse
import psycopg2
from datetime import date
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

def conn():
    return psycopg2.connect(**DB)

def get_fibrenew_payments(cur):
    """Get all Fibrenew payments from banking_transactions"""
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE debit_amount IS NOT NULL
          AND (
            LOWER(description) LIKE %s
            OR LOWER(description) LIKE %s
            OR LOWER(description) LIKE %s
          )
        ORDER BY transaction_date, transaction_id
        """,
        ('%fibrenew%', '%fibre new%', '%fib re new%')
    )
    return cur.fetchall()

def rebuild_ledger(cur, apply=False):
    # Get opening balance
    cur.execute("""
        SELECT id, transaction_date, charge_amount
        FROM rent_debt_ledger
        WHERE transaction_type = 'opening_balance'
        ORDER BY transaction_date
        LIMIT 1
    """)
    opening_row = cur.fetchone()
    if not opening_row:
        print("[WARN]  No opening balance found. Run add_fibrenew_opening_balance.py first.")
        return 0
    
    opening_id, opening_date, opening_amount = opening_row
    
    # Get recurring charges
    cur.execute("""
        SELECT id, charge_date, total_amount, description
        FROM recurring_invoices
        WHERE vendor_name = 'Fibrenew Office Rent' AND invoice_type = 'MONTHLY_RENT'
        ORDER BY charge_date
    """)
    charges = cur.fetchall()
    
    # Get payments
    payments = get_fibrenew_payments(cur)
    
    # Build transaction list
    transactions = []
    for charge_id, charge_date, amount, desc in charges:
        transactions.append({
            'date': charge_date,
            'type': 'CHARGE',
            'amount': amount,
            'description': desc,
            'recurring_invoice_id': charge_id,
            'banking_transaction_id': None
        })
    
    for tx_id, tx_date, desc, amount in payments:
        transactions.append({
            'date': tx_date,
            'type': 'PAYMENT',
            'amount': amount,
            'description': desc,
            'recurring_invoice_id': None,
            'banking_transaction_id': tx_id
        })
    
    # Sort chronologically (charges before payments on same day)
    transactions.sort(key=lambda x: (x['date'], 0 if x['type'] == 'CHARGE' else 1))
    
    # Calculate running balances starting from opening balance
    balance = opening_amount
    ledger_entries = []
    
    print("\n" + "="*120)
    print(f"REBUILDING LEDGER WITH OPENING BALANCE: ${opening_amount:,.2f} on {opening_date}")
    print("="*120)
    print(f"{'Date':<12} {'Type':<10} {'Charge':>12} {'Payment':>12} {'Balance':>12}")
    print("-"*120)
    
    # Show opening balance
    print(f"{opening_date!s:<12} {'OPENING':<10} ${opening_amount:>10,.2f} ${'0.00':>10} ${balance:>10,.2f}")
    
    for txn in transactions:
        if txn['type'] == 'CHARGE':
            balance += txn['amount']
            charge_amt = txn['amount']
            payment_amt = Decimal('0.00')
        else:
            balance -= txn['amount']
            charge_amt = Decimal('0.00')
            payment_amt = txn['amount']
        
        ledger_entries.append({
            'date': txn['date'],
            'type': txn['type'],
            'description': txn['description'],
            'charge_amount': charge_amt,
            'payment_amount': payment_amt,
            'running_balance': balance,
            'banking_transaction_id': txn['banking_transaction_id'],
            'recurring_invoice_id': txn['recurring_invoice_id']
        })
        
        # Show first 10 and last 10
        if len(ledger_entries) <= 10 or len(ledger_entries) > len(transactions) - 10:
            print(f"{txn['date']!s:<12} {txn['type']:<10} ${charge_amt:>10,.2f} ${payment_amt:>10,.2f} ${balance:>10,.2f}")
        elif len(ledger_entries) == 11:
            print(f"{'...':<12} {'...':<10} {'...':>12} {'...':>12} {'...':>12}")
    
    print("-"*120)
    total_charges = sum(e['charge_amount'] for e in ledger_entries)
    total_payments = sum(e['payment_amount'] for e in ledger_entries)
    print(f"{'TOTALS':<22} ${total_charges:>10,.2f} ${total_payments:>10,.2f} ${balance:>10,.2f}")
    print("="*120)
    
    print(f"\nSUMMARY:")
    print(f"  Opening balance: ${opening_amount:,.2f}")
    print(f"  + Charges: ${total_charges:,.2f}")
    print(f"  - Payments: ${total_payments:,.2f}")
    print(f"  = Final balance: ${balance:,.2f}")
    print(f"  Expected: ${opening_amount + total_charges - total_payments:,.2f}")
    
    if apply:
        # Delete old CHARGE/PAYMENT entries
        cur.execute("""
            DELETE FROM rent_debt_ledger
            WHERE transaction_type IN ('CHARGE', 'PAYMENT')
        """)
        deleted = cur.rowcount
        print(f"\n[OK] Deleted {deleted} old CHARGE/PAYMENT entries")
        
        # Insert new entries with correct balances
        for entry in ledger_entries:
            cur.execute("""
                INSERT INTO rent_debt_ledger (
                    transaction_date, transaction_type, vendor_name, description,
                    charge_amount, payment_amount, running_balance,
                    banking_transaction_id, recurring_invoice_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                entry['date'],
                entry['type'],
                'Fibrenew Office Rent',
                entry['description'],
                entry['charge_amount'],
                entry['payment_amount'],
                entry['running_balance'],
                entry['banking_transaction_id'],
                entry['recurring_invoice_id']
            ))
        
        print(f"[OK] Inserted {len(ledger_entries)} new entries with correct running balances")
        return len(ledger_entries)
    else:
        print(f"\nDry-run only. Re-run with --write to rebuild ledger.")
        return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes')
    args = ap.parse_args()
    
    cn = conn()
    try:
        cur = cn.cursor()
        count = rebuild_ledger(cur, apply=args.write)
        if args.write and count > 0:
            cn.commit()
            print(f"\n[OK] Ledger rebuilt successfully.")
    finally:
        cn.close()

if __name__ == '__main__':
    main()
