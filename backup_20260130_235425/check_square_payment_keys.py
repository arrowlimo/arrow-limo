import csv

negs = list(csv.DictReader(open('reports/negative_payments_analysis.csv', encoding='utf-8')))
square_negs = [n for n in negs if n['source_classification']=='Square']
with_key = [n for n in square_negs if n['payment_key']]
without_key = [n for n in square_negs if not n['payment_key']]

print(f'Square negatives: {len(square_negs)} total')
print(f'  With payment_key: {len(with_key)}')
print(f'  Without payment_key: {len(without_key)}')

if without_key:
    print(f'\nSample Square negatives WITHOUT payment_key (not in batches):')
    for n in without_key[:5]:
        print(f'  Payment {n["payment_id"]}: ${n["amount"]} on {n["payment_date"]}, Reserve: {n["reserve_number"]}')

if with_key:
    print(f'\nSquare negatives WITH payment_key (in batches):')
    for n in with_key[:5]:
        print(f'  Payment {n["payment_id"]}: ${n["amount"]} in batch {n["payment_key"]}, Reserve: {n["reserve_number"]}')
