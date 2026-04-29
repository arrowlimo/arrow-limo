import re
from pathlib import Path

text = Path(r"L:\pdf2012 merchant statement globalpayments_ocred.txt").read_text(encoding="utf-8", errors="ignore")
parts = re.split(r"===\s*PAGE\s*(\d+)\s*===", text)

DATE_RX = re.compile(r"\b\d{2}/\d{2}/\d{2}\b")
NUM_RX = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?$|^-?\d+\.\d{1,2}$")


def normalize_num(s: str) -> str:
    s = s.strip().replace(" ", "")
    s = re.sub(r"(\d)\.\s*(\d)", r"\1.\2", s)
    return s


print("page,date,visa,debit,mc,amex,diners,others,sum6")
for i in range(1, len(parts), 2):
    page = int(parts[i])
    lines = [ln.strip() for ln in parts[i + 1].splitlines()]

    stmt_date = None
    for k, ln in enumerate(lines):
        if "statement" in ln.lower() and "date" in ln.lower():
            for j in range(k, min(k + 6, len(lines))):
                m = DATE_RX.search(lines[j])
                if m:
                    stmt_date = m.group(0)
                    break
            break
    if not stmt_date:
        continue

    card_idx = None
    for k, ln in enumerate(lines):
        if "card" in ln.lower() and "summary" in ln.lower():
            card_idx = k
            break
    if card_idx is None:
        continue

    totals = []
    for k in range(card_idx, min(card_idx + 260, len(lines))):
        if lines[k].upper() == "TOTAL":
            vals = []
            for j in range(k + 1, min(k + 20, len(lines))):
                t = normalize_num(lines[j])
                if NUM_RX.match(t):
                    vals.append(float(t.replace(",", "")))
                    if len(vals) >= 6:
                        break
            if len(vals) >= 6:
                totals.append(vals[:6])

    if not totals:
        continue

    # usually multiple TOTALs exist; largest sum is monthly card total candidate
    best = max(totals, key=sum)
    print(
        f"{page},{stmt_date},{best[0]},{best[1]},{best[2]},{best[3]},{best[4]},{best[5]},{sum(best):.2f}"
    )
