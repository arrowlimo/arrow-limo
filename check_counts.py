import pandas as pd
import psycopg2

df = pd.read_excel('L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx')
df['date'] = pd.to_datetime(df['date'], errors='coerce')
valid = df[df['date'].notna()]

print("Excel file stats:")
print(f"  Total valid rows: {len(valid)}")
print(f"  2013: {len(valid[valid['date'].dt.year == 2013])}")
print(f"  2014: {len(valid[valid['date'].dt.year == 2014])}")

# Check database
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date) FROM banking_transactions WHERE account_number = '903990106011' AND EXTRACT(YEAR FROM transaction_date) = 2013")
count_2013, min_2013, max_2013 = cur.fetchone()

cur.execute("SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date) FROM banking_transactions WHERE account_number = '903990106011' AND EXTRACT(YEAR FROM transaction_date) = 2014")
count_2014, min_2014, max_2014 = cur.fetchone()

print("\nDatabase stats:")
print(f"  2013: {count_2013} ({min_2013} to {max_2013})")
print(f"  2014: {count_2014} ({min_2014} to {max_2014})")
print(f"  Total: {count_2013 + count_2014}")

cur.close()
conn.close()
