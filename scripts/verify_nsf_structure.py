import csv
from datetime import datetime

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"

# Find NSF-related transactions
print("NSF-RELATED TRANSACTIONS IN CSV (2018-12-28 example):")
print()
print(f"{'Date':<12} {'Description':<60} {'Debit':>12} {'Credit':>12}")
print("-" * 97)

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 4:
            date_str = row[0]
            desc = row[1]
            debit = row[2].strip()
            credit = row[3].strip()
            
            # Look for NSF or REVERSAL transactions on 2018-12-28
            if '2018-12-28' in date_str and ('NSF' in desc or 'REVERSAL' in desc or 'HEFFNER' in desc):
                debit_display = f"${float(debit):.2f}" if debit else "-"
                credit_display = f"${float(credit):.2f}" if credit else "-"
                print(f"{date_str} | {desc:<58} | {debit_display:>11} | {credit_display:>11}")

print()
print("INTERPRETATION:")
print("- NSF CHARGE (debit) = Bank fee when payment failed")
print("- EFT DEBIT REVERSAL (credit) = Bounced payment returned to account")  
print("- PREAUTHORIZED DEBIT (debit) = Original payment attempt")
print()
print("These are THREE separate transactions, not one combined entry.")
