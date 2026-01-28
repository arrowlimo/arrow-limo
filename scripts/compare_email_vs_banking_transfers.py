import psycopg2
from datetime import datetime, timedelta

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("EMAIL TRANSFER BANKING vs OUTLOOK EMAIL COMPARISON")
print("="*100)

# Check if email_financial_events table exists
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'email_financial_events'
    )
""")

has_email_table = cur.fetchone()[0]

if not has_email_table:
    print("\n⚠️  email_financial_events table does not exist!")
    print("Need to run email scanning scripts first.")
    cur.close()
    conn.close()
    exit(1)

# Get email transfer events from Outlook
cur.execute("""
    SELECT 
        email_date,
        recipient_name,
        amount,
        reference_number,
        subject
    FROM email_financial_events
    WHERE event_type = 'E_TRANSFER_SENT'
    ORDER BY email_date
""")

email_events = cur.fetchall()
print(f"\n1. OUTLOOK EMAIL EVENTS")
print("-"*100)
print(f"Found {len(email_events)} email transfer events from Outlook\n")

if len(email_events) == 0:
    print("⚠️  No email transfer events found. Need to scan Outlook PST/EML files.")
    cur.close()
    conn.close()
    exit(1)

# Show sample
print(f"Sample email events:")
print(f"{'Date':<12} | {'Amount':>10} | {'Recipient':<30} | {'Reference':<15}")
print("-"*100)
for date, recipient, amount, ref, subject in email_events[:20]:
    print(f"{str(date):<12} | ${float(amount) if amount else 0:>9,.2f} | {recipient[:28] if recipient else 'N/A':<30} | {ref if ref else 'N/A':<15}")

if len(email_events) > 20:
    print(f"  ... and {len(email_events) - 20} more")

# Get banking email transfers
cur.execute("""
    SELECT 
        bt.transaction_date,
        r.vendor_name,
        r.gross_amount,
        bt.description,
        r.receipt_id,
        bt.transaction_id
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.exclude_from_reports = FALSE
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%EMAIL TRANSFER%')
      AND r.vendor_name LIKE 'EMAIL TRANSFER%'
    ORDER BY bt.transaction_date
