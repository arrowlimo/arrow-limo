#!/usr/bin/env python3
"""
Create or replace a convenience view v_staging_driver_pay_with_employee that resolves employee_id
from either staging column (if present) or the link table staging_driver_pay_links.

This is non-destructive and safe to re-run.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Detect if staging_driver_pay has employee_id
    cur.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'staging_driver_pay' AND column_name = 'employee_id'
        ) AS has_emp
        """
    )
    has_emp_col = cur.fetchone()['has_emp']

    resolved_expr = "COALESCE(s.employee_id, l.employee_id)" if has_emp_col else "l.employee_id"

    cur.execute(
        f"""
        CREATE OR REPLACE VIEW v_staging_driver_pay_with_employee AS
        SELECT s.*,
               {resolved_expr} AS resolved_employee_id,
               e.full_name AS resolved_employee_name
        FROM staging_driver_pay s
        LEFT JOIN staging_driver_pay_links l ON l.staging_id = s.id
        LEFT JOIN employees e ON e.employee_id = {resolved_expr}
        """
    )
    conn.commit()
    print("View v_staging_driver_pay_with_employee created/updated.")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
