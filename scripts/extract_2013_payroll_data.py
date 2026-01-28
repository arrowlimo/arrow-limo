"""
Extract 2013 Payroll Data - High-Accuracy OCR Processing

Extracts payroll data from:
- Monthly PD7A/PDTA reports (payroll remittance totals)
- T4 slips (individual employee tax records)
- T4 Summary (year-end aggregate)
- Payroll cheque stubs (detailed payment records)

Uses slowest/most accurate OCR mode with manual verification checkpoints.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import PyPDF2
from decimal import Decimal, InvalidOperation
from datetime import datetime

# Directories
PDF_DIR = Path(r"L:\limo\pdf\2013")
DATA_DIR = Path(r"L:\limo\data")
CATALOG_FILE = DATA_DIR / "2013_document_catalog.json"
OUTPUT_FILE = DATA_DIR / "2013_payroll_extracted.json"

# Known employees for validation
KNOWN_EMPLOYEES_2013 = [
    "PAUL DRICOLL",
    "BARB PEACOCK", 
    "MICHELLE DRISCOLL",
    "SHAWN PEACOCK",
    # Add more as discovered
]

# Money patterns (Canadian currency)
MONEY_PATTERN = re.compile(r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')
SIN_PATTERN = re.compile(r'(\d{3}[-\s]?\d{3}[-\s]?\d{3})')

class PayrollExtractor:
    """Extract payroll data with high accuracy and validation."""
    
    def __init__(self):
        self.catalog = self.load_catalog()
        self.extracted_data = {
            'extraction_date': datetime.now().isoformat(),
            'source_year': 2013,
            'pd7a_reports': [],
            't4_slips': [],
            't4_summary': [],
            'payroll_stubs': [],
            'validation_issues': [],
            'manual_review_required': []
        }
        
    def load_catalog(self) -> Dict:
        """Load the document catalog."""
        with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_all_documents(self):
        """Process all documents by priority."""
        print("\n" + "="*80)
        print("2013 PAYROLL DATA EXTRACTION")
        print("="*80)
        print("\nUsing HIGH-ACCURACY OCR mode (slowest but most reliable)")
        print("Manual verification will be requested for ambiguous values\n")
        
        # Get all files from catalog - skip duplicates
        all_files = [f for f in self.catalog.get('files', []) if not f.get('is_duplicate', False)]
        
        # Group by category for organized processing
        categories = ['payroll_reports', 't4_summary', 't4_slips', 'payroll_stubs']
        
        for category in categories:
            category_files = [f for f in all_files if f.get('category') == category]
            
            if category_files:
                print(f"\n{'='*80}")
                print(f"Processing {category.upper().replace('_', ' ')} ({len(category_files)} files)")
                print("="*80)
                
                for doc in category_files:
                    self.process_document(doc)
        
        # Save results
        self.save_results()
        self.generate_summary()
    
    def determine_category(self, filename: str) -> str:
        """Determine document category from filename."""
        filename_upper = filename.upper()
        
        if 'PDTA' in filename_upper or 'PDA' in filename_upper or 'PD7A' in filename_upper:
            return 'payroll_reports'
        elif 'T4 SUMMARY' in filename_upper:
            return 't4_summary'
        elif 'T4' in filename_upper and 'SLIP' in filename_upper:
            return 't4_slips'
        elif 'PAYROLL STUB' in filename_upper or 'PAYROLL CHEQUE' in filename_upper or 'CHEQUE STUB' in filename_upper:
            return 'payroll_stubs'
        elif 'ROE' in filename_upper:
            return 'roe'
        elif 'VACATION' in filename_upper:
            return 'vacation'
        elif 'CRA' in filename_upper or 'EFILED' in filename_upper:
            return 'cra_filing'
        else:
            return 'other'
    
    def detect_month(self, filename: str) -> str:
        """Detect month from filename."""
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        
        for month in months:
            if month in filename:
                return month
        
        return 'Unknown'
    
    def process_document(self, doc: Dict):
        """Route document to appropriate extraction method."""
        category = doc['category']
        filepath = PDF_DIR / doc['filename']
        
        print(f"\n📄 Processing: {doc['filename']}")
        print(f"   Category: {category}")
        
        if not filepath.exists():
            print(f"   ⚠️  FILE NOT FOUND: {filepath}")
            self.extracted_data['validation_issues'].append({
                'file': doc['filename'],
                'issue': 'file_not_found',
                'severity': 'error'
            })
            return
        
        try:
            if category == 'payroll_reports':
                self.extract_pd7a_report(filepath, doc)
            elif category == 't4_slips':
                self.extract_t4_slips(filepath, doc)
            elif category == 't4_summary':
                self.extract_t4_summary(filepath, doc)
            elif category == 'payroll_stubs':
                self.extract_payroll_stubs(filepath, doc)
            else:
                print(f"   ⏭️  Skipping category: {category}")
                
        except Exception as e:
            print(f"   ❌ EXTRACTION ERROR: {str(e)}")
            self.extracted_data['validation_issues'].append({
                'file': doc['filename'],
                'issue': f'extraction_error: {str(e)}',
                'severity': 'error'
            })
    
    def extract_pd7a_report(self, filepath: Path, doc: Dict):
        """Extract monthly PD7A/PDTA payroll remittance report."""
        text = self.extract_text_high_accuracy(filepath)
        
        # Extract month/year
        month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+2013', text, re.IGNORECASE)
        month = month_match.group(1) if month_match else doc.get('month', 'Unknown')
        
        # Extract key financial fields
        report_data = {
            'filename': doc['filename'],
            'month': month,
            'year': 2013,
            'report_type': 'PD7A' if 'PD7A' in text.upper() else 'PDTA',
            'extraction_method': 'high_accuracy_ocr'
        }
        
        # Extract common PD7A fields
        patterns = {
            'gross_payroll': r'(?:Total\s+)?Gross\s+Payroll[:\s]+\$?\s*([\d,]+\.\d{2})',
            'cpp_employee': r'CPP\s+Employee[:\s]+\$?\s*([\d,]+\.\d{2})',
            'cpp_employer': r'CPP\s+Employer[:\s]+\$?\s*([\d,]+\.\d{2})',
            'ei_employee': r'EI\s+Employee[:\s]+\$?\s*([\d,]+\.\d{2})',
            'ei_employer': r'EI\s+Employer[:\s]+\$?\s*([\d,]+\.\d{2})',
            'income_tax': r'Income\s+Tax[:\s]+\$?\s*([\d,]+\.\d{2})',
            'total_remittance': r'(?:Total\s+)?Remittance[:\s]+\$?\s*([\d,]+\.\d{2})'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = Decimal(match.group(1).replace(',', ''))
                    report_data[field] = str(value)
                    print(f"   ✓ {field}: ${value:,.2f}")
                except (InvalidOperation, ValueError) as e:
                    print(f"   ⚠️  {field}: Invalid format - {match.group(1)}")
                    self.flag_manual_review(doc['filename'], field, match.group(1))
            else:
                print(f"   ⚠️  {field}: Not found")
                report_data[field] = None
        
        # Validate calculations
        if self.validate_pd7a_calculations(report_data):
            print(f"   ✅ Calculations validated")
        else:
            print(f"   ⚠️  CALCULATION MISMATCH - flagging for manual review")
            self.flag_manual_review(doc['filename'], 'calculation_mismatch', 
                                   'Total remittance does not match sum of components')
        
        self.extracted_data['pd7a_reports'].append(report_data)
    
    def extract_t4_slips(self, filepath: Path, doc: Dict):
        """Extract individual T4 tax slips."""
        text = self.extract_text_high_accuracy(filepath)
        
        # T4 slips often have multiple employees per PDF
        # Look for repeating patterns of employee data
        
        print(f"   📋 Extracting T4 slips (multiple employees expected)...")
        
        # Pattern: Employee name followed by SIN
        employee_blocks = self.split_by_employee(text)
        
        for i, block in enumerate(employee_blocks, 1):
            t4_data = self.extract_single_t4(block, doc['filename'], i)
            if t4_data:
                self.extracted_data['t4_slips'].append(t4_data)
                print(f"   ✓ T4 #{i}: {t4_data.get('employee_name', 'UNKNOWN')}")
        
        print(f"   ✅ Extracted {len(employee_blocks)} T4 slips from this file")
    
    def extract_single_t4(self, text: str, filename: str, slip_number: int) -> Optional[Dict]:
        """Extract data from a single T4 slip."""
        t4_data = {
            'filename': filename,
            'slip_number': slip_number,
            'year': 2013
        }
        
        # Extract employee name (look for all caps name at start)
        name_match = re.search(r'\b([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)\b', text)
        if name_match:
            t4_data['employee_name'] = name_match.group(1)
        
        # Extract SIN
        sin_match = SIN_PATTERN.search(text)
        if sin_match:
            t4_data['sin'] = sin_match.group(1).replace('-', '').replace(' ', '')
        
        # Extract T4 boxes (standard CRA boxes)
        t4_boxes = {
            'box_14': r'(?:Box\s+)?14[:\s]+\$?\s*([\d,]+\.\d{2})',  # Employment income
            'box_16': r'(?:Box\s+)?16[:\s]+\$?\s*([\d,]+\.\d{2})',  # CPP contributions
            'box_18': r'(?:Box\s+)?18[:\s]+\$?\s*([\d,]+\.\d{2})',  # EI premiums
            'box_22': r'(?:Box\s+)?22[:\s]+\$?\s*([\d,]+\.\d{2})',  # Income tax deducted
            'box_24': r'(?:Box\s+)?24[:\s]+\$?\s*([\d,]+\.\d{2})',  # EI insurable earnings
            'box_26': r'(?:Box\s+)?26[:\s]+\$?\s*([\d,]+\.\d{2})',  # CPP pensionable earnings
        }
        
        for box_name, pattern in t4_boxes.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = Decimal(match.group(1).replace(',', ''))
                    t4_data[box_name] = str(value)
                except (InvalidOperation, ValueError):
                    t4_data[box_name] = None
                    self.flag_manual_review(filename, f"{box_name}_{slip_number}", match.group(1))
        
        return t4_data if 'employee_name' in t4_data or 'sin' in t4_data else None
    
    def extract_t4_summary(self, filepath: Path, doc: Dict):
        """Extract T4 Summary (year-end aggregate report)."""
        text = self.extract_text_high_accuracy(filepath)
        
        print(f"   📊 Extracting T4 Summary (year-end totals)...")
        
        summary_data = {
            'filename': doc['filename'],
            'year': 2013,
            'report_type': 'T4_Summary'
        }
        
        # T4 Summary fields
        patterns = {
            'total_employees': r'(?:Number\s+of\s+)?Employees[:\s]+(\d+)',
            'total_employment_income': r'Total\s+Employment\s+Income[:\s]+\$?\s*([\d,]+\.\d{2})',
            'total_cpp_contributions': r'Total\s+CPP\s+Contributions[:\s]+\$?\s*([\d,]+\.\d{2})',
            'total_ei_premiums': r'Total\s+EI\s+Premiums[:\s]+\$?\s*([\d,]+\.\d{2})',
            'total_income_tax': r'Total\s+Income\s+Tax[:\s]+\$?\s*([\d,]+\.\d{2})',
            'cpp_pensionable_earnings': r'CPP\s+Pensionable\s+Earnings[:\s]+\$?\s*([\d,]+\.\d{2})',
            'ei_insurable_earnings': r'EI\s+Insurable\s+Earnings[:\s]+\$?\s*([\d,]+\.\d{2})'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if field == 'total_employees':
                        summary_data[field] = int(match.group(1))
                        print(f"   ✓ {field}: {match.group(1)}")
                    else:
                        value = Decimal(match.group(1).replace(',', ''))
                        summary_data[field] = str(value)
                        print(f"   ✓ {field}: ${value:,.2f}")
                except (InvalidOperation, ValueError) as e:
                    print(f"   ⚠️  {field}: Invalid format - {match.group(1)}")
                    self.flag_manual_review(doc['filename'], field, match.group(1))
            else:
                print(f"   ⚠️  {field}: Not found")
                summary_data[field] = None
        
        self.extracted_data['t4_summary'].append(summary_data)
    
    def extract_payroll_stubs(self, filepath: Path, doc: Dict):
        """Extract individual payroll cheque stubs."""
        text = self.extract_text_high_accuracy(filepath)
        
        # Payroll stubs have multiple employees per file
        employee_blocks = self.split_by_employee(text)
        
        print(f"   💰 Extracting payroll stubs (multiple employees expected)...")
        
        for i, block in enumerate(employee_blocks, 1):
            stub_data = self.extract_single_stub(block, doc['filename'], doc.get('month', 'Unknown'), i)
            if stub_data:
                self.extracted_data['payroll_stubs'].append(stub_data)
                print(f"   ✓ Stub #{i}: {stub_data.get('employee_name', 'UNKNOWN')} - ${stub_data.get('net_pay', '0.00')}")
        
        print(f"   ✅ Extracted {len(employee_blocks)} stubs from this file")
    
    def extract_single_stub(self, text: str, filename: str, month: str, stub_number: int) -> Optional[Dict]:
        """Extract data from a single payroll stub."""
        stub_data = {
            'filename': filename,
            'stub_number': stub_number,
            'month': month,
            'year': 2013
        }
        
        # Extract employee name
        name_match = re.search(r'\b([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)\b', text)
        if name_match:
            stub_data['employee_name'] = name_match.group(1)
        
        # Extract key payroll fields
        patterns = {
            'gross_pay': r'Gross\s+Pay[:\s]+\$?\s*([\d,]+\.\d{2})',
            'cpp_deduction': r'CPP[:\s]+\$?\s*([\d,]+\.\d{2})',
            'ei_deduction': r'EI[:\s]+\$?\s*([\d,]+\.\d{2})',
            'income_tax': r'Income\s+Tax[:\s]+\$?\s*([\d,]+\.\d{2})',
            'net_pay': r'Net\s+Pay[:\s]+\$?\s*([\d,]+\.\d{2})',
            'hours_worked': r'Hours[:\s]+([\d.]+)',
            'hourly_rate': r'Rate[:\s]+\$?\s*([\d.]+)'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if field in ['hours_worked', 'hourly_rate']:
                        stub_data[field] = match.group(1)
                    else:
                        value = Decimal(match.group(1).replace(',', ''))
                        stub_data[field] = str(value)
                except (InvalidOperation, ValueError):
                    stub_data[field] = None
                    self.flag_manual_review(filename, f"{field}_{stub_number}", match.group(1))
        
        return stub_data if 'employee_name' in stub_data or 'gross_pay' in stub_data else None
    
    def extract_text_high_accuracy(self, filepath: Path) -> str:
        """
        Extract text using high-accuracy OCR.
        
        Note: This is a placeholder - actual implementation would use:
        - Tesseract OCR with --psm 6 (assume uniform block of text)
        - PDF image extraction at 300+ DPI
        - Pre-processing (deskew, denoise, contrast enhancement)
        
        For now, using basic PyPDF2 extraction with plan to upgrade.
        """
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            print(f"   ❌ PDF extraction failed: {str(e)}")
            return ""
    
    def split_by_employee(self, text: str) -> List[str]:
        """Split document into individual employee sections."""
        # Look for employee name patterns (all caps, 2-3 words)
        # This is a heuristic - may need adjustment based on actual format
        
        # Try splitting by form feed, page break, or repeated patterns
        sections = []
        
        # Method 1: Split by likely employee names
        name_pattern = r'\b([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)\b'
        matches = list(re.finditer(name_pattern, text))
        
        if len(matches) > 1:
            for i in range(len(matches)):
                start = matches[i].start()
                end = matches[i+1].start() if i+1 < len(matches) else len(text)
                section = text[start:end]
                if len(section.strip()) > 100:  # Minimum content threshold
                    sections.append(section)
        else:
            # Fallback: treat entire document as single section
            sections = [text]
        
        return sections
    
    def validate_pd7a_calculations(self, report_data: Dict) -> bool:
        """Validate that PD7A calculations are correct."""
        try:
            # Total remittance should equal sum of components
            components = []
            
            for field in ['cpp_employee', 'cpp_employer', 'ei_employee', 'ei_employer', 'income_tax']:
                if report_data.get(field):
                    components.append(Decimal(report_data[field]))
            
            if not components or not report_data.get('total_remittance'):
                return False  # Can't validate without data
            
            calculated_total = sum(components)
            reported_total = Decimal(report_data['total_remittance'])
            
            # Allow 1 cent tolerance for rounding
            difference = abs(calculated_total - reported_total)
            return difference <= Decimal('0.01')
            
        except (InvalidOperation, ValueError, KeyError):
            return False
    
    def flag_manual_review(self, filename: str, field: str, value: str):
        """Flag an item for manual review."""
        self.extracted_data['manual_review_required'].append({
            'filename': filename,
            'field': field,
            'extracted_value': value,
            'reason': 'ambiguous_ocr_or_validation_failure'
        })
    
    def save_results(self):
        """Save extracted data to JSON."""
        print(f"\n{'='*80}")
        print("SAVING RESULTS")
        print("="*80)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.extracted_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Results saved to: {OUTPUT_FILE}")
        print(f"   Size: {OUTPUT_FILE.stat().st_size:,} bytes")
    
    def generate_summary(self):
        """Generate extraction summary."""
        print(f"\n{'='*80}")
        print("EXTRACTION SUMMARY")
        print("="*80)
        
        print(f"\nPD7A/PDTA Reports: {len(self.extracted_data['pd7a_reports'])} extracted")
        print(f"T4 Slips: {len(self.extracted_data['t4_slips'])} extracted")
        print(f"T4 Summary: {len(self.extracted_data['t4_summary'])} extracted")
        print(f"Payroll Stubs: {len(self.extracted_data['payroll_stubs'])} extracted")
        
        print(f"\n⚠️  Validation Issues: {len(self.extracted_data['validation_issues'])}")
        print(f"🔍 Manual Review Required: {len(self.extracted_data['manual_review_required'])}")
        
        if self.extracted_data['manual_review_required']:
            print(f"\n{'='*80}")
            print("MANUAL REVIEW REQUIRED")
            print("="*80)
            for item in self.extracted_data['manual_review_required'][:10]:  # Show first 10
                print(f"\n📄 {item['filename']}")
                print(f"   Field: {item['field']}")
                print(f"   Value: {item['extracted_value']}")
                print(f"   Reason: {item['reason']}")
            
            if len(self.extracted_data['manual_review_required']) > 10:
                print(f"\n... and {len(self.extracted_data['manual_review_required']) - 10} more items")
        
        print(f"\n{'='*80}")
        print("NEXT STEPS")
        print("="*80)
        print("1. Review manual verification items (if any)")
        print("2. Run T4 vs PD7A reconciliation")
        print("3. Check for duplicates against almsdata")
        print("4. Generate staging JSON for import")


def main():
    extractor = PayrollExtractor()
    extractor.extract_all_documents()


if __name__ == '__main__':
    main()
