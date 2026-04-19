import sys
sys.path.insert(0, 'l:/limo')
from modern_backend.app.tax.t2_data_extraction import T2DataExtractor
from decimal import Decimal

params = {
    'host': 'localhost', 'port': 5432, 'dbname': 'almsdata',
    'user': 'postgres', 'password': 'ArrowLimousine'
}
ex = T2DataExtractor(params)

rev = ex.extract_revenue_data(2012)
exp = ex.extract_expense_data(2012)
ded = ex.extract_t2_deductibility_analysis(2012)

print("=== 2012 T2 — REVENUE ===")
cr = rev['charter_revenue']
print(f"  Charter revenue (income_ledger): ${cr['amount']:,.2f}  ({cr['count']} entries)")
print(f"  GST collected:                   ${cr['gst']:,.2f}")
print(f"  Total revenue:                   ${rev['total_revenue']:,.2f}")

print()
print("=== 2012 T2 — DEDUCTIBILITY ANALYSIS ===")
print(f"  Total book expenses:      ${ded['total_book_expense']:,.2f}")
print(f"  Total DEDUCTIBLE:         ${ded['total_deductible_expenses']:,.2f}")
print(f"  Schedule 1 add-backs:     ${ded['total_add_back']:,.2f}")

print()
net = rev['total_revenue'] - ded['total_deductible_expenses']
print(f"=== NET INCOME (pre-tax estimate) ===")
print(f"  Revenue:       ${rev['total_revenue']:,.2f}")
print(f"  Deductible:   -${ded['total_deductible_expenses']:,.2f}")
print(f"  Net income:    ${net:,.2f}")

print()
print("=== Schedule 1 GL ADD-BACKS ===")
for row in sorted(ded.get('by_gl_code', []), key=lambda x: x.get('add_back', Decimal('0')), reverse=True):
    ab = row.get('add_back', Decimal('0'))
    if ab > 0:
        print(f"  {row.get('gl_code',''):6s}  {row.get('account_name','')[:35]:35s}  add-back: ${ab:,.2f}")

print()
print("=== Audit Warnings ===")
for w in ded.get('audit_warnings', [])[:15]:
    print(f"  [{w.get('type','')}] #{w.get('receipt_id','')} {w.get('vendor_name','')[:30]}  ${w.get('amount',0):,.2f}  {w.get('notes','')}")

print()
print("=== TOP 15 DEDUCTIBLE GL ACCOUNTS ===")
expense_types = {'expense','Expense'}
by_gl = [r for r in exp['by_gl_account']
         if (r['account_type'] or '') in expense_types and r['gl_code'] != 'UNASSIGNED']
for r in sorted(by_gl, key=lambda x: x['amount'], reverse=True)[:15]:
    print(f"  {r['gl_code']:6s}  {r['account_name'][:35]:35s}  ${r['amount']:>12,.2f}  ({r['count']} receipts)")
