#!/usr/bin/env python3
"""
Normalize vendor names like 'FAST GAS', 'FAY GAS', or 'FAS GAS' to 'Fas Gas' at the start of a line.

Usage examples:
  - Dry-run over CSV/TXT files in repo root:
      python -X utf8 scripts/fix_fas_gas_names.py --paths . --include-ext txt,csv

  - Apply changes with backups:
      python -X utf8 scripts/fix_fas_gas_names.py --paths reports,./,DAVID UPLOADS --include-ext txt,csv --write --backup

The script only rewrites when a line begins with one of: 'FAST GAS', 'FAY GAS', or 'FAS GAS' (case-insensitive).
The remainder of the line is preserved verbatim.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


# Allow running from anywhere by adding repo root to sys.path for consistency with other scripts
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


GLOBAL_PATTERN = re.compile(r"\b(?:FAST|FAY|FAS)\s+GAS\b", re.IGNORECASE)
REPLACEMENT = "Fas Gas"


def normalize_line(line: str) -> Tuple[str, bool]:
    """Replace any 'FAST|FAY|FAS GAS' (word-bounded) with 'Fas Gas'. Return (new_line, changed)."""
    new_line, count = GLOBAL_PATTERN.subn(REPLACEMENT, line)
    return new_line, count > 0


def iter_files(paths: Iterable[str], include_ext: Iterable[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    include_ext_norm = {"." + e.lower().lstrip(".") for e in include_ext}
    for p in paths:
        pth = Path(p)
        if not pth.exists():
            continue
        if pth.is_file():
            if not include_ext_norm or pth.suffix.lower() in include_ext_norm:
                if pth not in seen:
                    seen.add(pth)
                    yield pth
            continue
        for fp in pth.rglob("*"):
            if fp.is_file() and (not include_ext_norm or fp.suffix.lower() in include_ext_norm):
                if fp not in seen:
                    seen.add(fp)
                    yield fp


def read_text_with_fallback(path: Path) -> Tuple[str, str]:
    """Read file contents returning (text, encoding_used)."""
    encodings = ["utf-8", "cp1252", sys.getdefaultencoding()]
    tried = set()
    for enc in encodings:
        if enc in tried:
            continue
        tried.add(enc)
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError:
            continue
    # As a last resort, ignore errors with utf-8
    return path.read_text(encoding="utf-8", errors="ignore"), "utf-8/ignore"


def process_file(path: Path, write: bool, backup: bool) -> Tuple[int, int]:
    """Process a single file. Returns (changed_lines, total_lines)."""
    original_text, enc = read_text_with_fallback(path)
    changed = 0
    total = 0
    lines_out: List[str] = []
    for line in original_text.splitlines(keepends=True):
        total += 1
        new_line, did = normalize_line(line)
        if did:
            changed += 1
        lines_out.append(new_line)
    if write and changed > 0:
        if backup:
            bak = path.with_suffix(path.suffix + ".bak")
            try:
                if bak.exists():
                    bak.unlink()
                bak.write_text(original_text, encoding=enc)
            except Exception:
                # If backup fails, do not block the actual write but warn later
                pass
        Path(path).write_text("".join(lines_out), encoding=enc)
    return changed, total


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--paths",
        type=str,
        default=".",
        help="Comma-separated list of files or directories to scan (default: current directory)",
    )
    ap.add_argument(
        "--include-ext",
        type=str,
        default="txt,csv,sql",
        help="Comma-separated list of file extensions to include (no dots). Empty for all",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="Apply changes to files. If omitted, runs in dry-run mode.",
    )
    ap.add_argument(
        "--backup",
        action="store_true",
        help="Create .bak backups before writing changes.",
    )
    args = ap.parse_args(argv)

    paths = [p.strip() for p in args.paths.split(",") if p.strip()]
    include_ext = [e.strip() for e in args.include_ext.split(",") if e.strip()]

    files = list(iter_files(paths, include_ext))
    total_files = len(files)
    total_changed_files = 0
    total_changed_lines = 0
    total_lines = 0

    print(f"Scanning {total_files} files... (write={args.write}, backup={args.backup})")
    for fp in files:
        try:
            changed, lines = process_file(fp, write=args.write, backup=args.backup)
        except Exception as e:
            print(f"[WARN] Skipped {fp} due to error: {e}")
            continue
        total_lines += lines
        total_changed_lines += changed
        if changed > 0:
            total_changed_files += 1
            print(f"[{'WRITE' if args.write else 'DRY'}] {fp} -> {changed} line(s) updated")

    print(
        f"Done. Files with changes: {total_changed_files}/{total_files}; "
        f"Lines updated: {total_changed_lines}/{total_lines}."
    )
    if not args.write and total_changed_files > 0:
        print("Run again with --write --backup to apply changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
