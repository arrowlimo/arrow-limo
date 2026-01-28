"""
Quick check of banking_transactions in complete JSON.
"""
import json

print("Loading complete_almsdata_export.json...")
with open('l:/limo/reports/complete_almsdata_export.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"Tables in export: {len(data)}")
print("\nTable names:")
for table in sorted(data.keys()):
    print(f"  {table}: {len(data[table]):,} records")

if 'banking_transactions' in data:
    print("\n" + "=" * 80)
    print("BANKING_TRANSACTIONS ANALYSIS")
    print("=" * 80)
    
    banking = data['banking_transactions']
    
    # Count 2012 records
    count_2012 = sum(1 for t in banking if t.get('transaction_date') and '2012' in str(t['transaction_date']))
    print(f"Total 2012 records: {count_2012:,}")
    
    # Group by month
    months = {}
    for t in banking:
        if t.get('transaction_date') and '2012' in str(t['transaction_date']):
            month = str(t['transaction_date'])[:7]
            months[month] = months.get(month, 0) + 1
    
    print("\nBy month:")
    for month in sorted(months.keys()):
        print(f"  {month}: {months[month]:,} records")
