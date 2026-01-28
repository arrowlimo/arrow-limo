#!/usr/bin/env python3
"""
Enhanced Categorization for Banking Transactions
"""

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

CATEGORY_KEYWORDS = [
    # (Category, [keywords])
    ("Bank Charges & Interest", ["NON-SUFFICIENT", "NSF", "OVERDRAFT", "OVERLIMIT", "INSUFFICIENT", "SERVICE FEE", "BANK CHARGE"]),
    ("Banking service fee", ["BANKING SERVICE FEE", "SERVICE CHARGE"]),
    ("atm withdrawal", ["ATM WITHDRAWAL", "AUTOMATED BANKING MACHINE", "ATM-CANADA", "ATM INTL"]),
    ("Business expense", ["POINT OF SALE", "VISA DEBIT", "RETAIL PURCHASE", "POS", "SHOP/PARKING RENT"]),
    ("Cash withdrawal", ["CASH WITHDRAWAL"]),
    ("Square sales/fees", ["SQUARE", "SQ *", "SQUARE SALES", "SQUARE FEES"]),
    ("Loan payment", ["LOAN PAYMENT", "HEFFNER", "AUTO LOAN", "VEHICLE LOAN", "INTEREST"]),
    ("Fuel", ["GAS", "PETRO", "SHELL", "ESSO", "HUSKY", "FAS GAS", "DIESEL", "BULK FUEL"]),
]


def categorize(description):
    desc = (description or "").upper()
    for cat, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in desc:
                return cat
    return None


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("Re-categorizing uncategorized banking transactions...")
    cur.execute("""
        SELECT id, description, vendor_name
        FROM receipts
        WHERE created_from_banking = true AND category = 'UNCATEGORIZED'
    """)
    rows = cur.fetchall()
    updated = 0
    for row in rows:
        rid, desc, vendor = row
        new_cat = categorize(desc) or categorize(vendor)
        if new_cat:
            cur.execute("UPDATE receipts SET category = %s, expense_account = %s WHERE id = %s", (new_cat, f"{new_cat}", rid))
            updated += 1
    conn.commit()
    print(f"Updated {updated} uncategorized transactions.")
    conn.close()

if __name__ == "__main__":
    main()