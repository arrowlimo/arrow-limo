"""High-Accuracy, Deliberately Slow Bank Statement OCR Extraction

Processes 2012 CIBC PDFs whose original OCR was faulty:
  L:\limo\pdf\2012\2012cibc banking jan-mar_ocred.pdf
  L:\limo\pdf\2012\2012cibc banking apr- may_ocred.pdf
  L:\limo\pdf\2012\2012cibc banking jun-dec_ocred.pdf

Pipeline (phased):
  1. Text layer attempt (pdfminer) – fastest & most accurate if available
  2. Rasterization (PyMuPDF) at 600 DPI (optionally 900 DPI for retries)
  3. Highlight removal (HSV masking) + deskew + adaptive threshold variants
  4. Multi-pass Tesseract OCR: numeric columns (whitelist) / description / date
  5. Row segmentation (horizontal projection + column clustering)
  6. Running balance reconstruction & mismatch re-OCR
  7. Interactive confirmation loop for mismatches / low confidence
  8. Deterministic hashing & incremental resume

Deliberate slowness provided by: sequential processing, sleep intervals,
retry backoff, high DPI rendering, multi-variant preprocessing.

Outputs:
  CSV: data/2012_cibc_ocr_output.csv
  Audit JSON: data/2012_cibc_ocr_audit.json
  Backups: reports/ocr_backups/ timestamped folders

NOTE: This is a skeleton; some advanced heuristics / image operations are placeholders.
      Fill indicated TODO sections incrementally to avoid large unverified jumps.
"""

from __future__ import annotations
import os
import sys
import time
import math
import json
import hashlib
import argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

# Optional imports guarded – script should still run to show planned steps
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
except ImportError:  # pdfminer.six not installed yet
    pdfminer_extract_text = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import cv2  # OpenCV
except ImportError:
    cv2 = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    Image = None

DATE_MONTH_MAP = {
    'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04', 'MAY': '05', 'JUN': '06',
    'JUL': '07', 'AUG': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
}

BANK_YEAR = 2012

@dataclass
class OCRConfig:
    dpi_primary: int = 600
    dpi_retry: int = 900
    sleep_between_pages: float = 0.75
    sleep_between_variants: float = 0.4
    max_retries_per_line: int = 3
    low_confidence_threshold: float = 0.90  # placeholder – real confidence integration TODO
    enable_highlight_removal: bool = True
    interactive: bool = True
    month_hint: Optional[str] = None  # e.g. 'JAN', 'FEB' for segmented PDFs

@dataclass
class TransactionLine:
    page: int
    line_index: int
    raw_text: str
    date: Optional[str]
    vendor: Optional[str]
    withdrawal: float
    deposit: float
    pdf_balance: Optional[float]
    calc_balance: Optional[float]
    status: str  # OK / MISMATCH / NEEDS_CONFIRMATION
    source_method: str  # text / ocr
    confidence: float  # placeholder
    hash: str

def sha256_line(parts: List[str]) -> str:
    norm = '|'.join(p.strip() for p in parts)
    return hashlib.sha256(norm.encode('utf-8')).hexdigest()

def attempt_pdfminer_text(pdf_path: Path) -> List[str]:
    """Extract raw text lines using pdfminer if available.
    Returns empty list if pdfminer not installed or fails.
    """
    if not pdfminer_extract_text:
        return []
    try:
        text = pdfminer_extract_text(str(pdf_path))
        # Some statements produce merged lines; keep all non-empty
        lines = [l for l in text.splitlines() if l.strip()]
        return lines
    except Exception:
        return []

def extract_text_blocks_pymupdf(pdf_path: Path) -> List[Tuple[int, str]]:
    """Use PyMuPDF to extract text by blocks preserving order.
    Returns list of (page_number, text_block).
    """
    if not fitz:
        return []
    results: List[Tuple[int, str]] = []
    try:
        doc = fitz.open(str(pdf_path))
        for pno in range(len(doc)):
            page = doc.load_page(pno)
            blocks = page.get_text("blocks")  # (x0,y0,x1,y1,"text",block_no,page_no)
            # Sort blocks top-to-bottom then left-to-right for consistent reading
            blocks_sorted = sorted(blocks, key=lambda b: (round(b[1] / 5)*5, b[0]))
            for b in blocks_sorted:
                txt = b[4].strip()
                if txt:
                    results.append((pno+1, txt))
    except Exception:
        return []
    return results

