import pandas as pd

df = pd.read_excel('L:\\limo\\reports\\UNMATCHED_CHARTER_PAYMENTS.xlsx', sheet_name='Charters With Refunds')

print(f"Charters with refunds: {len(df)}")
print(f"Total refunds amount: ${df['refunds_total'].sum():,.2f}")
print(f"\nTop 10 by refunds_total:")
top = df.nlargest(10, 'refunds_total')
for idx, row in top.iterrows():
    print(f"  {row['reserve_number']}: ${row['refunds_total']:,.2f} ({int(row['refund_count'])} refunds)")
