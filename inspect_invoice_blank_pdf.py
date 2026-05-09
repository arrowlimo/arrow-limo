"""
Inspect invoice_BLANK.pdf to find actual text objects and cell boundaries.
This will help us map correct coordinates for text overlays.
"""

from pypdf import PdfReader
import sys

pdf_path = r"L:/Confirmation/invoice_BLANK.pdf"
reader = PdfReader(pdf_path)
page = reader.pages[0]

print(f"PDF Page size: {page.mediabox}")
print(f"Width: {float(page.mediabox.width)}, Height: {float(page.mediabox.height)}")
print(f"Rotation: {page.get('/Rotate', 0)}")
print()

# Extract all text and annotations to understand cell locations
print("=" * 80)
print("TEXT CONTENT (from /Contents stream):")
print("=" * 80)

# Try to extract text with location info
try:
    from pypdf.generic import RectangleObject
    
    if "/Annots" in page:
        print("\nAnnotations (form fields, etc.):")
        for annot in page["/Annots"]:
            obj = annot.get_object()
            if "/Rect" in obj:
                rect = obj["/Rect"]
                print(f"  Type: {obj.get('/Subtype', 'Unknown')}")
                print(f"  Rect: {rect}")
                print(f"  Name: {obj.get('/T', 'N/A')}")
                print()
except Exception as e:
    print(f"Could not extract annotations: {e}")

# Try pypdf's text extraction
print("\n" + "=" * 80)
print("EXTRACTED TEXT:")
print("=" * 80)
text = page.extract_text()
print(text[:1000] if text else "No text extracted")

# Check if there are images or other graphical elements
print("\n" + "=" * 80)
print("RESOURCES IN PAGE:")
print("=" * 80)
if "/Resources" in page:
    resources = page["/Resources"]
    if "/XObject" in resources:
        print("XObjects (embedded PDFs, images):")
        for name, obj in resources["/XObject"].items():
            print(f"  {name}: {obj}")
    if "/Font" in resources:
        print("Fonts:")
        for name, obj in resources["/Font"].items():
            print(f"  {name}: {obj}")

print("\n" + "=" * 80)
print("CONTENT STREAM OPS (raw):")
print("=" * 80)
if "/Contents" in page:
    content = page["/Contents"]
    if hasattr(content, 'get_object'):
        content = content.get_object()
    if hasattr(content, 'get_data'):
        data = content.get_data()
        # Print first 2000 bytes of content stream
        print(data[:2000].decode('latin-1', errors='replace'))
    else:
        print(f"Content type: {type(content)}")

print("\nTo properly map coordinates, we need to:")
print("1. Understand if cells are form fields or just borders drawn on the PDF")
print("2. Extract the exact (x, y) positions where each cell starts")
print("3. Measure cell widths/heights")
print("4. Adjust our reportlab overlay coordinates accordingly")
