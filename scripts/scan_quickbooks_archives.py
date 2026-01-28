import os
import re
import csv
import zipfile
from pathlib import Path
from datetime import datetime


SEARCH_ROOTS = [
    r"l:\\limo\\quickbooks",
    r"l:\\limo\\new_system\\backups\\guickbooks",
    r"l:\\limo\\docs\\oldalms\\COMPLETE-AUDIT-TRAIL",
    r"l:\\limo\\new_system\\backups\\oldalms\\COMPLETE-AUDIT-TRAIL",
    r"l:\\limo\\backups\\weekly_archives",
]

ZIP_GLOBS = [
    "**/*.zip",
]

QB_EXTS = {".qbb", ".qbm", ".qbw", ".iif", ".qbo", ".qbj", ".qbx", ".qwc", ".qfx", ".ofx"}
TABULAR_EXTS = {".csv", ".xls", ".xlsx", ".tsv"}

YEAR_REGEX = re.compile(r"\b(200[0-9]|201[0-1])\b")
BYTES_YEAR_REGEX = re.compile(rb"(200[0-9]|201[0-1])")
CONTENT_SNIFF_BYTES = 3_000_000  # read up to ~3 MB for content sniff


def find_zip_files() -> list[Path]:
    zips: list[Path] = []
    for root in SEARCH_ROOTS:
        p = Path(root)
        if not p.exists():
            continue
        for pattern in ZIP_GLOBS:
            zips.extend(p.glob(pattern))
    # Deduplicate, prefer sorted for stable output
    return sorted(set(zips))


def sniff_years_from_name(name: str) -> list[str]:
    years = set(m.group(1) for m in YEAR_REGEX.finditer(name))
    return sorted(years)


def scan_zip(zip_path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                entry_name = info.filename
                ext = Path(entry_name).suffix.lower()
                size = info.file_size
                years = sniff_years_from_name(entry_name)
                contains_2009 = '2009' in years
                category = (
                    'quickbooks' if ext in QB_EXTS else (
                        'tabular' if ext in TABULAR_EXTS else 'other'
                    )
                )
                # Optional content sniff for year markers inside files likely to matter
                content_years = []
                content_contains_2009 = False
                if category in { 'quickbooks', 'tabular' }:
                    try:
                        with zf.open(info, 'r') as fh:
                            data = fh.read(CONTENT_SNIFF_BYTES)
                            found = set(m.group(1).decode('ascii', errors='ignore') for m in BYTES_YEAR_REGEX.finditer(data))
                            if found:
                                content_years = sorted(found)
                                content_contains_2009 = '2009' in content_years
                    except Exception:
                        # ignore content sniff errors
                        pass
                rows.append({
                    'zip_path': str(zip_path),
                    'entry_name': entry_name,
                    'size': size,
                    'ext': ext,
                    'category': category,
                    'years_found': ",".join(years),
                    'contains_2009': contains_2009,
                    'content_years_found': ",".join(content_years),
                    'content_contains_2009': content_contains_2009,
                })
    except zipfile.BadZipFile:
        rows.append({
            'zip_path': str(zip_path),
            'entry_name': '<bad zip file>',
            'size': 0,
            'ext': '',
            'category': 'error',
            'years_found': '',
            'contains_2009': False,
            'content_years_found': '',
            'content_contains_2009': False,
        })
    return rows


def main():
    # Hard block: do not run QuickBooks scans unless explicitly allowed
    if os.environ.get("ALLOW_QUICKBOOKS") != "1":
        print("[blocked] QuickBooks scanning is disabled by policy.")
        return
    out_dir = Path(r"l:\\limo\\reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = out_dir / f"quickbooks_archive_scan_{timestamp}.csv"

    zips = find_zip_files()
    print(f"[scan] Found {len(zips)} zip archives to scan")

    fields = [
        'zip_path', 'entry_name', 'size', 'ext', 'category',
        'years_found', 'contains_2009', 'content_years_found', 'content_contains_2009'
    ]
    count = 0
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for zp in zips:
            rows = scan_zip(zp)
            for r in rows:
                writer.writerow(r)
                count += 1

    print(f"[done] Wrote {count} entries to {out_csv}")


if __name__ == '__main__':
    main()
