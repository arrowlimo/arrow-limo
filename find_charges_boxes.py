"""
Detailed inspection of invoice_BLANK.pdf to find CHARGES and TOTAL box coordinates.
"""

from pypdf import PdfReader
import re

pdf_path = r"L:/Confirmation/invoice_BLANK.pdf"
reader = PdfReader(pdf_path)
page = reader.pages[0]

print(f"PAGE: {float(page.mediabox.width)} x {float(page.mediabox.height)} points\n")

# Extract raw content stream
if "/Contents" in page:
    content = page["/Contents"]
    if hasattr(content, 'get_object'):
        content = content.get_object()
    if hasattr(content, 'get_data'):
        data = content.get_data()
        text = data.decode('latin-1', errors='replace')
        
        # Find all rectangle definitions
        print("ALL RECTANGLES FOUND (sorted by Y coordinate):")
        rect_pattern = r'(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+re'
        rects = []
        for match in re.finditer(rect_pattern, text):
            x, y, w, h = [float(m) for m in match.groups()]
            x1, y1 = x + w, y + h
            rects.append((y, x, y1, x1, w, h))
        
        # Sort by Y (bottom coordinate) descending to see from top to bottom
        rects.sort(reverse=True)
        
        for y, x, y1, x1, w, h in rects:
            print(f"  X:[{x:7.1f}-{x1:7.1f}]  Y:[{y:7.1f}-{y1:7.1f}]  Size: {w:.1f}x{h:.1f}")
        
        print("\n" + "="*80)
        print("KEY BOXES (likely):")
        print("="*80)
        
        # Group boxes by vertical proximity to identify sections
        # CHARGES box should be in lower middle area
        # TOTAL should be below that
        
        for y, x, y1, x1, w, h in rects:
            # Look for boxes in the vertical range where CHARGES and TOTAL appear
            # Rough estimate: CHARGES around Y 350-450, TOTAL around Y 300-350
            if 250 < y < 500:
                size_desc = "LARGE" if w > 200 else "MEDIUM" if w > 100 else "SMALL"
                print(f"  {size_desc:8} | X:[{x:7.1f}-{x1:7.1f}]  Y:[{y:7.1f}-{y1:7.1f}]  ({w:.1f}x{h:.1f})")

print("\nTo place text in boxes:")
print("1. Text should be drawn inside box boundaries (not just at X,Y)")
print("2. Y-coord: text baseline should be near bottom of box, with margin")
print("3. Box height tells us if multi-line text fits")
