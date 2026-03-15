#!/usr/bin/env python3
"""
Audit continuity and math for 2012 bank statements (CIBC + Scotia)
- Verifies per-month identity: opening + deposits - withdrawals == closing (±$0.01)
- Verifies continuity across months per account: prev_closing == next_opening (±$0.01)
- Outputs consolidated audit with PASS/FAIL per month and continuity notes

Inputs:
  - L:\\limo\\staging\\2012_comparison\\cibc_statement_monthly_2012.json
  - L:\\limo\\staging\\2012_comparison\\scotia_statement_monthly_2012.json

Outputs:
  - L:\\limo\\staging\\2012_comparison\\statements_continuity_audit_2012.txt
  - L:\\limo\\staging\\2012_comparison\\statements_continuity_audit_2012.json
"""
from __future__ import annotations
from pathlib import Path
import json
from decimal import Decimal

ROOT = Path(r"L:\\limo\\staging\\2012_comparison")
CIBC_JSON = ROOT / 'cibc_statement_monthly_2012.json'
SCOTIA_JSON = ROOT / 'scotia_statement_monthly_2012.json'
OUT_TXT = ROOT / 'statements_continuity_audit_2012.txt'
OUT_JSON = ROOT / 'statements_continuity_audit_2012.json'

YEAR = 2012
TOL = Decimal('0.01')


def load(path: Path):
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def to_d(v):
    if v is None:
        return None
    return Decimal(str(v))


def audit_account(name: str, rows: list[dict]):
    # Sort by month
    rows = [r for r in rows if str(r.get('month_key', '')).startswith(str(YEAR))]
    rows = sorted(rows, key=lambda r: r.get('month_key'))
    audited = []
    last_close = None
    for r in rows:
        mk = r.get('month_key')
        op = to_d(r.get('opening'))
        dep = to_d(r.get('deposits'))
        wdr = to_d(r.get('withdrawals'))
        cl = to_d(r.get('closing'))
        # Identity check
        math_ok = None
        if op is not None and dep is not None and wdr is not None and cl is not None:
            math_ok = abs((op + dep - wdr) - cl) <= TOL
        # Continuity check
        cont_ok = None
        cont_delta = None
        if last_close is not None and op is not None:
            cont_delta = op - last_close
            cont_ok = abs(cont_delta) <= TOL
        audited.append({
            'account': name,
            'month': mk,
            'opening': float(op) if op is not None else None,
            'deposits': float(dep) if dep is not None else None,
            'withdrawals': float(wdr) if wdr is not None else None,
            'closing': float(cl) if cl is not None else None,
            'math_ok': math_ok,
            'continuity_ok': cont_ok,
            'continuity_delta': float(cont_delta) if cont_delta is not None else None,
            'flags': r.get('audit') if isinstance(r.get('audit'), dict) else None,
        })
        if cl is not None:
            last_close = cl
    return audited


def main():
    cibc = load(CIBC_JSON)
    scotia = load(SCOTIA_JSON)

    cibc_a = audit_account('CIBC', cibc)
    scotia_a = audit_account('Scotia', scotia)

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as jf:
        json.dump({'year': YEAR, 'accounts': {'CIBC': cibc_a, 'Scotia': scotia_a}}, jf, indent=2)

    # Write TXT
    lines = []
    lines.append(f"STATEMENT CONTINUITY & MATH AUDIT {YEAR}")
    lines.append('=' * 80)
    for name, arr in [('CIBC', cibc_a), ('Scotia', scotia_a)]:
        lines.append('')
        lines.append(f"Account: {name}")
        for r in arr:
            lines.append(f"{r['month']}")
            lines.append(f"  Opening ${ (r['opening'] or 0):,.2f}  Deposits ${ (r['deposits'] or 0):,.2f}  Withdrawals ${ (r['withdrawals'] or 0):,.2f}  Closing ${ (r['closing'] or 0):,.2f}")
            lines.append(f"  Math OK: {r['math_ok']}  | Continuity OK: {r['continuity_ok']}  (Δ ${ (r['continuity_delta'] or 0):,.2f})")
            if r.get('flags'):
                flags = []
                if r['flags'].get('derived_withdrawals'): flags.append('derived_withdrawals')
                if r['flags'].get('derived_deposits'): flags.append('derived_deposits')
                if r['flags'].get('math_ok') is True: flags.append('math_ok')
                if r['flags'].get('math_ok') is False: flags.append('math_fail')
                lines.append(f"  Flags: {', '.join(flags)}")
            lines.append('')
    with open(OUT_TXT, 'w', encoding='utf-8') as tf:
        tf.write('\n'.join(lines))

    print(f"Saved statements continuity audit: {OUT_TXT}")


if __name__ == '__main__':
    main()
