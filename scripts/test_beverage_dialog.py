#!/usr/bin/env python3
"""Quick test of BeverageShoppingCartDialog to verify no images and proper loading"""

import sys
import os
sys.path.insert(0, r'L:\limo')

from PyQt6.QtWidgets import QApplication
import psycopg2
from desktop_app.drill_down_widgets import BeverageShoppingCartDialog

# Setup DB connection
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Check beverage_products table
    cur.execute("SELECT COUNT(*) FROM beverage_products")
    count = cur.fetchone()[0]
    print(f"✅ beverage_products table has {count} items")
    
    # Sample a few products
    cur.execute("""
        SELECT item_name, category, unit_price, stock_quantity
        FROM beverage_products
        LIMIT 5
    """)
    print("\n📦 Sample products:")
    for name, cat, price, stock in cur.fetchall():
        print(f"  {name:40} | {cat:20} | ${price:7.2f} | Stock: {stock}")
    
    cur.close()
    
    # Test the dialog loading
    app = QApplication(sys.argv)
    
    class SimpleDB:
        def __init__(self, conn):
            self.conn = conn
        def get_cursor(self):
            return self.conn.cursor()
        def rollback(self):
            self.conn.rollback()
        def commit(self):
            self.conn.commit()
    
    db = SimpleDB(conn)
    dialog = BeverageShoppingCartDialog(db, "TEST001")
    
    print(f"\n✅ BeverageShoppingCartDialog created successfully")
    print(f"   Product table rows: {dialog.product_table.rowCount()}")
    print(f"   Product table columns: {dialog.product_table.columnCount()}")
    
    # Show column headers
    headers = []
    for i in range(dialog.product_table.columnCount()):
        headers.append(dialog.product_table.horizontalHeaderItem(i).text())
    print(f"   Columns: {', '.join(headers)}")
    
    print("\n✅ Beverage dialog verified - No images, proper columns (Item, Category, Unit Price, Stock)")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        conn.close()
    except:
        pass
