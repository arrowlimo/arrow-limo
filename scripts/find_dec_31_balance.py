import pdfplumber

with pdfplumber.open("L:\\limo\\pdf\\2014\\2014 cibc3 8362.pdf") as pdf:
    # Get last page
    last_page = pdf.pages[-1]
    text = last_page.extract_text()
    
    # Print last 40 lines to find closing balance
    lines = text.split('\n')
    print("Last page content (bottom 40 lines):\n")
    for line in lines[-40:]:
        print(line)
