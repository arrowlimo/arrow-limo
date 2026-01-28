#!/usr/bin/env python3
"""
Compare oldlms.mdb vs lms.mdb for 2007-2023 reservation data.

Focus on:
- Driver information differences
- Payment records differences
- Any data loss or irregularities
- Charter field changes

READ-ONLY analysis - NO data modifications!
"""

import pyodbc
from datetime import datetime
from collections import defaultdict

OLD_LMS_PATH = r'L:\limo\backups\oldlms.mdb'
CURRENT_LMS_PATH = r'L:\limo\backups\lms.mdb'

def get_lms_connection(path):
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};'
    return pyodbc.connect(conn_str)

def get_reserve_data(conn, label):
    """Get all reserve records with driver and payment info."""
    print(f'\nReading {label} Reserve table...')
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            Reserve_No,
            Account_No,
            PU_Date,
            Rate,
            Balance,
            Deposit,
            Name,
            Vehicle,
            Driver,
            Notes,
            Pymt_Type
        FROM Reserve
        WHERE PU_Date >= #2007-01-01# AND PU_Date < #2024-01-01#
        ORDER BY Reserve_No
    """)
    
    reserves = {}
    for row in cur.fetchall():
        reserves[row[0]] = {
            'reserve_no': row[0],
            'account_no': row[1],
            'pu_date': row[2],
            'rate': float(row[3]) if row[3] else 0.0,
            'balance': float(row[4]) if row[4] else 0.0,
            'deposit': float(row[5]) if row[5] else 0.0,
            'name': row[6] if row[6] else '',
            'vehicle': row[7] if row[7] else '',
            'driver': row[8] if row[8] else '',
            'notes': row[9] if row[9] else '',
            'pymt_type': row[10] if row[10] else ''
        }
    
    print(f'  Loaded {len(reserves)} reserves from {label}')
    return reserves

def get_payment_data(conn, label):
    """Get all payment records."""
    print(f'\nReading {label} Payment table...')
    cur = conn.cursor()
    
    # First check what columns exist
    cur.execute("SELECT TOP 1 * FROM Payment")
    columns = [desc[0] for desc in cur.description]
    print(f'  Payment table columns: {", ".join(columns)}')
    
    cur.execute("""
        SELECT 
            PaymentID,
            Reserve_No,
            Account_No,
            Amount,
            [Key],
            LastUpdated,
            LastUpdatedBy
        FROM Payment
        ORDER BY PaymentID
    """)
    
    payments = {}
    reserve_payments = defaultdict(list)
    
    for row in cur.fetchall():
        payment_id = row[0]
        reserve_no = row[1] if row[1] else ''
        
        payment_data = {
            'payment_id': payment_id,
            'reserve_no': reserve_no,
            'account_no': row[2] if row[2] else '',
            'amount': float(row[3]) if row[3] else 0.0,
            'key': row[4] if row[4] else '',
            'last_updated': row[5],
            'last_updated_by': row[6] if row[6] else ''
        }
        
        payments[payment_id] = payment_data
        if reserve_no:
            reserve_payments[reserve_no].append(payment_data)
    
    print(f'  Loaded {len(payments)} payments from {label}')
    print(f'  Linked to {len(reserve_payments)} unique reserves')
    return payments, reserve_payments

def main():
    print('=' * 100)
    print('LMS DATABASE COMPARISON ANALYSIS')
    print('Comparing: oldlms.mdb vs lms.mdb (2007-2023)')
    print('READ-ONLY - No data modifications')
    print('=' * 100)
    
    # Connect to both databases
    print('\nConnecting to databases...')
    old_conn = get_lms_connection(OLD_LMS_PATH)
    curr_conn = get_lms_connection(CURRENT_LMS_PATH)
    
    # Get reserve data
    old_reserves = get_reserve_data(old_conn, 'OLD LMS')
    curr_reserves = get_reserve_data(curr_conn, 'CURRENT LMS')
    
    # Get payment data
    old_payments, old_reserve_payments = get_payment_data(old_conn, 'OLD LMS')
    curr_payments, curr_reserve_payments = get_payment_data(curr_conn, 'CURRENT LMS')
    
    print('\n\n' + '=' * 100)
    print('RESERVE RECORDS COMPARISON')
    print('=' * 100)
    
    # Find reserves only in old
    only_in_old = set(old_reserves.keys()) - set(curr_reserves.keys())
    only_in_curr = set(curr_reserves.keys()) - set(old_reserves.keys())
    in_both = set(old_reserves.keys()) & set(curr_reserves.keys())
    
    print(f'\nReserve counts:')
    print(f'  OLD LMS only: {len(only_in_old)} reserves')
    print(f'  CURRENT LMS only: {len(only_in_curr)} reserves')
    print(f'  In both: {len(in_both)} reserves')
    
    if only_in_old:
        print(f'\n⚠ RESERVES LOST (in OLD but not CURRENT):')
        for reserve_no in sorted(only_in_old)[:20]:  # Show first 20
            r = old_reserves[reserve_no]
            print(f'  {reserve_no}: {r["pu_date"]} - {r["name"]} - Rate: ${r["rate"]:.2f} - Driver: {r["driver"]}')
        if len(only_in_old) > 20:
            print(f'  ... and {len(only_in_old) - 20} more')
    
    if only_in_curr:
        print(f'\n✓ NEW RESERVES (in CURRENT but not OLD):')
        for reserve_no in sorted(only_in_curr)[:20]:  # Show first 20
            r = curr_reserves[reserve_no]
            print(f'  {reserve_no}: {r["pu_date"]} - {r["name"]} - Rate: ${r["rate"]:.2f}')
        if len(only_in_curr) > 20:
            print(f'  ... and {len(only_in_curr) - 20} more')
    
    # Compare reserves that exist in both
    print('\n\n' + '=' * 100)
    print('DRIVER INFORMATION CHANGES')
    print('=' * 100)
    
    driver_changes = []
    for reserve_no in sorted(in_both):
        old_driver = old_reserves[reserve_no]['driver']
        curr_driver = curr_reserves[reserve_no]['driver']
        
        if old_driver != curr_driver:
            driver_changes.append({
                'reserve_no': reserve_no,
                'date': old_reserves[reserve_no]['pu_date'],
                'name': old_reserves[reserve_no]['name'],
                'old_driver': old_driver,
                'curr_driver': curr_driver
            })
    
    print(f'\nFound {len(driver_changes)} driver field changes')
    if driver_changes:
        print('\nSample driver changes (first 50):')
        for change in driver_changes[:50]:
            print(f'  {change["reserve_no"]}: "{change["old_driver"]}" → "{change["curr_driver"]}"')
            print(f'    Date: {change["date"]}, Client: {change["name"]}')
        
        if len(driver_changes) > 50:
            print(f'\n  ... and {len(driver_changes) - 50} more driver changes')
    
    # Check for lost driver info (had driver, now empty)
    lost_drivers = [c for c in driver_changes if c['old_driver'] and not c['curr_driver']]
    if lost_drivers:
        print(f'\n⚠ CRITICAL: {len(lost_drivers)} reserves LOST driver information!')
        for change in lost_drivers[:20]:
            print(f'  {change["reserve_no"]}: Lost driver "{change["old_driver"]}"')
    
    # Check for gained driver info (empty, now has driver)
    gained_drivers = [c for c in driver_changes if not c['old_driver'] and c['curr_driver']]
    if gained_drivers:
        print(f'\n✓ {len(gained_drivers)} reserves GAINED driver information')
    
    # Compare financial fields
    print('\n\n' + '=' * 100)
    print('FINANCIAL FIELD CHANGES (Rate, Balance, Deposit)')
    print('=' * 100)
    
    financial_changes = []
    for reserve_no in sorted(in_both):
        old_r = old_reserves[reserve_no]
        curr_r = curr_reserves[reserve_no]
        
        if (old_r['rate'] != curr_r['rate'] or 
            old_r['balance'] != curr_r['balance'] or 
            old_r['deposit'] != curr_r['deposit']):
            
            financial_changes.append({
                'reserve_no': reserve_no,
                'date': old_r['pu_date'],
                'name': old_r['name'],
                'old_rate': old_r['rate'],
                'curr_rate': curr_r['rate'],
                'old_balance': old_r['balance'],
                'curr_balance': curr_r['balance'],
                'old_deposit': old_r['deposit'],
                'curr_deposit': curr_r['deposit']
            })
    
    print(f'\nFound {len(financial_changes)} financial field changes')
    if financial_changes:
        print('\nSample financial changes (first 30):')
        for change in financial_changes[:30]:
            print(f'\n  {change["reserve_no"]} - {change["name"]}:')
            if change['old_rate'] != change['curr_rate']:
                print(f'    Rate: ${change["old_rate"]:.2f} → ${change["curr_rate"]:.2f}')
            if change['old_balance'] != change['curr_balance']:
                print(f'    Balance: ${change["old_balance"]:.2f} → ${change["curr_balance"]:.2f}')
            if change['old_deposit'] != change['curr_deposit']:
                print(f'    Deposit: ${change["old_deposit"]:.2f} → ${change["curr_deposit"]:.2f}')
        
        if len(financial_changes) > 30:
            print(f'\n  ... and {len(financial_changes) - 30} more financial changes')
    
    # Payment comparison
    print('\n\n' + '=' * 100)
    print('PAYMENT RECORDS COMPARISON')
    print('=' * 100)
    
    print(f'\nPayment counts:')
    print(f'  OLD LMS: {len(old_payments)} payments')
    print(f'  CURRENT LMS: {len(curr_payments)} payments')
    
    only_in_old_payments = set(old_payments.keys()) - set(curr_payments.keys())
    only_in_curr_payments = set(curr_payments.keys()) - set(old_payments.keys())
    
    if only_in_old_payments:
        print(f'\n⚠ PAYMENTS LOST: {len(only_in_old_payments)} payments in OLD but not CURRENT')
        print('\nSample lost payments (first 20):')
        for payment_id in sorted(only_in_old_payments)[:20]:
            p = old_payments[payment_id]
            print(f'  Payment {payment_id}: Reserve {p["reserve_no"]}, ${p["amount"]:.2f}, Key: {p["key"]}')
    
    if only_in_curr_payments:
        print(f'\n✓ NEW PAYMENTS: {len(only_in_curr_payments)} payments in CURRENT but not OLD')
    
    # Check payment amounts for same payment IDs
    print('\n\n' + '=' * 100)
    print('PAYMENT AMOUNT CHANGES')
    print('=' * 100)
    
    payment_amount_changes = []
    for payment_id in set(old_payments.keys()) & set(curr_payments.keys()):
        old_p = old_payments[payment_id]
        curr_p = curr_payments[payment_id]
        
        if old_p['amount'] != curr_p['amount']:
            payment_amount_changes.append({
                'payment_id': payment_id,
                'reserve_no': old_p['reserve_no'],
                'old_amount': old_p['amount'],
                'curr_amount': curr_p['amount'],
                'difference': curr_p['amount'] - old_p['amount']
            })
    
    if payment_amount_changes:
        print(f'\n⚠ Found {len(payment_amount_changes)} payment amount changes!')
        for change in payment_amount_changes[:30]:
            print(f'  Payment {change["payment_id"]} (Reserve {change["reserve_no"]}):')
            print(f'    ${change["old_amount"]:.2f} → ${change["curr_amount"]:.2f} (Δ ${change["difference"]:.2f})')
        
        if len(payment_amount_changes) > 30:
            print(f'  ... and {len(payment_amount_changes) - 30} more payment changes')
    else:
        print('\n✓ No payment amount changes found')
    
    # Check reserves that lost ALL payment links
    print('\n\n' + '=' * 100)
    print('RESERVES WITH LOST PAYMENT LINKS')
    print('=' * 100)
    
    lost_payment_links = []
    for reserve_no in sorted(in_both):
        old_payment_count = len(old_reserve_payments.get(reserve_no, []))
        curr_payment_count = len(curr_reserve_payments.get(reserve_no, []))
        
        if old_payment_count > 0 and curr_payment_count == 0:
            lost_payment_links.append({
                'reserve_no': reserve_no,
                'date': old_reserves[reserve_no]['pu_date'],
                'name': old_reserves[reserve_no]['name'],
                'lost_payment_count': old_payment_count,
                'lost_payments': old_reserve_payments[reserve_no]
            })
    
    if lost_payment_links:
        print(f'\n⚠ CRITICAL: {len(lost_payment_links)} reserves LOST ALL payment links!')
        for item in lost_payment_links[:20]:
            print(f'\n  {item["reserve_no"]} - {item["name"]} ({item["date"]}):')
            print(f'    Lost {item["lost_payment_count"]} payment(s):')
            for p in item['lost_payments']:
                print(f'      Payment {p["payment_id"]}: ${p["amount"]:.2f}, Key: {p["key"]}')
        
        if len(lost_payment_links) > 20:
            print(f'\n  ... and {len(lost_payment_links) - 20} more reserves with lost payment links')
    else:
        print('\n✓ No reserves lost payment links')
    
    # Summary statistics
    print('\n\n' + '=' * 100)
    print('SUMMARY STATISTICS')
    print('=' * 100)
    
    total_old_rate = sum(r['rate'] for r in old_reserves.values())
    total_curr_rate = sum(r['rate'] for r in curr_reserves.values())
    total_old_payments = sum(p['amount'] for p in old_payments.values())
    total_curr_payments = sum(p['amount'] for p in curr_payments.values())
    
    print(f'\nReserve totals:')
    print(f'  OLD LMS total rate: ${total_old_rate:,.2f}')
    print(f'  CURRENT LMS total rate: ${total_curr_rate:,.2f}')
    print(f'  Difference: ${total_curr_rate - total_old_rate:,.2f}')
    
    print(f'\nPayment totals:')
    print(f'  OLD LMS total payments: ${total_old_payments:,.2f}')
    print(f'  CURRENT LMS total payments: ${total_curr_payments:,.2f}')
    print(f'  Difference: ${total_curr_payments - total_old_payments:,.2f}')
    
    # Write detailed report to file
    print('\n\n' + '=' * 100)
    print('WRITING DETAILED REPORT')
    print('=' * 100)
    
    report_file = 'L:\\limo\\reports\\LMS_COMPARISON_REPORT.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('LMS DATABASE COMPARISON REPORT\n')
        f.write('=' * 100 + '\n')
        f.write(f'Generated: {datetime.now()}\n')
        f.write(f'Comparing: {OLD_LMS_PATH}\n')
        f.write(f'Against:   {CURRENT_LMS_PATH}\n')
        f.write(f'Period: 2007-2023\n')
        f.write('=' * 100 + '\n\n')
        
        # Reserves only in old
        if only_in_old:
            f.write('RESERVES IN OLD LMS BUT NOT CURRENT (LOST):\n')
            f.write('-' * 100 + '\n')
            for reserve_no in sorted(only_in_old):
                r = old_reserves[reserve_no]
                f.write(f'{reserve_no}\t{r["pu_date"]}\t{r["name"]}\t${r["rate"]:.2f}\t{r["driver"]}\n')
            f.write(f'\nTotal lost: {len(only_in_old)}\n\n')
        
        # Driver changes
        if lost_drivers:
            f.write('RESERVES WITH LOST DRIVER INFORMATION:\n')
            f.write('-' * 100 + '\n')
            for change in lost_drivers:
                f.write(f'{change["reserve_no"]}\t{change["date"]}\t{change["name"]}\t')
                f.write(f'OLD: "{change["old_driver"]}" → CURRENT: (empty)\n')
            f.write(f'\nTotal lost drivers: {len(lost_drivers)}\n\n')
        
        # Payment losses
        if lost_payment_links:
            f.write('RESERVES WITH LOST PAYMENT LINKS:\n')
            f.write('-' * 100 + '\n')
            for item in lost_payment_links:
                f.write(f'{item["reserve_no"]}\t{item["date"]}\t{item["name"]}\n')
                for p in item['lost_payments']:
                    f.write(f'  → Lost Payment {p["payment_id"]}: ${p["amount"]:.2f}, Key: {p["key"]}\n')
            f.write(f'\nTotal reserves with lost payments: {len(lost_payment_links)}\n\n')
        
        # Financial changes
        if financial_changes:
            f.write('FINANCIAL FIELD CHANGES:\n')
            f.write('-' * 100 + '\n')
            for change in financial_changes:
                f.write(f'{change["reserve_no"]}\t{change["name"]}\n')
                if change['old_rate'] != change['curr_rate']:
                    f.write(f'  Rate: ${change["old_rate"]:.2f} → ${change["curr_rate"]:.2f}\n')
                if change['old_balance'] != change['curr_balance']:
                    f.write(f'  Balance: ${change["old_balance"]:.2f} → ${change["curr_balance"]:.2f}\n')
                if change['old_deposit'] != change['curr_deposit']:
                    f.write(f'  Deposit: ${change["old_deposit"]:.2f} → ${change["curr_deposit"]:.2f}\n')
            f.write(f'\nTotal financial changes: {len(financial_changes)}\n\n')
    
    print(f'\n✓ Detailed report written to: {report_file}')
    
    old_conn.close()
    curr_conn.close()
    
    print('\n' + '=' * 100)
    print('ANALYSIS COMPLETE - NO DATA MODIFIED')
    print('=' * 100)

if __name__ == '__main__':
    main()
