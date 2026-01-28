"""Debug OCR output from Scotia PDF."""
import pdfplumber
import pytesseract
import os

# Set tesseract path
if os.name == 'nt':
    for possible_path in [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]:
        if os.path.exists(possible_path):
            pytesseract.pytesseract.tesseract_cmd = possible_path
            break

pdf_path = r"L:\limo\pdf\2012\2012 scotiabank statements all.pdf"

with pdfplumber.open(pdf_path) as pdf:
    # Test multiple pages
    for test_page_num in [3, 4, 5, 6]:
        page = pdf.pages[test_page_num]
        print(f"\nConverting page {test_page_num + 1} to image...")
        im = page.to_image(resolution=300)
        pil_image = im.original
        
        print("Running OCR...")
        text = pytesseract.image_to_string(pil_image, config='--psm 6')
        
        print("\n" + "="*80)
        print(f"OCR OUTPUT FROM PAGE {test_page_num + 1}:")
        print("="*80)
        print(text[:1000])  # First 1000 chars
        print("\n... (showing first 1000 characters only)")
        
        # Check for date patterns
        import re
        lines = text.split('\n')
        date_lines = [l for l in lines if re.search(r'\d{1,2}[/-]\d{1,2}', l)]
        if date_lines:
            print(f"\nFound {len(date_lines)} lines with date patterns:")
            for line in date_lines[:5]:
                print(f"  {line}")
