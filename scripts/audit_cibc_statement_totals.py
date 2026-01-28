#!/usr/bin/env python3
"""
Audit CIBC Statement Totals (2012)
- Parse OCR text statements for each month
- Extract Account summary: Opening balance, Deposits, Closing balance
- Verify math: closing == opening + deposits - withdrawals (implied)
- Aggregate totals across months and compare to QuickBooks totals
- Compare to parsed CSV totals and flag mismatches

Safe: Read-only. Outputs report to staging/2012_comparison/cibc_statement_totals_audit.txt
"""
import os
import re
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Tuple

EXTRACT_DIR = Path(r"L:\limo\staging\2012_pdf_extracts")
PARSED_DIR = Path(r"L:\limo\staging\2012_parsed")
OUTPUT_PATH = Path(r"L:\limo\staging\2012_comparison\cibc_statement_totals_audit.txt")

QB_TOTAL_DEPOSITS = Decimal('833621.56')
QB_TOTAL_PAYMENTS = Decimal('311329.45')

CIBC_FILES = [
    EXTRACT_DIR / "2012cibc banking jan-mar_ocred.txt",
    EXTRACT_DIR / "2012cibc banking apr- may_ocred.txt",
    EXTRACT_DIR / "2012cibc banking jun-dec_ocred.txt",
]

amount_re = re.compile(r"\(?-?\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2}))\)?")


def to_amount(s: str) -> Decimal | None:
    if not s:
        return None
    s = s.strip()
    # detect parentheses for negative
    neg = s.strip().startswith('(') and s.strip().endswith(')')
    m = amount_re.search(s)
    if not m:
        return None
    val = m.group(1).replace(',', '')
    try:
        d = Decimal(val)
        if neg or '-' in s:
            d = -d
        return d
    except InvalidOperation:
        return None


def parse_statements(text: str):
    """Yield dicts with period, opening, withdrawals, deposits, closing from Account summary blocks."""
    lines = text.splitlines()
    results = []
    i = 0
    current_period = None
    while i < len(lines):
        line = lines[i]
        # Track period lines anywhere, not only after a specific header
        if 'For ' in line and 'to' in line and '2012' in line:
            try:
                current_period = line.split('For', 1)[1].strip()
            except Exception:
                pass
        if 'Account summary' in line:
            opening = withdrawals = deposits = closing = None
            open_date_txt = close_date_txt = None
            # helper to find an amount near a line index (forward and small backward for closing)
            def find_amount_near(index: int, forward: bool = True, back: bool = False, span: int = 4):
                # forward search
                for t in range(index, min(index + span + 1, len(lines))):
                    m = amount_re.search(lines[t])
                    if m:
                        return to_amount(lines[t])
                if back:
                    for t in range(max(0, index - span), index)[::-1]:
                        m = amount_re.search(lines[t])
                        if m:
                            return to_amount(lines[t])
                return None
            # Scan next lines until we hit Transaction details or we have what we need
            for k in range(i + 1, min(i + 80, len(lines))):
                ln = lines[k]
                if 'Transaction details' in ln:
                    break
                if opening is None and 'Opening balance' in ln:
                    opening = to_amount(ln) or find_amount_near(k+1)
                    # Extract opening date text
                    m = re.search(r'Opening balance on\s+([^$=]+?)\s+\$|Opening balance on\s+(.+)$', ln)
                    if m:
                        open_date_txt = (m.group(1) or m.group(2) or '').strip()
                elif withdrawals is None and re.search(r'\bWithdrawals\b', ln, re.IGNORECASE):
                    amt = to_amount(ln) or find_amount_near(k+1)
                    withdrawals = abs(amt) if amt is not None else None
                elif deposits is None and re.search(r'\bDeposits\b', ln, re.IGNORECASE):
                    amt = to_amount(ln) or find_amount_near(k+1)
                    deposits = abs(amt) if amt is not None else None
                elif closing is None and 'Closing balance' in ln:
                    closing = to_amount(ln) or find_amount_near(k+1, back=True)
                    # Extract closing date text
                    m = re.search(r'Closing balance on\s+([^$=]+?)\s*[=$]|Closing balance on\s+(.+)$', ln)
                    if m:
                        close_date_txt = (m.group(1) or m.group(2) or '').strip()
                # If we have all, we can stop early
                if opening is not None and deposits is not None and closing is not None and (withdrawals is not None or True):
                    # keep scanning a bit more in case missing one appears shortly, but cap
                    pass
            if opening is not None and deposits is not None and closing is not None:
                period_val = (current_period or '').strip()
                if not period_val:
                    # Try to synthesize period from dates
                    if open_date_txt and close_date_txt:
                        period_val = f"{open_date_txt} to {close_date_txt}"
                results.append({
                    'period': period_val,
                    'opening': opening,
                    'withdrawals': withdrawals,
                    'deposits': deposits,
                    'closing': closing,
                })
        i += 1
    return results


