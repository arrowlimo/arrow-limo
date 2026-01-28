import sys, csv
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("Usage: python summarize_manifest_by_year.py <manifest_csv> <year>")
        return
    manifest = Path(sys.argv[1])
    year = sys.argv[2]
    rows = []
    with manifest.open('r', encoding='utf-8', newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            if year in row['file']:
                rows.append(row)
    # Group by category
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r['category'], []).append(r['file'])
    out_md = manifest.parent / f'summary_{year}.md'
    lines = [f"# Files with '{year}' in name", '', f"Total: {len(rows)}", '']
    for cat, files in sorted(by_cat.items(), key=lambda x: (-len(x[1]), x[0])):
        lines.append(f"## {cat} ({len(files)})")
        for fn in sorted(files):
            lines.append(f"- {fn}")
        lines.append('')
    out_md.write_text('\n'.join(lines), encoding='utf-8')
    print(str(out_md))

if __name__ == '__main__':
    main()