def extract_words_pymupdf(pdf_path: Path, page_limit: Optional[int] = None) -> Dict[int, List[Dict[str, Any]]]:
    """Extract word-level bounding boxes using PyMuPDF.
    Returns {page_number: [ {x0,y0,x1,y1,text} ]}.
    """
    if not fitz:
        return {}
    out: Dict[int, List[Dict[str, Any]]] = {}
    doc = fitz.open(str(pdf_path))
    pages = range(len(doc)) if page_limit is None else range(min(page_limit, len(doc)))
    for pno in pages:
        page = doc.load_page(pno)
        words = page.get_text("words")  # list of tuples
        word_dicts = []
        for w in words:
            x0,y0,x1,y1,txt,block_no,line_no,word_no = w
            txt = txt.strip()
            if not txt:
                continue
            word_dicts.append({"x0":x0,"y0":y0,"x1":x1,"y1":y1,"text":txt})
        out[pno+1] = word_dicts
    return out

def cluster_column_boundaries(words: List[Dict[str, Any]], expected_columns: int = 5) -> List[Tuple[float,float]]:
    """Cluster x positions into column bands using a simple gap heuristic.
    Returns list of (min_x,max_x) sorted left→right.
    Approach: sort word centers; create a new band when gap exceeds dynamic threshold.
    """
    if not words:
        return []
    centers = sorted([(w['x0'] + w['x1'])/2 for w in words])
    if not centers:
        return []
    # dynamic threshold: median gap * 1.8
    gaps = [centers[i+1]-centers[i] for i in range(len(centers)-1)]
    if not gaps:
        return [(min(centers)-1, max(centers)+1)]
    median_gap = sorted(gaps)[len(gaps)//2]
    threshold = median_gap * 1.8
    bands: List[List[float]] = [[centers[0]]]
    for c in centers[1:]:
        if c - bands[-1][-1] > threshold and len(bands) < expected_columns:
            bands.append([c])
        else:
            bands[-1].append(c)
    ranges: List[Tuple[float,float]] = []
    for b in bands:
        ranges.append((min(b)-25, max(b)+25))  # widen margins
    return ranges

def assign_word_to_column(word: Dict[str, Any], column_ranges: List[Tuple[float,float]]) -> int:
    cx = (word['x0'] + word['x1'])/2
    for idx,(xmin,xmax) in enumerate(column_ranges):
        if xmin <= cx <= xmax:
            return idx
    return -1

def build_rows(words: List[Dict[str, Any]], column_ranges: List[Tuple[float,float]], y_tolerance: float = 4.0) -> List[Dict[str, Any]]:
    """Group words into rows based on y proximity and column assignment."""
    if not words:
        return []
    words_sorted = sorted(words, key=lambda w: (w['y0'], w['x0']))
    rows: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {"y": None, "cells": {}}
    for w in words_sorted:
        col = assign_word_to_column(w, column_ranges)
        if col < 0:
            continue
        if current['y'] is None:
            current['y'] = w['y0']
        # start new row if vertical gap large
        if abs(w['y0'] - current['y']) > y_tolerance:
            rows.append(current)
            current = {"y": w['y0'], "cells": {}}
        current['cells'].setdefault(col, []).append(w['text'])
    if current['cells']:
        rows.append(current)
    return rows

def parse_row_to_transaction(row: Dict[str, Any], month_hint: Optional[str]) -> Optional[TransactionLine]:
    cells = row['cells']
    # Expect columns: 0 Date, 1 Description, 2 Withdrawals, 3 Deposits, 4 Balance
    date_tokens = cells.get(0, [])
    if not date_tokens:
        return None
    raw_date = ' '.join(date_tokens)
    # Accept formats like Jan 3 or Jan 3
    parts = raw_date.replace('\u2013','-').split()
    day = None
    if len(parts) >= 2 and parts[1].isdigit():
        day = parts[1]
    elif len(parts) == 1 and parts[0].isdigit():
        day = parts[0]
    date_str = None
    if day and month_hint:
        date_str = f"{BANK_YEAR}-{DATE_MONTH_MAP.get(month_hint.upper(), '??')}-{int(day):02d}"
    description = ' '.join(cells.get(1, [])).strip()
    if description.lower().startswith('opening balance'):
        # Opening balance row – treat as non-transaction but establish balance
        balance_tokens = cells.get(4, [])
        try:
            bal = float(balance_tokens[-1].replace(',', '')) if balance_tokens else None
        except Exception:
            bal = None
        line_hash = sha256_line([str(date_str), description, '0.00','0.00', str(bal)])
        return TransactionLine(page=-1,line_index=-1,raw_text=description,date=date_str,vendor=description,
                               withdrawal=0.0,deposit=0.0,pdf_balance=bal,calc_balance=bal,status='OPENING',
                               source_method='text',confidence=1.0,hash=line_hash)
    # Withdraw / Deposit / Balance
    withdraw_tokens = cells.get(2, [])
    deposit_tokens = cells.get(3, [])
    balance_tokens = cells.get(4, [])
    def parse_amount(tokens: List[str]) -> float:
        if not tokens:
            return 0.0
        # join digits possibly split (e.g., by OCR) before conversion attempts
        candidate = ''.join(tokens)
        candidate = candidate.replace(',', '')
        try:
            return float(candidate)
        except Exception:
            # fallback attempt last token only
            try:
                return float(tokens[-1].replace(',', ''))
            except Exception:
                return 0.0
    withdrawal = parse_amount(withdraw_tokens)
    deposit = parse_amount(deposit_tokens)
    pdf_balance = None
    if balance_tokens:
        try:
            pdf_balance = float(balance_tokens[-1].replace(',', ''))
        except Exception:
            pdf_balance = None
    if not description:
        return None
    line_hash = sha256_line([str(date_str), description, f"{withdrawal:.2f}", f"{deposit:.2f}", str(pdf_balance)])
    return TransactionLine(page=-1,line_index=-1,raw_text=description,date=date_str,vendor=description,
                           withdrawal=withdrawal,deposit=deposit,pdf_balance=pdf_balance,calc_balance=None,
                           status='UNVERIFIED',source_method='text',confidence=0.0,hash=line_hash)

def render_page_images(pdf_path: Path, cfg: OCRConfig) -> List[Path]:
    if not fitz:
        return []
    doc = fitz.open(str(pdf_path))
    output_dir = Path('reports/ocr_backups') / time.strftime('%Y%m%d_%H%M%S') / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        mat = fitz.Matrix(cfg.dpi_primary / 72, cfg.dpi_primary / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = output_dir / f"page_{page_index+1:03d}.png"
        pix.save(str(img_path))
        image_paths.append(img_path)
        time.sleep(cfg.sleep_between_pages)
    return image_paths

def preprocess_image(image_path: Path, cfg: OCRConfig) -> List[Path]:
    """Return multiple preprocessed variants for robustness."""
    variants = []
    if not cv2:
        return variants
    img = cv2.imread(str(image_path))
    if img is None:
        return variants
    base_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Highlight removal (simple heuristic): convert to HSV, mask saturated bright colors
    if cfg.enable_highlight_removal:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Yellow highlight mask example
        mask_yellow = cv2.inRange(hsv, (20, 40, 120), (35, 255, 255))
        cleaned = img.copy()
        cleaned[mask_yellow > 0] = (255, 255, 255)
        base_gray = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY)

    # Variant A: Adaptive threshold
    var_a = cv2.adaptiveThreshold(base_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 31, 9)
    # Variant B: Otsu
    _, var_b = cv2.threshold(base_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Variant C: Light dilation to thicken thin strokes
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 2))
    var_c = cv2.dilate(var_a, kernel, iterations=1)

    out_dir = image_path.parent / 'variants'
    out_dir.mkdir(exist_ok=True)
    for label, matrix in [('a_adaptive', var_a), ('b_otsu', var_b), ('c_dilate', var_c)]:
        out_path = out_dir / f"{image_path.stem}_{label}.png"
        cv2.imwrite(str(out_path), matrix)
        variants.append(out_path)
        time.sleep(cfg.sleep_between_variants)
    return variants

