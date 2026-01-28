"""
Extract complete 2012 T4 data from CRA Copy PDF.
Captures all T4 boxes with values in proper CRA format:
- Last name, First name, Initials
- Full address and postal code
- All T4 box amounts (14, 22, 54, 10, 16, 24, 26, 18, 44, 20, 46, 52, 50, etc.)
"""
import pdfplumber
import re
import csv

PDF_PATH = r"L:\limo\pdf\2012\2012 CRA Copy of T4's_ocred.pdf"
OUTPUT_CSV = r"l:\limo\data\2012_cra_t4_complete_extraction.csv"

# T4 Box definitions (common boxes)
T4_BOXES = {
    '14': 'Employment income',
    '22': 'Income tax deducted',
    '16': 'Employee CPP contributions',
    '18': 'Employee EI premiums',
    '24': 'EI insurable earnings',
    '26': 'CPP/QPP pensionable earnings',
    '44': 'Union dues',
    '20': 'RPP contributions',
    '46': 'Charitable donations',
    '52': 'Pension adjustment',
    '50': 'RPP or DPSP registration number',
    '10': 'Province of employment',
    '12': 'Social insurance number',
    '28': 'Employee QPP contributions',
    '29': 'Employment code',
    '17': 'CPP/QPP pensionable earnings',
    '55': 'Employee PPIP premiums',
    '56': 'PPIP insurable earnings',
}

def extract_all_t4_data(pdf_path):
    """Extract complete T4 data from all pages."""
    t4_records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Processing {len(pdf.pages)} pages...")
        
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue
            
            # Each page can have 1 or 2 T4 slips
            # Split by T4 (11) marker or look for employee name patterns
            
            # Find all T4 sections on the page
            sections = text.split('T4 (11)')
            
            for section_idx, section in enumerate(sections):
                if not section.strip() or 'Arrow Limousine' not in section:
                    continue
                
                lines = [l.strip() for l in section.split('\n') if l.strip()]
                
                # Extract data
                record = {
                    'page': page_num,
                    'section': section_idx,
                    'last_name': None,
                    'first_name': None,
                    'initials': None,
                    'full_address': [],
                    'postal_code': None,
                    'sin': None,
                }
                
                # Initialize all T4 boxes
                for box_num in T4_BOXES.keys():
                    record[f'box_{box_num}'] = None
                
                i = 0
                while i < len(lines):
                    line = lines[i]
                    
                    # Extract Box 14 (Employment income) - first amount after "14 22"
                    if '14 22' in line and not record['box_14']:
                        # Look for amounts on next line or same line
                        amounts = re.findall(r'\b(\d{1,6}\.\d{2})\b', line)
                        if len(amounts) >= 2:
                            record['box_14'] = amounts[0]
                            record['box_22'] = amounts[1]
                        elif i + 1 < len(lines):
                            next_line = lines[i + 1]
                            amounts = re.findall(r'\b(\d{1,6}\.\d{2})\b', next_line)
                            if len(amounts) >= 2:
                                record['box_14'] = amounts[0]
                                record['box_22'] = amounts[1]
                    
                    # Extract Box 54, 10, 16, 24 line
                    if '54 10 16 24' in line:
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            # Pattern: 861556827RP0001 AB 189.25 4279.60
                            parts = next_line.split()
                            for part in parts:
                                if part == 'AB' or part == 'BC' or part == 'ON':
                                    record['box_10'] = part
                                elif re.match(r'^\d+\.\d{2}$', part):
                                    if not record['box_16']:
                                        record['box_16'] = part  # CPP contributions
                                    elif not record['box_24']:
                                        record['box_24'] = part  # EI insurable earnings
                    
                    # Extract SIN (12), 28, 29, 17, 26 line
                    if '12 28 29 17 26' in line:
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            # Pattern: 627 754 336 4279.60 or 627 754 336 x 4279.60
                            sin_match = re.search(r'(\d{3})\s+(\d{3})\s+(\d{3})', next_line)
                            if sin_match:
                                record['sin'] = ''.join(sin_match.groups())
                            # Look for pensionable earnings (last amount)
                            amounts = re.findall(r'\b(\d{1,6}\.\d{2})\b', next_line)
                            if amounts:
                                record['box_26'] = amounts[-1]  # Last amount is pensionable earnings
                    
                    # Extract Box 18, 44 line (EI premiums, Union dues)
                    if '18 44' in line:
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            amounts = re.findall(r'\b(\d{1,6}\.\d{2})\b', next_line)
                            if amounts:
                                record['box_18'] = amounts[0]  # EI premiums
                    
                    # Extract employee name (LASTNAME Firstname format)
                    # Look for pattern after "Last name (in capital letters)"
                    if 'Last name (in capital letters)' in line or 'LASTNAME' in line:
                        if i + 1 < len(lines):
                            name_line = lines[i + 1]
                            # Pattern: BLADES Michael or BOULLEY Kevin
                            name_parts = name_line.split()
                            if len(name_parts) >= 2 and name_parts[0].isupper():
                                record['last_name'] = name_parts[0]
                                record['first_name'] = name_parts[1] if len(name_parts) > 1 else ''
                                record['initials'] = name_parts[2] if len(name_parts) > 2 else ''
                    
                    # Extract address lines (after name, before "Pension adjustment")
                    if record['last_name'] and not record['postal_code']:
                        # Look for address pattern
                        if re.search(r'\d+.*(?:Street|Avenue|Crescent|Road|Drive|Court|Place)', line, re.IGNORECASE):
                            record['full_address'].append(line)
                        # Look for city, province pattern
                        elif re.match(r'Red Deer,?\s*AB', line, re.IGNORECASE):
                            record['full_address'].append(line)
                        # Look for postal code
                        elif re.match(r'T\d[A-Z]\s*\d[A-Z]\d', line):
                            record['postal_code'] = line
                    
                    # Extract Box 20, 46 (RPP contributions, Charitable donations)
                    if '20 46' in line:
                        # These are usually blank but check next line
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            amounts = re.findall(r'\b(\d{1,6}\.\d{2})\b', next_line)
                            if amounts:
                                record['box_20'] = amounts[0]
                                if len(amounts) > 1:
                                    record['box_46'] = amounts[1]
                    
                    # Extract Box 52, 50 (Pension adjustment, RPP registration)
                    if '52 50' in line:
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            amounts = re.findall(r'\b(\d{1,6}\.\d{2})\b', next_line)
                            if amounts:
                                record['box_52'] = amounts[0]
                    
                    i += 1
                
                # Only add record if we found a name
                if record['last_name']:
                    # Join address lines
                    record['address'] = ', '.join(record['full_address']) if record['full_address'] else ''
                    del record['full_address']
                    t4_records.append(record)
                    print(f"  Found: {record['last_name']}, {record['first_name']} - SIN: {record['sin']} - Box 14: ${record['box_14']}")
    
    return t4_records

