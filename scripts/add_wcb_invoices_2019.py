"""
Add WCB invoices from account 4973477

Three invoices from 2019 with past due amounts and overdue charges:
1. Invoice 24058172 (Nov 19, 2019): $460.23 + $5.27 overdue = $465.50 (due Dec 19)
2. Invoice 23962721 (Sep 19, 2019): $449.87 + $5.15 overdue = $455.02 (due date not specified)
3. Invoice 23855931 (Jul 19, 2019): $439.09 + $5.62 overdue = $444.71 (due Aug 18, 2019)

Usage:
  python -X utf8 scripts/add_wcb_invoices_2019.py           # dry-run
  python -X utf8 scripts/add_wcb_invoices_2019.py --write   # apply
"""
import argparse
import psycopg2
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

WCB_ACCOUNT = '4973477'

# Invoice data structure - due date is always one month after invoice date
INVOICES = [
    {
        'invoice_number': '23855931',
        'invoice_date': date(2019, 7, 19),
        'past_due_amount': Decimal('439.09'),
        'overdue_charge': Decimal('5.62'),
        'total_due': Decimal('444.71'),
        'description': 'WCB Invoice 23855931 - July 2019'
    },
    {
        'invoice_number': '23962721',
        'invoice_date': date(2019, 9, 19),
        'past_due_amount': Decimal('449.87'),
        'overdue_charge': Decimal('5.15'),
        'total_due': Decimal('455.02'),
        'description': 'WCB Invoice 23962721 - September 2019'
    },
    {
        'invoice_number': '24058172',
        'invoice_date': date(2019, 11, 19),
        'past_due_amount': Decimal('460.23'),
        'overdue_charge': Decimal('5.27'),
        'total_due': Decimal('465.50'),
        'description': 'WCB Invoice 24058172 - November 2019'
    }
]

# Calculate due dates (always one month after invoice date)
for inv in INVOICES:
    inv['due_date'] = inv['invoice_date'] + relativedelta(months=1)

def conn():
    return psycopg2.connect(**DB)

def insert_wcb_invoices(cur, apply=False):
    """Insert WCB invoices as receipts and update recurring charges"""
    
    print("\n" + "="*100)
    print(f"WCB INVOICES - ACCOUNT {WCB_ACCOUNT}")
    print("="*100)
    print(f"{'Invoice':<12} {'Date':<12} {'Due Date':<12} {'Past Due':>12} {'Overdue':>12} {'Total Due':>12}")
    print("-"*100)
    
    total_invoices = Decimal('0.00')
    total_overdue_charges = Decimal('0.00')
    total_due = Decimal('0.00')
    
    for inv in INVOICES:
        print(f"{inv['invoice_number']:<12} {str(inv['invoice_date']):<12} {str(inv['due_date']):<12} "
              f"${inv['past_due_amount']:>10,.2f} ${inv['overdue_charge']:>10,.2f} ${inv['total_due']:>10,.2f}")
        
        total_invoices += inv['past_due_amount']
        total_overdue_charges += inv['overdue_charge']
        total_due += inv['total_due']
        
        if apply:
            # Insert as receipt using canonical schema
            import hashlib
            source_ref = f"WCB-{WCB_ACCOUNT}-{inv['invoice_number']}"
            source_hash = hashlib.sha256(f"{source_ref}:{inv['invoice_date']}:{inv['total_due']}".encode()).hexdigest()
            
            cur.execute(
                """
                INSERT INTO receipts (
                    source_system, source_reference, receipt_date, vendor_name, description,
                    gross_amount, gst_amount, expense_account, source_hash
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_hash) DO NOTHING
                RETURNING id
                """,
                (
                    'WCB_INVOICE',
                    source_ref,
                    inv['invoice_date'],
                    f'WCB Alberta (Account {WCB_ACCOUNT})',
                    f"{inv['description']} - Invoice {inv['invoice_number']}, Due: {inv['due_date']}, "
                    f"Past due: ${inv['past_due_amount']:.2f}, Overdue charge: ${inv['overdue_charge']:.2f}",
                    inv['total_due'],
                    Decimal('0.00'),  # WCB premiums are not subject to GST
                    '6950 - WCB',
                    source_hash
                )
            )
            result = cur.fetchone()
            if result:
                receipt_id = result[0]
                print(f"  → Inserted as receipt id {receipt_id}")
            else:
                print(f"  → Already exists (skipped)")
    
    print("-"*100)
    print(f"{'TOTALS':<36} ${total_invoices:>10,.2f} ${total_overdue_charges:>10,.2f} ${total_due:>10,.2f}")
    print("="*100)
    
    # Compare to June 2019 payment
    print(f"\nRECONCILIATION:")
    print(f"  Total invoices (past due amounts): ${total_invoices:,.2f}")
    print(f"  Total overdue charges: ${total_overdue_charges:,.2f}")
    print(f"  Total amount due: ${total_due:,.2f}")
    print(f"  Payment made (June 12, 2019): $928.72")
    print(f"  Shortfall: ${total_due - Decimal('928.72'):,.2f}")
    
    # Calculate what period these invoices cover
    print(f"\nINVOICE ANALYSIS:")
    print(f"  Invoice period: July 2019 - November 2019 (5 months)")
    print(f"  Average per month: ${total_invoices / 3:,.2f}")
    print(f"  Our calculated WCB (Jul-Nov 2019): $513.47")
    print(f"    - July: $90.28")
    print(f"    - August: $104.08")
    print(f"    - September: $99.66")
    print(f"    - October: $83.63")
    print(f"    - November: $106.26")
    
    # Note: The WCB invoices ($1,349.37 past due) are significantly higher than our calculated amounts
    # This suggests there may be unpaid premiums from earlier periods
    
    print(f"\nDISCREPANCY NOTES:")
    print(f"  WCB invoices show $1,349.37 in past due amounts (before overdue charges)")
    print(f"  Our payroll-based calculation shows $513.47 for Jul-Nov 2019")
    print(f"  Difference: ${total_invoices - Decimal('513.47'):,.2f}")
    print(f"  ")
    print(f"  This suggests:")
    print(f"    1. These invoices include unpaid premiums from earlier periods")
    print(f"    2. WCB may have different assessment rates or payroll calculations")
    print(f"    3. There may be adjustments/reassessments we're not tracking")
    
    return len(INVOICES)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes to database')
    args = ap.parse_args()
    
    cn = conn()
    try:
        cur = cn.cursor()
        
        print(f"\nWCB Invoice Import - Account {WCB_ACCOUNT}")
        print(f"Adding {len(INVOICES)} invoices from 2019\n")
        
        # Insert invoices
        count = insert_wcb_invoices(cur, apply=args.write)
        
        if args.write:
            cn.commit()
            print(f"\n[OK] Inserted {count} WCB invoices into receipts table.")
        else:
            print(f"\nDry-run only. Re-run with --write to save.")
        
    finally:
        cn.close()

if __name__ == '__main__':
    main()
