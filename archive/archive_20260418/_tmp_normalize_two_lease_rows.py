import psycopg2
conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor()
try:
    cur.execute('''
        UPDATE receipts
        SET vendor_name = 'LEASE FINANCE GROUP',
            canonical_vendor = 'LEASE FINANCE GROUP',
            gl_account_code = '5150',
            gl_code = '5150',
            category = 'LEASE',
            updated_at = NOW(),
            receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\\n' END ||
                'Easy fix 2026-04-07: normalized vendor/GL/category after lease relink.'
        WHERE receipt_id IN (150730, 150731)
    ''')
    print('normalized_rows', cur.rowcount)
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
