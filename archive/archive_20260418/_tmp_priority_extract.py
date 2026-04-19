import csv
from collections import Counter
path = r'l:\limo\data\audit\duplicate_pairs_priority_queue_20260407_190606.csv'
rows = []
with open(path, newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

high = [x for x in rows if x['priority']=='HIGH']
cross = [x for x in high if 'cross_account_8362_1615' in x['reasons']]
same_banking = [x for x in high if 'same_banking_transaction' in x['reasons']]

print('TOTAL', len(rows))
print('HIGH', len(high))
print('HIGH_CROSS_8362_1615', len(cross))
print('HIGH_SAME_BANKING', len(same_banking))

vendor_counts = Counter(x['vendor_norm'] for x in high)
print('\nTOP_HIGH_VENDORS')
for vendor, cnt in vendor_counts.most_common(20):
    print(cnt, vendor)

print('\nSAMPLE_HIGH_CROSS_8362_1615')
for x in cross[:25]:
    print(x['receipt_id_1'], x['date_1'], x['receipt_id_2'], x['date_2'], x['vendor_norm'], x['amount'], x['account_1'], x['account_2'], x['banking_txn_1'], x['banking_txn_2'])
