import PyPDF2

pdf_path = r'l:\limo\pdf\2011\2011 cibc 1615.pdf'

with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    total_pages = len(reader.pages)
    
    print(f"Non-OCR PDF Total pages: {total_pages}")
    print()
    print("Checking first 3 and last 3 pages for date range...")
    print()
    
    # First page
    print("="*70)
    print("FIRST PAGE:")
    print("="*70)
    page = reader.pages[0]
    text = page.extract_text()
    print(text[:800])
    
    print("\n\n" + "="*70)
    print(f"LAST PAGE ({total_pages}):")
    print("="*70)
    page = reader.pages[-1]
    text = page.extract_text()
    print(text[-800:])
