#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

print("TYPE, CLASSIFICATION, SUB_CLASSIFICATION VALUES IN RECEIPTS")
print("=" * 120)

cur.execute("""
SELECT type, classification, sub_classification, COUNT(*) as count
FROM receipts
WHERE type IS NOT NULL OR classification IS NOT NULL OR sub_classification IS NOT NULL
GROUP BY type, classification, sub_classification
ORDER BY COUNT(*) DESC
LIMIT 40
""")

print(f"{'Type':<20} | {'Classification':<25} | {'Sub_classification':<30} | {'Count':<6}")
print("-" * 120)

for r in cur.fetchall():
    type_str = (r[0] or "")[:20]
    class_str = (r[1] or "")[:25]
    subclass_str = (r[2] or "")[:30]
    print(f"{type_str:<20} | {class_str:<25} | {subclass_str:<30} | {r[3]:<6}")

# Check GL codes
print("\n" + "=" * 120)
print("GL_ACCOUNT_CODE AND GL_ACCOUNT_NAME VALUES")
print("=" * 120)

cur.execute("""
SELECT gl_account_code, gl_account_name, COUNT(*) as count
FROM receipts
WHERE gl_account_code IS NOT NULL
GROUP BY gl_account_code, gl_account_name
ORDER BY COUNT(*) DESC
LIMIT 30
""")

print(f"{'GL Code':<15} | {'GL Account Name':<50} | {'Count':<6}")
print("-" * 120)

for r in cur.fetchall():
    code_str = (r[0] or "")[:15]
    name_str = (r[1] or "")[:50]
    print(f"{code_str:<15} | {name_str:<50} | {r[2]:<6}")

# Check redundancy: category vs gl_account_code
print("\n" + "=" * 120)
print("CATEGORY vs GL_ACCOUNT_CODE OVERLAP")
print("=" * 120)

cur.execute("""
SELECT category, COUNT(*) as count
FROM receipts
WHERE category IS NOT NULL
GROUP BY category
ORDER BY COUNT(*) DESC
LIMIT 20
""")

print(f"{'Category (legacy)':<30} | {'Count':<6}")
print("-" * 120)

for r in cur.fetchall():
    cat_str = (r[0] or "")[:30]
    print(f"{cat_str:<30} | {r[1]:<6}")

cur.close()
conn.close()
