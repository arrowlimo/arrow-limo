#!/usr/bin/env python3
"""
Final Recategorization Attempt for Remaining Uncategorized Transactions
"""

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

CATEGORY_SUBCATEGORY_KEYWORDS = [
    ("Branch Transaction Revenue", None, ["BRANCH TRANSACTION R", "BRANCH TRANSACTION E", "REVENUE - BRANCH TRANSACTION"]),
    ("Cheque", None, ["CHEQUE"]),
    ("Internet Banking Revenue", None, ["REVENUE - INTERNET BANKING", "INTERNET BANKING COR"]),
]

def categorize(description, vendor):
    desc = (description or "").upper()
    vend = (vendor or "").upper()
    for cat, subcat, keywords in CATEGORY_SUBCATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in desc or kw in vend:
                return cat, subcat
    return None, None

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Final recategorization for remaining uncategorized banking transactions...")
    cur.execute("""
        SELECT id, description, vendor_name
        FROM receipts
        WHERE created_from_banking = true AND category = 'UNCATEGORIZED'
    """)
    rows = cur.fetchall()
    updated = 0
    for row in rows:
        rid, desc, vendor = row
        new_cat, new_subcat = categorize(desc, vendor)
        if new_cat:
            cur.execute("UPDATE receipts SET category = %s, expense_account = %s, sub_classification = %s WHERE id = %s", (new_cat, f"{new_cat}", new_subcat, rid))
            updated += 1
    conn.commit()
    print(f"Updated {updated} remaining uncategorized transactions.")
    conn.close()

if __name__ == "__main__":
    main()