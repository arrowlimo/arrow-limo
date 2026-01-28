import os
import argparse
import psycopg2
from datetime import datetime

DROP_TABLES = [
    'bank_transactions_staging',
    'email_scanner_staging',
    'ocr_documents_staging',
    'qb_excel_staging',
    'receipts_gst_staging',
    'staging_t4_validation',
]

ARCHIVE_TABLES = [
    'staging_pd7a_year_end_summary',
    'staging_employee_reference_data',
]

SUFFIX = f"_archived_{datetime.now().strftime('%Y%m%d')}"

def conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def exists(cur, name:str) -> bool:
    cur.execute('SELECT to_regclass(%s)', (name,))
    return cur.fetchone()[0] is not None


def main():
    ap = argparse.ArgumentParser(description='Cleanup small staging tables (archive/drop).')
    ap.add_argument('--archive', action='store_true', help='Archive minor staging tables')
    ap.add_argument('--drop', action='store_true', help='Drop tiny/empty test staging tables')
    ap.add_argument('--apply', action='store_true', help='Execute changes; otherwise dry-run')
    args = ap.parse_args()

    do_archive = args.archive
    do_drop = args.drop

    if not do_archive and not do_drop:
        do_archive = do_drop = True

    cn = conn(); cur = cn.cursor()

    print('='*80)
    print('CLEANUP SMALL STAGING TABLES')
    print('='*80)
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'} | Suffix: {SUFFIX}")

    if do_archive:
        print('\nARCHIVE CANDIDATES')
        print('-'*80)
        for t in ARCHIVE_TABLES:
            if not exists(cur, t):
                print(f"{t}: SKIP (missing)")
                continue
            target = t + SUFFIX
            if exists(cur, target):
                print(f"{t}: SKIP (already archived as {target})")
                continue
            cur.execute(f'SELECT COUNT(*) FROM {t}')
            cnt = cur.fetchone()[0]
            print(f"{t}: {cnt:,} rows -> {'RENAMING' if args.apply else 'WOULD RENAME'} to {target}")
            if args.apply:
                cur.execute(f'ALTER TABLE {t} RENAME TO {target}')
                cn.commit()

    if do_drop:
        print('\nDROP CANDIDATES')
        print('-'*80)
        for t in DROP_TABLES:
            if not exists(cur, t):
                print(f"{t}: SKIP (missing)")
                continue
            cur.execute(f'SELECT COUNT(*) FROM {t}')
            cnt = cur.fetchone()[0]
            print(f"{t}: {cnt:,} rows -> {'DROPPING' if args.apply else 'WOULD DROP'}")
            if args.apply:
                cur.execute(f'DROP TABLE {t}')
                cn.commit()

    cur.close(); cn.close()

if __name__ == '__main__':
    main()