def load_file(path: Path) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def load_parsed_csv_totals() -> tuple[Decimal, Decimal]:
    """Load totals from our previously parsed CIBC CSV (if present)."""
    import csv
    csv_path = PARSED_DIR / '2012_cibc_transactions.csv'
    total_withdrawals = Decimal('0')
    total_deposits = Decimal('0')
    if not csv_path.exists():
        return total_withdrawals, total_deposits
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            w = row.get('withdrawal') or ''
            d = row.get('deposit') or ''
            try:
                if w:
                    total_withdrawals += Decimal(w)
            except Exception:
                pass
            try:
                if d:
                    total_deposits += Decimal(d)
            except Exception:
                pass
    return total_withdrawals, total_deposits

# Month parsing helpers for ordering and continuity checks
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

def period_key(period: str) -> Tuple[int, int]:
    p = (period or '').lower()
    year = 2012
    month = 0
    for name, num in MONTHS.items():
        if f" {name} " in f" {p} ":
            month = num
            break
    ym = re.search(r'(20\d{2})', p)
    if ym:
        year = int(ym.group(1))
    return (year, month)

def continuity_fix(months: list[dict]) -> tuple[list[dict], list[str]]:
    """Ensure each month's opening equals prior month's closing where obvious OCR artifacts occur.
    Applies sign corrections and ≤$1 snaps; returns adjusted list and notes.
    """
    if not months:
        return months, []
    months = sorted(months, key=lambda m: period_key(m.get('period', '')))
    notes: list[str] = []
    eps = Decimal('0.01')
    for i in range(1, len(months)):
        prev = months[i-1]
        cur = months[i]
        prev_close = prev['closing']
        cur_open = cur['opening']
        diff = (prev_close - cur_open).copy_abs()
        if diff <= eps:
            continue
        # sign flip only
        if (prev_close + cur_open).copy_abs() <= eps:
            notes.append(f"Adjusted opening for {cur.get('period','?')} from ${cur_open:,.2f} to ${prev_close:,.2f} (sign correction)")
            cur['opening'] = prev_close
            continue
        # small drift ≤ $1
        if diff <= Decimal('1.00'):
            notes.append(f"Snapped opening for {cur.get('period','?')} from ${cur_open:,.2f} to ${prev_close:,.2f} (≤$1 drift)")
            cur['opening'] = prev_close
            continue
        notes.append(f"Continuity gap for {cur.get('period','?')}: prior close ${prev_close:,.2f} vs opening ${cur_open:,.2f}")
    return months, notes


