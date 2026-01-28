#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Parse a loosely formatted QuickBooks-style register text dump and extract transactions.

Goals for this parser:
- Be tolerant of spacing and special characters (e.g., Ö checkmark) and mixed columns
- Identify transaction date, type, name, and amounts (debit/credit) heuristically
- Track current account section (e.g., CIBC Bank, Scotia Bank Main)
- Emit CSV of parsed rows and a CRA-focused CSV summary for a target year

Assumptions/heuristics:
- Lines that contain a dd/mm/yyyy date are considered transaction rows
- Amounts appear as numbers with thousands separators and 2 decimals (e.g., 1,234.56)
- The last numeric on a transaction line is typically the balance; the second-to-last is the txn amount
- CRA-related lines include any of these tokens (case-insensitive):
  'Canada Revenue Agency', 'Revenue Canada', 'Receiver General', 'Minister of Finance', 'CRA'

Outputs:
- exports/banking/<year>_qb_register_parsed.csv
- exports/banking/<year>_cra_candidates.csv

This is a best-effort extractor intended for preliminary reconciliation; manual review recommended.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple


DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
AMOUNT_RE = re.compile(r"\(?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?")

CRA_KEYWORDS = [
    "canada revenue agency",
    "revenue canada",
    "receiver general",
    "minister of finance",
    "cra",
]


@dataclass
class Txn:
    account: str
    date: Optional[str]
    type: Optional[str]
    num: Optional[str]
    name: Optional[str]
    memo: Optional[str]
    debit: Optional[str]
    credit: Optional[str]
    balance: Optional[str]
    raw: str


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Parse QuickBooks-style register text")
    ap.add_argument("--input", required=True, help="Path to input text file")
    ap.add_argument("--year", type=int, default=2012, help="Year filter (default: 2012)")
    ap.add_argument("--outdir", default="exports/banking", help="Output directory")
    return ap.parse_args()


def normalize_amount(s: str) -> Decimal:
    s = s.strip()
    neg = s.startswith("(") and s.endswith(")")
    s2 = s.replace("(", "").replace(")", "").replace(",", "")
    d = Decimal(s2)
    return -d if neg else d


def find_amounts(line: str) -> List[str]:
    return AMOUNT_RE.findall(line)


def contains_cra_keyword(s: str) -> bool:
    s_low = s.lower()
    return any(k in s_low for k in CRA_KEYWORDS)


def parse_date_from_line(line: str) -> Optional[datetime]:
    m = DATE_RE.search(line)
    if not m:
        return None
    d, mth, y = m.groups()
    try:
        # Day-first format in the provided data (e.g., 14/02/2012)
        return datetime(int(y), int(mth), int(d))
    except ValueError:
        return None


