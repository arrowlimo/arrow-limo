"""
Convert 2012 receipts HTML to PDF using weasyprint
"""

from weasyprint import HTML

print("Converting 2012 receipts HTML to PDF...")

# Convert the HTML file to PDF
HTML('l:\\limo\\2012_receipts_by_vendor.html').write_pdf(
    'l:\\limo\\2012_Receipts_Report_Verified.pdf'
)

print("✅ PDF created: l:\\limo\\2012_Receipts_Report_Verified.pdf")
