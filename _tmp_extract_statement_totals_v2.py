import re
from pathlib import Path

TXT = Path(r"L:\pdf2012 merchant statement globalpayments_ocred.txt")
text = TXT.read_text(encoding="utf-8", errors="ignore")
parts = re.split(r"===\s*PAGE\s*(\d+)\s*===", text)

pages = []
for i in range(1, len(parts), 2):
    pnum = int(parts[i])
    lines = [ln.strip() for ln in parts[i + 1].splitlines()]
    pages.append((pnum, lines))

DATE_RX = re.compile(r"\b\d{2}/\d{2}/\d{2}\b")
NUM_RX = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?$|^-?\d+\.\d{1,2}$")


def norm_num(s: str) -> str:
    s = s.replace(" ", "")
    s = re.sub(r"(\d)\.\s*(\d)", r"\1.\2", s)
    return s


def to_float(s: str) -> float:
    return float(s.replace(",", ""))


def find_date(lines):
    for i, ln in enumerate(lines):
        if "statement" in ln.lower() and "date" in ln.lower():
            for j in range(i, min(i + 6, len(lines))):
                m = DATE_RX.search(lines[j])
                if m:
                    return m.group(0)
    return None


def find_card_totals(lines):
    start = None
    for i, ln in enumerate(lines):
        if "card" in ln.lower() and "summary" in ln.lower():
            start = i
            break
    if start is None:
        return None

    total_idx = None
    for i in range(start, min(start + 260, len(lines))):
        if lines[i].strip().upper() == "TOTAL":
            total_idx = i
    if total_idx is None:
        return None

    vals = []
    for j in range(total_idx + 1, min(total_idx + 18, len(lines))):
        t = norm_num(lines[j])
        if NUM_RX.match(t):
            vals.append(to_float(t))
            if len(vals) >= 6:
                break
    if len(vals) >= 6:
        return vals[:6]
    return None


def find_deposit_net(lines):
    dep_idx = None
    for i, ln in enumerate(lines):
        if "de" in ln.lower() and "osit" in ln.lower():
            dep_idx = i
            break
    if dep_idx is None:
        return None

    stop_idx = len(lines)
    for i in range(dep_idx, min(dep_idx + 220, len(lines))):
        if "deposit item summary" in lines[i].lower():
            stop_idx = i
            break

    total_idx = None
    for i in range(dep_idx, stop_idx):
        if lines[i].strip().upper() == "TOTAL":
            total_idx = i
    if total_idx is None:
        return None

    vals = []
    for j in range(total_idx + 1, min(total_idx + 20, len(lines))):
        t = norm_num(lines[j])
        if NUM_RX.match(t):
            vals.append(to_float(t))
    # Typical sequence after TOTAL: items, sales, returns, non-funded, discount, net
    if len(vals) >= 6:
        return vals[5]
    return None


def find_fee_debit(lines):
    for i, ln in enumerate(lines):
        if "your account has been debited" in ln.lower():
            block = " ".join(lines[i:i + 4])
            m = re.search(r"\$\s*([0-9,]+\.[0-9]{2})", block)
            if m:
                return float(m.group(1).replace(",", ""))
            for j in range(i, min(i + 6, len(lines))):
                t = norm_num(lines[j])
                if NUM_RX.match(t):
                    val = to_float(t)
                    if 10 <= val <= 2000:
                        return val
    return None


by_date = {}
for pnum, lines in pages:
    dt = find_date(lines)
    card = find_card_totals(lines)
    dep_net = find_deposit_net(lines)
    fee = find_fee_debit(lines)

    if not dt and card is None and dep_net is None and fee is None:
        continue

    key = dt or f"UNKNOWN_PAGE_{pnum}"
    d = by_date.setdefault(
        key,
        {
            "visa": None,
            "debit": None,
            "mc": None,
            "amex": None,
            "diners": None,
            "others": None,
            "dep_net": None,
            "fee": None,
            "card_page": None,
            "dep_page": None,
            "fee_page": None,
        },
    )

    if card is not None and d["visa"] is None:
        d["visa"], d["debit"], d["mc"], d["amex"], d["diners"], d["others"] = card
        d["card_page"] = pnum
    if dep_net is not None and d["dep_net"] is None:
        d["dep_net"] = dep_net
        d["dep_page"] = pnum
    if fee is not None and d["fee"] is None:
        d["fee"] = fee
        d["fee_page"] = pnum

print("date,visa,debit,mc,amex,diners,others,dep_net,fee,card_page,dep_page,fee_page")

# Keep only real statement dates
real_dates = [d for d in by_date if DATE_RX.fullmatch(d)]
real_dates.sort(key=lambda s: (int(s[-2:]), int(s[:2]), int(s[3:5])))
for dt in real_dates:
    d = by_date[dt]
    vals = [
        d["visa"], d["debit"], d["mc"], d["amex"], d["diners"], d["others"], d["dep_net"], d["fee"], d["card_page"], d["dep_page"], d["fee_page"],
    ]
    out = [dt]
    for v in vals:
        out.append("" if v is None else str(v))
    print(",".join(out))
