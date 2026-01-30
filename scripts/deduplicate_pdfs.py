#!/usr/bin/env python3
"""
Deduplicate PDF files in L:\limo\pdf directory
Keep highest resolution version of duplicates
"""
import os
from pathlib import Path
from collections import defaultdict
import hashlib
import pypdf
import csv
import time
from datetime import datetime
import shutil
import psycopg2
import os

# DB connection for staging sync (optional)
DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

def get_pdf_info(pdf_path):
    """Get PDF metadata including page count, size, and text content hash"""
    try:
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            page_count = len(reader.pages)
            
            # Sample first page text for content comparison
            first_page_text = ""
            if page_count > 0:
                try:
                    first_page_text = reader.pages[0].extract_text()[:500]
                except:
                    pass
            
            # Get file size
            file_size = os.path.getsize(pdf_path)
            
            # Calculate content hash (first page text + page count)
            content = f"{first_page_text}_{page_count}".encode('utf-8')
            content_hash = hashlib.md5(content).hexdigest()
            
            return {
                'path': pdf_path,
                'page_count': page_count,
                'file_size': file_size,
                'content_hash': content_hash,
                'first_page_text': first_page_text[:100]
            }
    except Exception as e:
        print(f"  [WARN]  Error reading {pdf_path.name}: {e}")
        return None

def normalize_filename(filename):
    """Normalize filename for comparison (remove OCR suffixes, numeric copy suffixes, etc)."""
    import re
    # Lowercase and normalize common separators first
    name = filename.lower()
    # Unify underscores and dashes to spaces for more resilient grouping
    name = name.replace('_', ' ').replace('-', ' ')
    # Remove common OCR/copy markers
    for token in (
        ' ocred', ' scan', ' copy'
    ):
        name = name.replace(token, '')
    # Collapse extra whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Remove trailing numeric copy markers like " (1)", " (2)", ... at the end
    name = re.sub(r"\s*\(\d+\)$", "", name)
    # Final trim of whitespace
    name = name.strip()
    return name

def analyze_pdfs(pdf_dir: Path):
    """Analyze PDFs and return (groups, analysis, to_delete ordered lists)."""
    # Find all PDFs
    pdf_files = list(pdf_dir.glob('*.pdf'))
    print(f"\nFound {len(pdf_files)} PDF files")

    # Group by normalized filename
    groups = defaultdict(list)
    for pdf_path in pdf_files:
        normalized = normalize_filename(pdf_path.stem)
        groups[normalized].append(pdf_path)

    duplicates_found = 0
    to_delete = []
    analysis = []  # list of dicts for logging

    for normalized_name, files in groups.items():
        if len(files) > 1:
            # Get info for each file
            file_info = []
            for pdf_path in files:
                info = get_pdf_info(pdf_path)
                if info:
                    file_info.append(info)
            if not file_info:
                continue
            # Sort by file size (descending)
            file_info.sort(key=lambda x: x['file_size'], reverse=True)
            keeper = file_info[0]
            losers = file_info[1:]
            for loser in losers:
                to_delete.append(loser['path'])
                duplicates_found += 1
            # Keep structured record
            analysis.append({
                'group': normalized_name,
                'keeper': keeper,
                'losers': losers,
            })

    return groups, analysis, to_delete

def archive_and_log(analysis, archive_root: Path, log_path: Path, sync_staging: bool = True):
    """Archive loser PDFs to archive_root and write CSV log; optionally sync pdf_staging."""
    archive_root.mkdir(parents=True, exist_ok=True)
    with open(log_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp','group','action','keeper_name','keeper_size','loser_name','loser_size','loser_new_path'
        ])
        for rec in analysis:
            keeper = rec['keeper']
            for loser in rec['losers']:
                src = loser['path']
                dst = archive_root / src.name
                # Ensure unique name in archive
                counter = 1
                while dst.exists():
                    dst = archive_root / f"{src.stem}__dup{counter}{src.suffix}"
                    counter += 1
                shutil.move(str(src), str(dst))
                writer.writerow([
                    datetime.utcnow().isoformat(), rec['group'], 'archive',
                    keeper['path'].name, keeper['file_size'], src.name, loser['file_size'], str(dst)
                ])

    # Optional: sync pdf_staging statuses
    if sync_staging:
        try:
            conn = psycopg2.connect(**DSN)
            cur = conn.cursor()
            # For each loser moved, set status to archived_duplicate
            for rec in analysis:
                for loser in rec['losers']:
                    cur.execute(
                        """
                        UPDATE pdf_staging
                        SET status='archived_duplicate', processing_notes = COALESCE(processing_notes,'') || ' | archived duplicate moved to ' || %s
                        WHERE file_name = %s AND status IN ('pending','processed','error')
                        """,
                        (str(archive_root), loser['path'].name)
                    )
            conn.commit()
            cur.close(); conn.close()
        except Exception as e:
            print(f"  [WARN]  Staging sync failed: {e}")

