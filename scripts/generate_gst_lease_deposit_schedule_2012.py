import csv, os, re, json
from pathlib import Path

KEYWORDS = [
    'heffner', 'lease', 'leasing', 'ace truck', 'toyota', 'lexus', 'deposit', 'cmb', 'f235', 'lease agreement'
]

RATE = 0.05  # Alberta GST

def to_float(s):
    if s is None or s == '':
        return 0.0
    try:
        return float(str(s).replace(',',''))
    except Exception:
        return 0.0


def main():
    src_dir = Path('exports/banking/imported_csv')
    out_csv = Path('exports/banking/gst_itc_lease_deposits_2012.csv')
    out_md = Path('exports/banking/gst_itc_lease_deposits_2012.md')

    rows = []
    for p in src_dir.glob('*.csv'):
        with p.open('r', encoding='utf-8', newline='') as f:
            r = csv.DictReader(f)
            for row in r:
                desc = (row.get('description') or '').lower()
                if any(k in desc for k in KEYWORDS):
                    debit = to_float(row.get('debit'))
                    credit = to_float(row.get('credit'))
                    # Treat outgoing (debit) as payments; if only amount_signed exists, fallback
                    amount = debit if debit > 0 else 0.0
                    if amount == 0.0:
                        # If debit/credit missing, try amount_signed negative
                        amt_signed = to_float(row.get('amount_signed'))
                        if amt_signed < 0:
                            amount = -amt_signed
                    if amount == 0.0:
                        continue
                    gst = round(amount * RATE / (1 + RATE), 2)
                    net = round(amount - gst, 2)
                    rows.append({
                        'file': p.name,
                        'date': row.get('date') or row.get('transaction_date'),
                        'description': row.get('description') or '',
                        'gross_amount': round(amount, 2),
                        'gst_included': gst,
                        'net_amount': net,
                    })

    # Write CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['file','date','description','gross_amount','gst_included','net_amount'])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    total_gross = round(sum(r['gross_amount'] for r in rows), 2)
    total_gst = round(sum(r['gst_included'] for r in rows), 2)
    by_vendor = {}
    for r in rows:
        key = r['description'][:60].lower()
        by_vendor.setdefault(key, {'count':0,'gross':0.0,'gst':0.0})
        by_vendor[key]['count'] += 1
        by_vendor[key]['gross'] += r['gross_amount']
        by_vendor[key]['gst'] += r['gst_included']

    # Write MD summary
    lines = [
        '# GST ITC schedule (leases/deposits) - 2012',
        '',
        f'Total rows: {len(rows)}',
        f'Total gross: ${total_gross:,.2f}',
        f'Total GST (included): ${total_gst:,.2f}',
        '',
        '## Top descriptions (first 10)',
    ]
    for i, (k, v) in enumerate(sorted(by_vendor.items(), key=lambda x: -x[1]['gst'])):
        if i >= 10: break
        lines.append(f"- {k} - count {v['count']}, gross ${v['gross']:,.2f}, GST ${v['gst']:,.2f}")
    out_md.write_text('\n'.join(lines), encoding='utf-8')

    print(json.dumps({'rows': len(rows), 'total_gross': total_gross, 'total_gst': total_gst, 'out_csv': str(out_csv), 'out_md': str(out_md)}, indent=2))

if __name__ == '__main__':
    main()
