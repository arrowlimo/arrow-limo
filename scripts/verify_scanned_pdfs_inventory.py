#!/usr/bin/env python3
"""
Verify that a list of PDFs exist, are readable, and contain OCR text.
For bank statements, attempt to extract account identifiers and statement period.
"""

import os
import pdfplumber
import re
from datetime import datetime

PDF_LIST = [
    r"L:\limo\pdf\2012cibc banking jun-dec_ocred.pdf",
    r"L:\limo\pdf\2012cibc banking jan-mar_ocred.pdf",
    r"L:\limo\pdf\2012cibc banking apr- may_ocred.pdf",
    r"L:\limo\pdf\2012 YTD Hourly Payroll Remittance_ocred.pdf",
    r"L:\limo\pdf\2012 scotia bank statements_ocred.pdf",
    r"L:\limo\pdf\2012 scotia bank statements 6_ocred.pdf",
    r"L:\limo\pdf\2012 scotia bank statements 5_ocred.pdf",
    r"L:\limo\pdf\2012 scotia bank statements 4_ocred.pdf",
    r"L:\limo\pdf\2012 scotia bank statements 3_ocred.pdf",
    r"L:\limo\pdf\2012 scotia bank statements 2_ocred.pdf",
    r"L:\limo\pdf\2012 quickbooks scotiabank_ocred dec.pdf",
    r"L:\limo\pdf\2012 quickbooks monthly summary4_ocred.pdf",
    r"L:\limo\pdf\2012 quickbooks cibc bank reconciliation summary_ocred.pdf",
    r"L:\limo\pdf\2012 quickbooks cibc bank reconciliation detailed_ocred.pdf",
    r"L:\limo\pdf\2012 quickbook general journal_ocred.pdf",
    r"L:\limo\pdf\2012 merchant statement globalpayments_ocred.pdf",
    r"L:\limo\pdf\2012 merchant statement capital one 5457-4994-2077-9853_ocred.pdf",
]

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def extract_period(text: str):
    if not text:
        return None, None
    m = re.search(r"For\s+([A-Z][a-z]{2})\s+(\d{1,2})\s+to\s+([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(\d{4})", text)
    if m:
        sm, sd, em, ed, yr = m.groups()
        sm_i = MONTH_MAP.get(sm.lower()); em_i = MONTH_MAP.get(em.lower())
        if sm_i and em_i:
            try:
                return datetime(int(yr), sm_i, int(sd)).date(), datetime(int(yr), em_i, int(ed)).date()
            except Exception:
                return None, None
    return None, None

def extract_account(text: str):
    if not text:
        return None, None
    acc = None; branch = None
    m1 = re.search(r"Account number[:\s]+([0-9\-]{5,})", text, re.IGNORECASE)
    if m1:
        acc = m1.group(1).strip()
    m2 = re.search(r"Branch transit number[:\s]+(\d{3,5})", text, re.IGNORECASE)
    if m2:
        branch = m2.group(1).strip()
    # Scotia variants
    if not acc:
        m3 = re.search(r"Account\s*#:?\s*([0-9\-]{5,})", text, re.IGNORECASE)
        if m3:
            acc = m3.group(1).strip()
    if not branch:
        m4 = re.search(r"Transit\s*#:?\s*(\d{3,5})", text, re.IGNORECASE)
        if m4:
            branch = m4.group(1).strip()
    return acc, branch

def analyze_pdf(path: str):
    result = {
        'exists': os.path.exists(path),
        'pages': None,
        'has_text': False,
        'account': None,
        'branch': None,
        'period_start': None,
        'period_end': None,
        'error': None,
    }
    if not result['exists']:
        return result
    try:
        with pdfplumber.open(path) as pdf:
            result['pages'] = len(pdf.pages)
            # Probe first two pages for text and metadata
            for i in range(min(2, result['pages'])):
                page = pdf.pages[i]
                text = page.extract_text() or ''
                if text.strip():
                    result['has_text'] = True
                acc, branch = extract_account(text)
                if acc and not result['account']:
                    result['account'] = acc
                if branch and not result['branch']:
                    result['branch'] = branch
                ps, pe = extract_period(text)
                if ps and not result['period_start']:
                    result['period_start'] = ps
                if pe and not result['period_end']:
                    result['period_end'] = pe
    except Exception as e:
        result['error'] = str(e)
    return result


def main():
    print(f"{'='*100}")
    print("PDF SCAN & OCR VERIFICATION")
    print(f"{'='*100}")
    any_missing = False
    inventory = []
    
    for p in PDF_LIST:
        info = analyze_pdf(p)
        inventory.append((p, info))
        fname = os.path.basename(p)
        if not info['exists']:
            any_missing = True
            print(f"[WARN]  MISSING: {fname}")
            continue
        status = "[OK] OCR text" if info['has_text'] else "[WARN]  No text"
        print(f"📄 {fname} | Pages: {info['pages']} | {status}")
        if info['account'] or info['branch']:
            print(f"   Account: {info['account'] or '-'} | Branch: {info['branch'] or '-'}")
        if info['period_start'] and info['period_end']:
            print(f"   Period: {info['period_start']} to {info['period_end']}")
        if info['error']:
            print(f"   Error: {info['error']}")
    
    # Simple account consistency check for the bank statements
    cibc = [i for i in inventory if 'cibc banking' in i[0].lower()]
    scotia = [i for i in inventory if 'scotia bank statements' in i[0].lower()]
    
    def summarize_group(group, label):
        accs = {i[1]['account'] for i in group if i[1]['account']}
        branches = {i[1]['branch'] for i in group if i[1]['branch']}
        print(f"\n- {label} -")
        print(f"   Unique accounts: {accs or {'(unknown)'}}")
        print(f"   Unique branches: {branches or {'(unknown)'}}")
    
    if cibc:
        summarize_group(cibc, "CIBC PDFs")
    if scotia:
        summarize_group(scotia, "Scotia PDFs")
    
    print("\n[OK] Verification run complete.")

if __name__ == '__main__':
    main()
