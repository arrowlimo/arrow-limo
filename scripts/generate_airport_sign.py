"""
Airport Sign Generator - Create printable airport pickup signs
Generates PDF with Arrow Limousine branding and client name in large Magoo-style font
"""
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors


def generate_airport_sign(client_name: str, reserve_number: str = "", output_path: str = None) -> str:
    """
    Generate airport pickup sign PDF with Arrow Limousine branding
    
    Args:
        client_name: Name to display on sign
        reserve_number: Optional reservation number
        output_path: Output file path (default: auto-generated in reports/)
    
    Returns:
        Path to generated PDF
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() else "_" for c in client_name)
        output_path = f"L:/limo/reports/airport_sign_{safe_name}_{timestamp}.pdf"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Create PDF (landscape orientation for better visibility)
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter  # 11" x 8.5" in landscape
    
    # === HEADER: Arrow Limousine branding ===
    c.setFont("Helvetica-Bold", 48)
    c.setFillColor(colors.HexColor("#003366"))  # Dark blue
    header_text = "ARROW LIMOUSINE"
    text_width = c.stringWidth(header_text, "Helvetica-Bold", 48)
    c.drawString((width - text_width) / 2, height - 1.2 * inch, header_text)
    
    # Horizontal divider line
    c.setStrokeColor(colors.HexColor("#003366"))
    c.setLineWidth(3)
    c.line(0.5 * inch, height - 1.5 * inch, width - 0.5 * inch, height - 1.5 * inch)
    
    # === CLIENT NAME: Large Magoo-style font (Comic Sans style) ===
    # Use Helvetica-Bold as fallback (Magoo/Comic Sans not always available in ReportLab)
    # For true Magoo font, would need to register TTF file
    c.setFont("Helvetica-Bold", 96)
    c.setFillColor(colors.black)
    
    # Split long names into multiple lines if needed
    name_lines = []
    if len(client_name) > 20:
        words = client_name.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if len(test_line) <= 20:
                line = test_line
            else:
                if line:
                    name_lines.append(line)
                line = word
        if line:
            name_lines.append(line)
    else:
        name_lines = [client_name]
    
    # Center and draw client name(s)
    y_position = height / 2 + (len(name_lines) - 1) * 60
    for line in name_lines:
        text_width = c.stringWidth(line, "Helvetica-Bold", 96)
        c.drawString((width - text_width) / 2, y_position, line.upper())
        y_position -= 120
    
    # === FOOTER: Reservation number and contact info ===
    c.setFont("Helvetica", 24)
    c.setFillColor(colors.HexColor("#666666"))
    
    if reserve_number:
        footer_text = f"Reservation: {reserve_number}"
        text_width = c.stringWidth(footer_text, "Helvetica", 24)
        c.drawString((width - text_width) / 2, 1.8 * inch, footer_text)
    
    # Contact information
    c.setFont("Helvetica", 18)
    contact_text = "403-340-3466 • info@arrowlimo.ca"
    text_width = c.stringWidth(contact_text, "Helvetica", 18)
    c.drawString((width - text_width) / 2, 1.2 * inch, contact_text)
    
    # Horizontal divider line at bottom
    c.setStrokeColor(colors.HexColor("#003366"))
    c.setLineWidth(2)
    c.line(0.5 * inch, 0.9 * inch, width - 0.5 * inch, 0.9 * inch)
    
    # Small print instructions
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#999999"))
    instructions = "Driver: Hold sign at arrivals gate • Customer: Proceed to vehicle"
    text_width = c.stringWidth(instructions, "Helvetica", 12)
    c.drawString((width - text_width) / 2, 0.5 * inch, instructions)
    
    # Save PDF
    c.save()
    
    return output_path


if __name__ == "__main__":
    # Test generation
    import sys
    
    if len(sys.argv) > 1:
        client_name = " ".join(sys.argv[1:])
    else:
        client_name = "John Smith"
    
    pdf_path = generate_airport_sign(client_name, "019760")
    print(f"✅ Airport sign generated: {pdf_path}")
    print("Open with: start", pdf_path)
