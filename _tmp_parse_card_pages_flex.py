import re
from pathlib import Path

text = Path(r"L:\pdf2012 merchant statement globalpayments_ocred.txt").read_text(encoding="utf-8", errors="ignore")
parts = re.split(r"===\s*PAGE\s*(\d+)\s*===", text)

DATE_RX = re.compile(r"\b\d{2}/\d{2}/\d{2}\b")
NUM_RX = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?$|^-?\d+\.\d{1,2}$")


def fix_num(s: str) -> str:
    s = s.strip()
    s = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", s)
    s = s.replace(" ", "")
    return s


pages = []
anchors = {}
for i in range(1, len(parts), 2):
    p = int(parts[i])
    lines = [ln.strip() for ln in parts[i + 1].splitlines()]
    pages.append((p, lines))
    for k, ln in enumerate(lines):
        if "statement" in ln.lower() and "date" in ln.lower():
            for j in range(k, min(k + 6, len(lines))):
                m = DATE_RX.search(lines[j])
                if m:
                    anchors[p] = m.group(0)
                    break
            break

ap = sorted(anchors)

def nearest_date(page: int):
    if not ap:
        return None
    q = min(ap, key=lambda a: abs(a - page))
    return anchors[q]


print("page,date,visa,debit,mc,amex,diners,others")
for p, lines in pages:
    card_idx = None
    for i, ln in enumerate(lines):
        if "card" in ln.lower() and "summary" in ln.lower():
            card_idx = i
            break
    if card_idx is None:
        continue

    discount_idx = len(lines)
    for i in range(card_idx + 1, len(lines)):
        if lines[i].lower().startswith("discount"):
            discount_idx = i
            break

    totals = [i for i in range(card_idx, discount_idx) if lines[i].upper() == "TOTAL"]
    if not totals:
        continue

    t = totals[-1]
    nums = []
    for j in range(t + 1, discount_idx):
        tok = fix_num(lines[j])
        if NUM_RX.match(tok):
            nums.append(float(tok.replace(",", "")))
        elif nums:
            break

    if len(nums) < 4:
        continue

    # Most pages have Visa/Debit/MC/Amex and sometimes Diners/Others.
    visa = nums[0]
    debit = nums[1]
    mc = nums[2]
    amex = nums[3]
    diners = nums[4] if len(nums) > 4 else 0.0
    others = nums[5] if len(nums) > 5 else 0.0
    dt = anchors.get(p) or nearest_date(p)

    print(f"{p},{dt},{visa},{debit},{mc},{amex},{diners},{others}")
