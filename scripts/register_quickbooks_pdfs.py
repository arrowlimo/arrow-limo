"""
Register known QuickBooks year-end PDFs into external_documents for audit traceability.
"""
import os
import hashlib
import psycopg2
from datetime import datetime

PDFS = [
    r"L:\\limo\\quickbooks\\Arrow Limousine 2003.pdf",
    r"L:\\limo\\quickbooks\\Arrow Limousine 2004.pdf",
    r"L:\\limo\\quickbooks\\Arrow Limousine 2005.pdf",
    r"L:\\limo\\quickbooks\\Arrow Limousine 2006.pdf",
    r"L:\\limo\\quickbooks\\Arrow Limousine 2007.pdf",
    r"L:\\limo\\quickbooks\\Bal Sheet & comp Jan to Dec 2007.pdf",
    r"L:\\limo\\quickbooks\\arrow dec 21.pdf",
]

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def year_from_name(name: str):
    import re
    m = re.search(r'(20\d{2}|200\d)', name)
    return int(m.group(1)) if m else None


def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )
    cur = conn.cursor()

    # Ensure table exists (safe)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS external_documents (
            id SERIAL PRIMARY KEY,
            doc_type VARCHAR(100) NOT NULL,
            tax_year INTEGER,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_size BIGINT,
            sha256 CHAR(64),
            source_system VARCHAR(100),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sha256)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_external_documents_year ON external_documents(tax_year)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_external_documents_type ON external_documents(doc_type)")

    inserted = 0
    skipped = 0
    missing = 0

    for path in PDFS:
        if not os.path.exists(path):
            missing += 1
            print(f"[FAIL] Missing: {path}")
            continue
        fname = os.path.basename(path)
        size = os.path.getsize(path)
        digest = sha256_file(path)
        year = year_from_name(fname)

        # Insert if not present
        cur.execute(
            """
            INSERT INTO external_documents (
                doc_type, tax_year, file_path, file_name, file_size, sha256, source_system, notes
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            ) ON CONFLICT (sha256) DO NOTHING
            """,
            (
                'QuickBooks Year-End', year, path, fname, size, digest, 'QuickBooks',
                'Imported historical year-end PDF for CRA audit trail'
            )
        )
        if cur.rowcount > 0:
            inserted += 1
            print(f"[OK] Registered: {fname} (year={year}, size={size:,})")
        else:
            skipped += 1
            print(f"↪️  Already registered: {fname}")

    conn.commit()
    print("\nSummary:")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (exists): {skipped}")
    print(f"  Missing files: {missing}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
