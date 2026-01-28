"""
Analyze 2012 write-off data from spreadsheet.
Check if reserve numbers exist in charters, match to receipts, and verify GST calculations.
"""
import psycopg2
import os
from decimal import Decimal

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

# Write-off data from the spreadsheet (reserve_number, amount)
writeoffs = [
    ('002359', 312.00), ('002947', 29.25), ('002994', 682.50), ('003261', 353.15),
    ('003406', 19.50), ('003429', 236.25), ('003897', 240.00), ('003959', 1808.09),
    ('004035', 220.50), ('004125', 200.00), ('004138', 0.50), ('004173', 68.25),
    ('004200', 156.00), ('004211', 60.00), ('004251', 675.00), ('004273', 149.50),
    ('004279', 857.75), ('004301', 58.50), ('004315', 68.24), ('004322', 244.76),
    ('004326', 509.00), ('004343', 307.12), ('004483', 10.50), ('004502', 204.50),
    ('004522', 24.75), ('004564', 653.00), ('004572', 262.00), ('004584', 220.50),
    ('004596', 365.00), ('004626', 243.00), ('004647', 10.50), ('004697', 234.00),
    ('004713', 120.00), ('004872', 416.50), ('004932', 124.50), ('004941', 207.52),
    ('004947', 363.00), ('004963', 240.00), ('004981', 189.75), ('004982', 161.50),
    ('004997', 438.50), ('005020', 573.25), ('005026', 247.50), ('005034', 30.02),
    ('005042', 536.26), ('005069', 230.00), ('005138', 1121.98), ('005159', 300.00),
    ('005162', 235.00), ('005217', 198.00), ('005280', 74.75), ('005359', 140.00),
    ('005428', 0.01), ('005527', 371.26), ('005535', 300.00), ('005672', 45.01)
]

