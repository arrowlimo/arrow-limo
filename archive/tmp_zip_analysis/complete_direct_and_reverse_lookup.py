import csv
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg2

GL_CSV = Path(r"L:\limo\Copy of General_ledger.csv")
OUT_DIR = Path(r"L:\limo\archive\tmp_zip_analysis")
DIRECT_OUT = OUT_DIR / "gl_direct_matches_completed.csv"
REVERSE_OUT = OUT_DIR / "bank_unmatched_reverse_lookup.csv"
SUMMARY_OUT = OUT_DIR / "direct_and_reverse_lookup_summary.txt"

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")

AMT_EPS = Decimal("0.02")
DATE_DELAY_MIN = 8
DATE_DELAY_MAX = 120
DIRECT_MAX_DAY_DIFF = 120
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
    s = (s or "").strip().replace(",", "").replace("$", "").replace("\xa0", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def norm_text(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_gl_rows():
    rows = []
    with open(GL_CSV, encoding="utf-8-sig", errors="replace") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) < 9:
                continue
            if row[2].strip() != "Bill Payment (Cheque)":
                continue
            account = row[6].strip()
            if not any(account.startswith(p) for p in BANK_PREFIXES):
                continue
            d = parse_date_dmy(row[1])
            amt = parse_amount(row[8]) if parse_amount(row[8]) is not None else parse_amount(row[7])
            if d is None or amt is None:
                continue
            chq = (row[3] or "").strip()
            vend = (row[4] or "").strip()
            rows.append(
                {
                    "gl_date": d,
                    "gl_chq": chq,
                    "gl_vendor": vend,
                    "gl_vendor_norm": norm_text(vend),
                    "gl_amount": amt,
                    "gl_account": account,
                }
            )
    return rows


def load_bank_rows(cur, gl_min_date, gl_max_date):
    d1 = gl_min_date - timedelta(days=180)
    d2 = gl_max_date + timedelta(days=180)
    cur.execute(
        """
        SELECT transaction_id, transaction_date, debit_amount, description, check_number,
               check_recipient, account_number, receipt_id, reconciled_receipt_id
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND debit_amount IS NOT NULL
          AND debit_amount > 0
                    AND (
                                check_number IS NOT NULL
                                OR COALESCE(description, '') ILIKE 'CHQ %%'
                            )
        ORDER BY transaction_date, transaction_id
        """,
        (d1, d2),
    )
    rows = []
    for t in cur.fetchall():
        desc = t[3] or ""
        recip = t[5] or ""
        rows.append(
            {
                "bank_id": t[0],
                "bank_date": t[1],
                "bank_debit": Decimal(str(t[2])) if t[2] is not None else None,
                "bank_desc": desc,
                "bank_desc_norm": norm_text(desc),
                "bank_check": (t[4] or "").strip(),
                "bank_recipient": recip,
                "bank_recipient_norm": norm_text(recip),
                "bank_account": (t[6] or "").strip(),
                "receipt_id": t[7],
                "reconciled_receipt_id": t[8],
            }
        )
    return rows


def is_numeric_chq(chq):
    return bool(re.fullmatch(r"\d+", (chq or "").strip()))


def vendor_overlap(gl_vendor_norm, bank_desc_norm, bank_recipient_norm):
    if not gl_vendor_norm:
        return False
    return gl_vendor_norm in bank_desc_norm or gl_vendor_norm in bank_recipient_norm


def choose_best_candidate(gl, candidates):
    # prioritize: check number exact, vendor overlap, nearest date
    scored = []
    for b in candidates:
        check_exact = int(is_numeric_chq(gl["gl_chq"]) and gl["gl_chq"] == b["bank_check"])
        vend = int(vendor_overlap(gl["gl_vendor_norm"], b["bank_desc_norm"], b["bank_recipient_norm"]))
        day_diff = abs((b["bank_date"] - gl["gl_date"]).days)
        scored.append(((check_exact, vend, -day_diff), b))
    scored.sort(reverse=True, key=lambda x: x[0])
    best = scored[0][1] if scored else None
    return best


def complete_direct_matches(gl_rows, bank_rows):
    used_bank_ids = set()
    direct = []

    # Process in date order for stable matching
    for gl in sorted(gl_rows, key=lambda x: (x["gl_date"], x["gl_amount"])):
        candidates = []
        for b in bank_rows:
            if b["bank_id"] in used_bank_ids:
                continue
            if b["bank_debit"] is None:
                continue
            if abs(b["bank_debit"] - gl["gl_amount"]) > AMT_EPS:
                continue
            day_diff = abs((b["bank_date"] - gl["gl_date"]).days)
            if day_diff > DIRECT_MAX_DAY_DIFF:
                continue
            check_exact = is_numeric_chq(gl["gl_chq"]) and gl["gl_chq"] == b["bank_check"]
            vend = vendor_overlap(gl["gl_vendor_norm"], b["bank_desc_norm"], b["bank_recipient_norm"])
            if not (check_exact or vend):
                continue
            candidates.append(b)

        if not candidates:
            continue

        best = choose_best_candidate(gl, candidates)
        if best is None:
            continue

        used_bank_ids.add(best["bank_id"])
        day_diff = abs((best["bank_date"] - gl["gl_date"]).days)
        reason = []
        if is_numeric_chq(gl["gl_chq"]) and gl["gl_chq"] == best["bank_check"]:
            reason.append("check_exact")
        if vendor_overlap(gl["gl_vendor_norm"], best["bank_desc_norm"], best["bank_recipient_norm"]):
            reason.append("vendor_overlap")
        if day_diff > 7:
            reason.append("date_delay")

        direct.append(
            {
                **gl,
                **best,
                "date_diff_days": day_diff,
                "match_reason": "+".join(reason) if reason else "amount_only",
            }
        )

    return direct, used_bank_ids


def reverse_lookup_unmatched_bank(gl_rows, bank_rows, used_bank_ids):
    unmatched = [b for b in bank_rows if b["bank_id"] not in used_bank_ids]
    out = []

    for b in unmatched:
        # Closest GL by amount first, then date
        candidates = []
        for gl in gl_rows:
            if gl["gl_amount"] is None:
                continue
            amt_diff = abs(gl["gl_amount"] - b["bank_debit"])
            if amt_diff > AMT_EPS:
                continue
            day_diff = abs((b["bank_date"] - gl["gl_date"]).days)
            vend = vendor_overlap(gl["gl_vendor_norm"], b["bank_desc_norm"], b["bank_recipient_norm"])
            check_ov = int(is_numeric_chq(gl["gl_chq"]) and gl["gl_chq"] == b["bank_check"])
            candidates.append((day_diff, int(vend), check_ov, gl))

        if candidates:
            # Prefer check overlap, then vendor overlap, then nearest date
            candidates.sort(key=lambda x: (-x[2], -x[1], x[0]))
            day_diff, vend_flag, check_flag, gl = candidates[0]
            likely_date_delay = (day_diff >= DATE_DELAY_MIN and day_diff <= DATE_DELAY_MAX and (vend_flag == 1 or check_flag == 1))
            out.append(
                {
                    **b,
                    "closest_gl_date": gl["gl_date"],
                    "closest_gl_chq": gl["gl_chq"],
                    "closest_gl_vendor": gl["gl_vendor"],
                    "closest_gl_amount": gl["gl_amount"],
                    "closest_gl_account": gl["gl_account"],
                    "date_diff_days": day_diff,
                    "vendor_overlap": vend_flag,
                    "check_overlap": check_flag,
                    "likely_date_delay": int(likely_date_delay),
                }
            )
        else:
            out.append(
                {
                    **b,
                    "closest_gl_date": None,
                    "closest_gl_chq": "",
                    "closest_gl_vendor": "",
                    "closest_gl_amount": None,
                    "closest_gl_account": "",
                    "date_diff_days": None,
                    "vendor_overlap": 0,
                    "check_overlap": 0,
                    "likely_date_delay": 0,
                }
            )

    return out


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    gl_rows = load_gl_rows()
    gl_min = min(r["gl_date"] for r in gl_rows)
    gl_max = max(r["gl_date"] for r in gl_rows)

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    bank_rows = load_bank_rows(cur, gl_min, gl_max)
    cur.close()
    conn.close()

    direct, used_ids = complete_direct_matches(gl_rows, bank_rows)
    reverse = reverse_lookup_unmatched_bank(gl_rows, bank_rows, used_ids)

    direct_fields = [
        "gl_date",
        "gl_chq",
        "gl_vendor",
        "gl_amount",
        "gl_account",
        "bank_id",
        "bank_date",
        "bank_debit",
        "bank_desc",
        "bank_check",
        "bank_recipient",
        "bank_account",
        "receipt_id",
        "reconciled_receipt_id",
        "date_diff_days",
        "match_reason",
    ]

    reverse_fields = [
        "bank_id",
        "bank_date",
        "bank_debit",
        "bank_desc",
        "bank_check",
        "bank_recipient",
        "bank_account",
        "receipt_id",
        "reconciled_receipt_id",
        "closest_gl_date",
        "closest_gl_chq",
        "closest_gl_vendor",
        "closest_gl_amount",
        "closest_gl_account",
        "date_diff_days",
        "vendor_overlap",
        "check_overlap",
        "likely_date_delay",
    ]

    write_csv(DIRECT_OUT, direct, direct_fields)
    write_csv(REVERSE_OUT, reverse, reverse_fields)

    delay_cnt = sum(1 for r in reverse if r["likely_date_delay"] == 1)
    with open(SUMMARY_OUT, "w", encoding="utf-8") as f:
        f.write("Direct + Reverse Lookup Summary\n")
        f.write("=" * 80 + "\n")
        f.write(f"GL rows considered: {len(gl_rows)}\n")
        f.write(f"Bank rows considered: {len(bank_rows)}\n")
        f.write(f"Direct matches completed: {len(direct)}\n")
        f.write(f"Unmatched bank rows after direct pass: {len(reverse)}\n")
        f.write(f"Likely date-delay rows (reverse): {delay_cnt}\n")

    print(f"GL rows considered: {len(gl_rows)}")
    print(f"Bank rows considered: {len(bank_rows)}")
    print(f"Direct matches completed: {len(direct)}")
    print(f"Unmatched bank rows after direct pass: {len(reverse)}")
    print(f"Likely date-delay rows (reverse): {delay_cnt}")
    print(f"Wrote: {DIRECT_OUT}")
    print(f"Wrote: {REVERSE_OUT}")
    print(f"Wrote: {SUMMARY_OUT}")


if __name__ == "__main__":
    main()