def save_to_csv(records, output_path):
    """Save T4 records to CSV."""
    if not records:
        print("No records to save")
        return
    
    # Get all fieldnames
    fieldnames = ['page', 'section', 'last_name', 'first_name', 'initials', 'sin', 
                  'address', 'postal_code']
    
    # Add all box fields
    box_fields = [f'box_{num}' for num in sorted(T4_BOXES.keys(), key=lambda x: int(x))]
    fieldnames.extend(box_fields)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    
    print(f"\n[OK] Saved {len(records)} T4 records to: {output_path}")

def print_summary(records):
    """Print summary statistics."""
    print("\n" + "="*80)
    print("2012 CRA T4 EXTRACTION SUMMARY")
    print("="*80)
    
    print(f"\nTotal T4 Slips: {len(records)}")
    
    # Calculate totals
    total_box_14 = sum(float(r['box_14']) if r['box_14'] else 0 for r in records)
    total_box_22 = sum(float(r['box_22']) if r['box_22'] else 0 for r in records)
    total_box_16 = sum(float(r['box_16']) if r['box_16'] else 0 for r in records)
    total_box_18 = sum(float(r['box_18']) if r['box_18'] else 0 for r in records)
    
    print(f"\nTotals:")
    print(f"  Box 14 (Employment Income):    ${total_box_14:>12,.2f}")
    print(f"  Box 22 (Income Tax Deducted):  ${total_box_22:>12,.2f}")
    print(f"  Box 16 (CPP Contributions):    ${total_box_16:>12,.2f}")
    print(f"  Box 18 (EI Premiums):          ${total_box_18:>12,.2f}")
    
    print(f"\nEmployees:")
    for i, r in enumerate(records, 1):
        name = f"{r['last_name']}, {r['first_name']}"
        if r['initials']:
            name += f" {r['initials']}"
        print(f"  {i:2d}. {name:<35s} SIN: {r['sin']:<11s} Box 14: ${float(r['box_14']) if r['box_14'] else 0:>10,.2f}")

if __name__ == '__main__':
    print("="*80)
    print("2012 CRA T4 COMPLETE EXTRACTION")
    print("="*80)
    print(f"Source: {PDF_PATH}")
    print(f"Output: {OUTPUT_CSV}")
    print()
    
    # Extract data
    records = extract_all_t4_data(PDF_PATH)
    
    # Save to CSV
    save_to_csv(records, OUTPUT_CSV)
    
    # Print summary
    print_summary(records)
    
    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)
