import sys, os
from datetime import date
import psycopg2

# Use api.get_db_connection for consistency if available
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
try:
    from api import get_db_connection  # type: ignore
except Exception:
    def get_db_connection():
        return psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', '5432')),
            database=os.environ.get('DB_NAME', 'almsdata'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
        )

def main():
    year = 2012
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            COUNT(*) AS count,
            COALESCE(SUM(gross_amount),0) AS gross_total,
            COALESCE(SUM(gst_amount),0) AS gst_total,
            MIN(receipt_date) AS first_date,
            MAX(receipt_date) AS last_date
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date < %s;
        """,
        (date(year,1,1), date(year+1,1,1))
    )
    row = cur.fetchone()
    print({
        'year': year,
        'count': row[0],
        'gross_total': float(row[1] or 0),
        'gst_total': float(row[2] or 0),
        'first_date': str(row[3]) if row[3] else None,
        'last_date': str(row[4]) if row[4] else None,
    })

    # Optional: sample a few receipts for sanity
    cur.execute(
        """
        SELECT id, receipt_date, vendor_name, gross_amount, gst_amount, category
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date < %s
        ORDER BY receipt_date ASC
        LIMIT 5
        """,
        (date(year,1,1), date(year+1,1,1))
    )
    sample = cur.fetchall()
    print({'sample_first_5': [
        {
            'id': r[0],
            'date': str(r[1]),
            'vendor': r[2],
            'gross': float(r[3] or 0),
            'gst': float(r[4] or 0),
            'category': r[5],
        } for r in sample
    ]})

    # Optional: count by month to see coverage
    cur.execute(
        """
        SELECT to_char(receipt_date, 'YYYY-MM') AS ym, COUNT(*)
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date < %s
        GROUP BY 1
        ORDER BY 1
        """,
        (date(year,1,1), date(year+1,1,1))
    )
    by_month = cur.fetchall()
    print({'by_month': by_month})

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
