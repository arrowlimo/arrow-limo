#!/usr/bin/env python3
"""
Check what records were created today
"""

import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata', 
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("RECORDS CREATED TODAY:")
    print("====================")
    
    cur.execute("""
        SELECT source_system, COUNT(*), SUM(gross_amount) 
        FROM receipts 
        WHERE DATE(created_at) = CURRENT_DATE 
        GROUP BY source_system
    """)
    
    for row in cur.fetchall():
        print(f"{row[0] or 'NULL'}: {row[1]} records, ${row[2]:,.2f}")
    
    print("\nALL REVENUE CLASSIFICATION RECORDS:")
    print("=================================")
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount), SUM(gst_amount)
        FROM receipts 
        WHERE vendor_name = 'Business Income'
    """)
    
    count, total, gst = cur.fetchone()
    print(f"Business Income records: {count}, ${total:,.2f} gross, ${gst:,.2f} GST")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()