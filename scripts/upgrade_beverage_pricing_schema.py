"""
Upgrade schema for beverage pricing/markup tracking.
Adds columns if missing and creates tables if absent.
"""
import psycopg2

DDL = {
    'beverage_products': [
        ("our_cost", "NUMERIC(10,2)", "ALTER TABLE beverage_products ADD COLUMN our_cost NUMERIC(10,2)", 0),
        ("default_markup_pct", "NUMERIC(5,2)", "ALTER TABLE beverage_products ADD COLUMN default_markup_pct NUMERIC(5,2) DEFAULT 35", 35),
        ("deposit_amount", "NUMERIC(10,2)", "ALTER TABLE beverage_products ADD COLUMN deposit_amount NUMERIC(10,2) DEFAULT 0", 0),
        ("fees_amount", "NUMERIC(10,2)", "ALTER TABLE beverage_products ADD COLUMN fees_amount NUMERIC(10,2) DEFAULT 0", 0),
        ("gst_included", "BOOLEAN", "ALTER TABLE beverage_products ADD COLUMN gst_included BOOLEAN DEFAULT FALSE", False),
    ],
    'beverage_orders': [
        ("status", "TEXT", "ALTER TABLE beverage_orders ADD COLUMN status TEXT DEFAULT 'pending'", 'pending'),
    ],
    'beverage_order_items': [
        ("our_cost", "NUMERIC(10,2)", "ALTER TABLE beverage_order_items ADD COLUMN our_cost NUMERIC(10,2)", 0),
        ("markup_pct", "NUMERIC(5,2)", "ALTER TABLE beverage_order_items ADD COLUMN markup_pct NUMERIC(5,2)", 0),
        ("deposit_amount", "NUMERIC(10,2)", "ALTER TABLE beverage_order_items ADD COLUMN deposit_amount NUMERIC(10,2) DEFAULT 0", 0),
        ("fees_amount", "NUMERIC(10,2)", "ALTER TABLE beverage_order_items ADD COLUMN fees_amount NUMERIC(10,2) DEFAULT 0", 0),
        ("gst_amount", "NUMERIC(10,2)", "ALTER TABLE beverage_order_items ADD COLUMN gst_amount NUMERIC(10,2) DEFAULT 0", 0),
        ("price_override", "BOOLEAN", "ALTER TABLE beverage_order_items ADD COLUMN price_override BOOLEAN DEFAULT FALSE", False),
        ("override_reason", "TEXT", "ALTER TABLE beverage_order_items ADD COLUMN override_reason TEXT", None),
    ],
}

CREATE = {
    'beverage_orders': """
        CREATE TABLE IF NOT EXISTS beverage_orders (
            order_id SERIAL PRIMARY KEY,
            reserve_number VARCHAR(32) NOT NULL,
            order_date TIMESTAMP NOT NULL,
            subtotal NUMERIC(10,2) NOT NULL,
            gst NUMERIC(10,2) NOT NULL,
            total NUMERIC(10,2) NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """,
    'beverage_order_items': """
        CREATE TABLE IF NOT EXISTS beverage_order_items (
            item_line_id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES beverage_orders(order_id) ON DELETE CASCADE,
            item_id INTEGER,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price NUMERIC(10,2) NOT NULL,
            total NUMERIC(10,2) NOT NULL
        )
    """,
}


def ensure_table(conn, table):
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
        if cur.fetchone() is None:
            cur.execute(CREATE[table])
            conn.commit()
    finally:
        cur.close()


def ensure_columns(conn, table, specs):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s
        """, (table,))
        existing = {r[0] for r in cur.fetchall()}
        for col, _, alter_sql, _default in specs:
            if col not in existing:
                cur.execute(alter_sql)
        conn.commit()
    finally:
        cur.close()


def backfill_defaults(conn):
    cur = conn.cursor()
    try:
        # Backfill our_cost if null -> derive from unit_price and default markup if present
        cur.execute("""
            UPDATE beverage_products
            SET our_cost = COALESCE(our_cost,
                CASE 
                    WHEN unit_price IS NOT NULL AND default_markup_pct IS NOT NULL AND default_markup_pct > 0
                    THEN ROUND(unit_price / (1 + default_markup_pct/100.0), 2)
                    ELSE unit_price
                END)
        """)
        conn.commit()
    finally:
        cur.close()


def main():
    conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
    # Ensure order tables exist first
    ensure_table(conn, 'beverage_orders')
    ensure_table(conn, 'beverage_order_items')
    # Add columns
    for tbl, specs in DDL.items():
        ensure_columns(conn, tbl, specs)
    backfill_defaults(conn)
    conn.close()
    print("✅ Beverage pricing schema upgraded")

if __name__ == '__main__':
    main()
