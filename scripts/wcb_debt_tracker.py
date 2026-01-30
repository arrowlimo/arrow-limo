"""
WCB (Workers Compensation Board) Debt Tracking System

Tracks WCB premiums owed and payments made:
- Calculates monthly WCB premiums based on payroll
- Extracts WCB payment notifications from email_financial_events
- Matches banking transactions for WCB payments
- Shows running debt balance similar to Fibrenew rent tracker

Usage:
  python -X utf8 scripts/wcb_debt_tracker.py           # dry-run
  python -X utf8 scripts/wcb_debt_tracker.py --write   # apply
"""
import argparse
import psycopg2
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

# WCB rates for Charter/Limousine Services (industry code 74100 / 42201)
WCB_RATES = {
    2019: Decimal('1.25'),  # $ per $100 of payroll
    2020: Decimal('1.24'),
    2021: Decimal('1.68'),
    2022: Decimal('1.80'),
    2023: Decimal('1.68'),
    2024: Decimal('1.70'),
    2025: Decimal('1.68'),
}

MAX_ASSESSABLE = {
    2019: Decimal('98000.00'),
    2020: Decimal('98000.00'),
    2021: Decimal('98000.00'),
    2022: Decimal('98000.00'),
    2023: Decimal('98000.00'),
    2024: Decimal('102500.00'),
    2025: Decimal('102500.00'),
}

# Schema for WCB debt tracking
DDL_WCB_CHARGES = """
CREATE TABLE IF NOT EXISTS wcb_recurring_charges (
    id SERIAL PRIMARY KEY,
    charge_month DATE NOT NULL UNIQUE,
    gross_payroll NUMERIC(12,2) NOT NULL DEFAULT 0,
    wcb_rate NUMERIC(7,4) NOT NULL,
    wcb_premium NUMERIC(12,2) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DDL_WCB_LEDGER = """
CREATE TABLE IF NOT EXISTS wcb_debt_ledger (
    id SERIAL PRIMARY KEY,
    transaction_date DATE NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,  -- 'CHARGE', 'PAYMENT'
    description TEXT,
    charge_amount NUMERIC(12,2) DEFAULT 0,
    payment_amount NUMERIC(12,2) DEFAULT 0,
    running_balance NUMERIC(12,2) NOT NULL,
    wcb_charge_id INTEGER REFERENCES wcb_recurring_charges(id),
    email_event_id INTEGER,
    banking_transaction_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wcb_debt_ledger_date ON wcb_debt_ledger(transaction_date);
"""

def conn():
    return psycopg2.connect(**DB)

def ensure_schema(cur):
    cur.execute(DDL_WCB_CHARGES)
    cur.execute(DDL_WCB_LEDGER)

def calculate_monthly_payroll(cur, year, month):
    """Calculate total gross payroll for a specific month"""
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    
    # Sum from driver_payroll table
    cur.execute(
        """
        SELECT COALESCE(SUM(gross_pay), 0)
        FROM driver_payroll
        WHERE pay_date >= %s AND pay_date < %s
        """,
        (start_date, end_date)
    )
    return cur.fetchone()[0] or Decimal('0.00')

def generate_monthly_wcb_charges(cur, start_year, end_year):
    """Generate WCB charges based on actual payroll data"""
    charges_created = 0
    charges_updated = 0
    
    print("\nCALCULATING WCB CHARGES FROM PAYROLL DATA:")
    print(f"{'Month':<15} {'Gross Payroll':>15} {'WCB Rate':>12} {'WCB Premium':>15}")
    print("-" * 60)
    
    for year in range(start_year, end_year + 1):
        rate = WCB_RATES.get(year, Decimal('1.68'))  # Default to recent rate
        
        for month in range(1, 13):
            charge_month = date(year, month, 1)
            
            # Calculate payroll for this month
            gross_payroll = calculate_monthly_payroll(cur, year, month)
            
            # Calculate WCB premium: (payroll / 100) * rate
            wcb_premium = (gross_payroll / Decimal('100.00')) * rate
            wcb_premium = wcb_premium.quantize(Decimal('0.01'))
            
            # Only create charges for months with payroll
            if gross_payroll > 0:
                cur.execute(
                    """
                    INSERT INTO wcb_recurring_charges (charge_month, gross_payroll, wcb_rate, wcb_premium)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (charge_month) 
                    DO UPDATE SET 
                        gross_payroll = EXCLUDED.gross_payroll,
                        wcb_rate = EXCLUDED.wcb_rate,
                        wcb_premium = EXCLUDED.wcb_premium
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (charge_month, gross_payroll, rate, wcb_premium)
                )
                inserted = cur.fetchone()[0]
                if inserted:
                    charges_created += 1
                    print(f"{charge_month.strftime('%Y-%m'):<15} ${gross_payroll:>13,.2f} ${rate:>10,.4f} ${wcb_premium:>13,.2f}")
                else:
                    charges_updated += 1
    
    print(f"\nCharges created: {charges_created}, updated: {charges_updated}")
    return charges_created, charges_updated

