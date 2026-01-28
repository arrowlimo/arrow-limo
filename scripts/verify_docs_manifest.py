#!/usr/bin/env python
"""
Verify and catalog the contents of a documents folder.

Outputs:
- CSV manifest: one row per file with path, size, mtime, extension, and flags
- JSON anomalies: duplicates, suspect/corrupted markers, counts by extension/folder
- Markdown summary: quick, human-readable overview

Safe: read-only, no modifications.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime


def human_bytes(n: int) -> str:
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < step:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= step
    return f"{n:.2f} PB"


def is_suspect(filename: str) -> bool:
    lower = filename.lower()
    markers = [
        ".corrupted.",
        "corruption",
        "emergency-backup",
        ".corruption-backup",
        ".corrupted.backup",
        "startup.err.log",
    ]
    return any(m in lower for m in markers)


def is_backup_like(filename: str) -> bool:
    lower = filename.lower()
    return any(
        k in lower for k in ["backup", ".bak", ".old", "~$"]
    )


def hash_file(path: str, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root: str, max_files: int | None = None):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full)
            except FileNotFoundError:
                # Transient file; skip
                continue
            rel = os.path.relpath(full, root)
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            files.append(
                {
                    "relpath": rel.replace("\\", "/"),
                    "fullpath": full,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    "extension": ext or "",
                    "suspect": is_suspect(name),
                    "backup_like": is_backup_like(name),
                }
            )
            if max_files and len(files) >= max_files:
                return files
    return files


def find_duplicates(file_infos: list[dict], max_hash_bytes: int | None = None):
    # First group by size to minimize hashing
    by_size = defaultdict(list)
    for info in file_infos:
        by_size[info["size"]].append(info)

    duplicates = []
    for size, group in by_size.items():
        if len(group) < 2:
            continue
        # Optional short-circuit on extremely large files if max_hash_bytes set
        hash_map = defaultdict(list)
        for info in group:
            full = info["fullpath"]
            try:
                if max_hash_bytes is not None and size > max_hash_bytes:
                    # Use a cheap fingerprint: first and last 64KB + size
                    fp = hashlib.sha256()
                    with open(full, "rb") as f:
                        fp.update(f.read(64 * 1024))
                        try:
                            f.seek(-64 * 1024, os.SEEK_END)
                            fp.update(f.read(64 * 1024))
                        except OSError:
                            pass
                    digest = f"partial:{size}:{fp.hexdigest()}"
                else:
                    digest = hash_file(full)
            except Exception:
                # If hashing fails, skip this file for duplicate logic
                continue
            hash_map[digest].append(info)
        for digest, members in hash_map.items():
            if len(members) > 1:
                duplicates.append(
                    {
                        "size": size,
                        "hash": digest,
                        "files": [m["relpath"] for m in sorted(members, key=lambda x: x["relpath"])],
                    }
                )
    return duplicates


def write_csv(path: str, rows: list[dict]):
    fieldnames = [
        "relpath",
        "size",
        "mtime",
        "extension",
        "suspect",
        "backup_like",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def write_json(path: str, payload: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def write_markdown(path: str, summary: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Docs verification summary\n\n")
        f.write(f"Scanned root: `{summary['root']}`\n\n")
        f.write(f"Scanned at: {summary['timestamp']}\n\n")
        f.write(f"- Files scanned: {summary['files_scanned']}\n")
        f.write(f"- Total size: {summary['total_size_bytes']} bytes ({summary['total_size_human']})\n")
        f.write(f"- Suspect files: {summary['suspect_count']}\n")
        f.write(f"- Backup-like files: {summary['backup_like_count']}\n")
        f.write(f"- Duplicate groups: {summary['duplicate_groups']} (covering {summary['duplicate_files']} files)\n")
        f.write("\n## Top extensions\n\n")
        for ext, cnt in summary["top_extensions"]:
            label = ext or "(no ext)"
            f.write(f"- {label}: {cnt}\n")
        f.write("\n## Outputs\n\n")
        f.write(f"- CSV manifest: `{summary['csv_path']}`\n")
        f.write(f"- JSON anomalies: `{summary['json_path']}`\n")
        f.write(f"- This summary: `{path}`\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify docs folder and produce manifest/anomalies.")
    parser.add_argument("--root", default=str(os.path.join("l:\\", "limo", "docs")), help="Root folder to scan")
    parser.add_argument("--output-dir", default="exports/docs", help="Output directory for reports")
    parser.add_argument("--max-hash-bytes", type=int, default=250 * 1024 * 1024, help="Use partial hashing above this size")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of files (debug)")
    args = parser.parse_args(argv)

    root = args.root
    if not os.path.isdir(root):
        print(f"ERROR: Root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(args.output_dir, f"docs_manifest_{ts}.csv")
    json_path = os.path.join(args.output_dir, f"docs_anomalies_{ts}.json")
    md_path = os.path.join(args.output_dir, f"docs_summary_{ts}.md")

    print(f"Scanning: {root}")
    files = scan(root, max_files=args.limit)
    total_size = sum(f["size"] for f in files)
    suspect = [f for f in files if f["suspect"]]
    backup_like = [f for f in files if f["backup_like"]]

    print(f"Found files: {len(files)}; total size: {human_bytes(total_size)}")
    print(f"Suspect markers: {len(suspect)}; backup-like: {len(backup_like)}")

    # Duplicates (size-based prefilter, then hash)
    print("Detecting duplicates (size-prefilter, hashed within groups)...")
    dups = find_duplicates(files, max_hash_bytes=args.max_hash_bytes)
    dup_files_set = set()
    for grp in dups:
        for rel in grp["files"]:
            dup_files_set.add(rel)
    print(f"Duplicate groups: {len(dups)}; duplicate files: {len(dup_files_set)}")

    # Counts
    ext_counts = Counter(f["extension"] for f in files)
    folder_counts = Counter(os.path.dirname(f["relpath"]) for f in files)

    # Write outputs
    write_csv(csv_path, files)
    anomalies = {
        "root": root,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files_scanned": len(files),
        "total_size_bytes": total_size,
        "suspect_files": [f["relpath"] for f in suspect],
        "backup_like_files": [f["relpath"] for f in backup_like],
        "duplicate_groups": dups,
        "top_extensions": ext_counts.most_common(25),
        "top_folders": folder_counts.most_common(25),
    }
    write_json(json_path, anomalies)

    summary = {
        "root": root,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "files_scanned": len(files),
        "total_size_bytes": total_size,
        "total_size_human": human_bytes(total_size),
        "suspect_count": len(suspect),
        "backup_like_count": len(backup_like),
        "duplicate_groups": len(dups),
        "duplicate_files": len(dup_files_set),
        "top_extensions": ext_counts.most_common(10),
        "csv_path": os.path.abspath(csv_path),
        "json_path": os.path.abspath(json_path),
    }
    write_markdown(md_path, summary)

    # Print console summary
    print("\nSummary:")
    print(f"- Manifest: {summary['csv_path']}")
    print(f"- Anomalies: {summary['json_path']}")
    print(f"- Markdown: {os.path.abspath(md_path)}")
    print(f"- Files: {summary['files_scanned']} | Size: {summary['total_size_human']}")
    print(f"- Suspect: {summary['suspect_count']} | Backup-like: {summary['backup_like_count']}")
    print(f"- Duplicate groups: {summary['duplicate_groups']} (files: {summary['duplicate_files']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
