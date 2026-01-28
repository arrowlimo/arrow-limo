#!/usr/bin/env python3
"""
Parse Scotiabank QuickBooks Reconciliation PDFs (2012)
- Scans a folder for Scotiabank reconciliation PDFs (monthly or annual)
- Extracts 'Reconciliation Summary' blocks and parses key amounts
- Emits monthly JSON with deposits/payments (cleared, new, total) and balances

Input folder (drop your scans here): L:\\limo\\staging\\scotia_2012_pdfs
Outputs:
- L:\\limo\\staging\\2012_comparison\\scotia_qb_monthly_2012.json (machine-readable)
- L:\\limo\\staging\\2012_comparison\\scotia_qb_monthly_2012.txt (human-readable summary)

Safe: Read-only.
"""
from __future__ import annotations
from pathlib import Path
import re
import json
from decimal import Decimal, InvalidOperation
import pdfplumber
from datetime import datetime

INPUT_DIR = Path(r"L:\limo\staging\scotia_2012_pdfs")
OUTPUT_JSON = Path(r"L:\limo\staging\2012_comparison\scotia_qb_monthly_2012.json")
OUTPUT_TXT = Path(r"L:\limo\staging\2012_comparison\scotia_qb_monthly_2012.txt")

amount_re = re.compile(r"\(?-?\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2}))\)?")

def to_amount(s: str) -> Decimal | None:
    if not s:
        return None
    s = s.strip()
    neg = s.startswith('(') and s.endswith(')')
    m = amount_re.search(s)
    if not m:
        return None
    try:
        val = Decimal(m.group(1).replace(',', ''))
    except InvalidOperation:
        return None
    if neg or '-' in s:
        val = -val
    return val

MONTHS = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

def detect_period_end(fragment: str) -> tuple[str | None, str | None]:
    """Return YYYY-MM and raw date text from a reconciliation summary fragment."""
    # Match explicit 'Period Ending MM/DD/YYYY' or 'MMM DD, YY'
    m1 = re.search(r"Period\s+Ending\s+([0-9]{1,2}/[0-9]{1,2}/(?:20)?\d{2})", fragment, re.IGNORECASE)
    if m1:
        raw = m1.group(1)
        # Normalize to YYYY-MM
        parts = re.split(r"[/-]", raw)
        if len(parts) == 3:
            mm = int(parts[0])
            dd = int(parts[1])
            yy = int(parts[2])
            if yy < 100:
                yy += 2000
            return f"{yy:04d}-{mm:02d}", raw
    # Try textual month like 'Dec 31, 12'
    m2 = re.search(r"([A-Za-z]{3,9})\s+([0-9]{1,2}),\s*([0-9]{2,4})", fragment)
    if m2:
        mon = MONTHS.get(m2.group(1).lower())
        if mon:
            dd = int(m2.group(2))
            yy = int(m2.group(3))
            if yy < 100:
                yy += 2000
            return f"{yy:04d}-{mon:02d}", f"{m2.group(1)} {dd}, {yy}"
    return None, None


def parse_summary_block(text: str) -> dict | None:
    """Parse a single 'Reconciliation Summary' block."""
    # Find period end
    month_key, period_raw = detect_period_end(text)
    if not month_key:
        return None

    def find_amount(label: str) -> Decimal | None:
        # Look for 'label ... amount' on same or next lines
        pat = re.compile(re.escape(label) + r"[^\n$\d-]*([-()$ ,\d\.]+)", re.IGNORECASE)
        m = pat.search(text)
        if m:
            amt = to_amount(m.group(1))
            if amt is not None:
                return amt
        # Fallback: search following lines
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if re.search(re.escape(label), ln, re.IGNORECASE):
                for j in range(i, min(i+3, len(lines))):
                    amt = to_amount(lines[j])
                    if amt is not None:
                        return amt
        return None

    # Core fields
    beginning = find_amount('Beginning Balance')
    cleared_pay = find_amount('Cheques and Payments')
    if cleared_pay is not None:
        cleared_pay = abs(cleared_pay)
    cleared_dep = find_amount('Deposits and Credits')
    if cleared_dep is not None:
        cleared_dep = abs(cleared_dep)
    cleared_total = find_amount('Total Cleared Transactions')
    cleared_balance = find_amount('Cleared Balance')

    new_pay = None
    new_dep = None
    # New transactions (optional section)
    # Try more specific breakdowns if present
    mnp = re.search(r"New\s+Transactions.*?Cheques and Payments[^\n$\d-]*([-()$ ,\d\.]+)", text, re.IGNORECASE | re.DOTALL)
    if mnp:
        v = to_amount(mnp.group(1))
        if v is not None:
            new_pay = abs(v)
    mnd = re.search(r"New\s+Transactions.*?Deposits and Credits[^\n$\d-]*([-()$ ,\d\.]+)", text, re.IGNORECASE | re.DOTALL)
    if mnd:
        v = to_amount(mnd.group(1))
        if v is not None:
            new_dep = abs(v)

    # Reconciliation Difference (if present)
    # Some layouts use 'Reconciliation Difference', others just 'Difference'
    recon_diff = find_amount('Reconciliation Difference')
    if recon_diff is None:
        recon_diff = find_amount('Difference')

    ending = find_amount('Ending Balance')

    return {
        'month_key': month_key,
        'period_end': period_raw,
        'beginning_balance': beginning,
        'cleared_payments': cleared_pay,
        'cleared_deposits': cleared_dep,
        'cleared_total': cleared_total,
        'cleared_balance': cleared_balance,
        'new_payments': new_pay or Decimal('0'),
        'new_deposits': new_dep or Decimal('0'),
        'reconciliation_difference': recon_diff if recon_diff is not None else Decimal('0'),
        'ending_balance': ending,
    }


