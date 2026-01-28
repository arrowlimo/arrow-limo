"""
Examine raw text from fibrenew invoices2.pdf to understand the format.
"""
import PyPDF2

pdf_path = r'L:\limo\pdf\2012\fibrenew invoices2.pdf'

with open(pdf_path, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    print(f"\nPDF has {len(pdf.pages)} pages\n")
    
    for i in range(min(3, len(pdf.pages))):  # First 3 pages
        print(f"\n{'='*80}")
        print(f"PAGE {i+1}")
        print('='*80)
        text = pdf.pages[i].extract_text()
        print(text[:1500])  # First 1500 chars
        print("\n[... truncated ...]")
