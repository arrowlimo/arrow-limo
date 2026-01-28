#!/usr/bin/env python3
"""
Add split fuel receipt for 09/15/2012:
- Total: $135.00 (includes $6.43 GST, net $128.57)
- Jerry Can: $4.00 (3.28 LT, unknown allocation)
- L-2: $36.01 (29.53 LT)
- L-7: $94.99 (77.94 LT)
- Total Liters: 110.747 LT @ $1.219/L

Split receipts are stored as separate rows with parent-child links:
- Parent: split_group_total=$135.00, parent_receipt_id=NULL
- Children: individual amounts, parent_receipt_id=parent_id
"""

import psycopg2
from decimal import Decimal
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

try:
    # Receipt details
    receipt_date = '2012-09-15'
    vendor_name = 'FUEL STATION'  # Identify actual vendor from original
    gross_amount = Decimal('135.00')
    gst_amount = Decimal('6.43')
    net_amount = Decimal('128.57')
    fuel_amount_total = Decimal('110.747')
    price_per_liter = Decimal('1.219')
    
    # Split key for grouping (date|vendor|total)
    split_key = f"{receipt_date}|{vendor_name}|{gross_amount}"
    
    print("=" * 80)
    print("CREATING SPLIT FUEL RECEIPT - 09/15/2012")
    print("=" * 80)
    
    # ============ PARENT RECEIPT ============
    # Parent: total=$135.00, is_split_receipt=TRUE, parent_receipt_id=NULL
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            category, gl_account_code, fuel_amount,
            is_split_receipt, split_key, split_group_total,
            created_at, receipt_source, description
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        ) RETURNING receipt_id
    """, (
        receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
        'Fuel', '5110', fuel_amount_total,
        True, split_key, gross_amount,
        datetime.now(), 'MANUAL_ENTRY', f'SPLIT/{gross_amount} - Fuel Purchase (Parent)'
    ))
    
    parent_receipt_id = cur.fetchone()[0]
    print(f"✓ Created PARENT receipt ID: {parent_receipt_id}")
    print(f"  Amount: ${gross_amount} (GST: ${gst_amount}, Net: ${net_amount})")
    print(f"  Total Liters: {fuel_amount_total} @ ${price_per_liter}/L")
    print(f"  Split Key: {split_key}")
    
    # ============ CHILD 1: Jerry Can ============
    # $4.00, 3.28 LT, vehicle_id=NULL (unknown)
    jerry_can_amount = Decimal('4.00')
    jerry_can_liters = Decimal('3.28')
    
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            category, gl_account_code, fuel_amount,
            is_split_receipt, split_key, split_group_total, parent_receipt_id,
            created_at, receipt_source, description
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        ) RETURNING receipt_id
    """, (
        receipt_date, vendor_name, jerry_can_amount, Decimal('0.19'), jerry_can_amount - Decimal('0.19'),
        'Fuel', '5110', jerry_can_liters,
        True, split_key, gross_amount, parent_receipt_id,
        datetime.now(), 'MANUAL_ENTRY', f'SPLIT/{gross_amount} - Jerry Can (3.28 LT)'
    ))
    child_1_id = cur.fetchone()[0]
    print(f"\n✓ Created CHILD 1 (Jerry Can) - ID: {child_1_id}")
    print(f"  Amount: ${jerry_can_amount} | Liters: {jerry_can_liters} LT")
    print(f"  Parent Link: {parent_receipt_id}")
    
    # ============ CHILD 2: L-2 Vehicle ============
    # $36.01, 29.53 LT, vehicle_id=2
    l2_amount = Decimal('36.01')
    l2_liters = Decimal('29.53')
    l2_gst = (l2_amount / (1 + Decimal('0.05'))) * Decimal('0.05')  # Proportional GST
    l2_net = l2_amount - l2_gst
    
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            category, gl_account_code, fuel_amount, vehicle_id,
            is_split_receipt, split_key, split_group_total, parent_receipt_id,
            created_at, receipt_source, description
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        ) RETURNING receipt_id
    """, (
        receipt_date, vendor_name, l2_amount, round(l2_gst, 2), round(l2_net, 2),
        'Fuel', '5110', l2_liters, 2,
        True, split_key, gross_amount, parent_receipt_id,
        datetime.now(), 'MANUAL_ENTRY', f'SPLIT/{gross_amount} - L-2 Vehicle (29.53 LT)'
    ))
    child_2_id = cur.fetchone()[0]
    print(f"\n✓ Created CHILD 2 (L-2) - ID: {child_2_id}")
    print(f"  Amount: ${l2_amount} | Liters: {l2_liters} LT")
    print(f"  Vehicle ID: 2 | Parent Link: {parent_receipt_id}")
    
    # ============ CHILD 3: L-7 Vehicle ============
    # $94.99, 77.94 LT, vehicle_id=7
    l7_amount = Decimal('94.99')
    l7_liters = Decimal('77.94')
    l7_gst = (l7_amount / (1 + Decimal('0.05'))) * Decimal('0.05')  # Proportional GST
    l7_net = l7_amount - l7_gst
    
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            category, gl_account_code, fuel_amount, vehicle_id,
            is_split_receipt, split_key, split_group_total, parent_receipt_id,
            created_at, receipt_source, description
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        ) RETURNING receipt_id
    """, (
        receipt_date, vendor_name, l7_amount, round(l7_gst, 2), round(l7_net, 2),
        'Fuel', '5110', l7_liters, 7,
        True, split_key, gross_amount, parent_receipt_id,
        datetime.now(), 'MANUAL_ENTRY', f'SPLIT/{gross_amount} - L-7 Vehicle (77.94 LT)'
    ))
    child_3_id = cur.fetchone()[0]
    print(f"\n✓ Created CHILD 3 (L-7) - ID: {child_3_id}")
    print(f"  Amount: ${l7_amount} | Liters: {l7_liters} LT")
    print(f"  Vehicle ID: 7 | Parent Link: {parent_receipt_id}")
    
    # ============ VERIFICATION ============
    print(f"\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    total_amount = jerry_can_amount + l2_amount + l7_amount
    total_liters = jerry_can_liters + l2_liters + l7_liters
    
    print(f"Total Amount: ${total_amount} == ${gross_amount} ? {total_amount == gross_amount} ✓")
    print(f"Total Liters: {total_liters} LT ≈ {fuel_amount_total} LT ? {abs(total_liters - fuel_amount_total) < Decimal('0.01')} ✓")
    
    # Commit
    conn.commit()
    print(f"\n✅ SPLIT RECEIPT CREATED SUCCESSFULLY!")
    print(f"   Parent Receipt ID: {parent_receipt_id}")
    print(f"   Child Receipts: {child_1_id}, {child_2_id}, {child_3_id}")
    print(f"   Split Key: {split_key}")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
