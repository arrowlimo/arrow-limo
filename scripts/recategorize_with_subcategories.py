#!/usr/bin/env python3
"""
Enhanced Categorization with Subcategories from Screenshot List
"""

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

CATEGORY_SUBCATEGORY_KEYWORDS = [
    ("Bank Charges & Interest", "Banking service fee", ["SERVICE FEE", "BANK CHARGE", "BANKING SERVICE FEE"]),
    ("Bank Charges & Interest", "atm withdrawal", ["ATM WITHDRAWAL", "AUTOMATED BANKING MACHINE", "ATM-CANADA", "ATM INTL"]),
    ("Business expense", "Business meal", ["BUSINESS MEAL"]),
    ("Business expense", "Client Beverage", ["CLIENT BEVERAGE"]),
    ("Business expense", "Client Food", ["CLIENT FOOD"]),
    ("Business expense", "Client supplies", ["CLIENT SUPPLIES"]),
    ("Business expense", "Employment requirement", ["EMPLOYMENT REQUIREMENT"]),
    ("Business expense", "Ice", ["ICE"]),
    ("Business expense", "keys", ["KEYS"]),
    ("Cash withdrawal", None, ["CASH WITHDRAWAL"]),
    ("Square sales/fees", "Square sales", ["SQUARE SALES", "SQ *"]),
    ("Square sales/fees", "Square discount", ["SQUARE DISCOUNT"]),
    ("Square sales/fees", "Square fees", ["SQUARE FEES"]),
    ("Loan payment", "cash loan", ["LOAN PAYMENT", "CASH LOAN", "HEFFNER", "AUTO LOAN", "VEHICLE LOAN", "INTEREST"]),
    ("Fuel", "Fuel Surcharge", ["FUEL", "FUEL SURCHARGE", "GAS", "PETRO", "SHELL", "ESSO", "HUSKY", "FAS GAS", "DIESEL", "BULK FUEL"]),
    ("Office Supplies", "business cards", ["BUSINESS CARDS"]),
    ("Office Supplies", "chair", ["CHAIR"]),
    ("Office Supplies", "copies", ["COPIES"]),
    ("Office Supplies", "display pins", ["DISPLAY PINS"]),
    ("Office Supplies", "keys", ["KEYS"]),
    ("Office Supplies", "Paper", ["PAPER"]),
    ("Office Supplies", "printing", ["PRINTING"]),
    ("Office Supplies", "Taxes", ["TAXES"]),
    ("Office Supplies", "Toner", ["TONER"]),
    ("Office Supplies", "white board", ["WHITE BOARD"]),
    ("Vehicle R&M", "ac repair", ["AC REPAIR"]),
    ("Vehicle R&M", "battery", ["BATTERY"]),
    ("Vehicle R&M", "CVIP", ["CVIP"]),
    ("Vehicle R&M", "Diagnostic tool", ["DIAGNOSTIC TOOL"]),
    ("Vehicle R&M", "muffler parts", ["MUFFLER PARTS"]),
    ("Vehicle R&M", "oil change", ["OIL CHANGE"]),
    ("Vehicle R&M", "Paint", ["PAINT"]),
    ("Vehicle R&M", "parts", ["PARTS"]),
    ("Vehicle R&M", "repairs/cvip", ["REPAIRS/CVIP"]),
    ("Vehicle R&M", "Screw covers", ["SCREW COVERS"]),
    ("Vehicle R&M", "starter", ["STARTER"]),
    ("Vehicle R&M", "Tires", ["TIRES"]),
    ("Vehicle R&M", "towing", ["TOWING"]),
    ("Vehicle R&M", "window repair", ["WINDOW REPAIR"]),
    ("Internet", "site booster", ["SITE BOOSTER"]),
    ("Parking", "Airport parking", ["AIRPORT PARKING"]),
    ("Parking", "edmonton city parking", ["EDMONTON CITY PARKING"]),
    ("Purchases", None, ["PURCHASE"]),
    ("Uncategorized Expense", None, ["UNCATEGORIZED EXPENSE"]),
    ("Uncategorized Income", None, ["UNCATEGORIZED INCOME"]),
    ("Internet Bill Payment", None, ["INTERNET BILL"]),
    ("Branch Transaction Revenue", None, ["BRANCH TRANSACTION E"]),
    ("Branch Transaction Debit Memo", None, ["DEBIT MEMO"]),
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
    print("Re-categorizing all uncategorized banking transactions with subcategories...")
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
    print(f"Updated {updated} uncategorized transactions with categories and subcategories.")
    conn.close()

if __name__ == "__main__":
    main()