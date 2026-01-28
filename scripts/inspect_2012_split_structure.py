#!/usr/bin/env python3
"""
Inspect 2012 split receipt structure to determine if synthetic parents exist.

Background: 2019 had two-component splits (parent + child, no synthetic full-total parent)
2012 may have synthetic parents (full-total parent + component children)
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 70)
    print("2012 SPLIT RECEIPT STRUCTURE ANALYSIS")
    print("=" * 70)
    
    # Check 2012 split structure
    print("\n1. Overall 2012 receipt counts:")
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2012 AND parent_receipt_id IS NULL AND is_split_receipt) AS parent_count,
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2012 AND parent_receipt_id IS NOT NULL) AS child_count,
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2012) AS total_2012
        FROM receipts
    """)
    parent_count, child_count, total_2012 = cur.fetchone()
    print(f"   Parent receipts (is_split_receipt=TRUE, parent_receipt_id=NULL): {parent_count}")
    print(f"   Child receipts (parent_receipt_id NOT NULL):                     {child_count}")
    print(f"   Total 2012 receipts:                                              {total_2012}")
    
    if parent_count == 0 and child_count == 0:
        print("   ℹ️  No split receipts found in 2012 (all receipts are standalone)")
        print("\n✅ CONCLUSION: 2012 has NO parent-child structure to flatten")
        cur.close()
        conn.close()
        exit(0)
    
    # Check for synthetic full-total parents
    # Synthetic parent = is_split_receipt=TRUE AND parent_receipt_id=NULL AND amount = SUM(children amounts)
    print("\n2. Checking for synthetic full-total parents:")
    cur.execute("""
        SELECT 
            p.receipt_id,
            p.receipt_date,
            p.vendor_name,
            p.gross_amount AS parent_amount,
            p.split_group_total,
            COUNT(c.receipt_id) AS child_count,
            SUM(c.gross_amount) AS children_total
        FROM receipts p
        LEFT JOIN receipts c ON c.parent_receipt_id = p.receipt_id
        WHERE EXTRACT(YEAR FROM p.receipt_date) = 2012 
            AND p.parent_receipt_id IS NULL 
            AND p.is_split_receipt = TRUE
        GROUP BY p.receipt_id, p.receipt_date, p.vendor_name, p.gross_amount, p.split_group_total
        ORDER BY p.receipt_id
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    if not rows:
        print("   No split receipts found (matching parent criteria)")
        print("\n✅ CONCLUSION: 2012 has NO parent-child structure to flatten")
        cur.close()
        conn.close()
        exit(0)
    
    synthetic_parents = []
    regular_parents = []
    
    for parent_id, receipt_date, vendor_name, parent_amount, split_total, child_count, children_total in rows:
        # Synthetic parent: parent amount equals sum of children (no separate parent-level expense)
        # Regular parent: parent amount is independent; children are split components
        
        is_synthetic = parent_amount is not None and children_total is not None and abs(float(parent_amount) - float(children_total)) < 0.01
        
        print(f"   Parent {parent_id} | {receipt_date} | {vendor_name[:20]:20s}")
        print(f"     Parent amount: ${parent_amount if parent_amount else 'NULL':8.2f} | Children total: ${children_total if children_total else 0:8.2f} | Count: {child_count}")
        print(f"     Split group total: ${split_total if split_total else 'NULL':8.2f}")
        
        if is_synthetic:
            print(f"     🔴 SYNTHETIC: parent amount matches children sum")
            synthetic_parents.append({
                'id': parent_id,
                'date': receipt_date,
                'vendor': vendor_name,
                'amount': parent_amount,
                'child_count': child_count
            })
        else:
            print(f"     ✅ REGULAR: parent is independent expense with split components")
            regular_parents.append({
                'id': parent_id,
                'date': receipt_date,
                'vendor': vendor_name,
                'amount': parent_amount,
                'child_count': child_count
            })
    
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("=" * 70)
    print(f"Total parent receipts in 2012: {parent_count}")
    print(f"Total child receipts in 2012:  {child_count}")
    print(f"Synthetic parents found:       {len(synthetic_parents)}")
    print(f"Regular parents found:         {len(regular_parents)}")
    
    if synthetic_parents:
        print("\n🔴 ACTION REQUIRED: 2012 has synthetic parents that should be deleted")
        print("   These are redundant full-total receipts created for split tracking.")
        print("   Children should be kept; parents should be nulled (like 2019 flattening).")
        print("\n   Synthetic parents to delete:")
        for p in synthetic_parents:
            print(f"     - ID {p['id']} | {p['date']} | {p['vendor']} | {p['child_count']} children")
    else:
        print("\n✅ CONCLUSION: 2012 has only regular parent receipts")
        print("   All parents have independent expenses; children are split components.")
        print("   Same flattening approach as 2019 applies: null parent_receipt_id on children.")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.close()
    exit(1)
