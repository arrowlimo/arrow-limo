import os, json, shutil, sys
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("Usage: python move_duplicates_from_manifest.py <source_folder> <anomalies_json>")
        sys.exit(1)
    src = Path(sys.argv[1])
    anomalies = Path(sys.argv[2])
    data = json.loads(anomalies.read_text(encoding='utf-8'))
    dups = data.get('duplicate_groups', {})
    dest = src / 'Duplicates'
    dest.mkdir(exist_ok=True)

    moved = []
    kept = []
    errors = []
    for _hash, files in dups.items():
        if not files:
            continue
        # Keep the first alphabetically, move the rest
        files_sorted = sorted(files)
        keep = files_sorted[0]
        kept.append(keep)
        for fn in files_sorted[1:]:
            src_path = src / fn
            if not src_path.exists():
                continue
            try:
                target = dest / fn
                # If name clash, append a suffix
                if target.exists():
                    stem = target.stem
                    suff = target.suffix
                    i = 1
                    while True:
                        alt = dest / f"{stem} (dup{ i }).{suff.lstrip('.')}"
                        if not alt.exists():
                            target = alt
                            break
                        i += 1
                shutil.move(str(src_path), str(target))
                moved.append(fn)
            except Exception as e:
                errors.append({'file': fn, 'error': str(e)})

    print(json.dumps({
        'kept': kept,
        'moved': moved,
        'errors': errors,
        'dest': str(dest)
    }, indent=2))

if __name__ == '__main__':
    main()
