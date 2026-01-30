import psycopg2
import csv
from datetime import datetime, timedelta
from decimal import Decimal

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("EMAIL TRANSFER: OUTLOOK vs BANKING COMPARISON")
print("="*100)

# Load email data from CSV
email_transfers = []
with open('l:/limo/reports/etransfer_emails.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Parse email date
        email_date = datetime.fromisoformat(row['email_date'].replace('T', ' '))
        
        # Determine if sent or received
        from_name = row['from_name']
        subject = row['subject']
        
        if 'sent you money' in subject:
            direction = 'RECEIVED'
            name = from_name
        elif 'deposited' in subject:
            direction = 'SENT'
            # Extract recipient from subject
            if ' to ' in subject:
                name = subject.split(' to ')[1].split(' was')[0]
            else:
                name = None
        else:
            direction = 'UNKNOWN'
            name = from_name
        
        email_transfers.append({
            'date': email_date.date(),
            'amount': Decimal(row['amount']) if row['amount'] else Decimal('0'),
            'direction': direction,
            'name': name,
            'subject': subject,
            'interac_ref': row.get('interac_ref', '')
        })

print(f"\n1. OUTLOOK EMAIL DATA")
print("-"*100)
print(f"Total emails scanned: {len(email_transfers)}")

received = [e for e in email_transfers if e['direction'] == 'RECEIVED']
sent = [e for e in email_transfers if e['direction'] == 'SENT']

print(f"  - RECEIVED (sent to us): {len(received)} transfers")
print(f"  - SENT (we sent): {len(sent)} transfers")

total_received = sum(e['amount'] for e in received)
total_sent = sum(e['amount'] for e in sent)

print(f"  - Total received: ${total_received:,.2f}")
print(f"  - Total sent: ${total_sent:,.2f}")

# Get banking email transfers
cur.execute("""
    SELECT 
        bt.transaction_date,
        r.vendor_name,
        r.gross_amount,
        bt.description,
        r.receipt_id,
        bt.transaction_id,
        bt.debit_amount,
        bt.credit_amount
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.exclude_from_reports = FALSE
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%EMAIL TRANSFER%')
      AND r.vendor_name LIKE 'EMAIL TRANSFER%'
    ORDER BY bt.transaction_date
""")

banking_transfers = cur.fetchall()

print(f"\n2. BANKING TRANSACTIONS")
print("-"*100)
print(f"Total banking e-transfers: {len(banking_transfers)}")

banking_debits = [b for b in banking_transfers if b[6]]  # has debit_amount
banking_credits = [b for b in banking_transfers if b[7]]  # has credit_amount

print(f"  - DEBITS (we sent): {len(banking_debits)} transfers")
print(f"  - CREDITS (received): {len(banking_credits)} transfers")

total_debit = sum(float(b[6]) for b in banking_debits if b[6])
total_credit = sum(float(b[7]) for b in banking_credits if b[7])

print(f"  - Total sent (debits): ${total_debit:,.2f}")
print(f"  - Total received (credits): ${total_credit:,.2f}")

# Match email RECEIVED to banking CREDITS
print(f"\n3. MATCHING RECEIVED TRANSFERS (Outlook → Banking)")
print("-"*100)

banking_credits_dict = {}
for date, vendor, amount, desc, receipt_id, tx_id, debit, credit in banking_transfers:
    if credit:  # Has credit amount (money received)
        key = (date, round(float(credit), 2))
        if key not in banking_credits_dict:
            banking_credits_dict[key] = []
        banking_credits_dict[key].append({
            'vendor': vendor,
            'amount': credit,
            'description': desc,
            'receipt_id': receipt_id
        })

matched_received = []
unmatched_email_received = []

for email in received:
    match_found = False
    # Try +/- 3 days
    for offset in range(-3, 4):
        check_date = email['date'] + timedelta(days=offset)
        key = (check_date, float(email['amount']))
        
        if key in banking_credits_dict and len(banking_credits_dict[key]) > 0:
            banking_match = banking_credits_dict[key].pop(0)
            matched_received.append({
                'email_date': email['date'],
                'banking_date': check_date,
                'amount': email['amount'],
                'email_name': email['name'],
                'banking_vendor': banking_match['vendor'],
                'receipt_id': banking_match['receipt_id'],
                'offset': offset
            })
            match_found = True
            break
    
    if not match_found:
        unmatched_email_received.append(email)

# Remaining banking credits
unmatched_banking_received = []
for key, transactions in banking_credits_dict.items():
    for tx in transactions:
        unmatched_banking_received.append({
            'date': key[0],
            'amount': key[1],
            'vendor': tx['vendor']
        })

print(f"Matched: {len(matched_received)} transfers")
print(f"Missing from banking: {len(unmatched_email_received)} transfers")
print(f"Extra in banking: {len(unmatched_banking_received)} transfers")

# Show missing names
print(f"\n4. MISSING RECIPIENT NAMES")
print("-"*100)

missing_names = []
for match in matched_received:
    email_name = match['email_name']
    banking_vendor = match['banking_vendor']
    
    # Check if banking is generic
    if banking_vendor == 'EMAIL TRANSFER' and email_name:
        missing_names.append(match)
    # Check if names don't match
    elif email_name and email_name.upper() not in banking_vendor.upper():
        missing_names.append(match)

print(f"Found {len(missing_names)} transfers where name doesn't match\n")

if missing_names:
    print(f"{'Email Name':<30} | {'Banking Vendor':<40} | {'Amount':>10} | Receipt ID")
    print("-"*100)
    for match in missing_names[:30]:
        print(f"{match['email_name'][:28]:<30} | {match['banking_vendor'][:38]:<40} | ${float(match['amount']):>9,.2f} | {match['receipt_id']}")
    
    if len(missing_names) > 30:
        print(f"  ... and {len(missing_names) - 30} more")

# Show missing transactions
print(f"\n5. MISSING TRANSACTIONS (in Outlook but NOT in banking)")
print("-"*100)

if unmatched_email_received:
    missing_total = sum(float(e['amount']) for e in unmatched_email_received)
    print(f"Found {len(unmatched_email_received)} transfers (${missing_total:,.2f})\n")
    
    print(f"{'Date':<12} | {'From':<30} | {'Amount':>10}")
    print("-"*60)
    for email in sorted(unmatched_email_received, key=lambda x: x['amount'], reverse=True)[:30]:
        print(f"{str(email['date']):<12} | {email['name'][:28] if email['name'] else 'N/A':<30} | ${float(email['amount']):>9,.2f}")
    
    if len(unmatched_email_received) > 30:
        print(f"  ... and {len(unmatched_email_received) - 30} more")
else:
    print("✅ All email transfers found in banking!")

# SUMMARY
print(f"\n{'='*100}")
print(f"SUMMARY")
print(f"{'='*100}")
print(f"""
RECEIVED TRANSFERS (people sent to us):
  Outlook emails: {len(received)} transfers | ${total_received:,.2f}
  Banking credits: {len(banking_credits)} transfers | ${total_credit:,.2f}
  
  Matched: {len(matched_received)} transfers
  Missing from banking: {len(unmatched_email_received)} transfers (${sum(float(e['amount']) for e in unmatched_email_received):,.2f})
  Extra in banking: {len(unmatched_banking_received)} transfers
  
NAME QUALITY:
  Missing/wrong names: {len(missing_names)} receipts need name updates from email data
  
NEXT ACTIONS:
  1. Update {len(missing_names)} receipts with correct names from Outlook
  2. Investigate {len(unmatched_email_received)} missing banking transactions
""")

cur.close()
conn.close()
