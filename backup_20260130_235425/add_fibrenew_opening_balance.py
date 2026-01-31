"""
Add opening balance to Fibrenew rent debt ledger for historical accumulated debt.

Opening balance entry:
- Date: 2019-01-01 (start of complete banking records)
- Amount: $16,119.69 (total from statement dated 1/31/2019)
- Type: 'opening_balance'
- Notes: References 29 historical invoices from 2017-11-29 to 2019-01-31
- Receipts: ids 81842-81869 (FIBRENEW_STATEMENT source)

This preserves the audit trail from the Excel statement while keeping the
ledger clean and starting from when banking data is complete.

Usage:
  python -X utf8 scripts/add_fibrenew_opening_balance.py           # dry-run
  python -X utf8 scripts/add_fibrenew_opening_balance.py --write   # apply
"""
import argparse
import psycopg2
from datetime import date
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

OPENING_BALANCE = Decimal('16119.69')
OPENING_DATE = date(2019, 1, 1)

def conn():
    return psycopg2.connect(**DB)

def add_opening_balance(cur, apply=False):
    # Check if opening balance already exists
    cur.execute(
        """
        SELECT transaction_date, charge_amount, running_balance, description
        FROM rent_debt_ledger
        WHERE transaction_type = 'opening_balance'
        ORDER BY transaction_date
        LIMIT 1
        """
    )
    existing = cur.fetchone()
    
    if existing:
        print(f"\n[WARN]  Opening balance already exists:")
        print(f"  Date: {existing[0]}")
        print(f"  Amount: ${existing[1]:,.2f}")
        print(f"  Balance: ${existing[2]:,.2f}")
        print(f"  Description: {existing[3]}")
        print("\nSkipping insertion. Delete existing entry first if you need to re-add.")
        return 0
    
    # Get count and IDs of statement receipts
    cur.execute(
        """
        SELECT COUNT(*), MIN(id), MAX(id)
        FROM receipts
        WHERE source_system = 'FIBRENEW_STATEMENT'
        """
    )
    receipt_count, min_id, max_id = cur.fetchone()
    
    print("\n" + "="*100)
    print("FIBRENEW RENT DEBT LEDGER - OPENING BALANCE")
    print("="*100)
    print(f"Opening Balance Date: {OPENING_DATE}")
    print(f"Opening Balance Amount: ${OPENING_BALANCE:,.2f}")
    print(f"Source: Fibrenew statement dated 1/31/2019")
    print(f"Historical receipts: {receipt_count} invoices (receipt IDs {min_id}-{max_id})")
    print(f"Statement period: 2017-11-29 to 2019-01-31")
    print("="*100)
    
    if apply:
        # Insert opening balance entry  
        notes_text = (
            f'Based on Fibrenew statement dated 1/31/2019 showing $16,119.69 total due. '
            f'Represents {receipt_count} historical invoices from 2017-11-29 to 2019-01-31 '
            f'(receipt IDs {min_id}-{max_id}, source_system=FIBRENEW_STATEMENT). '
            f'Statement showed: Original amount $16,164.48, Amount due $16,119.69, '
            f'Partial payment $44.79 on invoice 7739.'
        )
        cur.execute(
            """
            INSERT INTO rent_debt_ledger (
                transaction_date, transaction_type, vendor_name, description,
                charge_amount, payment_amount, running_balance
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                OPENING_DATE,
                'opening_balance',
                'Fibrenew Office Rent',
                f'Opening balance - Historical accumulated debt. {notes_text}',
                OPENING_BALANCE,
                Decimal('0.00'),
                OPENING_BALANCE
            )
        )
        ledger_id = cur.fetchone()[0]
        print(f"\n[OK] Inserted opening balance as ledger entry ID {ledger_id}")
        
        # Verify ledger state after insertion
        cur.execute(
            """
            SELECT transaction_date, transaction_type, charge_amount, running_balance
            FROM rent_debt_ledger
            ORDER BY transaction_date, id
            LIMIT 5
            """
        )
        print("\nFirst 5 ledger entries after opening balance:")
        for row in cur.fetchall():
            print(f"  {row[0]} | {row[1]:20s} | ${row[2]:>10,.2f} | Balance: ${row[3]:>10,.2f}")
        
        return 1
    else:
        print("\nDry-run only. Re-run with --write to insert opening balance.")
        return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes to database')
    args = ap.parse_args()
    
    cn = conn()
    try:
        cur = cn.cursor()
        count = add_opening_balance(cur, apply=args.write)
        
        if args.write and count > 0:
            cn.commit()
            print("\n[OK] Opening balance committed to rent_debt_ledger.")
        
    finally:
        cn.close()

if __name__ == '__main__':
    main()
