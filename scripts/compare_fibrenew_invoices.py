#!/usr/bin/env python3
"""
Extract all invoice numbers from Fibrenew statement screenshots and compare
to what's in the receipts/rent_debt_ledger tables.
"""
import psycopg2
import re

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# All invoices visible in the two statement screenshots
statement_invoices = [
    # Page 1 - 2019-2020
    ('2019-01-02', '#8696', 301.48, 193.84),
    ('2019-01-23', '#8693', 682.50, 682.50),
    ('2019-01-30', '#8697', 946.98, 946.98),
    ('2019-03-08', '#8765', 682.50, 682.50),
    ('2019-07-05', '#8890', 295.69, 295.69),
    ('2019-07-05', '#8891', 682.50, 682.50),
    ('2019-07-31', '#8743', 682.50, 682.50),
    ('2019-08-31', '#8744', 254.32, 254.32),
    ('2019-09-01', '#8932', 682.50, 682.50),
    ('2019-11-07', '#8933', 153.13, 153.13),
    ('2019-06-06', '#8894', 144.89, 144.89),
    ('2019-06-06', '#8895', 682.50, 682.50),
    ('2019-04-09', '#8942', 682.50, 682.50),
    ('2019-04-09', '#8943', 183.91, 183.91),
    ('2019-01-10', '#8979', 682.50, 682.50),
    ('2019-01-10', '#8980', 152.62, 152.62),
    ('2019-01-11', '#9325', 163.46, 163.46),
    ('2019-06-11', '#9066', 682.50, 682.50),
    ('2019-06-11', '#9067', 157.88, 157.88),
    ('2019-08-12', '#9103', 126.60, 126.60),
    ('2019-01-01', '#9135', 682.50, 682.50),
    ('2020-08-01', '#9139', 190.20, 190.20),
    ('2020-08-31', '#9239', 682.50, 682.50),
    ('2020-02-14', '#5001', 228.12, 228.12),
    ('2020-02-03', '#9239', 682.50, 682.50),  # Duplicate invoice number
    ('2020-03-30', '#0288', 304.47, 304.47),
    ('2020-01-04', '#9287', 682.50, 682.50),
    ('2020-04-14', '#9326', 199.26, 199.26),
    ('2020-06-23', '#9390', 156.64, 156.64),
    ('2020-02-07', '#9407', 840.00, 840.00),
    ('2020-07-22', '#9436', 134.81, 134.81),
    ('2020-08-05', '#9490', 840.00, 840.00),
    
    # Page 2 - 2020-2021
    ('2020-01-09', '#9542', 840.00, 840.00),
    ('2020-09-10', '#9561', 142.63, 142.63),
    ('2020-01-10', '#9609', 840.00, 840.00),
    ('2020-08-10', '#9633', 145.20, 145.20),
    ('2020-10-11', '#9666', 140.81, 140.81),
    ('2020-11-18', '#9694', 162.21, 162.21),
    ('2020-01-12', '#9737', 840.00, 840.00),
    ('2020-07-12', '#9742', 191.25, 191.25),
    ('2021-01-01', '#9767', 840.00, 840.00),
    ('2021-18-01', '#9772', 201.35, 201.35),
    ('2021-01-02', '#9800', 840.00, 840.00),
    ('2021-05-02', '#9815', 169.44, 169.44),
    ('2021-01-03', '#9868', 840.00, 840.00),
    ('2021-08-03', '#9895', 220.34, 220.34),
    ('2021-06-04', '#9956', 840.00, 840.00),
    
    # Page 3 - 2023-2024 (with journal entries and payments)
    # Journal Entry #21: -3,508.25 (shareholder earnings)
    # Journal Entry #22: -2,787.50 (shareholder wedding)
    
    ('2024-02-01', '#12131', 1102.50, 1102.50),
    ('2024-01-02', '#12132', 1102.50, 1102.50),
    ('2024-01-03', '#12133', 1102.50, 1102.50),
    ('2024-01-04', '#12177', 1102.50, 1102.50),
    ('2024-01-05', '#12228', 1102.50, 1102.50),
    ('2024-02-07', '#12412', 1102.50, 167.06),
    ('2024-01-09', '#12494', 1102.50, 1102.50),
    ('2024-01-10', '#12546', 1102.50, 1102.50),
    ('2024-01-11', '#12601', 1102.50, 1102.50),
    ('2024-04-11', '#12664', 1102.50, 1102.50),
    ('2025-02-12', '#12714', 1102.50, 1102.50),
    ('2025-05-12', '#12775', 1102.50, 1102.50),
    ('2025-01-01', '#12835', 1102.50, 1102.50),
    ('2025-07-01', '#12909', 1102.50, 1102.50),
    ('2025-03-04', '#12973', 1102.50, 1102.50),
    ('2025-04-04', '#13041', 1102.50, 1102.50),
    ('2025-01-06', '#13103', 1102.50, 1102.50),
    ('2025-04-07', '#13180', 1260.00, 1260.00),
    ('2025-01-08', '#13248', 1260.00, 1260.00),
    ('2025-01-09', '#13310', 1260.00, 1260.00),
    ('2025-02-10', '#13379', 1260.00, 1260.00),
]