def get_wcb_payments(cur):
    """Get WCB payments from email events and banking transactions"""
    payments = []
    
    # From email_financial_events
    cur.execute(
        """
        SELECT id, email_date, amount, event_type, notes
        FROM email_financial_events
        WHERE entity = 'WCB' OR lender_name ILIKE '%WCB%'
        ORDER BY email_date
        """
    )
    for event_id, event_date, amount, event_type, notes in cur.fetchall():
        payments.append({
            'date': event_date,
            'amount': amount,
            'description': f"WCB {event_type}: {notes or 'Email notification'}",
            'email_event_id': event_id,
            'banking_transaction_id': None
        })
    
    # From banking_transactions
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE debit_amount IS NOT NULL
          AND (
            LOWER(description) LIKE '%wcb%'
            OR LOWER(description) LIKE '%workers comp%'
            OR LOWER(description) LIKE '%workers% compensation%'
          )
        ORDER BY transaction_date
        """
    )
    for tx_id, tx_date, desc, amount in cur.fetchall():
        payments.append({
            'date': tx_date,
            'amount': amount,
            'description': desc,
            'email_event_id': None,
            'banking_transaction_id': tx_id
        })
    
    return payments

def build_wcb_debt_ledger(cur, apply=False):
    """Build chronological ledger of WCB charges and payments"""
    
    # Get all charges
    cur.execute(
        """
        SELECT id, charge_month, wcb_premium, gross_payroll, wcb_rate
        FROM wcb_recurring_charges
        ORDER BY charge_month
        """
    )
    charges = cur.fetchall()
    
    # Get all payments
    payments = get_wcb_payments(cur)
    
    # Merge and sort chronologically
    transactions = []
    
    for charge_id, charge_month, premium, payroll, rate in charges:
        transactions.append({
            'date': charge_month,
            'type': 'CHARGE',
            'amount': premium,
            'description': f"WCB premium for {charge_month.strftime('%B %Y')} (${payroll:,.2f} payroll @ ${rate:.4f}/100)",
            'wcb_charge_id': charge_id,
            'email_event_id': None,
            'banking_transaction_id': None
        })
    
    for payment in payments:
        transactions.append({
            'date': payment['date'],
            'type': 'PAYMENT',
            'amount': payment['amount'],
            'description': payment['description'],
            'wcb_charge_id': None,
            'email_event_id': payment['email_event_id'],
            'banking_transaction_id': payment['banking_transaction_id']
        })
    
    # Sort by date
    transactions.sort(key=lambda x: (x['date'], 0 if x['type'] == 'CHARGE' else 1))
    
    # Calculate running balance
    balance = Decimal('0.00')
    ledger_entries = []
    
    print("\n" + "="*120)
    print("WCB DEBT LEDGER (Chronological)")
    print("="*120)
    print(f"{'Date':<12} {'Type':<10} {'Charge':>12} {'Payment':>12} {'Balance':>12} {'Description':<60}")
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
            'wcb_charge_id': txn['wcb_charge_id'],
            'email_event_id': txn['email_event_id'],
            'banking_transaction_id': txn['banking_transaction_id']
        })
        
        # Print all entries (WCB should be manageable volume)
        print(f"{txn['date']!s:<12} {txn['type']:<10} ${charge_amt:>10,.2f} ${payment_amt:>10,.2f} ${balance:>10,.2f} {txn['description'][:60]}")
    
    print("-"*120)
    total_charges = sum(e['charge_amount'] for e in ledger_entries)
    total_payments = sum(e['payment_amount'] for e in ledger_entries)
    print(f"{'TOTALS':<22} ${total_charges:>10,.2f} ${total_payments:>10,.2f} ${balance:>10,.2f}")
    print("="*120)
    
    # Summary
    print(f"\nSUMMARY:")
    print(f"  Total WCB charges: ${total_charges:,.2f}")
    print(f"  Total payments: ${total_payments:,.2f}")
    print(f"  Outstanding balance: ${balance:,.2f}")
    print(f"  Number of months with charges: {len(charges)}")
    print(f"  Number of payments: {len(payments)}")
    
    if apply:
        # Clear and rebuild ledger
        cur.execute("DELETE FROM wcb_debt_ledger")
        
        for entry in ledger_entries:
            cur.execute(
                """
                INSERT INTO wcb_debt_ledger
                (transaction_date, transaction_type, description, charge_amount, payment_amount, running_balance, 
                 wcb_charge_id, email_event_id, banking_transaction_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry['date'],
                    entry['type'],
                    entry['description'],
                    entry['charge_amount'],
                    entry['payment_amount'],
                    entry['running_balance'],
                    entry['wcb_charge_id'],
                    entry['email_event_id'],
                    entry['banking_transaction_id']
                )
            )
        print(f"\nInserted {len(ledger_entries)} ledger entries.")
    
    return ledger_entries, balance

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes to database')
    ap.add_argument('--start-year', dest='start_year', type=int, default=2019, help='Start year for WCB charges')
    ap.add_argument('--end-year', dest='end_year', type=int, default=2025, help='End year for WCB charges')
    args = ap.parse_args()
    
    cn = conn()
    try:
        cur = cn.cursor()
        
        print(f"\nWCB Debt Tracker")
        print(f"Period: {args.start_year} to {args.end_year}")
        print(f"WCB Rate: $1.25-$1.80 per $100 of payroll (varies by year)\n")
        
        # Create schema
        ensure_schema(cur)
        
        # Generate charges based on actual payroll
        created, updated = generate_monthly_wcb_charges(cur, args.start_year, args.end_year)
        
        if args.write:
            cn.commit()
        
        # Build ledger
        entries, balance = build_wcb_debt_ledger(cur, apply=args.write)
        
        if args.write:
            cn.commit()
            print("\nChanges saved to database.")
        else:
            print("\nDry-run only. Re-run with --write to save.")
        
    finally:
        cn.close()

if __name__ == '__main__':
    main()
