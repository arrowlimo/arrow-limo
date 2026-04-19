"""
Side-by-side verification: GL CSV "Bill Payment (Cheque)" bank-side rows vs ALMS banking_transactions.
- Filters to bank account rows only (accts 1000-1090) — skips the AP/expense double-entry side
- Date match tolerance: ±7 days
- Amount match: exact or within $0.02 rounding
- CHQ # column preserved for cheque book reference
"""

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg2

GL_CSV = Path(r"L:\limo\Copy of General_ledger.csv")
OUT_DIR = Path(r"L:\limo\archive\tmp_zip_analysis")
OUT_CSV = OUT_DIR / "gl_vs_banking_sidebyside.csv"
OUT_TXT = OUT_DIR / "gl_vs_banking_sidebyside.txt"

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")

DATE_TOLERANCE_DAYS = 7

# Only bank account prefixes — cash actually leaves these accounts
BANK_PREFIXES = ("1000", "1010", "1020", "1030", "1040", "1050", "1060", "1070", "1080", "1090")


def parse_date_dmy(s):
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def parse_amount(s):
    s = (s or "").strip().replace(",", "").replace("$", "").replace("\xa0", "").replace("\u00a0", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def load_gl_bill_payments():
    rows = []
    with open(GL_CSV, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        next(reader)  # skip header row
        for row in reader:
            if len(row) < 9:
                continue
            txn_type = row[2].strip()
            if txn_type != "Bill Payment (Cheque)":
                continue
            account = row[6].strip()
            # Only bank-side rows — skip AP/liability/expense entries
            if not any(account.startswith(pfx) for pfx in BANK_PREFIXES):
                continue
            date = parse_date_dmy(row[1])
            chq_ref = row[3].strip()
            vendor = row[4].strip()
            memo = row[5].strip()
            debit = parse_amount(row[7])
            credit = parse_amount(row[8])
            # Bank side: credit = cash leaving bank
            amount = credit if credit else debit
            rows.append({
                "date": date,
                "chq_ref": chq_ref,
                "vendor": vendor,
                "memo": memo,
                "account": account,
                "amount": amount,
            })
    return rows


def load_banking_transactions(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount,
               description, check_number
        FROM banking_transactions
        WHERE debit_amount IS NOT NULL AND debit_amount > 0
        ORDER BY transaction_date
    """)
    rows = []
    for r in cur.fetchall():
        rows.append({
            "id": r[0],
            "date": r[1],
            "debit": r[2],
            "credit": r[3],
            "description": r[4],
            "check_number": r[5],
        })
    cur.close()
    return rows


def find_best_match(gl_row, banking_rows, used_ids):
    gl_date = gl_row["date"]
    gl_amount = gl_row["amount"]
    if not gl_date or not gl_amount:
        return None, "NO_DATE_OR_AMOUNT"

    candidates = []
    for b in banking_rows:
        if b["id"] in used_ids:
            continue
        if b["date"] is None or b["debit"] is None:
            continue
        day_diff = abs((b["date"] - gl_date).days)
        if day_diff > DATE_TOLERANCE_DAYS:
            continue
        amt_diff = abs(Decimal(str(b["debit"])) - gl_amount)
        if amt_diff <= Decimal("0.02"):
            candidates.append((day_diff, amt_diff, b))

    if not candidates:
        return None, "NO_MATCH"
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2], "MATCHED"


def main():
    print("Loading GL CSV Bill Payment (Cheque) bank-side rows...")
    gl_rows = load_gl_bill_payments()
    print(f"  {len(gl_rows)} rows (bank-side only, AP double-entry side excluded)")

    print("Connecting to ALMS DB...")
    conn = psycopg2.connect(**DB)
    banking = load_banking_transactions(conn)
    print(f"  {len(banking)} banking_transactions with debit loaded")
    conn.close()

    used_ids = set()
    results = []

    for gl in gl_rows:
        match, status = find_best_match(gl, banking, used_ids)
        if match:
            used_ids.add(match["id"])
            date_diff = abs((match["date"] - gl["date"]).days) if gl["date"] else None
            amt_diff = abs(Decimal(str(match["debit"])) - gl["amount"]) if gl["amount"] else None
        else:
            date_diff = None
            amt_diff = None

        results.append({
            "status": status,
            "gl_date": gl["date"],
            "gl_chq": gl["chq_ref"],
            "gl_vendor": gl["vendor"],
            "gl_amount": gl["amount"],
            "gl_account": gl["account"],
            "bk_id": match["id"] if match else None,
            "bk_date": match["date"] if match else None,
            "bk_debit": match["debit"] if match else None,
            "bk_desc": match["description"] if match else None,
            "bk_chq": match["check_number"] if match else None,
            "date_diff_days": date_diff,
            "amt_diff": amt_diff,
        })

    matched = [r for r in results if r["status"] == "MATCHED"]
    unmatched = [r for r in results if r["status"] == "NO_MATCH"]
    no_data = [r for r in results if r["status"] == "NO_DATE_OR_AMOUNT"]

    print(f"\nResults: {len(matched)} MATCHED | {len(unmatched)} NO_MATCH | {len(no_data)} NO_DATE_OR_AMOUNT")

    # Write CSV
    fieldnames = ["status", "gl_date", "gl_chq", "gl_vendor", "gl_amount", "gl_account",
                  "bk_id", "bk_date", "bk_debit", "bk_desc", "bk_chq", "date_diff_days", "amt_diff"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)
    print(f"CSV: {OUT_CSV}")

    # Write text report
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write("GL CSV Bill Payment (Cheque) — Bank Side vs ALMS Banking Transactions\n")
        f.write("=" * 120 + "\n")
        f.write(f"GL bank-side rows: {len(results)} | MATCHED: {len(matched)} | NO_MATCH: {len(unmatched)} | NO_DATE/AMT: {len(no_data)}\n")
        f.write(f"Date tolerance: +/-{DATE_TOLERANCE_DAYS} days | Amount tolerance: $0.02\n\n")

        # MATCHED
        f.write(f"MATCHED ({len(matched)} rows)\n")
        f.write("-" * 120 + "\n")
        f.write(f"{'GL Date':<12} {'CHQ#':<10} {'GL Vendor':<32} {'GL Amt':>10}  "
                f"{'BK Date':<12} {'BK Debit':>10} {'Dd':>3}  {'BK Chq':<8} {'BK Description':<35}\n")
        f.write("-" * 120 + "\n")
        for r in sorted(matched, key=lambda x: x["gl_date"] or datetime.min.date()):
            f.write(
                f"{str(r['gl_date']):<12} {str(r['gl_chq']):<10} {str(r['gl_vendor'])[:31]:<32} "
                f"{str(r['gl_amount']):>10}  "
                f"{str(r['bk_date']):<12} {str(r['bk_debit']):>10} {str(r['date_diff_days']):>3}  "
                f"{str(r['bk_chq'] or ''):<8} {str(r['bk_desc'] or '')[:34]:<35}\n"
            )

        # UNMATCHED
        f.write(f"\nUNMATCHED ({len(unmatched)} rows) — need cheque book / manual verification\n")
        f.write("-" * 120 + "\n")
        f.write(f"{'GL Date':<12} {'CHQ#':<10} {'GL Vendor':<35} {'GL Amt':>10}  {'Bank Account':<28}\n")
        f.write("-" * 120 + "\n")
        for r in sorted(unmatched, key=lambda x: x["gl_date"] or datetime.min.date()):
            f.write(
                f"{str(r['gl_date']):<12} {str(r['gl_chq']):<10} {str(r['gl_vendor'])[:34]:<35} "
                f"{str(r['gl_amount']):>10}  {str(r['gl_account'])[:27]:<28}\n"
            )

        if no_data:
            f.write(f"\nNO DATE/AMOUNT ({len(no_data)} rows)\n")
            f.write("-" * 80 + "\n")
            for r in no_data:
                f.write(f"  {r['gl_vendor']:<35}  {r['gl_account']}\n")

    print(f"Text report: {OUT_TXT}")

    # Console: unmatched grouped by year
    by_year = defaultdict(list)
    for r in unmatched:
        yr = r["gl_date"].year if r["gl_date"] else 0
        by_year[yr].append(r)

    print(f"\n=== UNMATCHED by year ===")
    for yr in sorted(by_year):
        print(f"\n  [{yr}] {len(by_year[yr])} rows")
        for r in by_year[yr]:
            print(f"    {r['gl_date']}  CHQ:{str(r['gl_chq']):<10}  ${str(r['gl_amount']):>10}  "
                  f"{str(r['gl_vendor']):<35}  [{r['gl_account']}]")


if __name__ == "__main__":
    main()
