import sys
from pathlib import Path
import csv
from datetime import datetime

IIF_PATH = Path(r"l:\limo\qbb\qbw\limousine.IIF")

# Simple IIF reader: tab-delimited text; headers start with !TYPE, data rows begin with TYPE (e.g., TRNS, SPL, ACCNT)

def parse_iif(path: Path):
    stats = {
        'headers': {},   # e.g., {'TRNS': ['TRNSID', 'TRNSTYPE', ...]}
        'counts': {},    # per record type counts
        'trns_types': {},# TRNSTYPE distribution
        'trns_dates': [],# list of dates for range
        'samples': [],   # first few data rows
    }
    if not path.exists():
        print(f"[FAIL] File not found: {path}")
        sys.exit(1)
    
    def add_count(kind):
        stats['counts'][kind] = stats['counts'].get(kind, 0) + 1
    
    with path.open('r', encoding='utf-8', errors='ignore', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        current_header = None
        for row in reader:
            if not row:
                continue
            first = row[0].strip()
            # Header row: starts with !
            if first.startswith('!'):
                kind = first[1:].strip()  # e.g., '!TRNS' -> 'TRNS'
                stats['headers'][kind] = row
                current_header = (kind, row)
                continue
            # Data row: begins with kind name (e.g., TRNS, SPL, ACCNT, VEND, CUST)
            kind = first
            add_count(kind)
            if len(stats['samples']) < 5:
                stats['samples'].append(row[:10])  # capture first 10 columns for preview
            # Capture TRNS metadata
            if kind == 'TRNS' and 'TRNS' in stats['headers']:
                header = stats['headers']['TRNS']
                # Build name->value mapping where possible
                try:
                    hmap = {h: row[i] if i < len(row) else '' for i, h in enumerate(header)}
                except Exception:
                    hmap = {}
                # TRNSTYPE
                ttype = hmap.get('TRNSTYPE') or hmap.get('TRNS TYPE') or ''
                if ttype:
                    stats['trns_types'][ttype] = stats['trns_types'].get(ttype, 0) + 1
                # DATE
                dstr = hmap.get('DATE') or ''
                if dstr:
                    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            stats['trns_dates'].append(datetime.strptime(dstr, fmt).date())
                            break
                        except Exception:
                            pass
    return stats


def main():
    stats = parse_iif(IIF_PATH)
    print(f"IIF file: {IIF_PATH}")
    print("\nRecord type counts:")
    for k in sorted(stats['counts'].keys()):
        print(f"  {k}: {stats['counts'][k]:,}")
    if stats['trns_types']:
        print("\nTRNS transaction types:")
        for k, v in sorted(stats['trns_types'].items(), key=lambda x: (-x[1], x[0])):
            print(f"  {k}: {v:,}")
    if stats['trns_dates']:
        dmin = min(stats['trns_dates'])
        dmax = max(stats['trns_dates'])
        print(f"\nTRNS date range: {dmin} to {dmax}")
    if stats['samples']:
        print("\nSample rows (first 5, first 10 columns):")
        for i, s in enumerate(stats['samples'], 1):
            print(f"  [{i}] " + " | ".join(s))
    # Show which list headers exist
    if stats['headers']:
        print("\nHeaders found:")
        print("  " + ", ".join(sorted(stats['headers'].keys())))

if __name__ == '__main__':
    main()
