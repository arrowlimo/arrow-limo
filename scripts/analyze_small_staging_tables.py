import os, psycopg2

TABLES = [
    'bank_transactions_staging',
    'email_scanner_staging',
    'ocr_documents_staging',
    'qb_excel_staging',
    'receipts_gst_staging',
    'staging_t4_validation',
    'staging_pd7a_year_end_summary',
    'staging_employee_reference_data',
    'lms_staging_vehicles',
]

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )
    cur = conn.cursor()
    print("SMALL STAGING TABLES ANALYSIS")
    print("="*80)
    results = []
    for t in TABLES:
        cur.execute('SELECT to_regclass(%s)', (t,))
        exists = cur.fetchone()[0] is not None
        print(f"\n{t.upper()}")
        print("-"*80)
        if not exists:
            print("MISSING")
            results.append((t, 'missing', 0, [], None))
            continue
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        count = cur.fetchone()[0]
        cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position""", (t,))
        cols = [r[0] for r in cur.fetchall()]
        print(f"Rows: {count}")
        print(f"Columns ({len(cols)}): {', '.join(cols[:10])}{' ...' if len(cols)>10 else ''}")
        sample = None
        if count:
            cur.execute(f'SELECT * FROM {t} LIMIT 1')
            sample = cur.fetchone()
            if sample:
                print("Sample:")
                for i, col in enumerate(cols[:min(5,len(cols))]):
                    val = sample[i]
                    sval = str(val)[:60] + ('...' if len(str(val))>60 else '') if val is not None else 'NULL'
                    print(f"  {col}: {sval}")
        # Simple recommendation logic
        if count == 0:
            rec = 'DROP (empty)'
        elif count <= 5 and t.endswith('_staging'):
            rec = 'DROP (test remnants)'
        elif t.startswith('staging_') and count < 30:
            rec = 'ARCHIVE (minor staging)'
        else:
            rec = 'KEEP (operational or reference)'
        results.append((t, rec, count, cols, sample))
        print(f"Recommendation: {rec}")
    print("\n"+"="*80)
    print("SUMMARY")
    print("="*80)
    for t, rec, count, _, _ in results:
        print(f"{t}: {count} rows -> {rec}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
