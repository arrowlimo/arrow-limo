import PyPDF2
import re
import sys

pdf_path = sys.argv[1] if len(sys.argv) > 1 else 'l:/limo/pdf/2024-01-10-Triangle-Mastercard_ocred.pdf'
reader = PyPDF2.PdfReader(pdf_path)
text = ''.join((pg.extract_text() or '') for pg in reader.pages)
mon = 'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec'
pat = re.compile(rf'({mon})\s+(\d{{1,2}})\s+({mon})\s+(\d{{1,2}})\s+(.*?)(?:\s+([A-Z]{{2}}))?\s+(-?[\d,]*\.?\d{{2}})(?=\s+({mon})\s+\d{{1,2}}\s+({mon})\s+\d{{1,2}}|\s+WAYS TO PAY|$)', re.DOTALL)
count = 0
for m in pat.finditer(text):
    desc = ' '.join(m.group(5).split())
    amt = m.group(7)
    print(f"{m.group(1)} {m.group(2)} | {desc[:70]} ... {desc[-30:]} | {amt}")
    count += 1
print(f"total rows: {count}")