print("\n" + "="*100)
print("FIBRENEW INVOICE RECONCILIATION")
print("="*100)

# Extract unique invoice numbers
statement_invoice_nums = set()
for date, inv_num, amt, open_amt in statement_invoices:
    statement_invoice_nums.add(inv_num)

print(f"\n📋 STATEMENT INVOICES: {len(statement_invoices)} total ({len(statement_invoice_nums)} unique)")

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Check receipts table for Fibrenew invoices
        cur.execute("""
            SELECT receipt_date, description, gross_amount, source_reference
            FROM receipts
            WHERE LOWER(vendor_name) LIKE '%fibrenew%'
            AND receipt_date >= '2019-01-01'
            ORDER BY receipt_date
        """)
        
        receipts = cur.fetchall()
        
        print(f"\n📦 DATABASE RECEIPTS: {len(receipts)} Fibrenew receipts since 2019")
        
        # Extract invoice numbers from descriptions
        receipt_invoice_nums = set()
        for date, desc, amt, ref in receipts:
            # Try to extract invoice number from description or reference
            if desc:
                matches = re.findall(r'#?\d{4,5}', desc)
                for match in matches:
                    receipt_invoice_nums.add(match.replace('#', '#'))
            if ref:
                matches = re.findall(r'#?\d{4,5}', ref)
                for match in matches:
                    receipt_invoice_nums.add(match.replace('#', '#'))
        
        print(f"   Found {len(receipt_invoice_nums)} invoice numbers in receipts")
        
        # Check recurring_invoices table
        cur.execute("""
            SELECT due_date, invoice_number, amount
            FROM recurring_invoices
            WHERE vendor_name = 'Fibrenew'
            AND due_date >= '2019-01-01'
            ORDER BY due_date
        """)
        
        recurring = cur.fetchall()
        print(f"\n🔁 RECURRING_INVOICES: {len(recurring)} entries")
        
        recurring_invoice_nums = set()
        for date, inv_num, amt in recurring:
            if inv_num:
                recurring_invoice_nums.add(inv_num)
        
        print(f"   {len(recurring_invoice_nums)} with invoice numbers")

# Compare statement to database
print("\n" + "="*100)
print("MISSING INVOICE ANALYSIS")
print("="*100)

all_db_invoices = receipt_invoice_nums | recurring_invoice_nums

missing_in_db = []
for date, inv_num, amt, open_amt in statement_invoices:
    clean_num = inv_num.replace('#', '')
    if inv_num not in all_db_invoices and clean_num not in all_db_invoices:
        missing_in_db.append((date, inv_num, amt, open_amt))

if missing_in_db:
    print(f"\n❌ MISSING FROM DATABASE: {len(missing_in_db)} invoices")
    print("-" * 100)
    print(f"{'Date':<12} {'Invoice':<10} {'Amount':>12} {'Still Owing':>15}")
    print("-" * 100)
    
    total_missing_amt = 0
    total_missing_open = 0
    
    for date, inv_num, amt, open_amt in missing_in_db:
        print(f"{date:<12} {inv_num:<10} ${amt:>10,.2f} ${open_amt:>12,.2f}")
        total_missing_amt += amt
        total_missing_open += open_amt
    
    print("-" * 100)
    print(f"{'TOTAL':<22} ${total_missing_amt:>10,.2f} ${total_missing_open:>12,.2f}")
else:
    print("\n✓ All statement invoices found in database")

# Check for invoices in DB but not on statement
extra_in_db = []
for inv_num in all_db_invoices:
    clean_num = inv_num.replace('#', '')
    found = False
    for date, stmt_inv, amt, open_amt in statement_invoices:
        if stmt_inv == inv_num or stmt_inv.replace('#', '') == clean_num:
            found = True
            break
    if not found:
        extra_in_db.append(inv_num)

if extra_in_db:
    print(f"\n⚠️  EXTRA IN DATABASE (not on statement): {len(extra_in_db)} invoices")
    print("   These may be fully paid invoices not shown on outstanding balance report:")
    for inv_num in sorted(extra_in_db)[:20]:  # Show first 20
        print(f"   - {inv_num}")
    if len(extra_in_db) > 20:
        print(f"   ... and {len(extra_in_db) - 20} more")

print("\n" + "="*100)