def extract_reconciliation_summaries(text: str) -> list[dict]:
    # Split around 'Reconciliation Summary' markers
    blocks = re.split(r"Reconciliation\s+Summary", text, flags=re.IGNORECASE)
    out = []
    for b in blocks[1:]:  # skip leading preface
        # Take a wider window to capture reconciliation difference and balances
        header = "\n".join(b.splitlines()[:250])
        parsed = parse_summary_block(header)
        if parsed:
            out.append(parsed)
    return out


def parse_pdf(path: Path) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join([p.extract_text() or '' for p in pdf.pages])
    return extract_reconciliation_summaries(text)


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, dict] = {}

    # Also include the known annual QB reconciliation if present in main pdf folder
    extra_files = [
        Path(r"L:\limo\pdf\2012 quickbooks scotiabank_ocred.pdf"),
    ]

    files = list(INPUT_DIR.glob('*.pdf')) + [p for p in extra_files if p.exists()]
    for path in files:
        try:
            results = parse_pdf(path)
        except Exception as e:
            print(f"WARN: Failed to parse {path}: {e}")
            continue
        for r in results:
            mk = r['month_key']
            # Keep first occurrence per month_key
            if mk and mk not in summaries:
                summaries[mk] = r

    # Build ordered list
    months = sorted(summaries.keys())
    data = [summaries[m] for m in months]

    # Compute per-month totals
    for d in data:
        cdep = d.get('cleared_deposits') or Decimal('0')
        ndep = d.get('new_deposits') or Decimal('0')
        cpay = d.get('cleared_payments') or Decimal('0')
        npay = d.get('new_payments') or Decimal('0')
        d['total_deposits'] = (cdep + ndep)
        d['total_payments'] = (cpay + npay)

    # Write JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as jf:
        json.dump([
            {
                **{k: (float(v) if isinstance(v, Decimal) else v) for k, v in d.items()},
            } for d in data
        ], jf, indent=2)

    # Write text summary
    lines = []
    lines.append('SCOTIABANK QUICKBOOKS RECONCILIATIONS (2012)')
    lines.append('=' * 80)
    lines.append('')
    total_dep = Decimal('0')
    total_pay = Decimal('0')
    for d in data:
        lines.append(f"{d['month_key']} (Period End {d.get('period_end')})")
        lines.append(f"  Beginning:          ${ (d.get('beginning_balance') or 0):,.2f}")
        lines.append(f"  Cleared Deposits:   ${ (d.get('cleared_deposits') or 0):,.2f}")
        lines.append(f"  Cleared Payments:   ${ (d.get('cleared_payments') or 0):,.2f}")
        lines.append(f"  New Deposits:       ${ (d.get('new_deposits') or 0):,.2f}")
        lines.append(f"  New Payments:       ${ (d.get('new_payments') or 0):,.2f}")
        lines.append(f"  Total Deposits:     ${ (d.get('total_deposits') or 0):,.2f}")
        lines.append(f"  Total Payments:     ${ (d.get('total_payments') or 0):,.2f}")
        lines.append(f"  Reconc. Difference: ${ (d.get('reconciliation_difference') or 0):,.2f}")
        lines.append(f"  Ending:             ${ (d.get('ending_balance') or 0):,.2f}")
        lines.append('')
        total_dep += d.get('total_deposits') or Decimal('0')
        total_pay += d.get('total_payments') or Decimal('0')
    lines.append('-' * 80)
    lines.append(f"AGGREGATED TOTALS (QB Scotia): Deposits ${total_dep:,.2f} | Payments ${total_pay:,.2f}")

    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Saved Scotia QB monthly JSON: {OUTPUT_JSON}")
    print(f"Saved Scotia QB monthly report: {OUTPUT_TXT}")


if __name__ == '__main__':
    main()
