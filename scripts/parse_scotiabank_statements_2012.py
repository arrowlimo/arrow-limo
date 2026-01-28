#!/usr/bin/env python3
"""
Parse Scotiabank Statement PDFs (2012)
- Extract monthly totals from Scotiabank business statements
- Robust to OCR by searching for header and totals blocks

Inputs (PDFs):
  - L:\\limo\\pdf\\2012 scotia bank statements_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 2_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 3_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 4_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 5_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 6_ocred.pdf

Outputs:
  - L:\\limo\\staging\\2012_comparison\\scotia_statement_monthly_2012.json
  - L:\\limo\\staging\\2012_comparison\\scotia_statement_monthly_2012.txt

Safe: Read-only
"""
from __future__ import annotations
from pathlib import Path
import re
import json
from decimal import Decimal, InvalidOperation
import pdfplumber

INPUT_FILES = [
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 2_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 3_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 4_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 5_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 6_ocred.pdf"),
]
OUTPUT_JSON = Path(r"L:\\limo\\staging\\2012_comparison\\scotia_statement_monthly_2012.json")
OUTPUT_TXT = Path(r"L:\\limo\\staging\\2012_comparison\\scotia_statement_monthly_2012.txt")

amount_re = re.compile(r"\(?-?\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2}))\)?")

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


def detect_period(text: str) -> tuple[str | None, str | None, str | None]:
    """Detect From/To period; return (month_key, from_raw, to_raw)."""
    # Pattern like: Statement of BUSINESS ACCOUNT NOV 30 2012 DEC 31 2012
    m = re.search(r"BUSINESS\s+ACCOUNT\s+([A-Z]{3,9})\s+(\d{1,2})\s+(\d{4})\s+([A-Z]{3,9})\s+(\d{1,2})\s+(\d{4})", text, re.IGNORECASE)
    if m:
        mon_to = MONTHS.get(m.group(4).lower())
        dy_to = int(m.group(5))
        yr_to = int(m.group(6))
        if mon_to:
            return f"{yr_to:04d}-{mon_to:02d}", f"{m.group(1)} {m.group(2)} {m.group(3)}", f"{m.group(4)} {m.group(5)} {m.group(6)}"
    # Alternative: From ... To ... on same line
    m2 = re.search(r"From\s+([A-Z]{3,9})\s+(\d{1,2})\s+(\d{4})\s+To\s+([A-Z]{3,9})\s+(\d{1,2})\s+(\d{4})", text, re.IGNORECASE)
    if m2:
        mon_to = MONTHS.get(m2.group(4).lower())
        dy_to = int(m2.group(5))
        yr_to = int(m2.group(6))
        if mon_to:
            return f"{yr_to:04d}-{mon_to:02d}", f"{m2.group(1)} {m2.group(2)} {m2.group(3)}", f"{m2.group(4)} {m2.group(5)} {m2.group(6)}"
    return None, None, None


def extract_totals(text: str) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    """Return (opening, deposits_credits, withdrawals_debits, closing) if found."""
    opening = None
    closing = None
    deposits = None
    withdrawals = None

    # Try Balance Forward / Opening
    m = re.search(r"BALANCE\s+FORWARD.*?([-()$ ,\d\.]+)", text, re.IGNORECASE)
    if m:
        opening = to_amount(m.group(1))
    # Try a line near the header that shows opening balance
    if opening is None:
        m2 = re.search(r"Opening\s+Balance.*?([-()$ ,\d\.]+)", text, re.IGNORECASE)
        if m2:
            opening = to_amount(m2.group(1))

    # Totals area: try multiple phrasings seen on Scotiabank statements
    # 1) "TOTAL AMOUNT - DEBITS" / "TOTAL AMOUNT - CREDITS"
    ttl = re.search(r"TOTAL\s+AMOUNT\s*-\s*DEBITS.*?\n(.*?TOTAL\s+AMOUNT\s*-\s*CREDITS.*?\n)?", text, re.IGNORECASE | re.DOTALL)
    if ttl:
        win = ttl.group(0)
        md = re.search(r"TOTAL\s+AMOUNT\s*-\s*DEBITS[^\n$\d-]*([-()$ ,\d\.]+)", win, re.IGNORECASE)
        if md:
            val = to_amount(md.group(1))
            if val is not None:
                withdrawals = abs(val)
        mc = re.search(r"TOTAL\s+AMOUNT\s*-\s*CREDITS[^\n$\d-]*([-()$ ,\d\.]+)", win, re.IGNORECASE)
        if mc:
            val = to_amount(mc.group(1))
            if val is not None:
                deposits = abs(val)

    # 2) "Deposits / Credits" and "Withdrawals / Debits"
    if deposits is None:
        mc2 = re.search(r"(Deposits\s*/\s*Credits|Credits\s*/\s*Deposits|Total\s+Credits|Total\s+Deposits)[^\n$\d-]*([-()$ ,\d\.]+)", text, re.IGNORECASE)
        if mc2:
            val = to_amount(mc2.group(2))
            if val is not None:
                deposits = abs(val)
    if withdrawals is None:
        md2 = re.search(r"(Withdrawals\s*/\s*Debits|Debits\s*/\s*Withdrawals|Total\s+Debits|Total\s+Withdrawals)[^\n$\d-]*([-()$ ,\d\.]+)", text, re.IGNORECASE)
        if md2:
            val = to_amount(md2.group(2))
            if val is not None:
                withdrawals = abs(val)

    # Closing balance
    mcl = re.search(r"(Closing\s+balance|Ending\s+balance).*?([-()$ ,\d\.]+)", text, re.IGNORECASE)
    if mcl:
        closing = to_amount(mcl.group(2))

    return opening, deposits, withdrawals, closing


