"""
Extract exact CHARGES and TOTALS box positions from invoice_BLANK.pdf.
This will show us the precise coordinates where these labels appear.
"""

from pypdf import PdfReader

pdf_path = r"L:/Confirmation/invoice_BLANK.pdf"
reader = PdfReader(pdf_path)
page = reader.pages[0]

print("Extracting text with positions from invoice_BLANK.pdf...\n")

# Try different text extraction methods to find exact positions
text = page.extract_text()
print("FULL TEXT CONTENT:")
print("="*80)
print(text)
print("\n" + "="*80)

# Try to get text with location info
try:
    text_dict = page.extract_text_by_object()
    
    print("\nTEXT OBJECTS WITH POSITIONS:")
    print("="*80)
    
    # Sort by Y coordinate (top to bottom)
    objects_sorted = sorted(
        [obj for obj in text_dict if hasattr(obj, 'bbox')],
        key=lambda obj: -obj.bbox[3],  # Sort by top Y (descending)
    )
    
    for obj in objects_sorted:
        x0, y0, x1, y1 = obj.bbox
        text_content = obj.get_text().strip()
        
        # Highlight key sections
        marker = ""
        if "CHARGES" in text_content.upper():
            marker = " <-- CHARGES"
        elif "TOTAL" in text_content.upper():
            marker = " <-- TOTAL"
        elif "PAYMENT" in text_content.upper():
            marker = " <-- PAYMENT"
        
        if text_content and len(text_content) < 100:
            print(f"Y:[{y1:7.1f}-{y0:7.1f}] X:[{x0:6.1f}-{x1:6.1f}]  '{text_content}'{marker}")
            
except Exception as e:
    print(f"Could not extract with positions: {e}")

print("\n" + "="*80)
print("KEY FINDING: Look for 'CHARGES' and 'TOTAL' labels and their Y coordinates")
print("These Y coords tell us exactly where to place the data inside those boxes")