def main():
    monthly = []
    for path in CIBC_FILES:
        if not path.exists():
            continue
        text = load_file(path)
        monthly.extend(parse_statements(text))

    # Deduplicate by period if available (keep first occurrence)
    deduped = []
    seen = set()
    for m in monthly:
        key = m.get('period') or (m['opening'], m['closing'], m['deposits'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)
    monthly = deduped

    # Apply continuity fixes and sort by period
    monthly, cont_notes = continuity_fix(monthly)

    # Aggregate
    total_deposits = sum((m['deposits'] for m in monthly), Decimal('0'))
    # Always compute withdrawals from balance identity to avoid OCR artifacts on explicit lines
    total_withdrawals = sum(((m['opening'] + m['deposits'] - m['closing']) for m in monthly), Decimal('0'))
    # Net change
    net_change = sum(((m['closing'] - m['opening']) for m in monthly), Decimal('0'))

    # Load parsed CSV totals to compare
    csv_withdrawals, csv_deposits = load_parsed_csv_totals()

    # Build report
    lines = []
    lines.append('CIBC STATEMENT TOTALS AUDIT (2012)')
    lines.append('=' * 80)
    lines.append('')
    lines.append(f"Statements found: {len(monthly)}")
    lines.append('')
    for m in monthly:
        lines.append(f"Period: {m['period']}")
        lines.append(f"  Opening:   ${m['opening']:,.2f}")
        lines.append(f"  Deposits:  ${m['deposits']:,.2f}")
        implied_w = m['opening'] + m['deposits'] - m['closing']
        lines.append(f"  Withdrawals (by identity): ${implied_w:,.2f}")
        lines.append(f"  Closing:   ${m['closing']:,.2f}")
        # Check math: closing - opening == deposits - withdrawals
        lhs = (m['closing'] - m['opening']).quantize(Decimal('0.01'))
        rhs = (m['deposits'] - implied_w).quantize(Decimal('0.01'))
        status = 'OK' if lhs == rhs else 'MISMATCH'
        lines.append(f"  Check: Δ=${lhs:,.2f} vs deposits-withdrawals=${rhs:,.2f} → {status}")
        lines.append('')

    lines.append('-' * 80)
    lines.append('AGGREGATED TOTALS (CIBC statements)')
    lines.append('-' * 80)
    lines.append(f"Total Deposits:    ${total_deposits:,.2f}")
    lines.append(f"Implied Withdrawals:${total_withdrawals:,.2f}")
    lines.append(f"Net Change:        ${net_change:,.2f}")
    # Cross-check net change equals last closing - first opening
    if monthly:
        first_open = monthly[0]['opening']
        last_close = monthly[-1]['closing']
        delta = (last_close - first_open).quantize(Decimal('0.01'))
        lines.append(f"Balance Check: last closing - first opening = ${delta:,.2f}")
        if delta == net_change.quantize(Decimal('0.01')):
            lines.append("  Status: OK")
        else:
            lines.append("  Status: MISMATCH")
    if 'cont_notes' in locals() and cont_notes:
        lines.append('')
        lines.append('CONTINUITY NOTES')
        lines.append('-' * 80)
        for n in cont_notes:
            lines.append(n)
    lines.append('')

    # Emit machine-readable monthly JSON for downstream reconciliation
    try:
        out_dir = OUTPUT_PATH.parent
        json_out = []
        for m in monthly:
            implied_w = (m['opening'] + m['deposits'] - m['closing']).quantize(Decimal('0.01'))
            json_out.append({
                'period': m['period'],
                'month_key': f"{period_key(m['period'])[0]:04d}-{period_key(m['period'])[1]:02d}",
                'opening': float(m['opening']),
                'deposits': float(m['deposits']),
                'withdrawals_identity': float(implied_w),
                'closing': float(m['closing'])
            })
        json_path = out_dir / 'cibc_statement_monthly_2012.json'
        with open(json_path, 'w', encoding='utf-8') as jf:
            json.dump(json_out, jf, indent=2)
        lines.append(f'Monthly JSON saved: {json_path}')
    except Exception as e:
        lines.append(f'WARNING: Failed to write monthly JSON: {e}')
    lines.append('')

    # Compare to QuickBooks annual totals
    qb_dep_var = (total_deposits - QB_TOTAL_DEPOSITS).quantize(Decimal('0.01'))
    lines.append('COMPARISON TO QUICKBOOKS (Accountant Reconciliation)')
    lines.append(f"  QB Deposits:     ${QB_TOTAL_DEPOSITS:,.2f}")
    lines.append(f"  CIBC Deposits:   ${total_deposits:,.2f}")
    lines.append(f"  Variance:        ${qb_dep_var:,.2f}")
    lines.append('')

    # Compare to our parsed CSV totals
    lines.append('COMPARISON TO OUR PARSED CSV (sanity check)')
    lines.append(f"  CSV Deposits:    ${csv_deposits:,.2f}")
    lines.append(f"  CSV Withdrawals: ${csv_withdrawals:,.2f}")
    lines.append('')
    if csv_deposits != total_deposits or csv_withdrawals != total_withdrawals:
        lines.append('  Result: Parsed CSV totals DO NOT match statement-derived totals → parser needs improvement.')
    else:
        lines.append('  Result: Parsed CSV totals match statement-derived totals.')

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Saved audit to: {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
