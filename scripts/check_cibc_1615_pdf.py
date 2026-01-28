import pdfplumber

# Check if the file exists and what it contains
try:
    with pdfplumber.open("L:\\limo\\pdf\\2014\\2014 cibc 1615.pdf") as pdf:
        print(f"PDF opened successfully")
        print(f"Total pages: {len(pdf.pages)}\n")
        
        # Check first page for date range and account info
        first_page = pdf.pages[0]
        text = first_page.extract_text()
        
        # Look for date range and account info
        lines = text.split('\n')
        print("First 35 lines of first page:\n")
        for i, line in enumerate(lines[:35]):
            print(line)
except FileNotFoundError:
    print("File not found at L:\\limo\\pdf\\2014\\2014 cibc 1615.pdf")
except Exception as e:
    print(f"Error: {e}")
