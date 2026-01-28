import pdfplumber

pdf_path = r"L:\limo\quickbooks\New folder\2013 T4 Slips - Arrow Employees.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    for i, page in enumerate(pdf.pages[:2]):  # First 2 pages
        print(f"\n{'='*80}")
        print(f"PAGE {i+1}")
        print('='*80)
        text = page.extract_text()
        lines = text.split('\n')
        for j, line in enumerate(lines[:30]):  # First 30 lines
            print(f"{j:3d}: |{line}|")
