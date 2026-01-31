import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=== Reconciliation Statuses ===\n")
cur.execute("SELECT DISTINCT reconciliation_status, COUNT(*) FROM banking_transactions GROUP BY reconciliation_status ORDER BY COUNT(*) DESC")
for row in cur.fetchall():
    print(f"  {row[0] or 'NULL'}: {row[1]:,}")

print("\n=== Banking Source Files ===\n")
cur.execute("SELECT DISTINCT source_file FROM banking_transactions WHERE source_file IS NOT NULL ORDER BY source_file")
files = cur.fetchall()
print(f"Found {len(files)} unique source files")
for row in files[:10]:
    print(f"  {row[0]}")
if len(files) > 10:
    print(f"  ... and {len(files) - 10} more")

cur.close()
conn.close()
