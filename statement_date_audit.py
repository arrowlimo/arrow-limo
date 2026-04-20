import argparse
import re
from collections import defaultdict
from pathlib import Path


PAGE_RE = re.compile(r"^===\s*PAGE\s*(\d+)\s*===\s*$", re.IGNORECASE)
DATE_RE = re.compile(r"(?<!\d)(\d{2})\s*[/\-]?\s*(\d{2})\s*[/\-]?\s*(\d{2,4})(?!\d)")


def to_year(two_or_four: str) -> int:
    if len(two_or_four) == 4:
        return int(two_or_four)
    yr = int(two_or_four)
    return 2000 + yr if yr <= 30 else 1900 + yr


def normalize_date(mm: str, dd: str, yy: str) -> str:
    year = to_year(yy)
    return f"{int(mm):02d}/{int(dd):02d}/{year:04d}"


def parse_statement_dates(lines):
    current_page = None
    pages_by_date = defaultdict(set)
    evidence = defaultdict(list)

    for idx, line in enumerate(lines, start=1):
        m_page = PAGE_RE.match(line.strip())
        if m_page:
            current_page = int(m_page.group(1))
            continue

        low = line.lower()
        if "statement" in low and "date" in low:
            window_end = min(len(lines), idx + 6)
            for j in range(idx, window_end + 1):
                raw = lines[j - 1]
                for m_date in DATE_RE.finditer(raw):
                    mm, dd, yy = m_date.groups()
                    norm = normalize_date(mm, dd, yy)
                    page = current_page if current_page is not None else -1
                    pages_by_date[norm].add(page)
                    evidence[norm].append((page, j, raw.strip()))

    return pages_by_date, evidence


def main():
    parser = argparse.ArgumentParser(
        description="Audit OCR statement dates for duplicates and pre-2012 pages"
    )
    parser.add_argument(
        "--file",
        default=r"L:\pdf2012 merchant statement globalpayments_ocred.txt",
        help="Path to OCR text file",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=2012,
        help="Minimum statement year to keep (default: 2012)",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f"OCR file not found: {file_path}")

    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    pages_by_date, evidence = parse_statement_dates(lines)

    kept = {}
    excluded = {}
    for dt, pages in pages_by_date.items():
        year = int(dt[-4:])
        if year < args.min_year:
            excluded[dt] = sorted(pages)
        else:
            kept[dt] = sorted(pages)

    print(f"File: {file_path}")
    print(f"Min year: {args.min_year}")
    print("--- Included statement dates ---")
    for dt in sorted(kept):
        print(f"{dt}: pages={kept[dt]}")

    print("--- Duplicate included dates (non-duplication check) ---")
    dup_found = False
    for dt in sorted(kept):
        if len(kept[dt]) > 1:
            dup_found = True
            print(f"{dt}: count={len(kept[dt])} pages={kept[dt]}")
            for ev in evidence[dt][:5]:
                print(f"  evidence page={ev[0]} line={ev[1]} raw='{ev[2]}'")
    if not dup_found:
        print("None")

    print("--- Excluded pre-min-year dates ---")
    for dt in sorted(excluded):
        print(f"{dt}: pages={excluded[dt]}")


if __name__ == "__main__":
    main()
