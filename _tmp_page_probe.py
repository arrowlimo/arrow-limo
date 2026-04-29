import re
from pathlib import Path

path = Path(r"L:\pdf2012 merchant statement globalpayments_ocred.txt")
text = path.read_text(encoding="utf-8", errors="ignore")
parts = re.split(r"===\s*PAGE\s*(\d+)\s*===", text)
# parts: [pre, num1, content1, num2, content2, ...]
pages = []
for i in range(1, len(parts), 2):
    num = int(parts[i])
    content = parts[i+1]
    pages.append((num, content))

# regex for statement date styles
rxs = [
    re.compile(r"(?im)^\s*statement\s*date\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})"),
    re.compile(r"(?im)^\s*date\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})"),
]

keys = ["Card Summary", "Deposits", "TOTAL", "Your account has been debited"]

for num, content in pages[:20]:
    date = None
    for rx in rxs:
        m = rx.search(content)
        if m:
            date = m.group(1).strip()
            break
    print(f"PAGE {num} | statement_date={date or 'None'}")
    lines = [ln.strip() for ln in content.splitlines() if any(k.lower() in ln.lower() for k in keys)]
    if lines:
        for ln in lines[:10]:
            ln2 = re.sub(r"\s+", " ", ln)
            if len(ln2) > 180:
                ln2 = ln2[:177] + "..."
            print(f"  - {ln2}")
    else:
        print("  - (no key lines)")
