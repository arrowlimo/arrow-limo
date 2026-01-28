#!/usr/bin/env python3
"""Extract 2013 T4 slip values from the CRA PDF.

Inputs:
- PDF path: L:\\limo\\pdf\\2013\\2013 T4 Slips-CRA Copy_ocred (1).pdf

Outputs:
- Prints parsed slips to stdout (CSV-style)
- Writes JSON to reports/T4_2013_PARSED_FROM_PDF.json for inspection

Heuristic: parse each page text and capture key fields by regex near keywords.
Duplicate slips (two copies per page) are deduped by SIN + box14 value.
"""
import json
import re
from pathlib import Path

import pdfplumber

PDF_PATH = Path(r"L:\\limo\\pdf\\2013\\2013 T4 Slips-CRA Copy_ocred (1).pdf")
OUTPUT_JSON = Path(r"L:\\limo\\reports\\T4_2013_PARSED_FROM_PDF.json")

# Map keywords to target fields
BOX_PATTERNS = {
    "t4_employment_income": [
        r"Employment income[^\n]*?([0-9]+[0-9.,]*)",
    ],
    "t4_federal_tax": [
        r"Income tax deducted[^\n]*?([0-9]+[0-9.,]*)",
    ],
    "t4_cpp_contributions": [
        r"CPP.*contributions[^\n]*?([0-9]+[0-9.,]*)",
    ],
    "t4_ei_contributions": [
        r"EI premiums[^\n]*?([0-9]+[0-9.,]*)",
    ],
    "box_24_ei_insurable": [
        r"EI insurable earnings[^\n]*?([0-9]+[0-9.,]*)",
    ],
    "box_26_cpp_pensionable": [
        r"CPP/QPP pensionable earnings[^\n]*?([0-9]+[0-9.,]*)",
    ],
}

SIN_RE = re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b")
NAME_RE = re.compile(r"^[A-Z][A-Za-z'`-]+,\s*[A-Z][A-Za-z'`-]+", re.MULTILINE)


def clean_num(val: str | None):
    if not val:
        return None
    val = val.replace(",", "").strip()
    try:
        return float(val)
    except ValueError:
        return None


def parse_page_text(text: str):
    # Extract SINs from page text (there are two copies per page; duplicates are fine)
    sins = SIN_RE.findall(text)
    sin = sins[0].replace(" ", "") if sins else None

    # Extract name: find first Last, First pattern
    name_match = NAME_RE.search(text)
    name = name_match.group(0) if name_match else None

    fields = {}
    for field, patterns in BOX_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                fields[field] = clean_num(m.group(1))
                break
        if field not in fields:
            fields[field] = None

    return sin, name, fields


def main():
    if not PDF_PATH.exists():
        raise SystemExit(f"PDF not found: {PDF_PATH}")

    slips = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            sin, name, fields = parse_page_text(text)
            if sin and name:
                entry = {
                    "page": i,
                    "sin": sin,
                    "name": name,
                    **fields,
                }
                slips.append(entry)

    # Deduplicate: keep first occurrence per (sin, t4_employment_income)
    deduped = []
    seen = set()
    for s in slips:
        key = (s["sin"], s.get("t4_employment_income"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(deduped, indent=2), encoding="utf-8")

    print("sin,name,employment_income,federal_tax,cpp,ei,box24,box26,page")
    for s in deduped:
        print(
            f"{s['sin']},{s['name']},{s.get('t4_employment_income')},{s.get('t4_federal_tax')},{s.get('t4_cpp_contributions')},{s.get('t4_ei_contributions')},{s.get('box_24_ei_insurable')},{s.get('box_26_cpp_pensionable')},{s['page']}"
        )


if __name__ == "__main__":
    main()