def main():
    pdf_dir = Path('L:/limo/pdf')
    
    print("="*70)
    print("PDF DEDUPLICATION - L:/limo/pdf")
    print("="*70)
    
    if not pdf_dir.exists():
        print(f"[FAIL] Directory not found: {pdf_dir}")
        return
    
    print(f"\nAnalyzing PDF groups...")
    groups, analysis, to_delete = analyze_pdfs(pdf_dir)

    # Pretty print some groups
    for rec in analysis[:10]:
        print(f"\n{'='*70}")
        print(f"GROUP: {rec['group']} ({1+len(rec['losers'])} files)")
        print(f"{'='*70}")
        print(f"  [OK] KEEP {rec['keeper']['path'].name} | {rec['keeper']['file_size']:,} bytes | pages {rec['keeper']['page_count']}")
        for loser in rec['losers']:
            print(f"  [FAIL] DUP  {loser['path'].name} | {loser['file_size']:,} bytes | pages {loser['page_count']}")
    
    # Summary
    print("\n" + "="*70)
    print("DEDUPLICATION SUMMARY")
    print("="*70)
    total_pdfs = sum(1 for _ in Path('L:/limo/pdf').glob('*.pdf'))
    print(f"Total PDFs: {total_pdfs}")
    print(f"Duplicate groups: {sum(1 for files in groups.values() if len(files) > 1)}")
    print(f"Duplicates to remove: {len(to_delete)}")
    print(f"PDFs after cleanup: {total_pdfs - len(to_delete)}")
    
    if to_delete:
        print(f"\n{'='*70}")
        print("FILES MARKED FOR DELETION")
        print(f"{'='*70}")
        for pdf_path in to_delete:
            size_kb = os.path.getsize(pdf_path) / 1024
            print(f"  - {pdf_path.name} ({size_kb:.1f} KB)")
        
        print(f"\n[WARN]  DRY RUN MODE - No files deleted")
        print(f"To archive duplicates, add --apply flag")
        print(f"\nCommand: python scripts/deduplicate_pdfs.py --apply")
    else:
        print(f"\n[OK] No duplicates found!")

if __name__ == "__main__":
    import sys
    
    if '--apply' in sys.argv:
        print("\n[WARN]  APPLY MODE - Will archive duplicate files (keep largest).")
        response = input("Type 'yes' to confirm archiving duplicates: ")
        if response.lower() == 'yes':
            pdf_dir = Path('L:/limo/pdf')
            groups, analysis, to_delete = analyze_pdfs(pdf_dir)
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            archive_root = Path(f'L:/limo/pdf/.duplicates/{ts}')
            log_path = Path(f'L:/limo/pdf/dedupe_log_{ts}.csv')
            print(f"Archiving {len(to_delete)} files to {archive_root} ...")
            archive_and_log(analysis, archive_root, log_path, sync_staging=True)
            print(f"[OK] Archived {len(to_delete)} files. Log: {log_path}")
        else:
            print("[FAIL] Cancelled")
    elif '--canonicalize' in sys.argv:
        # Rename keepers to canonical names by stripping trailing (n) copies when safe
        import re
        pdf_dir = Path('L:/limo/pdf')
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        log_path = Path(f'L:/limo/pdf/canonicalize_log_{ts}.csv')
        print("\n📝 CANONICALIZE MODE - Renaming files to remove trailing (n) suffix when no conflict.")
        changed = 0
        skipped = 0
        with open(log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp','action','old_name','new_name','reason'])
            for pdf_path in pdf_dir.glob('*.pdf'):
                m = re.match(r"^(?P<base>.*)\s\((?P<num>\d+)\)\.pdf$", pdf_path.name, re.IGNORECASE)
                if not m:
                    continue
                target_name = f"{m.group('base')}.pdf"
                target_path = pdf_dir / target_name
                if not target_path.exists():
                    # Perform rename
                    old_name = pdf_path.name
                    pdf_path.rename(target_path)
                    changed += 1
                    writer.writerow([datetime.utcnow().isoformat(),'rename',old_name,target_name,'ok'])
                    # Sync pdf_staging file_name
                    try:
                        conn = psycopg2.connect(**DSN)
                        cur = conn.cursor()
                        cur.execute(
                            """
                            UPDATE pdf_staging
                            SET file_name = %s,
                                processing_notes = COALESCE(processing_notes,'') || ' | canonicalized name from ' || %s
                            WHERE file_name = %s
                            """,
                            (target_name, old_name, old_name)
                        )
                        conn.commit()
                        cur.close(); conn.close()
                    except Exception as e:
                        writer.writerow([datetime.utcnow().isoformat(),'staging_sync_error',old_name,target_name,str(e)])
                else:
                    skipped += 1
                    writer.writerow([datetime.utcnow().isoformat(),'skip',pdf_path.name,target_name,'exists'])
        print(f"[OK] Canonicalization complete. Renamed: {changed}, Skipped: {skipped}. Log: {log_path}")
    else:
        main()
