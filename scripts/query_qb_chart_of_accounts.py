#!/usr/bin/env python3
"""Query existing QuickBooks chart of accounts structure."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)

cur = conn.cursor()

print("\n" + "=" * 120)
print("QUICKBOOKS CHART OF ACCOUNTS - CURRENT STRUCTURE")
print("=" * 120)

cur.execute("""
    SELECT 
        account_code,
        account_name,
        account_type,
        parent_account_id,
        account_level,
        is_header_account,
        qb_account_type
    FROM chart_of_accounts
    WHERE is_active = true
    ORDER BY 
        CASE 
            WHEN account_code ~ '^[0-9]' THEN LPAD(account_code, 10, '0')
            ELSE account_code
        END
    LIMIT 100
""")

rows = cur.fetchall()

print(f"\nTotal active accounts: {len(rows)}\n")
print(f"{'Code':15} {'Name':40} {'Type':20} {'Level':5} {'Header':6} {'QB Type':20}")
print("-" * 120)

for row in rows:
    code, name, acc_type, parent, level, is_header, qb_type = row
    indent = "  " * (level or 0)
    name_display = f"{indent}{name}"[:40]
    print(f"{code or 'None':15} {name_display:40} {acc_type or '':20} {level or 0:5} {str(is_header or False):6} {qb_type or '':20}")

print("\n" + "=" * 120)
print("ACCOUNT TYPE DISTRIBUTION")
print("=" * 120)

cur.execute("""
    SELECT 
        account_type,
        qb_account_type,
        COUNT(*) as count
    FROM chart_of_accounts
    WHERE is_active = true
    GROUP BY account_type, qb_account_type
    ORDER BY count DESC
""")

print(f"\n{'Account Type':30} {'QB Type':30} {'Count':10}")
print("-" * 72)
for row in cur.fetchall():
    print(f"{row[0] or 'NULL':30} {row[1] or 'NULL':30} {row[2]:10}")

print("\n" + "=" * 120)
print("ACCOUNT HIERARCHY SAMPLE (with parents)")
print("=" * 120)

cur.execute("""
    SELECT 
        c.account_code,
        c.account_name,
        p.account_code as parent_code,
        p.account_name as parent_name,
        c.account_level
    FROM chart_of_accounts c
    LEFT JOIN chart_of_accounts p ON c.parent_account_id = p.account_id
    WHERE c.is_active = true
    AND c.parent_account_id IS NOT NULL
    ORDER BY c.account_level, p.account_code, c.account_code
    LIMIT 30
""")

print(f"\n{'Code':10} {'Account Name':35} {'Parent Code':12} {'Parent Name':35} {'Level':5}")
print("-" * 100)
for row in cur.fetchall():
    print(f"{row[0] or '':10} {row[1][:34]:35} {row[2] or '':12} {row[3][:34] if row[3] else '':35} {row[4]:5}")

cur.close()
conn.close()
