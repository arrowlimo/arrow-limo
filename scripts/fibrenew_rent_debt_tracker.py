"""
Fibrenew Rent Debt Tracking System

Creates a running debt ledger for recurring monthly rent:
- $682.50 per month TOTAL (includes GST of $32.50)
- Monthly charges for Jan 2019 through Dec 2025 (84 months)
- Tracks all payments against accumulated debt
- Shows running balance after each transaction

NOTE: GST is INCLUDED in the total, not added on top.
      Total $682.50 = Net $650.00 + GST $32.50 (5% included)

Usage:
  python -X utf8 scripts/fibrenew_rent_debt_tracker.py           # dry-run
  python -X utf8 scripts/fibrenew_rent_debt_tracker.py --write   # apply
"""
import argparse
import psycopg2
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

MONTHLY_TOTAL = Decimal('682.50')      # Total price including GST
MONTHLY_GST = Decimal('32.50')         # GST included in total
MONTHLY_RENT_BASE = Decimal('650.00')  # Net amount (total - GST)

# Schema for recurring invoices and debt ledger
DDL_RECURRING = """
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id SERIAL PRIMARY KEY,
    vendor_name VARCHAR(200) NOT NULL,
    invoice_type VARCHAR(50) NOT NULL,  -- 'MONTHLY_RENT', 'UTILITY', etc
    charge_date DATE NOT NULL,
    description TEXT,
    base_amount NUMERIC(12,2) NOT NULL,
    gst_amount NUMERIC(12,2) NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vendor_name, invoice_type, charge_date)
);
"""

DDL_DEBT_LEDGER = """
CREATE TABLE IF NOT EXISTS rent_debt_ledger (
    id SERIAL PRIMARY KEY,
    transaction_date DATE NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,  -- 'CHARGE', 'PAYMENT'
    vendor_name VARCHAR(200) NOT NULL,
    description TEXT,
    charge_amount NUMERIC(12,2) DEFAULT 0,
    payment_amount NUMERIC(12,2) DEFAULT 0,
    running_balance NUMERIC(12,2) NOT NULL,
    banking_transaction_id BIGINT,
    recurring_invoice_id INTEGER REFERENCES recurring_invoices(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rent_debt_ledger_date ON rent_debt_ledger(transaction_date);
CREATE INDEX IF NOT EXISTS idx_rent_debt_ledger_vendor ON rent_debt_ledger(vendor_name);
"""

def conn():
    return psycopg2.connect(**DB)

def ensure_schema(cur):
    cur.execute(DDL_RECURRING)
    cur.execute(DDL_DEBT_LEDGER)

def generate_monthly_charges(cur, start_date, end_date):
    """Generate recurring monthly rent charges"""
    current = start_date
    charges_created = 0
    
    while current <= end_date:
        cur.execute(
            """
            INSERT INTO recurring_invoices (vendor_name, invoice_type, charge_date, description, base_amount, gst_amount, total_amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (vendor_name, invoice_type, charge_date) DO NOTHING
            RETURNING id
            """,
            (
                'Fibrenew Office Rent',
                'MONTHLY_RENT',
                current,
                f"Monthly office rent {current.strftime('%B %Y')}",
                MONTHLY_RENT_BASE,
                MONTHLY_GST,
                MONTHLY_TOTAL
            )
        )
        if cur.fetchone():
            charges_created += 1
        
        current = current + relativedelta(months=1)
    
    return charges_created

