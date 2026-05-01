from pypdf import PdfReader

p = r"L:\Confirmation\quote.pdf"
r = PdfReader(p)
print("PAGES", len(r.pages))
for i, pg in enumerate(r.pages):
    print(f"=PAGE{i+1}=")
    print(pg.extract_text() or "(no text)")
