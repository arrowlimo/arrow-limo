import os
from pathlib import Path

input_dir = Path("L:\\limo\\data")
text_files = sorted([f for f in input_dir.glob('2014_cibc_nov_dec_page*.txt')])

print("Checking which pages contain Nov or Dec:\n")

for text_file in text_files:
    with open(text_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_nov = 'Nov' in content or 'November' in content.upper()
    has_dec = 'Dec' in content or 'December' in content.upper()
    
    # Find month mentioned in header
    month = "Unknown"
    if "Sep" in content[:500]:
        month = "September"
    elif "Oct" in content[:500]:
        month = "October"
    elif has_nov:
        month = "November"
    elif has_dec:
        month = "December"
    
    if has_nov or has_dec:
        print(f"✓ {text_file.name:30} {month}")