""")

banking_transfers = cur.fetchall()
print(f"\n2. BANKING EMAIL TRANSFERS")
print("-"*100)
print(f"Found {len(banking_transfers)} email transfer receipts in banking\n")

print(f"Sample banking transfers:")
print(f"{'Date':<12} | {'Amount':>10} | {'Vendor Name':<50}")
print("-"*100)
for date, vendor, amount, desc, receipt_id, tx_id in banking_transfers[:20]:
    print(f"{str(date):<12} | ${float(amount) if amount else 0:>9,.2f} | {vendor[:48]}")

if len(banking_transfers) > 20:
    print(f"  ... and {len(banking_transfers) - 20} more")

# 3. MATCH EMAIL EVENTS TO BANKING TRANSACTIONS
print(f"\n3. MATCHING EMAIL EVENTS TO BANKING")
print("-"*100)

matches = []
unmatched_emails = []
unmatched_banking = []

banking_dict = {}
for date, vendor, amount, desc, receipt_id, tx_id in banking_transfers:
    key = (date, round(float(amount) if amount else 0, 2))
    if key not in banking_dict:
        banking_dict[key] = []
    banking_dict[key].append({
        'vendor': vendor,
        'amount': amount,
        'description': desc,
        'receipt_id': receipt_id,
        'tx_id': tx_id
    })

for email_date, recipient, email_amt, ref, subject in email_events:
    email_amount = round(float(email_amt) if email_amt else 0, 2)
    
    # Try exact date match
    match_found = False
    for offset in [0, 1, 2, -1, -2]:  # Check +/- 2 days
        check_date = email_date + timedelta(days=offset)
        key = (check_date, email_amount)
        
        if key in banking_dict:
            # Found match!
            banking_match = banking_dict[key][0]
            matches.append({
                'email_date': email_date,
                'banking_date': check_date,
                'amount': email_amount,
                'email_recipient': recipient,
                'banking_vendor': banking_match['vendor'],
                'receipt_id': banking_match['receipt_id'],
                'offset_days': offset
            })
            # Remove from dict to avoid duplicate matching
            banking_dict[key].pop(0)
            if len(banking_dict[key]) == 0:
                del banking_dict[key]
            match_found = True
            break
    
    if not match_found:
        unmatched_emails.append({
            'date': email_date,
            'amount': email_amount,
            'recipient': recipient,
            'reference': ref
        })

# Remaining banking transactions are unmatched
for key, transactions in banking_dict.items():
    for tx in transactions:
        unmatched_banking.append({
            'date': key[0],
            'amount': key[1],
            'vendor': tx['vendor'],
            'receipt_id': tx['receipt_id']
        })

print(f"Matched: {len(matches)} transfers")
print(f"Unmatched in emails: {len(unmatched_emails)} transfers")
print(f"Unmatched in banking: {len(unmatched_banking)} transfers")

# 4. ANALYZE MISSING RECIPIENT NAMES
print(f"\n4. MISSING RECIPIENT NAMES (banking generic, email has name)")
print("-"*100)

missing_names = []
for match in matches:
    email_recipient = match['email_recipient']
    banking_vendor = match['banking_vendor']
    
    # Check if banking vendor is generic (no recipient extracted)
    if banking_vendor == 'EMAIL TRANSFER' and email_recipient:
        missing_names.append(match)

print(f"Found {len(missing_names)} transfers where email has recipient but banking doesn't\n")

if missing_names:
    print(f"{'Date':<12} | {'Amount':>10} | {'Email Recipient':<30} | {'Banking':<20} | {'Receipt ID'}")
    print("-"*100)
    for match in missing_names[:30]:
        print(f"{str(match['email_date']):<12} | ${match['amount']:>9,.2f} | {match['email_recipient'][:28]:<30} | {match['banking_vendor']:<20} | {match['receipt_id']}")
    
    if len(missing_names) > 30:
        print(f"  ... and {len(missing_names) - 30} more")

# 5. MISSING TRANSACTIONS (in email but not in banking)
print(f"\n5. MISSING TRANSACTIONS (in Outlook but not in banking)")
print("-"*100)

if unmatched_emails:
    print(f"Found {len(unmatched_emails)} email transfers NOT in banking\n")
    
    print(f"{'Date':<12} | {'Amount':>10} | {'Recipient':<30} | {'Reference'}")
    print("-"*100)
    
    total_missing = sum(x['amount'] for x in unmatched_emails)
    
    for email in sorted(unmatched_emails, key=lambda x: x['amount'], reverse=True)[:30]:
        print(f"{str(email['date']):<12} | ${email['amount']:>9,.2f} | {email['recipient'][:28] if email['recipient'] else 'N/A':<30} | {email['reference'] if email['reference'] else 'N/A'}")
    
    if len(unmatched_emails) > 30:
        print(f"  ... and {len(unmatched_emails) - 30} more")
    
    print(f"\nTOTAL MISSING FROM BANKING: ${total_missing:,.2f}")
else:
    print("✅ All email transfers are in banking!")

# 6. EXTRA TRANSACTIONS (in banking but not in email)
print(f"\n6. EXTRA TRANSACTIONS (in banking but not in Outlook emails)")
print("-"*100)

if unmatched_banking:
    print(f"Found {len(unmatched_banking)} banking transfers NOT in emails\n")
    print("(This is expected - emails may be deleted or in different folders)\n")
    
    print(f"{'Date':<12} | {'Amount':>10} | {'Vendor Name':<50}")
    print("-"*100)
    
    for banking in sorted(unmatched_banking, key=lambda x: x['amount'], reverse=True)[:20]:
        print(f"{str(banking['date']):<12} | ${banking['amount']:>9,.2f} | {banking['vendor'][:48]}")
    
    if len(unmatched_banking) > 20:
        print(f"  ... and {len(unmatched_banking) - 20} more")
else:
    print("✅ All banking transfers have matching emails!")

# SUMMARY
print(f"\n{'='*100}")
print(f"SUMMARY")
print(f"{'='*100}")
print(f"""
Email events from Outlook: {len(email_events)} transfers
Banking receipts: {len(banking_transfers)} transfers

Matched: {len(matches)} transfers
  - With missing recipient names: {len(missing_names)} (can update from email)

Unmatched:
  - In email but NOT in banking: {len(unmatched_emails)} transfers (MISSING TRANSACTIONS)
  - In banking but NOT in emails: {len(unmatched_banking)} transfers (emails deleted/not scanned)

ACTION ITEMS:
1. Update {len(missing_names)} receipts with recipient names from emails
2. Investigate {len(unmatched_emails)} missing transactions from banking
""")

cur.close()
conn.close()