def split_type_num_name(line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Heuristic split: try to capture Type, Num, Name in order.
    We'll look for a Type token near the beginning: 'Cheque', 'General Journal', etc.
    Then a Num token could be alphanumeric up to a tab/large space, and then Name as a chunk.
    Since the text is irregular, this is best-effort.
    """
    # Common types we can look for explicitly
    TYPES = [
        "Cheque",
        "General Journal",
        "Deposit",
        "Service Charge",
        "WD",
        "TSF",
        "ETSFR",
        "ETSF",
        "Auto",
        "Online",
        "DD",
        "SS",
        "DDF",
        "aUTO",
        "wd",
        "dd",
    ]
    type_found = None
    for t in sorted(TYPES, key=len, reverse=True):
        idx = line.find(t)
        if idx != -1 and idx < 20:  # near the start of the row
            type_found = t
            break
    if not type_found:
        return None, None, None

    # After type, try to find a token that looks like a reference/Num up to two tabs or double spaces
    rest = line[line.find(type_found) + len(type_found):]
    # Simplify whitespace sequences
    rest_norm = re.sub(r"\s{2,}", "\t", rest)
    parts = [p for p in rest_norm.split("\t") if p.strip()]
    num = None
    name = None
    if parts:
        # First part might be a date; if so, Num could be next
        if DATE_RE.search(parts[0] or ""):
            if len(parts) > 1:
                # This could be Num or Adj
                num = parts[1].strip() if parts[1].strip() else None
            if len(parts) > 2:
                name = parts[2].strip() if parts[2].strip() else None
        else:
            # If not a date, maybe the first is Num and second is Name
            num = parts[0].strip() if parts[0].strip() else None
            if len(parts) > 1:
                name = parts[1].strip() if parts[1].strip() else None

    return type_found, num, name


def extract_name_memo(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Try to extract a Name and a Memo-ish chunk near the middle.
    This is fuzzy; we'll prioritize keeping the name over a memo.
    """
    # After date, the next tokens are typically num/adj -> name -> memo
    # We'll normalize whitespace and pick the next chunks after the date token.
    m = DATE_RE.search(line)
    if not m:
        return None, None
    tail = line[m.end():]
    tail_norm = re.sub(r"\s{2,}", "\t", tail)
    parts = [p for p in tail_norm.split("\t") if p.strip()]
    name = parts[1].strip() if len(parts) > 1 else None
    memo = parts[2].strip() if len(parts) > 2 else None
    return name, memo


def parse_text(path: str, year: int) -> List[Txn]:
    txns: List[Txn] = []
    current_account = None

    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line.strip():
                continue

            # Detect account section headers (simple heuristic)
            if line.strip().endswith("Bank") or line.strip().lower().startswith("scotia bank"):
                current_account = line.strip().split("\t")[0].strip()
                continue
            if line.strip().lower().startswith("uncategorized expenses"):
                current_account = "Uncategorized Expenses"
                continue

            # Attempt to find a transaction date
            dt = parse_date_from_line(line)
            if not dt:
                continue

            if dt.year != year:
                continue

            # Extract amounts: usually the last is balance, second-to-last is txn amount
            amounts = find_amounts(line)
            debit: Optional[str] = None
            credit: Optional[str] = None
            balance: Optional[str] = None
            if amounts:
                try:
                    balance = amounts[-1]
                except Exception:
                    balance = None
                if len(amounts) >= 2:
                    txn_amt = amounts[-2]
                    # Heuristic: consider positive value as debit by default; if the line contains words often associated
                    # with incoming money (Deposit), treat as credit.
                    try:
                        val = normalize_amount(txn_amt)
                        if "Deposit" in line or "Sales" in line:
                            credit = txn_amt
                        else:
                            # Most entries in provided sample are payments (debits)
                            if val >= 0:
                                debit = txn_amt
                            else:
                                credit = txn_amt
                    except InvalidOperation:
                        pass

            ttype, num, _ = split_type_num_name(line)
            name, memo = extract_name_memo(line)

            txns.append(
                Txn(
                    account=current_account or "",
                    date=dt.strftime("%Y-%m-%d"),
                    type=ttype,
                    num=num,
                    name=name,
                    memo=memo,
                    debit=debit,
                    credit=credit,
                    balance=balance,
                    raw=line,
                )
            )

    return txns


def ensure_outdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_csv(path: str, rows: List[dict]) -> None:
    if not rows:
        # Create file with headers only
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["account", "date", "type", "num", "name", "memo", "debit", "credit", "balance"])
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["account", "date", "type", "num", "name", "memo", "debit", "credit", "balance"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    ensure_outdir(args.outdir)

    txns = parse_text(args.input, args.year)

    # Write all parsed rows
    all_rows = [
        {
            "account": t.account,
            "date": t.date,
            "type": t.type,
            "num": t.num,
            "name": t.name,
            "memo": t.memo,
            "debit": t.debit,
            "credit": t.credit,
            "balance": t.balance,
        }
        for t in txns
    ]
    out_all = os.path.join(args.outdir, f"{args.year}_qb_register_parsed.csv")
    write_csv(out_all, all_rows)

    # CRA-focused extraction
    cra_rows: List[dict] = []
    cra_total = Decimal("0")
    for t in txns:
        text = " ".join(filter(None, [t.account, t.type, t.num, t.name, t.memo, t.raw]))
        if contains_cra_keyword(text):
            amt_str = t.debit or t.credit
            amt_val: Optional[Decimal] = None
            if amt_str:
                try:
                    amt_val = normalize_amount(amt_str)
                except Exception:
                    amt_val = None
            if amt_val is not None:
                cra_total += amt_val
            cra_rows.append(
                {
                    "date": t.date,
                    "account": t.account,
                    "type": t.type,
                    "num": t.num,
                    "name": t.name,
                    "memo": t.memo,
                    "amount": amt_str,
                    "raw": t.raw,
                }
            )
    out_cra = os.path.join(args.outdir, f"{args.year}_cra_candidates.csv")
    # Write CRA CSV
    with open(out_cra, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "account", "type", "num", "name", "memo", "amount", "raw"],
        )
        writer.writeheader()
        writer.writerows(cra_rows)

    print(f"Parsed {len(txns)} transactions for {args.year}.")
    print(f"Saved CSV: {out_all}")
    print(f"Saved CRA candidates: {out_cra}")
    print(f"CRA candidate total (sum of parsed amounts): {cra_total}")


if __name__ == "__main__":
    main()
