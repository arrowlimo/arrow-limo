"""
Summarise missing 1615 transactions (in Excel but not in almsdata DB), 2012-2014.
Groups by year, then by description keyword category.
"""
import openpyxl
import psycopg2
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from collections import defaultdict

XLSX_PATH = r"L:\CIBC_7461615_2012_2017_VERIFIED.xlsx"
ACCT_NUM = '1615'
YEAR_START = 2012
YEAR_END = 2014


def parse_date(val):
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return None


def parse_amount(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(round(val, 2)))
    return None


# Load Excel
wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
ws = wb.active
all_rows = list(ws.iter_rows(values_only=True))

# Columns: 0=date, 1=description, 2=debit, 3=credit
xl_txns = []
for i, row in enumerate(all_rows[1:], start=2):  # skip header
    d = parse_date(row[0])
    if d is None or d.year < YEAR_START or d.year > YEAR_END:
        continue
    debit = parse_amount(row[2])
    credit = parse_amount(row[3])
    desc = str(row[1]).strip() if row[1] else ""
    xl_txns.append({"row": i, "date": d, "debit": debit, "credit": credit, "desc": desc})

print(f"Excel rows 2012-2014: {len(xl_txns)}")

# Load DB
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute("""
    SELECT transaction_date, debit_amount, credit_amount, description, transaction_id
    FROM banking_transactions
    WHERE account_number=%s
    AND transaction_date BETWEEN %s AND %s
    ORDER BY transaction_date, transaction_id
""", (ACCT_NUM, f"{YEAR_START}-01-01", f"{YEAR_END}-12-31"))
db_rows = cur.fetchall()
conn.close()
print(f"DB rows 2012-2014: {len(db_rows)}")

# Build DB lookup (date, debit, credit) -> list of bt_ids
db_lookup = defaultdict(list)
for txn_date, debit, credit, desc, tid in db_rows:
    key = (txn_date, debit or Decimal("0"), credit or Decimal("0"))
    db_lookup[key].append(tid)

# Match
missing = []
matched = 0
for t in xl_txns:
    d = t["date"]
    debit = t["debit"] or Decimal("0")
    credit = t["credit"] or Decimal("0")
    key = (d, debit, credit)
    if db_lookup.get(key):
        db_lookup[key].pop(0)
        matched += 1
    else:
        missing.append(t)

print(f"Matched: {matched}  |  Missing from DB: {len(missing)}\n")

# Categorize missing
def categorize(desc):
    d = desc.upper()
    if "CENTEX" in d or "FAS GAS" in d or "MOHAWK" in d or "FUEL" in d:
        return "FUEL"
    if "NSF" in d:
        return "NSF FEE/RETURN"
    if "CASH WITHDRAWAL" in d or "WITHDRAWAL" in d:
        return "CASH WITHDRAWAL"
    if "TRANSFER" in d:
        return "TRANSFER"
    if "DEPOSIT" in d:
        return "DEPOSIT/INCOME"
    if "SERVICE CHARGE" in d:
        return "BANK FEE"
    if "HEFFNER" in d:
        return "HEFFNER LEASE"
    if "JACK CARTER" in d:
        return "JACK CARTER"
    if "ROGERS" in d or "TELUS" in d or "BELL" in d:
        return "TELECOM"
    if "FACEBOOK" in d or "GOOGLE" in d:
        return "ADVERTISING"
    if d == "OPENING BALANCE":
        return "OPENING BALANCE"
    return "OTHER"

# Print missing by year + category
by_year = defaultdict(list)
for t in missing:
    by_year[t["date"].year].append(t)

overall_cats = defaultdict(lambda: {"count": 0, "total": Decimal("0")})
for year in sorted(by_year):
    cats = defaultdict(lambda: {"count": 0, "total": Decimal("0"), "items": []})
    for t in by_year[year]:
        cat = categorize(t["desc"])
        amt = t["debit"] or t["credit"] or Decimal("0")
        cats[cat]["count"] += 1
        cats[cat]["total"] += amt
        cats[cat]["items"].append(t)
        overall_cats[cat]["count"] += 1
        overall_cats[cat]["total"] += amt
    
    print(f"=== {year}: {len(by_year[year])} missing ===")
    for cat in sorted(cats):
        print(f"  {cat:<22} {cats[cat]['count']:>4} txns  ${float(cats[cat]['total']):>10.2f}")

print(f"\n=== OVERALL MISSING TOTALS ===")
grand_count = 0
grand_total = Decimal("0")
for cat in sorted(overall_cats):
    c = overall_cats[cat]["count"]
    t = overall_cats[cat]["total"]
    grand_count += c
    grand_total += t
    print(f"  {cat:<22} {c:>4} txns  ${float(t):>10.2f}")
print(f"  {'TOTAL':<22} {grand_count:>4} txns  ${float(grand_total):>10.2f}")

# Print detailed list of non-income, non-transfer missing DEBITS (i.e. expense gaps)
print(f"\n=== EXPENSE DEBITS MISSING FROM DB (not payroll/transfer/income/NSF/fee) ===")
skip_cats = {"OPENING BALANCE", "DEPOSIT/INCOME", "NSF FEE/RETURN", "TRANSFER", "BANK FEE"}
expense_missing = [t for t in missing
                   if t["debit"] and t["debit"] > 0
                   and categorize(t["desc"]) not in skip_cats]
print(f"Count: {len(expense_missing)}")
print(f"{'Date':<12} {'Amount':>8}  {'Category':<20}  Description")
print("-" * 75)
for t in sorted(expense_missing, key=lambda x: x["date"]):
    cat = categorize(t["desc"])
    print(f"  {t['date'].strftime('%Y-%m-%d')}  ${float(t['debit']):>7.2f}  {cat:<20}  {t['desc'][:50]}")