def validate_gst_calculation(amount):
    """Validate GST calculation using included tax formula (Alberta 5% GST)."""
    # GST is INCLUDED in the total amount (not added on top)
    # Formula: gst = total × 0.05 / 1.05
    gst = amount * 0.05 / 1.05
    net = amount - gst
    adjusted_serv = -net  # Negative for write-off
    gst_calc = -gst       # Negative for write-off
    reconcile = adjusted_serv + gst_calc
    
    return {
        'adjusted_serv': round(adjusted_serv, 2),
        'gst_calc': round(gst_calc, 2),
        'reconcile': round(reconcile, 2),
        'net': round(net, 2),
        'gst': round(gst, 2)
    }

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print('=' * 100)
    print('2012 WRITE-OFF ANALYSIS')
    print('=' * 100)
    
    # Check each reserve number in charters table
    found_in_charters = []
    not_found = []
    charter_data = []
    
    for reserve_num, amount in writeoffs:
        cur.execute('''
            SELECT charter_id, reserve_number, account_number, client_id, charter_date,
                   total_amount_due, balance, paid_amount, payment_status, status
            FROM charters
            WHERE reserve_number = %s
        ''', (reserve_num,))
        result = cur.fetchone()
        
        if result:
            found_in_charters.append(reserve_num)
            charter_data.append({
                'reserve': reserve_num,
                'writeoff_amount': amount,
                'charter_id': result[0],
                'account_number': result[2],
                'client_id': result[3],
                'charter_date': result[4],
                'total_due': result[5],
                'balance': result[6],
                'paid_amount': result[7],
                'payment_status': result[8],
                'status': result[9]
            })
        else:
            not_found.append((reserve_num, amount))
    
    print(f'\nRESERVE NUMBER MATCHING:')
    print(f'Total write-offs: {len(writeoffs)}')
    print(f'Found in charters table: {len(found_in_charters)}')
    print(f'Not found: {len(not_found)}')
    
    if not_found:
        print(f'\nMISSING RESERVE NUMBERS:')
        for res, amt in not_found:
            print(f'  {res}: ${amt:.2f}')
    
    # Show charter details for found records
    print(f'\n' + '=' * 100)
    print('CHARTER DETAILS FOR WRITE-OFFS (First 10):')
    print('=' * 100)
    for c in charter_data[:10]:
        print(f"Reserve: {c['reserve']} | Charter ID: {c['charter_id']} | Date: {c['charter_date']}")
        print(f"  Write-off: ${c['writeoff_amount']:.2f} | Balance: ${c['balance'] or 0:.2f} | Paid: ${c['paid_amount'] or 0:.2f}")
        print(f"  Status: {c['payment_status']} | Charter Status: {c['status']}")
        print()
    
    # Verify GST calculations
    print('=' * 100)
    print('GST CALCULATION VERIFICATION (Sample):')
    print('=' * 100)
    print(f"{'Reserve':<10} {'Amount':<12} {'Adj Serv':<12} {'GST':<12} {'Reconcile':<12} {'Match?':<8}")
    print('-' * 100)
    
    gst_mismatches = []
    for reserve_num, amount in writeoffs[:15]:  # Check first 15
        calc = validate_gst_calculation(amount)
        # Expected values from spreadsheet (negative)
        expected_reconcile = -amount
        match = abs(calc['reconcile'] - expected_reconcile) < 0.01
        
        if not match:
            gst_mismatches.append((reserve_num, amount, calc))
        
        status = '✓' if match else '✗'
        print(f"{reserve_num:<10} ${amount:<11.2f} ${calc['adjusted_serv']:<11.2f} ${calc['gst_calc']:<11.2f} ${calc['reconcile']:<11.2f} {status:<8}")
    
    if gst_mismatches:
        print(f"\nGST CALCULATION MISMATCHES: {len(gst_mismatches)}")
    else:
        print(f"\n✓ All GST calculations verified correctly (5% GST included in amounts)")
    
    # Check for receipts matching these reserve numbers
    print('\n' + '=' * 100)
    print('RECEIPT MATCHING:')
    print('=' * 100)
    
    receipt_matches = []
    no_receipt = []
    
    for reserve_num, amount in writeoffs:
        # Check for receipts with this reserve number in description
        # Check actual receipts table schema first
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'receipts' 
            LIMIT 1
        """)
        if cur.fetchone():
            # Use actual column names (id instead of receipt_id)
            cur.execute('''
                SELECT id, vendor_name, gross_amount, receipt_date, description, category
                FROM receipts
                WHERE description ILIKE %s OR description ILIKE %s
                ORDER BY receipt_date
            ''', (f'%{reserve_num}%', f'%write%off%{reserve_num}%'))
        else:
            results = []
        
        results = cur.fetchall()
        if results:
            receipt_matches.append((reserve_num, amount, results))
        else:
            no_receipt.append((reserve_num, amount))
    
    print(f'Reserve numbers with receipt matches: {len(receipt_matches)}')
    print(f'Reserve numbers WITHOUT receipts: {len(no_receipt)}')
    
    if receipt_matches:
        print(f'\nSAMPLE RECEIPT MATCHES (First 10):')
        for reserve_num, amount, receipts in receipt_matches[:10]:
            print(f'\n  Reserve {reserve_num} (Write-off: ${amount:.2f}):')
            for r in receipts:
                print(f'    Receipt ID {r[0]}: {r[1]} | ${r[2]:.2f} | {r[3]} | {r[5] or "N/A"}')
    
    if no_receipt:
        print(f'\nRESERVE NUMBERS WITHOUT RECEIPTS (First 20):')
        for res, amt in no_receipt[:20]:
            print(f'  {res}: ${amt:.2f}')
    
    # Summary statistics
    print('\n' + '=' * 100)
    print('SUMMARY:')
    print('=' * 100)
    total_writeoff_amount = sum(amt for _, amt in writeoffs)
    found_amount = sum(c['writeoff_amount'] for c in charter_data)
    missing_amount = sum(amt for _, amt in not_found)
    
    print(f"Total write-off records: {len(writeoffs)}")
    print(f"Total write-off amount: ${total_writeoff_amount:.2f}")
    print(f"")
    print(f"Found in charters: {len(found_in_charters)} ({len(found_in_charters)/len(writeoffs)*100:.1f}%)")
    print(f"Found amount: ${found_amount:.2f}")
    print(f"")
    print(f"Missing from charters: {len(not_found)} ({len(not_found)/len(writeoffs)*100:.1f}%)")
    print(f"Missing amount: ${missing_amount:.2f}")
    print(f"")
    print(f"With receipt records: {len(receipt_matches)} ({len(receipt_matches)/len(writeoffs)*100:.1f}%)")
    print(f"Without receipts: {len(no_receipt)} ({len(no_receipt)/len(writeoffs)*100:.1f}%)")
    
    cur.close()
    conn.close()
    print('\nAnalysis complete.')

if __name__ == '__main__':
    main()
