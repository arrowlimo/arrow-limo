import csv
from collections import Counter

charter_csv = r'l:\limo\data\audit\charter_payment_relinks_20260401_181722.csv'
receipt_csv = r'l:\limo\data\audit\staged_receipt_links_20260401_181722.csv'

with open(charter_csv, newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
print('charter_links_rows', len(rows))
print('charter_methods', Counter(r['method'] for r in rows))
print('charter_sources_top', Counter((r.get('source') or '').strip() for r in rows).most_common(8))

with open(receipt_csv, newline='', encoding='utf-8') as f:
    rrows = list(csv.DictReader(f))
print('receipt_links_rows', len(rrows))
print('receipt_vendor_rules', Counter(r['vendor_rule'] for r in rrows))
