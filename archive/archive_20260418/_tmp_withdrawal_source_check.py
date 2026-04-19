import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute(
    "SELECT import_batch, source_file, category, description, COUNT(*), SUM(debit_amount) "
    "FROM banking_transactions "
    "WHERE EXTRACT(YEAR FROM transaction_date) IN (2013, 2014) "
    "  AND debit_amount IS NOT NULL "
    "  AND description IN ('BANK WITHDRAWAL', 'MONEY MART WITHDRAWAL') "
    "GROUP BY import_batch, source_file, category, description "
    "ORDER BY COUNT(*) DESC"
)
rows = cur.fetchall()
print("NULL-source BANK/MM WITHDRAWAL breakdown:")
for r in rows:
    print(f"  batch={r[0]} source={r[1]} cat={r[2]} desc={r[3]} cnt={r[4]} total={r[5]:.2f}")

print()

cur.execute(
    "SELECT MIN(transaction_id), MAX(transaction_id), import_batch, source_file, COUNT(*) "
    "FROM banking_transactions "
    "WHERE transaction_id BETWEEN 88000 AND 89500 "
    "GROUP BY import_batch, source_file "
    "ORDER BY import_batch"
)
rows = cur.fetchall()
print("88xxx-89xxx range IDs:")
for r in rows:
    print(f"  min={r[0]} max={r[1]} batch={r[2]} source={r[3]} cnt={r[4]}")

print()
# Show the distinct import batches present in 2013-2014 withdrawals overall
cur.execute(
    "SELECT import_batch, source_file, COUNT(*), SUM(debit_amount) "
    "FROM banking_transactions "
    "WHERE EXTRACT(YEAR FROM transaction_date) IN (2013, 2014) "
    "  AND debit_amount IS NOT NULL "
    "  AND (description ILIKE '%withdrawal%' OR description ILIKE '%money mart%') "
    "GROUP BY import_batch, source_file "
    "ORDER BY SUM(debit_amount) DESC"
)
rows = cur.fetchall()
print("All withdrawal rows by batch/source (2013-2014):")
for r in rows:
    print(f"  batch={r[0]} source={r[1]} cnt={r[2]} total={r[3]:.2f}")

conn.close()
