import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

queries = {
    "unique_receipt_vendors": """SELECT COUNT(DISTINCT vendor_name) FROM receipts WHERE vendor_name IS NOT NULL AND vendor_name <> ''""",
    "unique_receipt_vendors_linked": """SELECT COUNT(DISTINCT r.vendor_name) FROM receipts r JOIN banking_transactions b ON r.banking_transaction_id = b.transaction_id WHERE r.vendor_name IS NOT NULL AND r.vendor_name <> ''""",
    "mismatch_vs_bank_description": """SELECT COUNT(*) FROM receipts r JOIN banking_transactions b ON r.banking_transaction_id = b.transaction_id WHERE COALESCE(r.vendor_name,'') <> COALESCE(b.description,'')""",
    "mismatch_vs_bank_vendor": """SELECT COUNT(*) FROM receipts r JOIN banking_transactions b ON r.banking_transaction_id = b.transaction_id WHERE COALESCE(r.vendor_name,'') <> COALESCE(b.vendor_extracted,'')""",
    "top_receipt_vendors": """SELECT vendor_name, COUNT(*) AS c FROM receipts WHERE vendor_name IS NOT NULL AND vendor_name <> '' GROUP BY vendor_name ORDER BY c DESC LIMIT 15""",
    "top_bank_vendors": """SELECT vendor_extracted, COUNT(*) AS c FROM banking_transactions WHERE vendor_extracted IS NOT NULL AND vendor_extracted <> '' GROUP BY vendor_extracted ORDER BY c DESC LIMIT 15""",
}

results = {}
for key, sql in queries.items():
    cur.execute(sql)
    results[key] = cur.fetchall()

cur.close(); conn.close()

print("Counts:")
print(f"  unique_receipt_vendors: {results['unique_receipt_vendors'][0][0]}")
print(f"  unique_receipt_vendors_linked: {results['unique_receipt_vendors_linked'][0][0]}")
print(f"  mismatched_linked_vs_bank_description: {results['mismatch_vs_bank_description'][0][0]}")
print(f"  mismatched_linked_vs_bank_vendor_extracted: {results['mismatch_vs_bank_vendor'][0][0]}")

print("\nTop receipt vendors:")
for v, c in results['top_receipt_vendors']:
    print(f"  {v[:60]:60} {c:6}")

print("\nTop banking vendors:")
for v, c in results['top_bank_vendors']:
    print(f"  {v[:60]:60} {c:6}")
