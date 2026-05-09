"""
Detailed PDF structure inspection to find exact Client and Routing boxes.
Uses PDF stream parsing to locate rectangles and their boundaries.
"""

from pypdf import PdfReader
import re

pdf_path = r"L:/Confirmation/invoice_BLANK.pdf"
reader = PdfReader(pdf_path)
page = reader.pages[0]

print(f"PAGE: {float(page.mediabox.width)} x {float(page.mediabox.height)} points")
print()

# Extract raw content stream to find rectangles (re, RG, etc.)
if "/Contents" in page:
    content = page["/Contents"]
    if hasattr(content, 'get_object'):
        content = content.get_object()
    if hasattr(content, 'get_data'):
        data = content.get_data()
        text = data.decode('latin-1', errors='replace')
        
        # Find all rectangle definitions (re = rectangle)
        # Format: x y width height re (stroke rectangle)
        print("RECTANGLES (x y width height re):")
        rect_pattern = r'(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+re'
        for match in re.finditer(rect_pattern, text):
            x, y, w, h = [float(m) for m in match.groups()]
            x1, y1 = x + w, y + h
            print(f"  [{x:7.1f}, {y:7.1f}] -> [{x1:7.1f}, {y1:7.1f}]  (size: {w:.1f}x{h:.1f})")
        print()

# Extract text with positions
print("TEXT OBJECTS (with approximate positions):")
try:
    from pypdf.generic import RectangleObject
    text_dict = page.extract_text_by_object()
    
    # Group by vertical position to identify sections
    objects_by_y = {}
    for obj in text_dict:
        if hasattr(obj, 'bbox'):
            x0, y0, x1, y1 = obj.bbox
            y_key = int(y1)  # Round to nearest point
            if y_key not in objects_by_y:
                objects_by_y[y_key] = []
            objects_by_y[y_key].append((x0, y0, x1, y1, obj.get_text().strip()))
    
    # Print sorted by Y position (top to bottom in PDF = high Y to low Y)
    for y in sorted(objects_by_y.keys(), reverse=True):
        items = objects_by_y[y]
        for x0, y0, x1, y1, text in sorted(items):
            if text:
                print(f"  Y={y:3d}  [{x0:6.1f}-{x1:6.1f}]  '{text[:40]}'")
except Exception as e:
    print(f"  Error: {e}")

print()
print("KEY FINDINGS:")
print("- 'Client' label and box should be near top")
print("- 'ROUTING' section header and box below that")
print("- Exact Y coordinates of boxes will tell us where to place text")