def get_fibrenew_payments(cur):
    """Get all Fibrenew payments from banking_transactions"""
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE debit_amount IS NOT NULL
          AND (
            LOWER(description) LIKE '%fibrenew%'
            OR LOWER(description) LIKE '%fibre new%'
            OR LOWER(description) LIKE '%fib re new%'
          )
        ORDER BY transaction_date, transaction_id
        """
    )
    return cur.fetchall()

def build_debt_ledger(cur, apply=False):
    """Build chronological ledger of charges and payments with running balance"""
    
    # Get all recurring charges
    cur.execute(
        """
        SELECT id, charge_date, total_amount, description
        FROM recurring_invoices
        WHERE vendor_name = 'Fibrenew Office Rent' AND invoice_type = 'MONTHLY_RENT'
        ORDER BY charge_date
        """
    )
    charges = cur.fetchall()
    
    # Get all payments
    payments = get_fibrenew_payments(cur)
    
    # Merge and sort chronologically
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
    
    # Sort by date, then by type (charges before payments on same day)
    transactions.sort(key=lambda x: (x['date'], 0 if x['type'] == 'CHARGE' else 1))
    
    # Calculate running balance
    balance = Decimal('0.00')
    ledger_entries = []
    
    print("\n" + "="*120)
    print("FIBRENEW RENT DEBT LEDGER (Chronological)")
    print("="*120)
    print(f"{'Date':<12} {'Type':<10} {'Charge':>12} {'Payment':>12} {'Balance':>12} {'Description':<50}")
    print("-"*120)
    
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
        
        # Print summary (first 20 and last 20)
        if len(ledger_entries) <= 20 or len(ledger_entries) > len(transactions) - 20:
            print(f"{txn['date']!s:<12} {txn['type']:<10} ${charge_amt:>10,.2f} ${payment_amt:>10,.2f} ${balance:>10,.2f} {txn['description'][:50]}")
        elif len(ledger_entries) == 21:
            print(f"{'...':<12} {'...':<10} {'...':<12} {'...':<12} {'...':<12} {'...':<50}")
    
    print("-"*120)
    print(f"{'TOTALS':<22} ${sum(e['charge_amount'] for e in ledger_entries):>10,.2f} ${sum(e['payment_amount'] for e in ledger_entries):>10,.2f} ${balance:>10,.2f}")
    print("="*120)
    
    # Summary stats
    total_charges = sum(e['charge_amount'] for e in ledger_entries)
    total_payments = sum(e['payment_amount'] for e in ledger_entries)
    
    print(f"\nSUMMARY:")
    print(f"  Total charges (rent): ${total_charges:,.2f}")
    print(f"  Total payments: ${total_payments:,.2f}")
    print(f"  Outstanding balance: ${balance:,.2f}")
    print(f"  Number of monthly charges: {len(charges)}")
    print(f"  Number of payments: {len(payments)}")
    
    if apply:
        # Clear existing ledger and rebuild
        cur.execute("DELETE FROM rent_debt_ledger WHERE vendor_name = 'Fibrenew Office Rent'")
        
        # Insert all entries
        for entry in ledger_entries:
            cur.execute(
                """
                INSERT INTO rent_debt_ledger 
                (transaction_date, transaction_type, vendor_name, description, charge_amount, payment_amount, running_balance, banking_transaction_id, recurring_invoice_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry['date'],
                    entry['type'],
                    'Fibrenew Office Rent',
                    entry['description'],
                    entry['charge_amount'],
                    entry['payment_amount'],
                    entry['running_balance'],
                    entry['banking_transaction_id'],
                    entry['recurring_invoice_id']
                )
            )
        print(f"\nInserted {len(ledger_entries)} ledger entries.")
    
    return ledger_entries, balance

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes to database')
    ap.add_argument('--start-date', dest='start_date', default='2019-01-01', help='Start date for recurring charges (YYYY-MM-DD)')
    ap.add_argument('--end-date', dest='end_date', default='2025-12-01', help='End date for recurring charges (YYYY-MM-DD)')
    args = ap.parse_args()
    
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    
    cn = conn()
    try:
        cur = cn.cursor()
        
        print(f"\nFibrenew Rent Debt Tracker")
        print(f"Recurring charges: {start.strftime('%B %Y')} to {end.strftime('%B %Y')}")
        print(f"Monthly rent: ${MONTHLY_TOTAL:,.2f} (${MONTHLY_RENT_BASE:,.2f} + ${MONTHLY_GST:,.2f} GST)\n")
        
        # Create schema
        ensure_schema(cur)
        
        # Generate monthly charges
        charges_created = generate_monthly_charges(cur, start, end)
        print(f"Recurring invoices: {charges_created} new charges created")
        
        if args.write:
            cn.commit()
        
        # Build ledger
        entries, balance = build_debt_ledger(cur, apply=args.write)
        
        if args.write:
            cn.commit()
            print("\nChanges saved to database.")
        else:
            print("\nDry-run only. Re-run with --write to save.")
        
    finally:
        cn.close()

if __name__ == '__main__':
    main()
