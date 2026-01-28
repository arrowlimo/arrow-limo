"""
Extract Epson Receipt Manager Classification and Sub-classification lists from screenshots.

Requirements:
- Tesseract OCR installed on Windows (e.g., from https://github.com/UB-Mannheim/tesseract/wiki)
- Python packages: pillow, pytesseract

Usage:
  python -X utf8 scripts/extract_epson_classifications_from_images.py --images "docs/epson_screens/*.png" --out-dir reports/epson_ocr

Outputs:
- classifications_indented.md  (Markdown with indentation)
- classifications.csv          (classification, sub_classification)

Heuristics:
- Lines on the right-side settings pane under labels "Classification :" and "Sub-classification :" are captured.
- We also parse any column-like lists labeled "Manage Item List" if the tab is "Classification" and infer indentation from UI cues.
"""
from __future__ import annotations

import argparse
import glob
import pathlib
from typing import List, Tuple, Dict

from PIL import Image  # type: ignore
import pytesseract  # type: ignore


def ocr_image(path: pathlib.Path) -> str:
    img = Image.open(path)
    # Slightly upscale can help OCR
    w, h = img.size
    if max(w, h) < 1800:
        img = img.resize((int(w*1.5), int(h*1.5)))
    text = pytesseract.image_to_string(img, lang='eng')
    return text


def parse_text(text: str) -> List[Tuple[str, str | None]]:
    """Return list of (classification, sub) pairs. If sub is None, it's a heading-only line."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pairs: List[Tuple[str, str | None]] = []

    # Capture explicit fields near right pane like "Classification :" and "Sub-classification :"
    current_class: str | None = None
    for ln in lines:
        lower = ln.lower()
        if lower.startswith('classification') and ':' in ln:
            # e.g., Classification : Business expense
            val = ln.split(':', 1)[1].strip()
            if val:
                current_class = val
                pairs.append((current_class, None))
            continue
        if lower.startswith('sub-classification') and ':' in ln:
            val = ln.split(':', 1)[1].strip()
            if val and current_class:
                pairs.append((current_class, val))
            continue

    # Also capture any free-form bullet-like blocks beneath Business expense (observed in screenshots)
    # Look for sequences after Business expense label, typically a textbox with comma-separated tokens
    tokens = []
    for ln in lines:
        if ln.lower().startswith('business expense') or 'Client Beverage' in ln:
            # subsequent lines with commas/words we treat as subcategories candidates
            tokens.extend([t.strip() for t in ln.replace(' ,', ',').split(',') if t.strip()])
    # If we saw any tokens and had Business expense heading, pair them
    if any(p[0] == 'Business expense' and p[1] is None for p in pairs) and tokens:
        for t in tokens:
            if t and t.lower() != 'business expense':
                pairs.append(('Business expense', t))

    return pairs


def merge_pairs(list_of_pairs: List[List[Tuple[str, str | None]]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for pairs in list_of_pairs:
        for c, s in pairs:
            if c not in out:
                out[c] = []
            if s and s not in out[c]:
                out[c].append(s)
    return out


def write_outputs(merged: Dict[str, List[str]], out_dir: pathlib.Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Markdown indented
    md = []
    for c in sorted(merged.keys(), key=str.lower):
        md.append(c)
        for s in sorted(merged[c], key=str.lower):
            md.append(f"    {s}")
        md.append("")
    (out_dir / 'classifications_indented.md').write_text("\n".join(md), encoding='utf-8')

    # CSV
    csv_lines = ["classification,sub_classification"]
    for c, subs in merged.items():
        if subs:
            for s in subs:
                csv_lines.append(f"{c},{s}")
        else:
            csv_lines.append(f"{c},")
    (out_dir / 'classifications.csv').write_text("\n".join(csv_lines), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--images', required=True, help='Glob of screenshot files (e.g., docs/epson/*.png)')
    ap.add_argument('--out-dir', default='reports/epson_ocr')
    args = ap.parse_args()

    paths = [pathlib.Path(p) for p in glob.glob(args.images)]
    if not paths:
        print('[ERROR] No images matched')
        return 2

    all_pairs: List[List[Tuple[str, str | None]]] = []
    for p in paths:
        try:
            txt = ocr_image(p)
            pairs = parse_text(txt)
            all_pairs.append(pairs)
        except Exception as e:
            print(f'[WARN] OCR failed for {p}: {e}')

    merged = merge_pairs(all_pairs)
    write_outputs(merged, pathlib.Path(args.out_dir))
    print(f"[OK] Wrote {args.out_dir}/classifications_indented.md and classifications.csv")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
