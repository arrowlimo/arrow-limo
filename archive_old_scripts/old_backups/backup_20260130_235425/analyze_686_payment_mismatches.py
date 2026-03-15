#!/usr/bin/env python3
"""
DETAILED ANALYSIS OF 686 PAYMENT MISMATCHES
===========================================

For each charter with payment mismatch, show:
1. Original matching method (how payment was linked)
2. Why it's not matching now (what changed)
3. LMS status (is this payment in LMS?)
4. Customer, charter, payment details
5. Root cause of mismatch
"""
import os
import csv
import psycopg2
import pyodbc
from decimal import Decimal
from datetime import datetime

# Connect to PostgreSQL
pg_conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
pg_cur = pg_conn.cursor()

# Connect to LMS
try:
    LMS_PATH = r'L:\limo\backups\lms.mdb'
    lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    lms_available = True
    print("✓ Connected to LMS")
except Exception as e:
    print(f"⚠ LMS not available: {e}")
    lms_available = False
    lms_conn = None
    lms_cur = None

print("="*120)
print("DETAILED ANALYSIS OF 686 PAYMENT MISMATCHES")
print("="*120)
print()

# Get all charters with payment mismatches
pg_cur.execute("""
    WITH payment_sums AS (
        SELECT 
            reserve_number,
            COUNT(*) as payment_count,
            SUM(amount) as total_paid,
            ARRAY_AGG(payment_id ORDER BY payment_date) as payment_ids,
            ARRAY_AGG(amount ORDER BY payment_date) as amounts,
            ARRAY_AGG(payment_date ORDER BY payment_date) as dates,
            ARRAY_AGG(payment_method ORDER BY payment_date) as methods,
            ARRAY_AGG(payment_key ORDER BY payment_date) as keys,
            ARRAY_AGG(COALESCE(charter_id, 0) ORDER BY payment_date) as charter_ids_used,
            ARRAY_AGG(notes ORDER BY payment_date) as payment_notes
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        c.reserve_number,
        c.charter_id,
        c.charter_date,
        c.account_number,
        cl.client_name,
        c.paid_amount,
        ps.total_paid as sum_payments,
        c.paid_amount - ps.total_paid as difference,
        ps.payment_count,
        ps.payment_ids,
        ps.amounts,
        ps.dates,
        ps.methods,
        ps.keys,
        ps.charter_ids_used,
        ps.payment_notes,
        c.total_amount_due,
        c.balance,
        c.status,
        c.created_at,
        c.updated_at
    FROM charters c
    INNER JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    WHERE c.cancelled = FALSE
      AND ABS(COALESCE(c.paid_amount,0) - ps.total_paid) > 0.01
    ORDER BY ABS(c.paid_amount - ps.total_paid) DESC
""")

mismatches = pg_cur.fetchall()
print(f"Found {len(mismatches)} charters with payment mismatches")
print()

# Analyze each mismatch
detailed_results = []

