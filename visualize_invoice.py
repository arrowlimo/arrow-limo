from pypdf import PdfReader
from pypdf.generic import RectangleObject

pdf_path = r"L:/Confirmation/invoice_BLANK.pdf"
reader = PdfReader(pdf_path)
page = reader.pages[0]

print(f"PAGE DIMENSIONS: Width={float(page.mediabox.width)}, Height={float(page.mediabox.height)}")
print()

# Check annotations (form fields)
print("\nANNOTATIONS (Form Fields):")
if "/Annots" in page:
    for annot in page["/Annots"]:
        obj = annot.get_object()
        if "/Rect" in obj:
            rect = obj["/Rect"]
            x0, y0, x1, y1 = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
            subtype = obj.get("/Subtype")
            name = obj.get("/T", "unnamed")
            print(f"  [{x0:6.1f}, {y0:6.1f}, {x1:6.1f}, {y1:6.1f}] {name} ({subtype})")
else:
    print("  No form fields found")

# Try to find specific text labels and their coordinates
print("\nLAYOUT SEARCH (Looking for labels):")
def visitor_body(text, cm, tm, font_dict, font_size):
    if text.strip():
        x = tm[4]
        y = tm[5]
        print(f"  [{x:6.1f}, {y:6.1f}] '{text.strip()}'")

page.extract_text(visitor_text=visitor_body)