def ocr_image(img_path: Path, mode: str) -> str:
    if not pytesseract or not Image:
        return ""
    custom_config = ''
    if mode == 'numeric':
        custom_config = '--psm 6 -c tessedit_char_whitelist=0123456789.,-'  # restrict
    elif mode == 'date':
        custom_config = '--psm 6'
    else:
        custom_config = '--psm 6'
    try:
        return pytesseract.image_to_string(Image.open(str(img_path)), config=custom_config)
    except Exception:
        return ''

def segment_rows_and_columns(ocr_text: str) -> List[str]:
    """Split text into candidate transaction rows using conservative heuristics.
    Later improvement: bounding box clustering to reconstruct columns.
    """
    lines: List[str] = []
    for raw in ocr_text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        # Accept lines with a day number and at least one keyword OR lines with multiple amounts
        has_day = any(part.isdigit() and 1 <= int(part) <= 31 for part in stripped.split()[:2])
        amount_like = sum(1 for token in stripped.split() if any(ch.isdigit() for ch in token) and any(d in token for d in ['.', ',']))
        keyword_hit = any(k in upper for k in ['PURCHASE', 'DEPOSIT', 'MEMO', 'WITHDRAW', 'CHEQUE', 'LEASE', 'INSURANCE', 'NSF', 'CORRECTION', 'PAYMENT'])
        if (has_day and keyword_hit) or (amount_like >= 3 and keyword_hit):
            lines.append(stripped)
    return lines

