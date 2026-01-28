import pandas as pd

df = pd.read_excel('reports/banking_accounts_all_years.xlsx', sheet_name='903990106011')
df['transaction_date'] = pd.to_datetime(df['transaction_date'])

amounts = [193.00, 594.98, 102.23, 165.00, 205.00]
print('Searching for deposit amounts from PDF statement:', amounts)
print('='*80)

for amt in amounts:
    matches = df[(df['credit_amount'] == amt) | (df['debit_amount'] == amt)]
    if len(matches) > 0:
        print(f'\n${amt}: Found {len(matches)} matches')
        for idx, row in matches.head(5).iterrows():
            date_str = row['transaction_date'].strftime('%Y-%m-%d')
            desc = row['description'][:60] if pd.notna(row['description']) else 'N/A'
            print(f'  Row {idx+2}: {date_str} | {desc} | Credit:{row["credit_amount"]} Debit:{row["debit_amount"]}')
    else:
        print(f'\n${amt}: NOT FOUND in any transaction')

print('\n' + '='*80)
print('Checking database for these amounts...')
