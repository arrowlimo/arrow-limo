"""
Step 1: Import missing 1615 transactions from Excel into banking_transactions.
Step 2: Find unverified 8362 transactions that duplicate 1615 (same date+amount).
Step 3: Delete those 8362 duplicates (only if unverified AND no receipt_banking_links).

DRY_RUN=True: report only, no changes.
DRY_RUN=False: apply inserts and deletes.
"""
import openpyxl
import psycopg2
from datetime import date, datetime
from decimal import Decimal
from collections import defaultdict

DRY_RUN = False  # Set False to apply

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


# ── Load Excel ──────────────────────────────────────────────────────────────
print(f"Loading {XLSX_PATH} ...")
wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
ws = wb.active
all_rows = list(ws.iter_rows(values_only=True))

xl_txns = []
for i, row in enumerate(all_rows[1:], start=2):
    d = parse_date(row[0])
    if d is None or d.year < YEAR_START or d.year > YEAR_END:
        continue
    debit = parse_amount(row[2])
    credit = parse_amount(row[3])
    desc = str(row[1]).strip() if row[1] else ""
    xl_txns.append({"row": i, "date": d, "debit": debit, "credit": credit, "desc": desc})

print(f"Excel rows {YEAR_START}-{YEAR_END}: {len(xl_txns)}")

# ── Load DB ─────────────────────────────────────────────────────────────────
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata',
                        user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, debit_amount, credit_amount, description, transaction_id
    FROM banking_transactions
    WHERE account_number=%s
    AND transaction_date BETWEEN %s AND %s
""", (ACCT_NUM, f"{YEAR_START}-01-01", f"{YEAR_END}-12-31"))
db_rows = cur.fetchall()
print(f"DB rows: {len(db_rows)}")

# Build lookup (date, debit, credit) -> [tid, ...]
db_lookup = defaultdict(list)
for txn_date, debit, credit, desc, tid in db_rows:
    key = (txn_date, debit or Decimal("0"), credit or Decimal("0"))
    db_lookup[key].append(tid)

# ── Identify missing ────────────────────────────────────────────────────────
missing = []
for t in xl_txns:
    d = t["date"]
    debit = t["debit"] or Decimal("0")
    credit = t["credit"] or Decimal("0")
    key = (d, debit, credit)
    if db_lookup.get(key):
        db_lookup[key].pop(0)
    else:
        missing.append(t)

# Filter out pure opening balance row (amount=0 both sides)
missing = [t for t in missing if (t["debit"] or Decimal("0")) + (t["credit"] or Decimal("0")) > 0]

print(f"\nMissing from DB (to insert): {len(missing)}")

# Classify direction
def is_transfer(desc):
    d = desc.upper()
    return any(x in d for x in ["TRANSFER TO:", "TRANSFER FROM:", "E-TRANSFER", "ETRANSFER"])

def reconciliation_status(desc):
    d = desc.upper()
    if "PAYROLL" in d or "CHQ" in d:
        return "reconciled"
    if is_transfer(desc):
        return "reconciled"
    return "unreconciled"

def biz_personal(desc):
    d = desc.upper()
    personal_keywords = ["BED BATH", "CINEPLEX", "RESTAURANT", "RED LOBSTER",
                         "SHAMMY", "CAR WASH", "PERSONAL"]
    if any(k in d for k in personal_keywords):
        return "Personal"
    return "Business"

# ── STEP 1: Insert missing 1615 transactions ───────────────────────────────
print(f"\n{'DRY RUN — ' if DRY_RUN else ''}Inserting {len(missing)} missing 1615 transactions ...")

inserted = 0
for t in missing:
    debit = t["debit"] if t["debit"] and t["debit"] > 0 else None
    credit = t["credit"] if t["credit"] and t["credit"] > 0 else None
    xfer = is_transfer(t["desc"])
    status = "reconciled" if xfer else "unreconciled"
    biz = biz_personal(t["desc"])

    if not DRY_RUN:
        cur.execute("""
            INSERT INTO banking_transactions
                (account_number, transaction_date, debit_amount, credit_amount,
                 description, source_file, import_batch,
                 reconciliation_status, is_transfer, business_personal, verified)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ACCT_NUM,
            t["date"],
            debit,
            credit,
            t["desc"],
            XLSX_PATH,
            "1615_gap_import_20260324",
            status,
            xfer,
            biz,
            False,  # not verified — needs review
        ))
    inserted += 1