def parse_transaction_line(raw: str, month_hint: Optional[str]) -> Optional[TransactionLine]:
    """Parse a raw line into structured fields.
    Strategy:
      - Identify leading day number.
      - Extract all tokens that look like monetary amounts.
      - Classify amounts: last numeric assumed PDF balance; preceding numeric assumed amount.
      - Determine withdrawal vs deposit by keyword heuristics (improve later with column positioning).
    """
    parts = raw.split()
    if len(parts) < 3:
        return None
    # Leading day
    day = None
    if parts[0].isdigit() and 1 <= int(parts[0]) <= 31:
        day = parts[0]
        parts_work = parts[1:]
    else:
        parts_work = parts
    date_str = None
    if day and month_hint:
        date_str = f"{BANK_YEAR}-{DATE_MONTH_MAP.get(month_hint.upper(), '??')}-{int(day):02d}"
    # Collect numeric tokens preserving order
    numeric_tokens: List[str] = []
    for p in parts_work:
        cleaned = p.replace(',', '')
        if any(ch.isdigit() for ch in cleaned) and any(d in cleaned for d in ['.', '-']):
            # Basic sanity: must have a digit and either a dot or be pure integer > 0
            numeric_tokens.append(p)
    if len(numeric_tokens) < 2:
        return None
    pdf_balance = None
    try:
        pdf_balance = float(numeric_tokens[-1].replace(',', ''))
    except ValueError:
        pdf_balance = None
    amount_token = None
    if len(numeric_tokens) >= 2:
        amount_token = numeric_tokens[-2]
    withdrawal = deposit = 0.0
    upper_raw = raw.upper()
    if amount_token:
        try:
            amt_val = float(amount_token.replace(',', ''))
            if any(k in upper_raw for k in ['PURCHASE', 'WITHDRAW', 'CHEQUE', 'LEASE', 'INSURANCE', 'NSF', 'DEBIT', 'PAYMENT']):
                withdrawal = amt_val
            else:
                deposit = amt_val
        except ValueError:
            pass
    # Vendor: remove numeric tokens and day
    vendor_tokens = []
    for p in parts_work:
        if p not in numeric_tokens:
            vendor_tokens.append(p)
    vendor = ' '.join(vendor_tokens).strip()[:140]
    line_hash = sha256_line([str(date_str), vendor, f"{withdrawal:.2f}", f"{deposit:.2f}", str(pdf_balance)])
    return TransactionLine(page=-1, line_index=-1, raw_text=raw, date=date_str, vendor=vendor or 'UNKNOWN',
                           withdrawal=withdrawal, deposit=deposit,
                           pdf_balance=pdf_balance, calc_balance=None,
                           status='UNVERIFIED', source_method='ocr', confidence=0.0,
                           hash=line_hash)