def parse_pdf(path: Path) -> dict | None:
    with pdfplumber.open(path) as pdf:
        first_n = min(2, len(pdf.pages))
        text_first = "\n".join([(pdf.pages[i].extract_text() or '') for i in range(first_n)])
        # Build a full-text fallback for totals that may appear later
        text_all = "\n".join([(p.extract_text() or '') for p in pdf.pages])
    month_key, from_raw, to_raw = detect_period(text_first)
    if not month_key:
        # Fallback: try detecting period from all pages
        month_key, from_raw, to_raw = detect_period(text_all)
    if not month_key:
        return None
    # Prefer totals from anywhere in the document (they often appear in a summary page)
    opening, deposits, withdrawals, closing = extract_totals(text_all)

    # Derive missing piece if possible and add audit flags
    audit = {"derived_withdrawals": False, "derived_deposits": False, "math_ok": None}
    if opening is not None and deposits is not None and closing is not None and withdrawals is None:
        # withdrawals = opening + deposits - closing
        try:
            withdrawals = (opening + deposits) - closing
            audit["derived_withdrawals"] = True
        except Exception:
            pass
    if opening is not None and withdrawals is not None and closing is not None and deposits is None:
        # deposits = closing + withdrawals - opening
        try:
            deposits = (closing + withdrawals) - opening
            audit["derived_deposits"] = True
        except Exception:
            pass
    # Verify identity if 3 of 4 are present
    if opening is not None and deposits is not None and withdrawals is not None and closing is not None:
        audit["math_ok"] = abs((opening + deposits - withdrawals) - closing) <= Decimal('0.01')
    return {
        'source': str(path),
        'month_key': month_key,
        'from': from_raw,
        'to': to_raw,
        'opening': float(opening) if isinstance(opening, Decimal) else None,
        'deposits': float(deposits) if isinstance(deposits, Decimal) else None,
        'withdrawals': float(withdrawals) if isinstance(withdrawals, Decimal) else None,
        'closing': float(closing) if isinstance(closing, Decimal) else None,
        'audit': audit,
    }


def main():
    summaries: dict[str, dict] = {}
    for path in INPUT_FILES:
        if not path.exists():
            continue
        try:
            res = parse_pdf(path)
        except Exception as e:
            print(f"WARN: Failed to parse {path}: {e}")
            continue
        if not res:
            print(f"WARN: No period detected in {path}")
            continue
        mk = res['month_key']
        if mk not in summaries:
            summaries[mk] = res
        else:
            # if duplicate, prefer one with both deposits and withdrawals
            cur = summaries[mk]
            cur_score = int(bool(cur.get('deposits'))) + int(bool(cur.get('withdrawals')))
            new_score = int(bool(res.get('deposits'))) + int(bool(res.get('withdrawals')))
            if new_score > cur_score:
                summaries[mk] = res

    # Write outputs
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    ordered = [summaries[k] for k in sorted(summaries.keys())]
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as jf:
        json.dump(ordered, jf, indent=2)

    lines = []
    lines.append('SCOTIABANK STATEMENT TOTALS (2012)')
    lines.append('=' * 80)
    lines.append('')
    t_dep = Decimal('0')
    t_wdr = Decimal('0')
    for d in ordered:
        lines.append(f"{d['month_key']}  From {d.get('from')} To {d.get('to')}")
        lines.append(f"  Opening:     ${d.get('opening') or 0:,.2f}")
        lines.append(f"  Deposits:    ${d.get('deposits') or 0:,.2f}")
        lines.append(f"  Withdrawals: ${d.get('withdrawals') or 0:,.2f}")
        lines.append(f"  Closing:     ${d.get('closing') or 0:,.2f}")
        a = d.get('audit') or {}
        if a:
            flags = []
            if a.get('derived_withdrawals'): flags.append('derived_withdrawals')
            if a.get('derived_deposits'): flags.append('derived_deposits')
            if a.get('math_ok') is True: flags.append('math_ok')
            if a.get('math_ok') is False: flags.append('math_fail')
            if flags:
                lines.append(f"  Audit:       {', '.join(flags)}")
        lines.append('')
        if d.get('deposits'):
            t_dep += Decimal(str(d['deposits']))
        if d.get('withdrawals'):
            t_wdr += Decimal(str(d['withdrawals']))
    lines.append('-' * 80)
    lines.append(f"AGGREGATED TOTALS (Statements): Deposits ${t_dep:,.2f} | Withdrawals ${t_wdr:,.2f}")

    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Saved Scotia statement monthly JSON: {OUTPUT_JSON}")
    print(f"Saved Scotia statement monthly report: {OUTPUT_TXT}")


if __name__ == '__main__':
    main()