for idx, row in enumerate(mismatches, 1):
    (reserve, charter_id, charter_date, account, client, paid_amt, sum_pay, diff, 
     pay_count, pay_ids, amounts, dates, methods, keys, charter_ids_used, notes,
     total_due, balance, status, created_at, updated_at) = row
    
    if idx <= 10 or idx % 100 == 0:
        print(f"Processing {idx}/{len(mismatches)}: {reserve}")
    
    result = {
        'reserve_number': reserve,
        'charter_id': charter_id,
        'charter_date': charter_date,
        'account_number': account,
        'client_name': client or 'Unknown',
        'charter_paid_amount': float(paid_amt or 0),
        'sum_payments': float(sum_pay),
        'difference': float(diff),
        'payment_count': pay_count,
        'total_amount_due': float(total_due or 0),
        'balance': float(balance or 0),
        'charter_status': status or '',
        'charter_created_at': created_at,
        'charter_updated_at': updated_at
    }
    
    # Analyze individual payments
    payment_details = []
    lms_payment_count = 0
    non_lms_payment_count = 0
    linkage_methods = set()
    root_causes = set()
    
    for i in range(pay_count):
        pay_id = pay_ids[i]
        amount = float(amounts[i])
        pay_date = dates[i]
        method = methods[i] or 'unknown'
        key = keys[i] or ''
        cid_used = charter_ids_used[i]
        note = notes[i] or ''
        
        # Determine linkage method
        if cid_used == charter_id:
            linkage = 'charter_id'
            linkage_methods.add('charter_id')
        else:
            linkage = 'reserve_number'
            linkage_methods.add('reserve_number')
        
        # Check if payment exists in LMS
        in_lms = False
        lms_info = ''
        if lms_available and key:
            try:
                lms_cur.execute("SELECT PaymentID, Account_No, Reserve_No, Amount, LastUpdated FROM Payment WHERE [Key] = ?", (key,))
                lms_row = lms_cur.fetchone()
                if lms_row:
                    in_lms = True
                    lms_payment_count += 1
                    lms_pid, lms_acct, lms_res, lms_amt, lms_date = lms_row
                    lms_info = f"LMS:{lms_pid}/Res:{lms_res}/Amt:{lms_amt}"
                    
                    # Check if LMS reserve matches
                    if lms_res != reserve:
                        root_causes.add('lms_reserve_mismatch')
                else:
                    non_lms_payment_count += 1
            except:
                pass
        elif not key:
            non_lms_payment_count += 1
            root_causes.add('no_payment_key')
        
        # Identify source system
        source = 'unknown'
        if key and key.startswith('LMSDEP:'):
            source = 'lms_deposit'
            root_causes.add('lms_deposit')
        elif key and key.startswith('BTX:'):
            source = 'banking'
            root_causes.add('banking_import')
        elif key and key.startswith('SQ:'):
            source = 'square'
            root_causes.add('square_import')
        elif in_lms:
            source = 'lms'
        elif method in ('credit_card', 'debit_card'):
            source = 'card_processing'
            root_causes.add('card_processing')
        elif 'square' in note.lower():
            source = 'square'
            root_causes.add('square_import')
        
        payment_details.append({
            'payment_id': pay_id,
            'amount': amount,
            'date': pay_date,
            'method': method,
            'key': key,
            'linkage': linkage,
            'source': source,
            'in_lms': in_lms,
            'lms_info': lms_info
        })
    
    # Determine root cause
    if len(linkage_methods) > 1:
        root_causes.add('mixed_linkage')
    
    if non_lms_payment_count > 0 and lms_payment_count > 0:
        root_causes.add('mixed_sources')
    elif non_lms_payment_count == pay_count:
        root_causes.add('all_non_lms')
    
    # Check for payment date vs charter creation
    if payment_details and created_at:
        earliest_payment = min(p['date'] for p in payment_details)
        # Convert both to dates for comparison
        created_date = created_at.date() if hasattr(created_at, 'date') else created_at
        payment_date = earliest_payment if isinstance(earliest_payment, datetime) else earliest_payment
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()
        
        if payment_date > created_date:
            days_diff = (payment_date - created_date).days
            if days_diff > 30:
                root_causes.add('late_payment_import')
    
    # Check if paid_amount was never updated
    if paid_amt == 0 and sum_pay > 0:
        root_causes.add('paid_amount_never_set')
    elif paid_amt > 0 and paid_amt < sum_pay:
        root_causes.add('paid_amount_not_updated')
    elif paid_amt > sum_pay:
        root_causes.add('overstated_paid_amount')
    
    result['lms_payment_count'] = lms_payment_count
    result['non_lms_payment_count'] = non_lms_payment_count
    result['linkage_methods'] = ', '.join(sorted(linkage_methods))
    result['root_causes'] = ', '.join(sorted(root_causes))
    result['payment_details_json'] = str(payment_details)
    
    detailed_results.append(result)

print()
print("="*120)
print("ANALYSIS COMPLETE")
print("="*120)
print()

# Summary statistics
root_cause_counts = {}
for r in detailed_results:
    causes = r['root_causes'].split(', ')
    for cause in causes:
        if cause:
            root_cause_counts[cause] = root_cause_counts.get(cause, 0) + 1