def compute_running_balances(lines: List[TransactionLine], opening_balance: Optional[float]) -> None:
    balance = opening_balance
    for line in lines:
        if balance is not None:
            balance = balance - line.withdrawal + line.deposit
            line.calc_balance = round(balance, 2)
            if line.pdf_balance is not None and abs(line.calc_balance - line.pdf_balance) < 0.005:
                line.status = 'OK'
            else:
                line.status = 'MISMATCH'
        else:
            line.calc_balance = None
            line.status = 'NO_OPENING'

def interactive_confirm(lines: List[TransactionLine]) -> None:
    if not lines:
        return
    for line in lines:
        if line.status == 'MISMATCH':
            print(f"Mismatch: {line.raw_text}")
            print(f"  Parsed withdrawal={line.withdrawal} deposit={line.deposit} pdf={line.pdf_balance} calc={line.calc_balance}")
            choice = input("[A]ccept / [E]dit / [S]kip? ").strip().upper() or 'A'
            if choice == 'E':
                new_withdraw = input("  Withdrawal (blank keep): ").strip()
                new_deposit = input("  Deposit (blank keep): ").strip()
                new_pdf = input("  PDF Balance (blank keep): ").strip()
                if new_withdraw:
                    line.withdrawal = float(new_withdraw)
                if new_deposit:
                    line.deposit = float(new_deposit)
                if new_pdf:
                    line.pdf_balance = float(new_pdf)
                line.status = 'EDITED'
            elif choice == 'S':
                line.status = 'PENDING_REVIEW'
            else:
                line.status = 'ACCEPTED_MISMATCH'

