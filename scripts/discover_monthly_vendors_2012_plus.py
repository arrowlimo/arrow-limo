import os
import csv
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

OUT_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), "reports")
OUT_CSV = os.path.join(OUT_DIR, "DISCOVERED_MONTHLY_VENDORS_2012_PLUS.csv")
OUT_TXT = os.path.join(OUT_DIR, "DISCOVERED_MONTHLY_VENDORS_2012_PLUS.txt")

START_DATE = date(2012, 1, 1)

EXCLUDE_CATEGORY_TERMS = {"PAYROLL", "DRIVER PAY", "WAGES", "SALARY"}
EXCLUDE_DESC_TERMS = {"PAYROLL", "DRIVER PAY", "T4"}
EXCLUDE_VENDOR_KEYS = {
    # Bank/system generics
    "BANK","TRANSFER","ATM","FEE","NSF","DEPOSIT","SERVICE","ACCOUNT","BRANCH","POINT","AUTOMATED","OVERDRAFT","MONEY","CHEQUE","CASH",
    # Merchant services / cards
    "VCARD","MCARD","VCARD PAYMENT","MCARD PAYMENT","MERCHANT","SQUARE","VISA","MASTERCARD","GLOBAL","PAYMENT",
    # Retail/fuel (non-monthly utilities)
    "SAFEWAY","STAPLES","CINEPLEX","LIQUOR","CENTEX","ESSO","HUSKY","PETRO","CO-OP","WOODRIDGE","RED",
}


def conn_cur():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    return conn, conn.cursor()


def fetch_accounts(cur):
    cur.execute("SELECT canonical_vendor FROM vendor_accounts")
    return { (r[0] or '').strip().upper() for r in cur.fetchall() }


def load_bank_tx(cur):
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               COALESCE(credit_amount,0) - COALESCE(debit_amount,0) AS amount,
               vendor_extracted, category, is_nsf_charge, is_transfer, check_recipient
        FROM banking_transactions
        WHERE transaction_date IS NOT NULL AND transaction_date >= %s
    """, (START_DATE,))
    rows = []
    for tid, tdate, desc, amt, vend, cat, nsf, is_txfer, recip in cur.fetchall():
        rows.append({
            "transaction_id": tid,
            "transaction_date": tdate,
            "description": desc or "",
            "amount": Decimal(str(amt or 0)),
            "vendor_extracted": (vend or "").strip().upper(),
            "category": (cat or "").strip().upper(),
            "is_nsf": bool(nsf) if nsf is not None else False,
            "is_transfer": bool(is_txfer) if is_txfer is not None else False,
            "check_recipient": (recip or "").strip(),
        })
    return rows


def exclude_row(row):
    # Exclude transfers and payroll/employee-related terms
    if row["is_transfer"]:
        return True
    cat = row["category"]
    if any(term in cat for term in EXCLUDE_CATEGORY_TERMS):
        return True
    desc_up = row["description"].upper()
    if any(term in desc_up for term in EXCLUDE_DESC_TERMS):
        return True
    return False


def vendor_key_for(row):
    v = row["vendor_extracted"].strip().upper()
    if v:
        return v
    # Fallback: first significant token from description
    d = row["description"].upper()
    tokens = [t for t in d.replace("*", " ").replace("-", " ").split() if t.isalpha() and len(t) >= 3]
    return tokens[0] if tokens else "UNKNOWN"


def analyze_monthly(rows, existing_accounts):
    groups = defaultdict(list)
    for r in rows:
        if r["amount"] >= 0:
            continue  # only outflows (payments)
        if exclude_row(r):
            continue
        key = vendor_key_for(r)
        if key in EXCLUDE_VENDOR_KEYS:
            continue
        groups[key].append(r)

    results = []
    for vendor, items in groups.items():
        # Build month buckets
        month_counts = defaultdict(int)
        amounts = []
        nsf_present = False
        sample_desc = None
        for it in items:
            d = it["transaction_date"]
            yyyymm = f"{d.year:04d}-{d.month:02d}"
            month_counts[yyyymm] += 1
            amounts.append(abs(it["amount"]))
            nsf_present = nsf_present or it["is_nsf"]
            if not sample_desc:
                sample_desc = it["description"]
        distinct_months = len(month_counts)
        total_tx = len(items)
        median_amt = sorted(amounts)[len(amounts)//2] if amounts else Decimal("0")
        monthly_candidate = False
        # Heuristic: >= 6 distinct months across any span, and at least 10 total transactions
        if distinct_months >= 6 and total_tx >= 10:
            monthly_candidate = True
        already_account = vendor in existing_accounts
        results.append({
            "vendor": vendor,
            "distinct_months": distinct_months,
            "total_payments": total_tx,
            "median_amount": f"{median_amt:.2f}",
            "has_nsf": "Y" if nsf_present else "N",
            "sample_desc": sample_desc or "",
            "already_in_accounts": "Y" if already_account else "N",
            "recommend_add": "Y" if (monthly_candidate and not already_account) else "N",
        })
    # Sort by candidate flag then months desc
    results.sort(key=lambda r: (r["recommend_add"] == "Y", r["distinct_months"]), reverse=True)
    return results


def write_outputs(results):
    os.makedirs(OUT_DIR, exist_ok=True)
    fields = ["vendor","distinct_months","total_payments","median_amount","has_nsf","already_in_accounts","recommend_add","sample_desc"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow(r)
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        lines = ["Discovered Monthly/NSF Vendors (2012+)"]
        for r in results[:50]:
            lines.append(f"{r['vendor']} | months={r['distinct_months']} | tx={r['total_payments']} | med={r['median_amount']} | nsf={r['has_nsf']} | in_acc={r['already_in_accounts']} | add={r['recommend_add']}")
        f.write("\n".join(lines))
    return OUT_CSV, OUT_TXT


def main():
    conn, cur = conn_cur()
    existing = fetch_accounts(cur)
    rows = load_bank_tx(cur)
    conn.close()
    results = analyze_monthly(rows, existing)
    csv_path, txt_path = write_outputs(results)
    # Prepare vendor list for import
    vendors_to_add = [r["vendor"] for r in results if r["recommend_add"] == "Y" and r["vendor"] != "UNKNOWN"]
    print(csv_path)
    print(txt_path)
    print("VENDORS_TO_ADD:")
    for v in vendors_to_add[:50]:
        print(v)


if __name__ == "__main__":
    main()
