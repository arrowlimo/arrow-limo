#!/usr/bin/env python
import argparse
from pathlib import Path
import json

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


def list_fields(pdf_path: Path) -> dict:
    if not PdfReader:
        raise RuntimeError('pypdf not available. Install pypdf to inspect PDF fields.')
    reader = PdfReader(str(pdf_path))
    fields = {}
    try:
        fields = reader.get_fields() or {}
    except Exception:
        pass
    return {k: {kk: str(vv) for kk, vv in (v or {}).items()} for k, v in fields.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--out', help='Write JSON of field names')
    args = ap.parse_args()

    pdf = Path(args.pdf)
    info = list_fields(pdf)

    if args.out:
        Path(args.out).write_text(json.dumps(info, indent=2))
        print(f"✅ Wrote {args.out} ({len(info)} fields)")
    else:
        print(json.dumps(info, indent=2))

if __name__ == '__main__':
    main()
