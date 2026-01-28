"""
Add Fibrenew invoices with rent and utility charges

Invoice 8487 (Jan 3, 2019):
  - Rent: $682.50 + $32.50 GST = $715.00
  - Utilities: $306.17 + $14.58 GST = $320.75

Invoice 8743 (May 31, 2019):
  - Rent: $682.50 + $32.50 GST = $715.00
  - Utilities: $254.32 + $12.11 GST = $266.43

Invoice 8691 (May 7, 2019):
  - Rent: $682.50 + $32.50 GST = $715.00
  - Utilities: $295.69 + $14.08 GST = $309.77 (invoice 8690)

Usage:
  python -X utf8 scripts/add_fibrenew_invoices_early_2019.py           # dry-run
  python -X utf8 scripts/add_fibrenew_invoices_early_2019.py --write   # apply
"""
import argparse
import psycopg2
import hashlib
from datetime import date
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# Invoice structure: separate invoice numbers for rent and utilities
INVOICES = [
    {
        'invoice_number': '8487',
        'invoice_date': date(2019, 1, 3),
        'type': 'rent',
        'base': Decimal('682.50'),
        'gst': Decimal('32.50'),
        'total': Decimal('715.00'),
        'description': 'Monthly office rent - January 2019'
    },
    {
        'invoice_number': '8488',
        'invoice_date': date(2019, 1, 3),
        'type': 'utilities',
        'base': Decimal('306.17'),
        'gst': Decimal('14.58'),
        'total': Decimal('320.75'),
        'description': 'Office utilities - January 2019'
    },
    {
        'invoice_number': '8691',
        'invoice_date': date(2019, 5, 7),
        'type': 'rent',
        'base': Decimal('682.50'),
        'gst': Decimal('32.50'),
        'total': Decimal('715.00'),
        'description': 'Monthly office rent - May 2019'
    },
    {
        'invoice_number': '8690',
        'invoice_date': date(2019, 5, 7),
        'type': 'utilities',
        'base': Decimal('295.69'),
        'gst': Decimal('14.08'),
        'total': Decimal('309.77'),
        'description': 'Office utilities - May 2019'
    },
    {
        'invoice_number': '8743',
        'invoice_date': date(2019, 5, 31),
        'type': 'rent',
        'base': Decimal('682.50'),
        'gst': Decimal('32.50'),
        'total': Decimal('715.00'),
        'description': 'Monthly office rent - May 2019'
    },
    {
        'invoice_number': '8744',
        'invoice_date': date(2019, 5, 31),
        'type': 'utilities',
        'base': Decimal('254.32'),
        'gst': Decimal('12.11'),
        'total': Decimal('266.43'),
        'description': 'Office utilities - May 2019'
    }
]

def conn():
    return psycopg2.connect(**DB)

def insert_fibrenew_invoices(cur, apply=False):
    """Insert Fibrenew invoices as receipts"""
    
    print("\n" + "="*100)
    print("FIBRENEW INVOICES - EARLY 2019 (Separate invoice numbers for rent and utilities)")
    print("="*100)
    print(f"{'Invoice':<10} {'Date':<12} {'Type':<12} {'Base':>12} {'GST':>12} {'Total':>12}")
    print("-"*100)
    
    total_base = Decimal('0.00')
    total_gst = Decimal('0.00')
    total_amount = Decimal('0.00')
    receipts_inserted = 0
    receipts_skipped = 0
    
    for inv in INVOICES:
        print(f"{inv['invoice_number']:<10} {str(inv['invoice_date']):<12} {inv['type']:<12} "
              f"${inv['base']:>10,.2f} ${inv['gst']:>10,.2f} ${inv['total']:>10,.2f}")
        
        total_base += inv['base']
        total_gst += inv['gst']
        total_amount += inv['total']
        
        if apply:
            # Create unique source reference and hash
            source_ref = f"FIBRENEW-{inv['invoice_number']}"
            source_hash = hashlib.sha256(
                f"{source_ref}:{inv['invoice_date']}:{inv['total']}".encode()
            ).hexdigest()
            
            # Insert as receipt
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
                    'FIBRENEW_INVOICE',
                    source_ref,
                    inv['invoice_date'],
                    'Fibrenew Office Rent',
                    f"Invoice {inv['invoice_number']} - {inv['description']}",
                    inv['total'],
                    inv['gst'],
                    '6800 - Rent' if inv['type'] == 'rent' else '6820 - Utilities',
                    source_hash
                )
            )
            result = cur.fetchone()
            if result:
                receipts_inserted += 1
            else:
                receipts_skipped += 1
    
    print("-"*100)
    print(f"{'TOTALS':<34} ${total_base:>10,.2f} ${total_gst:>10,.2f} ${total_amount:>10,.2f}")
    print("="*100)
    
    # Summary
    print(f"\nSUMMARY:")
    print(f"  Invoices processed: {len(INVOICES)}")
    print(f"  Total base amount: ${total_base:,.2f}")
    print(f"  Total GST: ${total_gst:,.2f}")
    print(f"  Total invoice amount: ${total_amount:,.2f}")
    
    if apply:
        print(f"\n  Receipts inserted: {receipts_inserted}")
        print(f"  Receipts skipped (duplicates): {receipts_skipped}")
    
    # Breakdown by type
    rent_total = sum(inv['total'] for inv in INVOICES if inv['type'] == 'rent')
    util_total = sum(inv['total'] for inv in INVOICES if inv['type'] == 'utilities')
    
    print(f"\nBREAKDOWN:")
    print(f"  Rent invoices (8487, 8691, 8743): ${rent_total:,.2f}")
    print(f"  Utility invoices (8488, 8690, 8744): ${util_total:,.2f}")
    
    # Check against debt tracker
    print(f"\nDEBT TRACKER INTEGRATION:")
    print(f"  These invoices represent charges from Jan-May 2019")
    print(f"  Monthly rent charge in debt ledger: $682.50")
    print(f"  These invoice rents (base): ${sum(inv['base'] for inv in INVOICES if inv['type'] == 'rent'):,.2f}")
    
    return len(INVOICES)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes to database')
    args = ap.parse_args()
    
    cn = conn()
    try:
        cur = cn.cursor()
        
        print(f"\nFibrenew Invoice Import - Early 2019")
        print(f"Adding {len(INVOICES)} separate invoices (3 rent + 3 utilities)\n")
        
        # Insert invoices
        count = insert_fibrenew_invoices(cur, apply=args.write)
        
        if args.write:
            cn.commit()
            print(f"\n[OK] Processed {count} Fibrenew invoices.")
        else:
            print(f"\nDry-run only. Re-run with --write to save.")
        
    finally:
        cn.close()

if __name__ == '__main__':
    main()
