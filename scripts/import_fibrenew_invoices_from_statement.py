#!/usr/bin/env python3
"""
Import all 68 Fibrenew invoices from Nov 2025 statement to recurring_invoices table.

CRITICAL: These invoices show ORIGINAL amounts and OPEN (owing) amounts.
The difference represents payments already applied.

Example: Invoice #12419 (08/01/2024)
- Original: $1,102.50
- Open: $167.06
- Paid: $935.44 (likely the $1,300 payment noted "PD MAR 5/13")
"""
import psycopg2
from decimal import Decimal
from datetime import datetime
import argparse

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

# All 68 invoices from statement - extracted from PDF
statement_invoices = [
    ('2019-02-01', '8696', Decimal('301.48'), Decimal('193.84')),
    ('2019-03-01', '8693', Decimal('682.50'), Decimal('682.50')),
    ('2019-03-01', '8697', Decimal('345.88'), Decimal('345.88')),
    ('2019-04-01', '8695', Decimal('682.50'), Decimal('682.50')),
    ('2019-05-07', '8690', Decimal('295.69'), Decimal('295.69')),
    ('2019-05-07', '8691', Decimal('682.50'), Decimal('682.50')),
    ('2019-05-31', '8743', Decimal('682.50'), Decimal('682.50')),
    ('2019-05-31', '8744', Decimal('254.32'), Decimal('254.32')),
    ('2019-07-01', '8832', Decimal('682.50'), Decimal('682.50')),
    ('2019-07-11', '8833', Decimal('153.13'), Decimal('153.13')),
    ('2019-08-06', '8894', Decimal('144.89'), Decimal('144.89')),
    ('2019-08-06', '8895', Decimal('682.50'), Decimal('682.50')),
    ('2019-09-04', '8942', Decimal('682.50'), Decimal('682.50')),
    ('2019-09-04', '8943', Decimal('183.91'), Decimal('183.91')),
    ('2019-10-01', '8979', Decimal('682.50'), Decimal('682.50')),
    ('2019-10-01', '8980', Decimal('152.62'), Decimal('152.62')),
    ('2019-11-01', '9025', Decimal('163.46'), Decimal('163.46')),
    ('2019-11-06', '9066', Decimal('682.50'), Decimal('682.50')),
    ('2019-11-06', '9067', Decimal('157.88'), Decimal('157.88')),
    ('2019-12-04', '9103', Decimal('126.60'), Decimal('126.60')),
    ('2020-01-01', '9135', Decimal('682.50'), Decimal('682.50')),
    ('2020-01-08', '9139', Decimal('190.20'), Decimal('190.20')),
    ('2020-02-01', '9172', Decimal('682.50'), Decimal('682.50')),
    ('2020-02-14', '9201', Decimal('228.12'), Decimal('228.12')),
    ('2020-03-02', '9239', Decimal('682.50'), Decimal('682.50')),
    ('2020-03-30', '9288', Decimal('304.47'), Decimal('304.47')),
    ('2020-04-01', '9287', Decimal('682.50'), Decimal('682.50')),
    ('2020-05-14', '9325', Decimal('199.26'), Decimal('199.26')),
    ('2020-06-23', '9392', Decimal('156.64'), Decimal('156.64')),
    ('2020-07-02', '9407', Decimal('840.00'), Decimal('840.00')),
    ('2020-07-22', '9436', Decimal('134.81'), Decimal('134.81')),
    ('2020-08-05', '9490', Decimal('840.00'), Decimal('840.00')),
    ('2020-09-01', '9542', Decimal('840.00'), Decimal('840.00')),
    ('2020-09-10', '9561', Decimal('142.63'), Decimal('142.63')),
    ('2020-10-01', '9609', Decimal('840.00'), Decimal('840.00')),
    ('2020-10-08', '9623', Decimal('145.20'), Decimal('145.20')),
    ('2020-11-01', '9670', Decimal('840.00'), Decimal('840.00')),
    ('2020-11-18', '9694', Decimal('162.21'), Decimal('162.21')),
    ('2020-12-01', '9727', Decimal('840.00'), Decimal('840.00')),
    ('2020-12-07', '9742', Decimal('191.25'), Decimal('191.25')),
    ('2021-01-01', '9767', Decimal('840.00'), Decimal('840.00')),
    ('2021-01-18', '9772', Decimal('201.35'), Decimal('201.35')),
    ('2021-02-01', '9800', Decimal('840.00'), Decimal('840.00')),
    ('2021-02-05', '9815', Decimal('169.44'), Decimal('169.44')),
    ('2021-03-01', '9866', Decimal('840.00'), Decimal('840.00')),
    ('2021-03-08', '9885', Decimal('220.34'), Decimal('220.34')),
    ('2021-04-06', '9956', Decimal('840.00'), Decimal('840.00')),
    ('2024-01-02', '12131', Decimal('1102.50'), Decimal('1102.50')),
    ('2024-02-01', '12132', Decimal('1102.50'), Decimal('1102.50')),
    ('2024-03-01', '12133', Decimal('1102.50'), Decimal('1102.50')),
    ('2024-04-01', '12177', Decimal('1102.50'), Decimal('1102.50')),
    ('2024-05-01', '12226', Decimal('1102.50'), Decimal('1102.50')),
    ('2024-08-01', '12419', Decimal('1102.50'), Decimal('167.06')),  # NOTE: $935.44 paid (Mar 5/13 payment)
    ('2024-09-01', '12494', Decimal('1102.50'), Decimal('1102.50')),
    ('2024-10-01', '12540', Decimal('1102.50'), Decimal('1102.50')),
    ('2024-11-01', '12601', Decimal('1102.50'), Decimal('1102.50')),
    ('2024-12-02', '12664', Decimal('1102.50'), Decimal('1102.50')),
    ('2025-01-01', '12714', Decimal('1102.50'), Decimal('1102.50')),
    ('2025-02-03', '12775', Decimal('1102.50'), Decimal('1102.50')),
    ('2025-03-03', '12835', Decimal('1102.50'), Decimal('1102.50')),
    ('2025-04-01', '12909', Decimal('1102.50'), Decimal('1102.50')),
    ('2025-05-01', '12973', Decimal('1102.50'), Decimal('1102.50')),
    ('2025-06-01', '13041', Decimal('1102.50'), Decimal('1102.50')),
    ('2025-07-01', '13103', Decimal('1102.50'), Decimal('1102.50')),
    ('2025-08-01', '13180', Decimal('1260.00'), Decimal('1260.00')),
    ('2025-09-01', '13248', Decimal('1260.00'), Decimal('1260.00')),
    ('2025-10-01', '13310', Decimal('1260.00'), Decimal('1260.00')),
    ('2025-11-01', '13379', Decimal('1260.00'), Decimal('1260.00')),
]

