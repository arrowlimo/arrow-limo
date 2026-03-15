#!/usr/bin/env python3
"""
PERRON VENTURES LIMITED - CHARTER AUDIT REPORT
===============================================
Comprehensive audit of all Perron Ventures Limited/Ltd. charters
including payment details, balances, and verification status.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from decimal import Decimal
import json

from dotenv import load_dotenv
load_dotenv()

print("="*80)
print("PERRON VENTURES LIMITED - CHARTER AUDIT")
print("="*80)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Connect to database
password = os.getenv('LOCAL_DB_PASSWORD') or os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD') or 'ArrowLimousine'
database = os.getenv('LOCAL_DB_NAME') or os.getenv('DB_NAME') or 'almsdata'
user = os.getenv('LOCAL_DB_USER') or os.getenv('DB_USER') or 'postgres'

conn = psycopg2.connect(
    host='localhost',
    database=database,
    user=user,
    password=password,
    cursor_factory=RealDictCursor
)

cur = conn.cursor()

# ============================================================================
# STEP 1: Find all Perron Ventures charters
# ============================================================================
print("STEP 1: SEARCHING FOR PERRON VENTURES CHARTERS")
print("-" * 80)

cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.client_display_name,
        c.client_id,
        c.total_amount_due,
        c.balance,
        c.status,
        c.driver_gratuity,
        c.created_at,
        c.updated_at,
        c.client_notes,
        c.booking_notes
    FROM charters c
    WHERE c.client_display_name ILIKE '%Perron Ventures%'
    ORDER BY c.charter_date DESC, c.reserve_number
""")

charters = cur.fetchall()
print(f"✅ Found {len(charters)} charter(s) for Perron Ventures\n")

if len(charters) == 0:
    print("⚠️  No charters found. Checking for alternate spellings...")
    cur.execute("""
        SELECT DISTINCT client_display_name 
        FROM charters 
        WHERE client_display_name ILIKE '%perr%'
        ORDER BY client_display_name
    """)
    similar = cur.fetchall()
    if similar:
        print(f"   Found {len(similar)} similar client names:")
        for row in similar:
            print(f"      - {row['client_display_name']}")
    else:
        print("   No similar names found.")
    conn.close()
    exit()

# ============================================================================
# STEP 2: Get payment details for each charter
# ============================================================================
print("\nSTEP 2: RETRIEVING PAYMENT DETAILS")
print("-" * 80)

charter_details = []
total_charter_amount = Decimal('0.00')
total_paid_amount = Decimal('0.00')
total_balance = Decimal('0.00')

