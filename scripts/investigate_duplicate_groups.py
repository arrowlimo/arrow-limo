#!/usr/bin/env python3
"""
Investigate specific duplicate groups to determine if they're legitimate
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*120)
print("INVESTIGATING SPECIFIC DUPLICATE GROUPS")
print("="*120)

# GROUP 2: 2014-05-08 - Two $1.00 EMAIL MONEY TRANSFER FEE
print("\n" + "="*120)
print("GROUP 2: 2014-05-08 - Two $1.00 EMAIL MONEY TRANSFER FEE receipts")
print("="*120)

print("\nReceipts:")
cur.execute("""
    SELECT receipt_id, description, gross_amount, gst_amount
    FROM receipts
    WHERE receipt_id IN (137611, 137621)
    ORDER BY receipt_id
""")
for rec_id, desc, gross, gst in cur.fetchall():
    print(f"   Receipt #{rec_id}: ${gross} - {desc}")

print("\nBanking transactions on 2014-05-08:")
cur.execute("""
    SELECT 
        transaction_uid,
        transaction_date,
        vendor_extracted,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE transaction_date = '2014-05-08'
    ORDER BY transaction_uid
""")

transactions = cur.fetchall()
print(f"   Found {len(transactions)} transactions on this date:")

etransfer_count = 0
etransfer_fee_count = 0

for uid, date, vendor, desc, debit, credit in transactions:
    desc_lower = (desc or '').lower()
    vendor_lower = (vendor or '').lower()
    
    is_etransfer = 'e-transfer' in desc_lower or 'email' in desc_lower or 'money transfer' in desc_lower
    is_fee = 'fee' in desc_lower
    
    if is_etransfer and not is_fee:
        etransfer_count += 1
        print(f"   ✉️  {uid}: E-TRANSFER - {desc[:60]} (${debit or credit})")
    elif is_etransfer and is_fee:
        etransfer_fee_count += 1
        print(f"   💰 {uid}: FEE - {desc[:60]} (${debit or credit})")
    else:
        print(f"      {uid}: {desc[:60]} (${debit or credit})")

print(f"\n   📊 Summary: {etransfer_count} e-transfers, {etransfer_fee_count} e-transfer fees")
print(f"   💡 VERDICT: {'LEGITIMATE - Keep both fees' if etransfer_fee_count == 2 else 'DUPLICATE - Delete one fee'}")

# GROUP 10: 2014-03-04 - $45.00 NSF vs Email Money Deposit Fee
print("\n\n" + "="*120)
print("GROUP 10: 2014-03-04 - $45.00 'nsf fee' vs 'email money deposit fee'")
print("="*120)

print("\nReceipts:")
cur.execute("""
    SELECT receipt_id, description, gross_amount, gst_amount
    FROM receipts
    WHERE receipt_id IN (137276, 137281)
    ORDER BY receipt_id
""")
for rec_id, desc, gross, gst in cur.fetchall():
    print(f"   Receipt #{rec_id}: ${gross} - {desc}")

print("\nBanking transactions on 2014-03-04:")
cur.execute("""
    SELECT 
        transaction_uid,
        transaction_date,
        vendor_extracted,
        description,
        debit_amount,
        credit_amount,
        is_nsf_charge
    FROM banking_transactions
    WHERE transaction_date = '2014-03-04'
    ORDER BY transaction_uid
""")

transactions = cur.fetchall()
print(f"   Found {len(transactions)} transactions on this date:")

nsf_count = 0
fee_count = 0

for uid, date, vendor, desc, debit, credit, is_nsf in transactions:
    desc_str = (desc or '')[:70]
    amount = debit or credit or 0
    
    is_nsf_flag = is_nsf or False
    desc_lower = desc_str.lower()
    
    if is_nsf_flag or 'nsf' in desc_lower:
        nsf_count += 1
        print(f"   🚫 {uid}: NSF - {desc_str} (${amount}) [is_nsf_charge={is_nsf_flag}]")
    elif 'fee' in desc_lower or 'charge' in desc_lower:
        fee_count += 1
        print(f"   💰 {uid}: FEE - {desc_str} (${amount})")
    else:
        print(f"      {uid}: {desc_str} (${amount})")

print(f"\n   📊 Summary: {nsf_count} NSF-related, {fee_count} other fees")
print(f"   💡 VERDICT: {'LEGITIMATE - Keep both (NSF + separate fee)' if nsf_count >= 1 and fee_count >= 1 else 'Need manual review'}")

# GROUP 17: 2013-10-08 - $42.50 NSF Fee vs Service Charge
print("\n\n" + "="*120)
print("GROUP 17: 2013-10-08 - $42.50 'NSF FEE' vs 'SERVICE CHARGE'")
print("="*120)

print("\nReceipts:")
cur.execute("""
    SELECT receipt_id, description, gross_amount, gst_amount
    FROM receipts
    WHERE receipt_id IN (136601, 136602)
    ORDER BY receipt_id
""")
for rec_id, desc, gross, gst in cur.fetchall():
    print(f"   Receipt #{rec_id}: ${gross} - {desc}")

print("\nBanking transactions on 2013-10-08:")
cur.execute("""
    SELECT 
        transaction_uid,
        transaction_date,
        vendor_extracted,
        description,
        debit_amount,
        credit_amount,
        is_nsf_charge
    FROM banking_transactions
    WHERE transaction_date = '2013-10-08'
    ORDER BY transaction_uid
""")

transactions = cur.fetchall()
print(f"   Found {len(transactions)} transactions on this date:")

nsf_count = 0
service_charge_count = 0

for uid, date, vendor, desc, debit, credit, is_nsf in transactions:
    desc_str = (desc or '')[:70]
    amount = debit or credit or 0
    
    is_nsf_flag = is_nsf or False
    desc_lower = desc_str.lower()
    
    if is_nsf_flag or 'nsf' in desc_lower:
        nsf_count += 1
        print(f"   🚫 {uid}: NSF - {desc_str} (${amount}) [is_nsf_charge={is_nsf_flag}]")
    elif 'service' in desc_lower and 'charge' in desc_lower:
        service_charge_count += 1
        print(f"   💰 {uid}: SERVICE CHARGE - {desc_str} (${amount})")
    else:
        print(f"      {uid}: {desc_str} (${amount})")

print(f"\n   📊 Summary: {nsf_count} NSF charges, {service_charge_count} service charges")
print(f"   💡 VERDICT: {'LEGITIMATE - Keep both (NSF + service charge)' if nsf_count >= 1 and service_charge_count >= 1 else 'Need manual review'}")

print("\n\n" + "="*120)
print("OVERALL SUMMARY")
print("="*120)
print("\nGroups to investigate further:")
print("   Group 2 (2014-05-08): Check if 2 e-transfers = 2 legitimate fees")
print("   Group 10 (2014-03-04): NSF + separate fee = both legitimate")
print("   Group 17 (2013-10-08): NSF + service charge = both legitimate")

cur.close()
conn.close()
