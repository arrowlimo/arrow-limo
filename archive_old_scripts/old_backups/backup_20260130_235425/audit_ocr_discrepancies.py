"""
OCR discrepancy auditor
Compares pdfplumber vs Tesseract OCR text extraction
"""
import json
import re
import subprocess
import os
import tempfile
from pathlib import Path
from datetime import datetime
import pdfplumber

try:
    from PIL import Image
    # Use direct subprocess call instead of pytesseract library
    TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    TESSERACT_AVAILABLE = Path(TESSERACT_CMD).exists()
    if TESSERACT_AVAILABLE:
        print(f"✓ Tesseract found: {TESSERACT_CMD}")
except Exception as e:
    TESSERACT_AVAILABLE = False
    print(f"Warning: {e}")

INVENTORY_PATH = Path(r"L:\limo\reports\PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json")
OUTPUT_JSON = Path(r"L:\limo\reports\OCR_DISCREPANCY_REPORT.json")
OUTPUT_MD = Path(r"L:\limo\reports\OCR_DISCREPANCY_REPORT.md")

CATEGORIES_TO_CHECK = {"T4", "PD7A", "PAYROLL_SUMMARY", "ROE"}


def tesseract_ocr(image_path: str) -> str:
    """Call tesseract directly via subprocess."""
    try:
        result = subprocess.run(
            [TESSERACT_CMD, image_path, "stdout"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except Exception as e:
        return f"[OCR Error: {e}]"


def extract_numeric_tokens(text: str) -> list:
    """Extract numeric values from text."""
    tokens = re.findall(r'\d+(?:\.\d{1,2})?', text)
    return [float(t) for t in tokens]


def analyze_document(doc_path: str, categories: set) -> dict:
    """Analyze a single document."""
    path = Path(doc_path)
    
    # Determine category
    doc_category = None
    for cat in categories:
        if cat in path.name.upper():
            doc_category = cat
            break
    
    if not doc_category:
        return {"file": doc_path, "status": "skip", "reason": "category not recognized"}
    
    if not path.exists():
        return {"file": doc_path, "status": "skip", "reason": "file not found"}
    
    try:
        # Pass A: pdfplumber (text layer)
        pass_a_text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pass_a_text += (page.extract_text() or "") + "\n"
        
        pass_a_tokens = extract_numeric_tokens(pass_a_text)
        pass_a_sum = sum(pass_a_tokens)
        
        # Pass B: Tesseract OCR (if available)
        pass_b_sum = pass_a_sum
        flags = []
        
        if TESSERACT_AVAILABLE:
            try:
                pass_b_text = ""
                with pdfplumber.open(path) as pdf:
                    for i, page in enumerate(pdf.pages):
                        img = page.to_image(resolution=300).original
                        # Save temp image
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                            img.save(tmp.name)
                            ocr_text = tesseract_ocr(tmp.name)
                            pass_b_text += ocr_text + "\n"
                            os.unlink(tmp.name)
                
                pass_b_tokens = extract_numeric_tokens(pass_b_text)
                pass_b_sum = sum(pass_b_tokens)
                
                # Compare sums
                if pass_a_sum > 0 and pass_b_sum > 0:
                    delta = abs(pass_a_sum - pass_b_sum)
                    pct_diff = (delta / max(pass_a_sum, pass_b_sum)) * 100
                    if delta > 1.00 or pct_diff > 0.1:
                        flags.append(f"MISMATCH: ${delta:.2f} ({pct_diff:.2f}%)")
            except Exception as ocr_err:
                flags.append(f"OCR_ERROR: {str(ocr_err)[:50]}")
        
        return {
            "file": doc_path,
            "category": doc_category,
            "pass_a_sum": round(pass_a_sum, 2),
            "pass_b_sum": round(pass_b_sum, 2),
            "flags": flags,
            "status": "analyzed"
        }
    except Exception as e:
        return {
            "file": doc_path,
            "status": "error",
            "error": str(e)
        }


def main():
    """Main entry point."""
    if not INVENTORY_PATH.exists():
        print(f"❌ Inventory not found: {INVENTORY_PATH}")
        return
    
    with open(INVENTORY_PATH) as f:
        inventory = json.load(f)
    
    docs = inventory.get("documents", [])
    print(f"Analyzing {len(docs)} documents")
    print(f"Tesseract available: {TESSERACT_AVAILABLE}\n")
    
    results = []
    for i, doc in enumerate(docs, 1):
        result = analyze_document(doc.get("path"), CATEGORIES_TO_CHECK)
        results.append(result)
        
        if result.get("flags"):
            print(f"[{i}/{len(docs)}] {Path(result['file']).name}: {result['flags']}")
    
    # Save JSON report
    with open(OUTPUT_JSON, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)
    
    # Generate markdown summary
    flagged = [r for r in results if r.get("flags")]
    with open(OUTPUT_MD, 'w') as f:
        f.write(f"# OCR Discrepancy Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Tesseract:** {TESSERACT_AVAILABLE}\n")
        f.write(f"**Total Documents:** {len(docs)}\n")
        f.write(f"**Flagged:** {len(flagged)}\n\n")
        
        if flagged:
            f.write(f"## Issues Found\n")
            for r in flagged:
                f.write(f"- {Path(r['file']).name}: {r['flags']}\n")
    
    print(f"\n✅ Report saved: {OUTPUT_JSON}")
    print(f"✅ Summary saved: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
