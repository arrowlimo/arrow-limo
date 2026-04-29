import re

with open(r'L:\pdf2012 merchant statement globalpayments_ocred.txt', encoding='utf-8') as f:
    text = f.read()

pages = re.split(r'=== PAGE \d+ ===', text)


def clean(s: str) -> float:
    return float(s.replace(',', '').replace(' ', '')) if s.strip() else 0.0


stmts = {}

for pg in pages:
    date_m = re.search(r'Statement Date\s+([\d/]+)', pg)
    if not date_m:
        continue

    stmt_date = date_m.group(1)
    if stmt_date not in stmts:
        stmts[stmt_date] = {'visa': 0.0, 'debit': 0.0, 'mc': 0.0, 'amex': 0.0, 'dep_net': 0.0, 'fees': 0.0}
    d = stmts[stmt_date]

    # Capture Card Summary TOTAL row: Visa, Debit, MasterCard, Amex, Diners, Others.
    cs_block = re.search(
        r'Card Summary.*?TOTAL\s+([\-\d,\.]+)\s+([\-\d,\.]+)\s+([\-\d,\.]+)\s+([\-\d,\.]+)\s+([\-\d,\.]+)\s+([\-\d,\.]+)',
        pg,
        re.DOTALL,
    )
    if cs_block and d['visa'] == 0.0:
        d['visa'] = clean(cs_block.group(1))
        d['debit'] = clean(cs_block.group(2))
        d['mc'] = clean(cs_block.group(3))
        d['amex'] = clean(cs_block.group(4))

    # Capture Deposits TOTAL row and keep the net deposit column.
    dep_block = re.search(
        r'De.osits.*?TOTAL\s+\d+\s+([\-\d,\.]+)\s+([\-\d,\.]+)\s+([\-\d,\.]+)\s+([\-\d,\.]+)\s+([\-\d,\.]+)',
        pg,
        re.DOTALL,
    )
    if dep_block and d['dep_net'] == 0.0:
        d['dep_net'] = clean(dep_block.group(5))

    deb_m = re.search(r'Your account has been debited\s+\$?([\d,\.]+)', pg)
    if deb_m:
        d['fees'] = clean(deb_m.group(1))


print(f"{'Date':<12} {'Visa':>12} {'Debit':>10} {'MC':>12} {'Amex':>10} {'DepNet':>12} {'FeeDebit':>10}")
print('-' * 82)
for dt in sorted(stmts):
    d = stmts[dt]
    card_total = d['visa'] + d['debit'] + d['mc'] + d['amex']
    print(
        f"{dt:<12} {d['visa']:>12,.2f} {d['debit']:>10,.2f} {d['mc']:>12,.2f} {d['amex']:>10,.2f} {d['dep_net']:>12,.2f} {d['fees']:>10,.2f}"
    )
    print(f"{'  CardTotal':<12} {card_total:>12,.2f}")