for charter in charters:
    charter_id = charter['charter_id']
    
    # Get all payments for this charter
    cur.execute("""
        SELECT 
            cp.payment_id,
            cp.payment_date,
            cp.payment_method,
            cp.amount,
            cp.payment_key,
            cp.source
        FROM charter_payments cp
        WHERE cp.charter_id = %s
        ORDER BY cp.payment_date, cp.payment_id
    """, (str(charter_id),))
    
    payments = cur.fetchall()
    
    # Calculate totals
    charter_total = charter['total_amount_due'] or Decimal('0.00')
    paid_total = sum(p['amount'] for p in payments) if payments else Decimal('0.00')
    balance = charter_total - paid_total
    
    # Get banking transaction links (if any)
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.credit_amount,
            bt.description,
            bt.check_number,
            bt.vendor_extracted
        FROM banking_transactions bt
        WHERE bt.reconciled_charter_id = %s
        ORDER BY bt.transaction_date
    """, (charter_id,))
    
    banking_links = cur.fetchall()
    
    charter_info = {
        'charter': dict(charter),
        'payments': [dict(p) for p in payments],
        'banking_links': [dict(b) for b in banking_links],
        'summary': {
            'charter_total': float(charter_total),
            'paid_total': float(paid_total),
            'balance': float(balance),
            'payment_count': len(payments),
            'banking_link_count': len(banking_links)
        }
    }
    
    charter_details.append(charter_info)
    
    total_charter_amount += charter_total
    total_paid_amount += paid_total
    total_balance += balance

print(f"✅ Retrieved payment data for {len(charter_details)} charter(s)\n")

# ============================================================================
# STEP 3: Display detailed report
# ============================================================================
print("\n" + "="*80)
print("DETAILED CHARTER REPORT")
print("="*80)

for idx, detail in enumerate(charter_details, 1):
    charter = detail['charter']
    payments = detail['payments']
    banking = detail['banking_links']
    summary = detail['summary']
    
    print(f"\n{'='*80}")
    print(f"CHARTER #{idx}: {charter['reserve_number']}")
    print(f"{'='*80}")
    
    print(f"\n📅 Charter Date:     {charter['charter_date']}")
    print(f"👤 Client Name:      {charter['client_display_name']}")
    print(f"💰 Total Amount:     ${summary['charter_total']:,.2f}")
    print(f"✅ Paid Amount:      ${summary['paid_total']:,.2f}")
    print(f"📊 Balance:          ${summary['balance']:,.2f}")
    print(f"🔖 Status:           {charter['status']}")
    
    if charter['driver_gratuity']:
        print(f"   Gratuity:         ${charter['driver_gratuity']:,.2f}")
    
    # Payment details
    print(f"\n💳 PAYMENTS ({len(payments)}):")
    if payments:
        for pidx, payment in enumerate(payments, 1):
            print(f"   {pidx}. {payment['payment_date']} - {payment['payment_method']}")
            print(f"      Amount: ${payment['amount']:,.2f}")
            if payment.get('payment_key'):
                print(f"      Key: {payment['payment_key']}")
            if payment.get('source'):
                print(f"      Source: {payment['source']}")
    else:
        print("   (No payments recorded)")
    
    # Banking links
    print(f"\n🏦 BANKING LINKS ({len(banking)}):")
    if banking:
        for bidx, bank in enumerate(banking, 1):
            credit = bank.get('credit_amount') or 0
            print(f"   {bidx}. {bank['transaction_date']} - ${credit:,.2f}")
            print(f"      Desc: {bank['description']}")
            if bank.get('check_number'):
                print(f"      Check #: {bank['check_number']}")
            if bank.get('vendor_extracted'):
                print(f"      Vendor: {bank['vendor_extracted']}")
    else:
        print("   (No banking transaction links)")
    
    # Verification status
    print(f"\n🔍 VERIFICATION:")
    if abs(summary['balance']) < 0.01:
        print("   ✅ FULLY PAID")
    elif summary['balance'] > 0.01:
        print(f"   ⚠️  OUTSTANDING BALANCE: ${summary['balance']:,.2f}")
    elif summary['balance'] < -0.01:
        print(f"   🔴 OVERPAID: ${abs(summary['balance']):,.2f}")
    
    if summary['payment_count'] > 0 and summary['banking_link_count'] == 0:
        print("   ⚠️  Payments exist but no banking links found")
    elif summary['payment_count'] != summary['banking_link_count']:
        print(f"   ⚠️  Payment/Banking mismatch: {summary['payment_count']} payments, {summary['banking_link_count']} banking links")

# ============================================================================
# STEP 4: Summary totals
# ============================================================================
print("\n" + "="*80)
print("SUMMARY TOTALS")
print("="*80)

print(f"\n📊 Total Charters:       {len(charter_details)}")
print(f"💰 Total Charter Value:  ${total_charter_amount:,.2f}")
print(f"✅ Total Paid:           ${total_paid_amount:,.2f}")
print(f"📊 Total Balance:        ${total_balance:,.2f}")

fully_paid = [c for c in charter_details if abs(c['summary']['balance']) < 0.01]
outstanding = [c for c in charter_details if c['summary']['balance'] > 0.01]
overpaid = [c for c in charter_details if c['summary']['balance'] < -0.01]

print(f"\n✅ Fully Paid:           {len(fully_paid)} charter(s)")
print(f"⚠️  Outstanding Balance:  {len(outstanding)} charter(s)")
print(f"🔴 Overpaid:             {len(overpaid)} charter(s)")

# Payment method breakdown
all_payments = []
for detail in charter_details:
    all_payments.extend(detail['payments'])

payment_methods = {}
for payment in all_payments:
    method = payment['payment_method'] or 'UNKNOWN'
    if method not in payment_methods:
        payment_methods[method] = {'count': 0, 'total': Decimal('0.00')}
    payment_methods[method]['count'] += 1
    payment_methods[method]['total'] += payment['amount']

if payment_methods:
    print(f"\n💳 PAYMENT METHOD BREAKDOWN:")
    for method, data in sorted(payment_methods.items()):
        print(f"   {method:20s}: {data['count']:>3} payment(s) = ${data['total']:>10,.2f}")

# ============================================================================
# STEP 5: Save JSON report
# ============================================================================
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
report_file = f"perron_ventures_audit_{timestamp}.json"

report_data = {
    'generated': datetime.now().isoformat(),
    'client': 'Perron Ventures Limited',
    'summary': {
        'total_charters': len(charter_details),
        'total_charter_amount': float(total_charter_amount),
        'total_paid_amount': float(total_paid_amount),
        'total_balance': float(total_balance),
        'fully_paid_count': len(fully_paid),
        'outstanding_count': len(outstanding),
        'overpaid_count': len(overpaid),
        'payment_methods': {k: {'count': v['count'], 'total': float(v['total'])} 
                           for k, v in payment_methods.items()}
    },
    'charters': charter_details
}

with open(report_file, 'w') as f:
    json.dump(report_data, f, indent=2, default=str)

print(f"\n💾 Report saved: {report_file}")

# ============================================================================
# STEP 6: Action items
# ============================================================================
print("\n" + "="*80)
print("ACTION ITEMS")
print("="*80)

if outstanding:
    print(f"\n⚠️  {len(outstanding)} charter(s) with outstanding balances:")
    for detail in outstanding:
        charter = detail['charter']
        print(f"   - {charter['reserve_number']} ({charter['charter_date']}): ${detail['summary']['balance']:,.2f}")

if overpaid:
    print(f"\n🔴 {len(overpaid)} charter(s) overpaid (needs investigation):")
    for detail in overpaid:
        charter = detail['charter']
        print(f"   - {charter['reserve_number']} ({charter['charter_date']}): ${abs(detail['summary']['balance']):,.2f}")

# Check for missing banking links
no_banking = [c for c in charter_details if c['summary']['payment_count'] > 0 and c['summary']['banking_link_count'] == 0]
if no_banking:
    print(f"\n⚠️  {len(no_banking)} charter(s) have payments but no banking links:")
    for detail in no_banking:
        charter = detail['charter']
        print(f"   - {charter['reserve_number']} ({charter['charter_date']}): {detail['summary']['payment_count']} payment(s)")

print("\n" + "="*80)
print("AUDIT COMPLETE")
print("="*80)

conn.close()
