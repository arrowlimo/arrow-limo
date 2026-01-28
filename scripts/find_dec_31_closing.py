import pdfplumber
import re

with pdfplumber.open("L:\\limo\\pdf\\2014\\2014 cibc3 8362.pdf") as pdf:
    # Search through all pages for Dec 31 and closing balance
    for page_num in range(len(pdf.pages)-1, max(0, len(pdf.pages)-5), -1):
        page = pdf.pages[page_num]
        text = page.extract_text()
        
        if 'Dec 31' in text or 'Closing balance' in text:
            print(f"\n=== PAGE {page_num+1} ===\n")
            lines = text.split('\n')
            
            # Find and print lines with Dec 31 or Closing balance
            for i, line in enumerate(lines):
                if 'Dec 31' in line or 'Closing balance' in line:
                    # Print context (5 lines before and after)
                    start = max(0, i-5)
                    end = min(len(lines), i+6)
                    for j in range(start, end):
                        marker = ">>> " if j == i else "    "
                        print(f"{marker}{lines[j]}")
                    print()