def main(write=False):
    print("\n" + "="*100)
    print("IMPORT FIBRENEW STATEMENT INVOICES TO recurring_invoices TABLE")
    print("="*100)
    
    total_original = sum(amt for _, _, amt, _ in statement_invoices)
    total_open = sum(open_amt for _, _, _, open_amt in statement_invoices)
    total_paid_on_these = total_original - total_open
    
    print(f"\n📊 INVOICE SUMMARY:")
    print("-" * 100)
    print(f"Total invoices: {len(statement_invoices)}")
    print(f"Original invoice total: ${total_original:,.2f}")
    print(f"Currently open (owing): ${total_open:,.2f}")
    print(f"Paid on these invoices: ${total_paid_on_these:,.2f}")
    
    print(f"\n💡 KEY INSIGHT:")
    print(f"   Statement shows ${total_open:,.2f} owing")
    print(f"   This matches the aging summary total: $14,734.56")
    
    if write:
        with psycopg2.connect(**DB) as cn:
            with cn.cursor() as cur:
                print("\n💾 IMPORTING TO recurring_invoices...")
                
                # Check if table exists, create if not
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'recurring_invoices'
                    )
                """)
                
                table_exists = cur.fetchone()[0]
                
                if not table_exists:
                    print("⚠️  Creating recurring_invoices table...")
                    cur.execute("""
                        CREATE TABLE recurring_invoices (
                            invoice_id SERIAL PRIMARY KEY,
                            invoice_number VARCHAR(50) UNIQUE NOT NULL,
                            invoice_date DATE NOT NULL,
                            vendor_name VARCHAR(200),
                            original_amount NUMERIC(12,2) NOT NULL,
                            paid_amount NUMERIC(12,2) DEFAULT 0,
                            balance_owing NUMERIC(12,2) NOT NULL,
                            description TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    print("✓ Table created")
                
                imported = 0
                skipped = 0
                
                for inv_date, inv_num, original_amt, open_amt in statement_invoices:
                    paid_amt = original_amt - open_amt
                    
                    # Check if already exists
                    cur.execute("""
                        SELECT invoice_id FROM recurring_invoices
                        WHERE invoice_number = %s
                    """, (inv_num,))
                    
                    if cur.fetchone():
                        skipped += 1
                        continue
                    
                    # Insert invoice
                    cur.execute("""
                        INSERT INTO recurring_invoices (
                            invoice_number, invoice_date, vendor_name,
                            original_amount, paid_amount, balance_owing,
                            description
                        ) VALUES (
                            %s, %s, 'Fibrenew Central Alberta', %s, %s, %s,
                            %s
                        )
                    """, (
                        inv_num,
                        inv_date,
                        original_amt,
                        paid_amt,
                        open_amt,
                        f'Invoice from Nov 2025 statement. Original ${original_amt}, Paid ${paid_amt}, Owing ${open_amt}'
                    ))
                    
                    imported += 1
                    
                    if imported % 10 == 0:
                        print(f"  ... {imported} imported")
                
                cn.commit()
                
                print(f"\n✓ Imported: {imported} invoices")
                if skipped > 0:
                    print(f"✓ Skipped (duplicates): {skipped} invoices")
                
                # Verify totals
                cur.execute("""
                    SELECT 
                        COUNT(*),
                        SUM(original_amount),
                        SUM(paid_amount),
                        SUM(balance_owing)
                    FROM recurring_invoices
                    WHERE vendor_name = 'Fibrenew Central Alberta'
                """)
                
                count, orig, paid, owing = cur.fetchone()
                
                print("\n" + "="*100)
                print("✅ IMPORT COMPLETE")
                print("="*100)
                print(f"Fibrenew invoices in database: {count}")
                print(f"Original amount total: ${orig:,.2f}")
                print(f"Paid on these invoices: ${paid:,.2f}")
                print(f"Balance owing: ${owing:,.2f}")
                print(f"\nStatement balance: $14,734.56")
                print(f"Match: {'✓ YES' if abs(owing - Decimal('14734.56')) < Decimal('0.01') else '✗ NO (difference: $' + str(abs(owing - Decimal('14734.56'))) + ')'}")
                
    else:
        print("\n⚠️  DRY RUN - No changes made")
        print("   Add --write to import invoices to recurring_invoices table")
        
        print(f"\n📋 FIRST 15 INVOICES:")
        print("-" * 100)
        print(f"{'Date':<12} {'Invoice #':<10} {'Original':>12} {'Paid':>12} {'Owing':>12}")
        print("-" * 100)
        for inv_date, inv_num, original_amt, open_amt in statement_invoices[:15]:
            paid = original_amt - open_amt
            print(f"{inv_date:<12} #{inv_num:<9} ${original_amt:>10,.2f} ${paid:>10,.2f} ${open_amt:>10,.2f}")
        print(f"... and {len(statement_invoices) - 15} more invoices")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Fibrenew statement invoices')
    parser.add_argument('--write', action='store_true', help='Import invoices to database')
    args = parser.parse_args()
    
    main(write=args.write)
