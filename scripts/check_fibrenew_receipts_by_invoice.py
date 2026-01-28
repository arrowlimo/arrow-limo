import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

nums = ['8487','8488']

with psycopg2.connect(**DB) as cn:
    with cn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, source_system, source_reference, receipt_date, vendor_name,
                   gross_amount, gst_amount, description
            FROM receipts
            WHERE source_reference IN (%s,%s,%s,%s)
               OR description ILIKE %s OR description ILIKE %s
            ORDER BY id
            """,
            (f'FIBRENEW-{nums[0]}', f'FIBRENEW-{nums[1]}', f'FIBRENEW-STATEMENT-{nums[0]}', f'FIBRENEW-STATEMENT-{nums[1]}',
             f'%Invoice {nums[0]}%', f'%Invoice {nums[1]}%')
        )
        rows = cur.fetchall()
        if not rows:
            print('No matching receipts found.')
        else:
            for r in rows:
                print(f"id={r['id']} sys={r['source_system']} ref={r['source_reference']} date={r['receipt_date']} gross={r['gross_amount']} gst={r['gst_amount']} desc={r['description']}")
