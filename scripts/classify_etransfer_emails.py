#!/usr/bin/env python3
"""
Classify l:/limo/reports/etransfer_emails.csv rows into DEPOSIT vs CLAIM and write
two CSVs for downstream review:
- l:/limo/reports/etransfer_emails_deposit.csv
- l:/limo/reports/etransfer_emails_claim.csv
Adds a 'kind' column to indicate classification.
"""
import os
import csv

SRC = r"l:/limo/reports/etransfer_emails.csv"
OUT_DEP = r"l:/limo/reports/etransfer_emails_deposit.csv"
OUT_CLAIM = r"l:/limo/reports/etransfer_emails_claim.csv"


def is_claim(subject: str, excerpt: str) -> bool:
    text = f"{subject}\n{excerpt}".lower()
    claim_kw = ['sent you', 'claim your deposit', 'your funds await', 'select your financial institution']
    # Exclude explicit deposit phrasing
    deposit_kw = ['was deposited', 'has been deposited', 'deposit complete', 'deposited to', 'has been automatically deposited']
    if any(d in text for d in deposit_kw):
        return False
    return any(k in text for k in claim_kw)


def main():
    if not os.path.exists(SRC):
        print('Source not found:', SRC)
        return
    with open(SRC, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    dep_rows, claim_rows = [], []
    for r in rows:
        subj = r.get('subject') or ''
        excerpt = r.get('message_excerpt') or ''
        if is_claim(subj, excerpt):
            r['kind'] = 'CLAIM'
            claim_rows.append(r)
        else:
            r['kind'] = 'DEPOSIT'
            dep_rows.append(r)

    os.makedirs('l:/limo/reports', exist_ok=True)
    def write_csv(path, rows):
        with open(path, 'w', newline='', encoding='utf-8') as fp:
            if rows:
                w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
                w.writeheader(); w.writerows(rows)
            else:
                fp.write('')
    write_csv(OUT_DEP, dep_rows)
    write_csv(OUT_CLAIM, claim_rows)
    print(f"Classified e-transfer emails: deposit={len(dep_rows)} claim={len(claim_rows)}")
    print(' ', OUT_DEP)
    print(' ', OUT_CLAIM)


if __name__ == '__main__':
    main()
