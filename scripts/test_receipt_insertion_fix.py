#!/usr/bin/env python3
"""
Test receipt insertion with explicit net_amount to verify the column conversion fix.
"""

import psycopg2
from datetime import datetime

def test_receipt_insertion():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()

    print('🧪 TESTING RECEIPT INSERTION WITH EXPLICIT NET_AMOUNT')
    print('=' * 60)

    # Test insert with explicit net_amount (this should now work)
    test_receipt = {
        'source_system': 'TEST-INSERTION',
        'source_reference': 'TEST-001',
        'receipt_date': datetime.now().date(),
        'vendor_name': 'Test Vendor',
        'description': 'Test Receipt with explicit net_amount',
        'currency': 'CAD',
        'gross_amount': 105.00,
        'gst_amount': 5.00,
        'net_amount': 100.00,
        'category': 'test',
        'validation_status': 'test',
        'source_hash': 'test_hash_12345'
    }

    try:
        cur.execute("""
            INSERT INTO receipts (
                source_system, source_reference, receipt_date, vendor_name,
                description, currency, gross_amount, gst_amount, net_amount,
                category, validation_status, source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, gross_amount, gst_amount, net_amount
        """, (
            test_receipt['source_system'],
            test_receipt['source_reference'],
            test_receipt['receipt_date'],
            test_receipt['vendor_name'],
            test_receipt['description'],
            test_receipt['currency'],
            test_receipt['gross_amount'],
            test_receipt['gst_amount'],
            test_receipt['net_amount'],
            test_receipt['category'],
            test_receipt['validation_status'],
            test_receipt['source_hash']
        ))
        
        inserted_id, gross, gst, net = cur.fetchone()
        conn.commit()
        
        print(f'[OK] SUCCESS: Inserted receipt ID {inserted_id}')
        print(f'   Gross: ${gross:.2f}')
        print(f'   GST: ${gst:.2f}')
        print(f'   Net: ${net:.2f}')
        print(f'   Calculation check: ${gross - gst:.2f} (should equal net)')
        
        # Clean up test record
        cur.execute('DELETE FROM receipts WHERE id = %s', (inserted_id,))
        conn.commit()
        print(f'   Cleaned up test record')
        
        print(f'\n🎯 RESULT: Receipt insertion with explicit net_amount now works!')
        print(f'   This fixes the QuickBooks import and other GST calculation issues.')
        
    except Exception as e:
        print(f'[FAIL] ERROR: {str(e)}')
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    test_receipt_insertion()