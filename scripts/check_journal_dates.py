import pandas as pd

df = pd.read_excel('L:/limo/quickbooks/old quickbooks/initial journal.xlsx', header=3)
df = df[df['Date'].notna()]
df['Date'] = pd.to_datetime(df['Date'])

print(f'Total rows with dates: {len(df)}')
print(f'Date range: {df["Date"].min()} to {df["Date"].max()}')
print(f'Rows before 2012: {len(df[df["Date"]<"2012-01-01"])}')
print(f'Rows 2012+: {len(df[df["Date"]>="2012-01-01"])}')
