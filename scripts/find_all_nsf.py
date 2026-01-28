import csv
from datetime import datetime

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"

# Find ALL NSF-related transactions
nsf_entries = []
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 4:
            date_str = row[0]
            desc = row[1]
            debit = row[2].strip()
            credit = row[3].strip()
            
            if 'NSF' in desc or 'REVERSAL' in desc:
                nsf_entries.append({
                    'date': date_str,
                    'desc': desc,
                    'debit': float(debit) if debit else None,
                    'credit': float(credit) if credit else None
                })

print("ALL NSF-RELATED ENTRIES IN CSV (2018):")
print(f"{'Date':<12} {'Description':<55} {'Debit':>12} {'Credit':>12}")
print("-" * 82)

for entry in sorted(nsf_entries, key=lambda x: x['date'], reverse=True):
    debit_display = f"${entry['debit']:.2f}" if entry['debit'] else "-"
    credit_display = f"${entry['credit']:.2f}" if entry['credit'] else "-"
    print(f"{entry['date']} | {entry['desc']:<53} | {debit_display:>11} | {credit_display:>11}")

print()
print(f"Total NSF entries: {len(nsf_entries)}")

# Count by type
charges = [e for e in nsf_entries if 'CHARGE' in e['desc']]
reversals = [e for e in nsf_entries if 'REVERSAL' in e['desc']]

print(f"NSF CHARGEs (fees): {len(charges)}")
print(f"EFT REVERSALS (returns): {len(reversals)}")
