import pdfplumber

# Extract PDF pages to text files for parsing
with pdfplumber.open("L:\\limo\\pdf\\2014\\2014 cibc3 8362.pdf") as pdf:
    # Only extract pages that contain Nov-Dec (approximately pages 31-60)
    # Based on structure: ~2 pages per month = pages 21-30 is Oct, pages 31-60 is Nov-Dec
    
    for i in range(30, len(pdf.pages)):  # Start from page 31 (0-indexed = 30)
        page = pdf.pages[i]
        text = page.extract_text()
        
        # Save to file
        output_path = f"L:\\limo\\data\\2014_cibc_nov_dec_page{i+1}.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"Extracted page {i+1}")

print(f"\nExtracted pages 31-60 for Nov-Dec parsing")
