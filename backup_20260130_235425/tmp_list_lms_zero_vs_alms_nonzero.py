import csv
path = r'L:\limo\reports\ALMS_LMS_BALANCE_AUDIT.csv'
rows = []
with open(path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        try:
            alms = float(r['alms_balance']) if r['alms_balance'] else 0.0
            lms = float(r['lms_balance']) if r['lms_balance'] else None
        except Exception:
            continue
        if lms is None:
            continue
        if abs(lms) < 1.0 and abs(alms) > 0.01:
            rows.append((r['reserve_number'], alms, lms, r.get('status',''), r.get('category','')))
print(f'Total LMS~0 but alms non-zero: {len(rows)}')
for r in sorted(rows, key=lambda x: -abs(x[1]))[:20]:
    print(f"{r[0]} | alms_balance={r[1]:+.2f} | lms_balance={r[2]:+.2f} | status={r[3]} | cat={r[4]}")
