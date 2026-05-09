"""
Parse PDF content stream to find exact positions of CHARGES and TOTAL labels.
Then infer the box boundaries from those positions.
"""

from pypdf import PdfReader
import re

pdf_path = r"L:/Confirmation/invoice_BLANK.pdf"
reader = PdfReader(pdf_path)
page = reader.pages[0]

print("Analyzing PDF structure to find CHARGES and TOTAL boxes...\n")

# Extract text with simple extraction
text = page.extract_text()
print("TEMPLATE TEXT LAYOUT:")
print("="*80)
lines = text.split('\n')
for i, line in enumerate(lines):
    if line.strip():
        print(f"Line {i:2d}: {line}")

print("\n" + "="*80)

# Now parse the raw content stream for text positioning
if "/Contents" in page:
    content = page["/Contents"]
    if hasattr(content, 'get_object'):
        content = content.get_object()
    if hasattr(content, 'get_data'):
        data = content.get_data()
        text = data.decode('latin-1', errors='replace')
        
        # Look for specific strings in the content stream
        print("\nSearching for 'CHARGES' and 'TOTAL' text objects in PDF stream...")
        
        # Find text positioning commands around CHARGES
        if 'CHARGES' in text:
            idx = text.find('CHARGES')
            start = max(0, idx - 150)
            end = min(len(text), idx + 150)
            print("\nContext around 'CHARGES':")
            print(repr(text[start:end]))
        
        if 'TOTAL' in text:
            # Find all occurrences of TOTAL
            import re
            for match in re.finditer(r'TOTAL', text):
                idx = match.start()
                start = max(0, idx - 150)
                end = min(len(text), idx + 150)
                print(f"\nContext around 'TOTAL' (offset {idx}):")
                print(repr(text[start:end]))

print("\n" + "="*80)
print("INFERENCE: Look for BT (begin text), numbers before text, and closing Tj commands")
print("Numbers like '100 500 Td' indicate text position (x y coordinates)")
