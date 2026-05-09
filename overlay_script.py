import pypdf
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import os

def create_overlay():
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setStrokeColorRGB(1, 1, 1)
    can.setFillColorRGB(1, 1, 1)
    
    # Define rectangles to cover data areas (estimates based on standard invoice layouts)
    # Coordinates in points (1/72 inch). 0,0 is bottom left.
    # Note: These are rough guesses and might need adjustment based on the actual PDF layout.
    
    # Bill To / Customer values (Top area)
    can.rect(50, 600, 200, 100, fill=1)
    
    # Account/Order/Date/Invoice values (Top right area)
    can.rect(400, 650, 150, 100, fill=1)
    
    # Charges value rows (Middle left)
    can.rect(50, 300, 100, 250, fill=1)
    
    # Description/Amount value rows (Middle right)
    can.rect(150, 300, 400, 250, fill=1)
    
    # Comments value area (Lower middle)
    can.rect(50, 200, 500, 80, fill=1)
    
    # Payments body / Routing body (Bottom area)
    can.rect(50, 100, 250, 80, fill=1)
    can.rect(300, 100, 250, 80, fill=1)
    
    # Net-days line
    can.rect(50, 50, 500, 30, fill=1)
    
    can.save()
    packet.seek(0)
    return packet

path = r'L:/Confirmation/invoice_filled.pdf'
reader = pypdf.PdfReader(path)
writer = pypdf.PdfWriter()

overlay_packet = create_overlay()
overlay_pdf = pypdf.PdfReader(overlay_packet)
overlay_page = overlay_pdf.pages[0]

for i in range(len(reader.pages)):
    page = reader.pages[i]
    if i == 0:
        page.merge_page(overlay_page)
    writer.add_page(page)

with open(path, 'wb') as f:
    writer.write(f)

# Extraction and print
reader = pypdf.PdfReader(path)
text = reader.pages[0].extract_text() or ""
print(text[:1500])
print(f"File size: {os.path.getsize(path)} bytes")
