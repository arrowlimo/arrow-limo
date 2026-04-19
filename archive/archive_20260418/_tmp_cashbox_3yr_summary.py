"""
Cash Box 3-Year Consolidated Summary (2012-2014)
-------------------------------------------------
Uses the sub-classification logic to produce a year-by-year clean balance.
"""

import psycopg2
from collections import defaultdict

CONN = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata',
    user='postgres', password='ArrowLimousine'
)
cur = CONN.cursor()

def is_bank_summary(desc):
    return (desc or "").upper() in ("BANK WITHDRAWAL", "MONEY MART WITHDRAWAL")

def sub_classify(row, group):
    _, _, _, desc, cat, _, _ = row
    d = (desc or "").upper()
    if is_bank_summary(desc):
        has_detailed = any(not is_bank_summary(r[3]) for r in group)
        return "dup" if has_detailed else "owner"
    if "MONEY MART" in d:
        return "true"
    if "BRANCH TRANSACTION" in d or "IBB" in d:
        return "true"
    if "ATM" in d or "ABM" in d or "AUTOMATED BANKING" in d or "INSTANT TELLER" in d:
        return "true"
    if cat and "owner" in (cat or "").lower():
        return "owner"
    return "true"

print("=" * 75)
print("CLEAN CASH-BOX BALANCE BY YEAR (2012-2014)")
print("=" * 75)
print(f"{'Year':<6} {'Withdrawals IN':>16} {'Dup Removed':>14} {'Cash Dep OUT':>14} "
      f"{'Receipts OUT':>13} {'Reimb OUT':>11} {'Net (Deficit)':>14}")
print("-" * 75)

for year in [2012, 2013, 2014]:
    # --- withdrawals ---
    cur.execute(
        "SELECT transaction_id, transaction_date, debit_amount, description, "
        "       category, source_file, import_batch "
        "FROM banking_transactions "
        "WHERE EXTRACT(YEAR FROM transaction_date) = %s "
        "  AND debit_amount IS NOT NULL AND debit_amount > 0 "
        "  AND (description ILIKE '%%withdrawal%%' "
        "       OR description ILIKE '%%atm%%' "
        "       OR description ILIKE '%%abm%%' "
        "       OR description ILIKE '%%cash advance%%' "
        "       OR description ILIKE '%%money mart%%') "
        "ORDER BY transaction_date, debit_amount DESC, transaction_id",
        (year,)
    )
    all_rows = cur.fetchall()
    by_date_amt = defaultdict(list)
    for row in all_rows:
        by_date_amt[(row[1], row[2])].append(row)
    
    true_total = sum(float(r[2]) for r in all_rows
                     if sub_classify(r, by_date_amt[(r[1], r[2])]) == "true")
    dup_total  = sum(float(r[2]) for r in all_rows
                     if sub_classify(r, by_date_amt[(r[1], r[2])]) == "dup")
    
    # --- cash deposits out ---
    cur.execute(
        "SELECT COALESCE(SUM(credit_amount), 0) "
        "FROM banking_transactions "
        "WHERE EXTRACT(YEAR FROM transaction_date) = %s "
        "  AND credit_amount IS NOT NULL AND credit_amount > 0 "
        "  AND (description ILIKE '%%bank deposit%%' "
        "       OR description ILIKE '%%branch transaction deposit%%')",
        (year,)
    )
    cash_dep = float(cur.fetchone()[0])
    
    # --- cash receipts ---
    cur.execute(
        "SELECT COALESCE(SUM(gross_amount), 0) "
        "FROM receipts "
        "WHERE EXTRACT(YEAR FROM receipt_date) = %s "
        "  AND payment_method ILIKE 'cash' "
        "  AND (receipt_source IS NULL OR receipt_source NOT IN ('manual_reimbursement')) "
        "  AND (description IS NULL OR description NOT ILIKE '%%reimburse%%')",
        (year,)
    )
    cash_rcpts = float(cur.fetchone()[0])
    
    # --- reimbursements ---
    cur.execute(
        "SELECT COALESCE(SUM(gross_amount), 0) "
        "FROM receipts "
        "WHERE EXTRACT(YEAR FROM receipt_date) = %s "
        "  AND (receipt_source = 'manual_reimbursement' "
        "       OR description ILIKE '%%reimburse%%' "
        "       OR description ILIKE '%%reimburs%%')",
        (year,)
    )
    reimb = float(cur.fetchone()[0])
    
    total_out = cash_dep + cash_rcpts + reimb
    net = total_out - true_total  # positive = deficit, negative = surplus

    flag = " <- DEFICIT" if net > 0 else " (surplus)"
    print(f"{year:<6} ${true_total:>14,.2f}  ${dup_total:>12,.2f}  ${cash_dep:>12,.2f}  "
          f"${cash_rcpts:>11,.2f}  ${reimb:>9,.2f}  ${net:>12,.2f}{flag}")

print("-" * 75)
print()
print("Interpretation:")
print("  2012 DEFICIT = genuine unrecorded cash receipts from charter clients.")
print("  2013-2014 SURPLUS = bank withdrawals exceeded all identified cash uses;")
print("    either some cash was spent on items not in receipts table,")
print("    or some receipts remain unlinked/unrecorded.")
print()

# Also show owner_personal rows that are NOT confirmed duplicates
for year in [2012, 2013, 2014]:
    cur.execute(
        "SELECT transaction_id, transaction_date, debit_amount, description, category "
        "FROM banking_transactions "
        "WHERE EXTRACT(YEAR FROM transaction_date) = %s "
        "  AND debit_amount IS NOT NULL AND debit_amount > 0 "
        "  AND (description ILIKE '%%withdrawal%%' OR description ILIKE '%%money mart%%') "
        "  AND category ILIKE '%%owner%%' "
        "  AND description NOT IN ('BANK WITHDRAWAL', 'MONEY MART WITHDRAWAL') "
        "  AND (description NOT ILIKE '%%branch transaction%%' AND description NOT ILIKE '%%atm%%') "
        "ORDER BY debit_amount DESC "
        "LIMIT 5",
        (year,)
    )
    rows = cur.fetchall()
    if rows:
        print(f"  {year} owner-labelled but not duplicate (top 5):")
        for r in rows:
            print(f"    {r[0]} {r[1]} ${r[2]:.2f}  [{r[3]}] cat={r[4]}")

CONN.close()