print("ROOT CAUSE BREAKDOWN:")
print("-" * 80)
for cause, count in sorted(root_cause_counts.items(), key=lambda x: -x[1]):
    print(f"  {cause:<40} {count:>6} charters")

print()
print("LINKAGE METHOD BREAKDOWN:")
linkage_counts = {}
for r in detailed_results:
    linkage = r['linkage_methods']
    linkage_counts[linkage] = linkage_counts.get(linkage, 0) + 1
for linkage, count in sorted(linkage_counts.items(), key=lambda x: -x[1]):
    print(f"  {linkage:<40} {count:>6} charters")

print()
print("LMS vs NON-LMS PAYMENT DISTRIBUTION:")
all_lms = len([r for r in detailed_results if r['non_lms_payment_count'] == 0])
all_non_lms = len([r for r in detailed_results if r['lms_payment_count'] == 0])
mixed = len([r for r in detailed_results if r['lms_payment_count'] > 0 and r['non_lms_payment_count'] > 0])
print(f"  All LMS payments:        {all_lms:>6} charters")
print(f"  All non-LMS payments:    {all_non_lms:>6} charters")
print(f"  Mixed LMS/non-LMS:       {mixed:>6} charters")

# Export detailed CSV
print()
print("="*120)
print("EXPORTING DETAILED REPORT")
print("="*120)

csv_file = 'reports/payment_mismatch_detailed_analysis.csv'
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = [
        'reserve_number', 'charter_id', 'charter_date', 'account_number', 'client_name',
        'charter_paid_amount', 'sum_payments', 'difference', 'payment_count',
        'total_amount_due', 'balance', 'charter_status',
        'lms_payment_count', 'non_lms_payment_count', 'linkage_methods', 'root_causes',
        'charter_created_at', 'charter_updated_at', 'payment_details_json'
    ]
    
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(detailed_results)

print(f"✓ Detailed analysis: {csv_file} ({len(detailed_results)} rows)")

# Export individual payment details
csv_file2 = 'reports/payment_mismatch_individual_payments.csv'
with open(csv_file2, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Reserve_Number', 'Charter_ID', 'Client', 'Charter_Date',
        'Payment_ID', 'Payment_Amount', 'Payment_Date', 'Payment_Method', 'Payment_Key',
        'Linkage_Method', 'Source_System', 'In_LMS', 'LMS_Info'
    ])
    
    for r in detailed_results:
        reserve = r['reserve_number']
        charter_id = r['charter_id']
        client = r['client_name']
        charter_date = r['charter_date']
        
        # Parse payment details
        import ast
        try:
            payments = ast.literal_eval(r['payment_details_json'])
            for p in payments:
                writer.writerow([
                    reserve, charter_id, client, charter_date,
                    p['payment_id'], p['amount'], p['date'], p['method'], p['key'],
                    p['linkage'], p['source'], p['in_lms'], p['lms_info']
                ])
        except:
            pass

print(f"✓ Individual payments: {csv_file2}")

# Top 20 examples
print()
print("="*120)
print("TOP 20 EXAMPLES (Largest Differences)")
print("="*120)
print()
print(f"{'Reserve':<10} {'Client':<25} {'Date':<12} {'Charter$':<12} {'Sum$':<12} {'Diff$':<12} {'Root Cause':<40}")
print("-" * 120)

for r in detailed_results[:20]:
    reserve = r['reserve_number']
    client = (r['client_name'] or '')[:23]
    date = r['charter_date'].strftime('%Y-%m-%d') if r['charter_date'] else ''
    charter_paid = f"${r['charter_paid_amount']:,.2f}"
    sum_pay = f"${r['sum_payments']:,.2f}"
    diff = f"${r['difference']:,.2f}"
    causes = r['root_causes'][:38]
    
    print(f"{reserve:<10} {client:<25} {date:<12} {charter_paid:<12} {sum_pay:<12} {diff:<12} {causes:<40}")

if lms_conn:
    lms_cur.close()
    lms_conn.close()

pg_cur.close()
pg_conn.close()

print()
print("="*120)
print("ANALYSIS COMPLETE")
print("="*120)
