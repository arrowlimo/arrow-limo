import sys
sys.path.insert(0, 'l:/limo')
from modern_backend.app.tax.t2_data_extraction import T2DataExtractor
from decimal import Decimal
from collections import defaultdict

params = {'host': 'localhost', 'port': 5432, 'dbname': 'almsdata',
          'user': 'postgres', 'password': 'ArrowLimousine'}
ded = T2DataExtractor(params).extract_t2_deductibility_analysis(2012)

# Inspect row keys
if ded['by_gl_code']:
    print("Keys:", list(ded['by_gl_code'][0].keys()))
    print()

# Aggregate add-backs by GL code
agg = defaultdict(lambda: {'account_name': '', 'book': Decimal(0), 'deductible': Decimal(0)})
for row in ded['by_gl_code']:
    gl = row.get('gl_code', '') or 'UNASSIGNED'
    agg[gl]['account_name'] = row.get('account_name', '')
    # Try different amount key names
    book = Decimal(str(row.get('book_amount', row.get('amount', row.get('gross_amount', 0))) or 0))
    ded_amt = Decimal(str(row.get('deductible_amount', row.get('deductible', 0)) or 0))
    agg[gl]['book'] += book
    agg[gl]['deductible'] += ded_amt

print(f"{'GL':6s}  {'Account Name':35s}  {'Book':>14s}  {'Deductible':>12s}  {'Add-back':>10s}")
print('-' * 82)
total_book = Decimal(0)
total_ded = Decimal(0)
for gl, v in sorted(agg.items(), key=lambda x: x[1]['book'] - x[1]['deductible'], reverse=True):
    ab = v['book'] - v['deductible']
    if v['book'] > 0:
        print(f"{gl:6s}  {v['account_name'][:35]:35s}  {v['book']:>14,.2f}  {v['deductible']:>12,.2f}  {ab:>10,.2f}")
    total_book += v['book']
    total_ded += v['deductible']
print('-' * 82)
print(f"{'TOTAL':44s}  {total_book:>14,.2f}  {total_ded:>12,.2f}  {total_book - total_ded:>10,.2f}")

print()
print(f"Summary: book={ded['total_book_expense']}  deductible={ded['total_deductible_expenses']}  add_back={ded['total_add_back']}")
