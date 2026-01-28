#!/usr/bin/env python
"""Quick check of PDF content and structure"""

import os

pdf_path = r"L:\limo\pdf\2012\2012 quickbooks cibc bank reconciliation detailed_ocred.pdf"

print(f"=== PDF FILE CHECK ===")
print(f"Path: {pdf_path}")
print(f"Exists: {os.path.exists(pdf_path)}")

if os.path.exists(pdf_path):
    size = os.path.getsize(pdf_path)
    print(f"Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
    
    # Try pdfplumber
    try:
        import pdfplumber
        print("\n[OK] pdfplumber is available")
        
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Pages: {len(pdf.pages)}")
            
            # Show first page sample
            if pdf.pages:
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                if text:
                    lines = text.split('\n')
                    print(f"\n=== FIRST PAGE SAMPLE (first 30 lines) ===")
                    for i, line in enumerate(lines[:30]):
                        print(f"{i+1:3d}: {line}")
    except ImportError:
        print("\n[WARN] pdfplumber not installed")
        print("   Install with: pip install pdfplumber")
    except Exception as e:
        print(f"\n[FAIL] Error reading PDF: {e}")

else:
    print("[FAIL] File not found!")
