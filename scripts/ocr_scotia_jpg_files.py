#!/usr/bin/env python3
"""
OCR Scotia Bank JPG statement files using Tesseract.

Requirements:
    pip install pytesseract pillow
    Install Tesseract-OCR: https://github.com/UB-Mannheim/tesseract/wiki

This script will:
1. Process all JPG files in order
2. Extract text using OCR
3. Save raw OCR output to text files
4. Optionally parse transactions
"""

import os
import re
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("WARNING: pytesseract or Pillow not installed")
    print("Install with: pip install pytesseract pillow")
    print("Also install Tesseract-OCR from: https://github.com/UB-Mannheim/tesseract/wiki")

# List of JPG files to process
JPG_FILES = [
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0001.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0002.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0003.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0004.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0005.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0006.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0007.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0008.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0009.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0010.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0011.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0012.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0013.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0014.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0015.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0016.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0017.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0018.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0019.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0020.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0021.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0022.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0023.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0024.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0025.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0026.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0027.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0028.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0029.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0030.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0031.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0032.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0033.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0034.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0035.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0036.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0037.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0038.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0039.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0040.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0041.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0042.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0043.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0044.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0045.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0046.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0047.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0048.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0049.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0050.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0051.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0052.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0053.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0054.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0055.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0056.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0057.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0058.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0059.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0060.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0061.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0062.jpg",
    r"L:\limo\pdf\2013\2013 scotiabank jpg_0063.jpg",
]

def ocr_image(image_path):
    """Extract text from image using Tesseract OCR."""
    if not HAS_OCR:
        return None
    
    try:
        # Try to set Tesseract path (common Windows location)
        if os.name == 'nt':
            possible_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
        
        # Open image and run OCR
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

def main():
    output_dir = Path(r"L:\limo\data\scotia_ocr_output")
    output_dir.mkdir(exist_ok=True)
    
    print(f"{'='*80}")
    print(f"Scotia Bank JPG OCR Processing")
    print(f"{'='*80}")
    print(f"Files to process: {len(JPG_FILES)}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*80}\n")
    
    if not HAS_OCR:
        print("\nERROR: OCR libraries not available")
        print("\nTo install:")
        print("1. pip install pytesseract pillow")
        print("2. Download Tesseract-OCR from: https://github.com/UB-Mannheim/tesseract/wiki")
        print("3. Install Tesseract-OCR (usually to C:\\Program Files\\Tesseract-OCR)")
        return
    
    all_text = []
    
    for i, jpg_file in enumerate(JPG_FILES, 1):
        if not os.path.exists(jpg_file):
            print(f"[{i:2d}/{len(JPG_FILES)}] MISSING: {os.path.basename(jpg_file)}")
            continue
        
        print(f"[{i:2d}/{len(JPG_FILES)}] Processing: {os.path.basename(jpg_file)}...", end=' ')
        
        text = ocr_image(jpg_file)
        
        if text:
            # Save individual file output
            output_file = output_dir / f"{Path(jpg_file).stem}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(text)
            
            all_text.append(f"\n{'='*80}\n")
            all_text.append(f"FILE: {os.path.basename(jpg_file)}\n")
            all_text.append(f"{'='*80}\n")
            all_text.append(text)
            
            # Count lines
            line_count = len(text.strip().split('\n'))
            print(f"✓ ({line_count} lines)")
        else:
            print("✗ FAILED")
    
    # Save combined output
    combined_file = output_dir / "scotia_all_pages_combined.txt"
    with open(combined_file, 'w', encoding='utf-8') as f:
        f.writelines(all_text)
    
    print(f"\n{'='*80}")
    print(f"OCR Complete!")
    print(f"Individual files: {output_dir}")
    print(f"Combined output: {combined_file}")
    print(f"{'='*80}")
    
    # Show first 500 characters of combined output
    if all_text:
        combined_text = ''.join(all_text)
        print(f"\nFirst 500 characters of output:")
        print(f"{'-'*80}")
        print(combined_text[:500])
        print(f"{'-'*80}")

if __name__ == '__main__':
    main()