if not DRY_RUN:
    conn.commit()
    print(f"Inserted {inserted} rows into banking_transactions.")
else:
    print(f"[DRY RUN] Would insert {inserted} rows.")

# ── STEP 2: Find unverified 8362 duplicates of 1615 ────────────────────────
print("\n\n=== STEP 2: Find unverified 8362 rows that duplicate 1615 ===")

# Use the FULL Excel set as the canonical 1615 reference
# (covers both existing DB rows and newly-inserted ones)
lut_1615 = defaultdict(int)
for t in xl_txns:
    key = (t["date"], t["debit"] or Decimal("0"), t["credit"] or Decimal("0"))
    lut_1615[key] += 1
print(f"1615 canonical set (Excel {YEAR_START}-{YEAR_END}): {len(xl_txns)} rows")

# Get all UNVERIFIED 8362 rows in the date range with no receipt links
cur.execute("""
    SELECT bt.transaction_id, bt.transaction_date, bt.debit_amount, bt.credit_amount,
           bt.description, bt.reconciliation_status, bt.import_batch, bt.source_file
    FROM banking_transactions bt
    WHERE bt.account_number='0228362'
    AND bt.transaction_date BETWEEN %s AND %s
    AND bt.verified = FALSE
    AND NOT EXISTS (
        SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id = bt.transaction_id
    )
    ORDER BY bt.transaction_date, bt.transaction_id
""", (f"{YEAR_START}-01-01", f"{YEAR_END}-12-31"))
unverified_8362 = cur.fetchall()
print(f"Unverified 8362 rows (no receipt link, {YEAR_START}-{YEAR_END}): {len(unverified_8362)}")

# Match against 1615 lookup
to_delete = []
lut_copy = defaultdict(int, lut_1615)  # use a copy for multi-set matching

for row in unverified_8362:
    tid, txn_date, debit, credit, desc, status, batch, source = row
    key = (txn_date, debit or Decimal("0"), credit or Decimal("0"))
    if lut_copy[key] > 0:
        lut_copy[key] -= 1
        to_delete.append(row)

print(f"\nUnverified 8362 rows matching 1615 (date+amount): {len(to_delete)}")

if to_delete:
    print(f"\n{'Date':<12} {'Debit':>8} {'Credit':>8}  {'Description':<40}  Batch/Source")
    print("-" * 105)
    by_batch = defaultdict(list)
    for row in to_delete:
        tid, txn_date, debit, credit, desc, status, batch, source = row
        by_batch[batch or source or 'unknown'].append(row)
        deb_str = f"${float(debit):.2f}" if debit else ""
        cre_str = f"${float(credit):.2f}" if credit else ""
        print(f"  {txn_date}  {deb_str:>9} {cre_str:>9}  {(desc or '')[:40]:<40}  [{batch or source}]  id={tid}")

    # Group by batch
    print(f"\nBy import batch:")
    for batch, rows in sorted(by_batch.items()):
        tids = [r[0] for r in rows]
        print(f"  {batch:<50}  {len(rows):>4} rows")

# ── STEP 3: Delete the 8362 duplicates ─────────────────────────────────────
if to_delete:
    print(f"\n{'DRY RUN — ' if DRY_RUN else ''}Deleting {len(to_delete)} duplicate 8362 rows ...")
    delete_ids = [r[0] for r in to_delete]

    if not DRY_RUN:
        cur.execute(
            "DELETE FROM banking_transactions WHERE transaction_id = ANY(%s)",
            (delete_ids,)
        )
        deleted = cur.rowcount
        conn.commit()
        print(f"Deleted {deleted} unverified 8362 duplicate rows.")
    else:
        print(f"[DRY RUN] Would delete {len(delete_ids)} rows: {delete_ids[:10]}{'...' if len(delete_ids)>10 else ''}")

print("\nDone.")
conn.close()
