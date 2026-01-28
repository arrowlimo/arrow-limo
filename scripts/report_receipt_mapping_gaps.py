import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import get_db_connection  # type: ignore

SQL_TOP_PAY_ACCOUNTS = """
SELECT COALESCE(NULLIF(TRIM(pay_account),''),'(blank)') AS pay_account,
       mapping_status,
       COUNT(*) AS cnt,
       SUM(COALESCE(gross_amount,0)) AS total
FROM receipts
GROUP BY 1,2
ORDER BY cnt DESC
LIMIT 50;
"""

SQL_STATUS_COUNTS = """
SELECT mapping_status, COUNT(*) FROM receipts GROUP BY mapping_status ORDER BY 2 DESC;
"""

def main():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(SQL_STATUS_COUNTS)
        status = cur.fetchall()
        print('Status counts:')
        for row in status:
            print(row)

        # Detect whether category column exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='receipts' AND column_name='category'
            )
        """)
        has_category = cur.fetchone()[0]
        top_class_sql = (
            """
            SELECT COALESCE(NULLIF(TRIM(classification),''), '(blank)') AS class,
                   mapping_status,
                   COUNT(*) AS cnt,
                   SUM(COALESCE(gross_amount,0)) AS total
            FROM receipts
            GROUP BY 1,2
            ORDER BY cnt DESC
            LIMIT 50
            """
            if not has_category else
            """
            SELECT COALESCE(NULLIF(TRIM(classification),''), NULLIF(TRIM(category),''), '(blank)') AS class,
                   mapping_status,
                   COUNT(*) AS cnt,
                   SUM(COALESCE(gross_amount,0)) AS total
            FROM receipts
            GROUP BY 1,2
            ORDER BY cnt DESC
            LIMIT 50
            """
        )
        print('\nTop classes/categories:')
        cur.execute(top_class_sql)
        for row in cur.fetchall():
            print(row)

        print('\nTop pay accounts:')
        cur.execute(SQL_TOP_PAY_ACCOUNTS)
        for row in cur.fetchall():
            print(row)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
