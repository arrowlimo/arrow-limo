import csv
from datetime import datetime

wix_file = 'l:\\limo\\wix\\billing_history_Dec_06_2025 (1).csv'

print("\nWIX G SUITE MAILBOX ENTRIES:\n")
print("-" * 100)
print(f"{'Date':<12} {'Invoice #':<15} {'Description':<30} {'Amount':<12} {'Status':<10}")
print("-" * 100)

with open(wix_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if 'mailbox' in row.get('Description', '').lower() or 'g suite' in row.get('Subscription', '').lower():
            date_str = row.get('Date', '')
            invoice = row.get('Invoice Number', '')
            desc = row.get('Description', '')
            amount = row.get('Amount', '')
            status = row.get('Status', '')
            
            print(f"{date_str:<12} {invoice:<15} {desc:<30} {amount:<12} {status:<10}")

print("-" * 100)
print("\nANALYSIS:")
print("""
If the same invoice number appears multiple times on the same date with same amount = DUPLICATE
If different invoice numbers on same date = separate invoices (multiple mailboxes)
If single invoice with amount = total for ALL mailboxes
""")
