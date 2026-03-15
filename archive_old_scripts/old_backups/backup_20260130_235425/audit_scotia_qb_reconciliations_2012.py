#!/usr/bin/env python3
"""
Audit QuickBooks Scotia reconciliation monthly summaries (2012)
- Validates math per month: beginning + cleared_deposits - cleared_payments +/- difference == ending
- Tolerates small rounding up to $0.01

Inputs:
  - L:\\limo\\staging\\2012_comparison\\scotia_qb_monthly_2012.json
Outputs:
  - L:\\limo\\staging\\2012_comparison\\scotia_qb_reconciliation_audit_2012.txt
  - L:\\limo\\staging\\2012_comparison\\scotia_qb_reconciliation_audit_2012.json
"""
from __future__ import annotations
from pathlib import Path
import json
from decimal import Decimal

ROOT = Path(r"L:\\limo\\staging\\2012_comparison")
IN_JSON = ROOT / 'scotia_qb_monthly_2012.json'
OUT_TXT = ROOT / 'scotia_qb_reconciliation_audit_2012.txt'
OUT_JSON = ROOT / 'scotia_qb_reconciliation_audit_2012.json'

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


def main():
    rows = load(IN_JSON)
    audited = []
    for r in rows:
        mk = r.get('month_key')
        beg = to_d(r.get('beginning_balance') or r.get('beginning'))
        dep = to_d(r.get('cleared_deposits') or r.get('deposits'))
        pay = to_d(r.get('cleared_payments') or r.get('payments'))
        end = to_d(r.get('ending_balance') or r.get('ending'))
        diff = to_d(r.get('reconciliation_difference') or r.get('difference'))
        cleared_bal = to_d(r.get('cleared_balance'))
        math_ok = None
        delta = None
        if None not in (beg, dep, pay, end):
            # If difference missing but cleared_balance present, infer diff = end - cleared_balance
            if diff is None and cleared_bal is not None:
                diff = end - cleared_bal
            d = diff if diff is not None else Decimal('0')
            delta = (beg + dep - pay + d) - end
            math_ok = abs(delta) <= TOL
        audited.append({
            'month': mk,
            'beginning': float(beg) if beg is not None else None,
            'deposits': float(dep) if dep is not None else None,
            'payments': float(pay) if pay is not None else None,
            'difference': float(diff) if diff is not None else 0.0,
            'ending': float(end) if end is not None else None,
            'math_ok': math_ok,
            'delta': float(delta) if delta is not None else None,
        })

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as jf:
        json.dump(audited, jf, indent=2)

    lines = []
    lines.append('SCOTIA QB RECONCILIATION AUDIT 2012')
    lines.append('=' * 80)
    lines.append('')
    for a in audited:
        lines.append(f"{a['month']}")
        lines.append(f"  Beg ${ (a['beginning'] or 0):,.2f} + Deposits ${ (a['deposits'] or 0):,.2f} - Payments ${ (a['payments'] or 0):,.2f} + Diff ${ (a['difference'] or 0):,.2f} = End ${ (a['ending'] or 0):,.2f}")
        lines.append(f"  Math OK: {a['math_ok']} (Δ ${ (a['delta'] or 0):,.2f})")
        lines.append('')

    with open(OUT_TXT, 'w', encoding='utf-8') as tf:
        tf.write('\n'.join(lines))

    print(f"Saved QB reconciliation audit: {OUT_TXT}")


if __name__ == '__main__':
    main()
