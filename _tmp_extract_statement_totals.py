import re
from pathlib import Path

TXT = Path(r"L:\pdf2012 merchant statement globalpayments_ocred.txt")
text = TXT.read_text(encoding="utf-8", errors="ignore")
parts = re.split(r"===\s*PAGE\s*(\d+)\s*===", text)

pages = []
for i in range(1, len(parts), 2):
    pnum = int(parts[i])
    content = parts[i + 1]
    pages.append((pnum, content))

# explicit statement date anchors
page_date = {}
for pnum, content in pages:
    m = re.search(r"Statement\s*Date\s*[:\-]?\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})", content, re.IGNORECASE)
    if m:
        page_date[pnum] = m.group(1)

# helper for nearest anchor page date
anchor_pages = sorted(page_date)

def nearest_date(pnum):
    if not anchor_pages:
        return None
    best = min(anchor_pages, key=lambda a: abs(a - pnum))
    return page_date.get(best)

records = []
for pnum, content in pages:
    lines = content.splitlines()

    # normalize OCR weird decimal spacing (e.g. 741. 10 -> 741.10)
    norm_lines = [re.sub(r"(\d)\.\s+(\d)", r"\1.\2", ln) for ln in lines]

    # card summary total line
    in_card = False
    card_total = None
    for ln in norm_lines:
        l = " ".join(ln.split())
        if re.search(r"Card\s+Summary", l, re.IGNORECASE):
            in_card = True
            continue
        if in_card and re.search(r"^Discount\b", l, re.IGNORECASE):
            in_card = False
        if in_card and re.search(r"\bTOTAL\b", l, re.IGNORECASE):
            nums = re.findall(r"-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|-?\d+\.\d{1,2}", l)
            # expect 6 values: visa, debit, mc, amex, diners, others
            if len(nums) >= 6:
                vals = [float(n.replace(",", "")) for n in nums[:6]]
                card_total = vals
                break

    # fee debit line
    fee_amt = None
    mfee = re.search(r"Your\s+account\s+has\s+been\s+debited\s*\$?\s*([0-9,]+\.[0-9]{2})", content, re.IGNORECASE)
    if mfee:
        fee_amt = float(mfee.group(1).replace(",", ""))

    if card_total is not None or fee_amt is not None:
        records.append({
            "page": pnum,
            "date": page_date.get(pnum) or nearest_date(pnum),
            "card": card_total,
            "fee": fee_amt,
            "explicit_date": page_date.get(pnum),
        })

# collapse per date: take first non-null card totals and fee
by_date = {}
for r in records:
    d = r["date"]
    if not d:
        continue
    x = by_date.setdefault(d, {"card": None, "fee": None, "card_page": None, "fee_page": None})
    if r["card"] is not None and x["card"] is None:
        x["card"] = r["card"]
        x["card_page"] = r["page"]
    if r["fee"] is not None and x["fee"] is None:
        x["fee"] = r["fee"]
        x["fee_page"] = r["page"]

print("date,visa,debit,mc,amex,diners,others,fee,card_page,fee_page")
for d in sorted(by_date.keys(), key=lambda s: tuple(map(int, s.split('/')[::-1]))):
    info = by_date[d]
    c = info["card"] or [None] * 6
    print(
        f"{d},{c[0] if c[0] is not None else ''},{c[1] if c[1] is not None else ''},{c[2] if c[2] is not None else ''},{c[3] if c[3] is not None else ''},{c[4] if c[4] is not None else ''},{c[5] if c[5] is not None else ''},{info['fee'] if info['fee'] is not None else ''},{info['card_page'] if info['card_page'] else ''},{info['fee_page'] if info['fee_page'] else ''}"
    )