def write_outputs(lines: List[TransactionLine], output_csv: Path, audit_json: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    audit_json.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open('w', encoding='utf-8') as f:
        f.write('date,vendor,withdrawal,deposit,pdf_balance,calc_balance,status,hash\n')
        for line in lines:
            f.write(f"{line.date or ''},{line.vendor},{line.withdrawal:.2f},{line.deposit:.2f},{'' if line.pdf_balance is None else f'{line.pdf_balance:.2f}'},{'' if line.calc_balance is None else f'{line.calc_balance:.2f}'},{line.status},{line.hash}\n")
    with audit_json.open('w', encoding='utf-8') as f:
        json.dump([asdict(l) for l in lines], f, indent=2)

def process_pdf(pdf_path: Path, cfg: OCRConfig, opening_balance: Optional[float], month_hint: Optional[str]) -> List[TransactionLine]:
    print(f"Processing PDF: {pdf_path}")
    print(f"PyMuPDF available={bool(fitz)} pdfminer_available={bool(pdfminer_extract_text)}")
    # Phase 1: Attempt pdfminer text layer
    text_lines = attempt_pdfminer_text(pdf_path)
    # Phase 1b: If pdfminer empty, attempt PyMuPDF text blocks (often survives highlight overlays)
    if not text_lines:
        block_texts = extract_text_blocks_pymupdf(pdf_path)
        # Flatten blocks into lines
        for _, block in block_texts:
            for bl in block.splitlines():
                if bl.strip():
                    text_lines.append(bl.strip())
    candidate_lines: List[TransactionLine] = []
    # New structured word-based extraction (page-limited for initial run)
    word_pages = extract_words_pymupdf(pdf_path, page_limit=1)  # limit to first page initial
    if not word_pages:
        print("Word-level extraction returned 0 pages (PyMuPDF missing or extraction failed).")
    if word_pages:
        # cluster columns using words of first page (table area heuristics – filter out header lines by requiring digits)
        first_page_words = word_pages.get(1, [])
        print(f"First page words count={len(first_page_words)} sample={first_page_words[:20]}")
        # Attempt table detection: try with cutoff then fallback to all words if too few
        table_words = [w for w in first_page_words if w['y0'] > 200]
        if len(table_words) < 50:  # fallback threshold
            table_words = first_page_words
            print("Fallback to all words for column clustering (too few after cutoff).")
        column_ranges = cluster_column_boundaries(table_words)
        if len(column_ranges) >= 4:
            rows = build_rows(table_words, column_ranges)
            for r in rows:
                tx = parse_row_to_transaction(r, month_hint)
                if tx:
                    candidate_lines.append(tx)
            print(f"Structured extraction page1: columns={column_ranges} rows={len(rows)} parsed={len(candidate_lines)}")
    if not candidate_lines and text_lines:
        for raw in text_lines:
            parsed = parse_transaction_line(raw, month_hint)
            if parsed:
                parsed.source_method = 'text'
                candidate_lines.append(parsed)
        print(f"Fallback line-based produced {len(candidate_lines)} candidates.")
    else:
        print("No usable text layer – falling back to raster OCR.")
        image_paths = render_page_images(pdf_path, cfg)
        for img_path in image_paths:
            variants = preprocess_image(img_path, cfg) or [img_path]
            # Combine OCR of variants – pick longest text as heuristic
            ocr_combined = ''
            for v in variants:
                txt_variant = ocr_image(v, 'full')
                if len(txt_variant) > len(ocr_combined):
                    ocr_combined = txt_variant
            segmented = segment_rows_and_columns(ocr_combined)
            for raw in segmented:
                parsed = parse_transaction_line(raw, month_hint)
                if parsed:
                    candidate_lines.append(parsed)
            print(f"Page {img_path.name} variants -> {len(segmented)} segmented lines, {len(candidate_lines)} cumulative.")
    compute_running_balances(candidate_lines, opening_balance)
    if cfg.interactive:
        interactive_confirm(candidate_lines)
    return candidate_lines

def main():
    parser = argparse.ArgumentParser(description='High-accuracy, slow OCR for 2012 CIBC statements.')
    parser.add_argument('--pdf', action='append', help='PDF path(s) to process')
    parser.add_argument('--month-hint', help='Month abbreviation (e.g., JAN) if file covers a single segment')
    parser.add_argument('--opening-balance', type=float, help='Opening balance for first line')
    parser.add_argument('--no-interactive', action='store_true', help='Disable interactive confirmation')
    parser.add_argument('--output-csv', default='l:/limo/data/2012_cibc_ocr_output.csv')
    parser.add_argument('--audit-json', default='l:/limo/data/2012_cibc_ocr_audit.json')
    args = parser.parse_args()

    cfg = OCRConfig(interactive=not args.no_interactive, month_hint=args.month_hint)

    if not args.pdf:
        print('No PDFs specified. Example usage:')
        print('  python scripts/extract_bank_statement_transactions.py --pdf "L:/limo/pdf/2012/2012cibc banking jan-mar_ocred.pdf" --opening-balance 7177.34')
        sys.exit(1)

    all_lines: List[TransactionLine] = []
    opening = args.opening_balance
    for pdf in args.pdf:
        pdf_path = Path(pdf)
        if not pdf_path.exists():
            print(f"PDF not found: {pdf_path}")
            continue
        lines = process_pdf(pdf_path, cfg, opening, cfg.month_hint)
        # After first PDF, opening balance becomes last calc balance for continuity if present
        if lines and lines[-1].calc_balance is not None:
            opening = lines[-1].calc_balance
        all_lines.extend(lines)
        # Slow intentional pause between PDFs
        time.sleep(2.0)

    write_outputs(all_lines, Path(args.output_csv), Path(args.audit_json))
    print(f"Written {len(all_lines)} lines to {args.output_csv}")
    print(f"Audit JSON: {args.audit_json}")
    mismatches = sum(1 for l in all_lines if l.status.startswith('MISMATCH'))
    print(f"Mismatches flagged: {mismatches}")
    print("Next TODOs: refine parse_transaction_line, add bounding box based segmentation, integrate real confidence scores.")

if __name__ == '__main__':
    main()
