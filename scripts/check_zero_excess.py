import csv

rows = [r for r in csv.DictReader(open('l:/limo/reports/credit_ledger_proposal.csv')) 
        if r['proposed_action']=='CREDIT_LEDGER' and float(r['excess_amount'])<=0]
print(f'Found {len(rows)} with zero/negative excess')
for r in rows[:10]:
    print(f"  {r['reserve_number']}: excess={r['excess_amount']}")
