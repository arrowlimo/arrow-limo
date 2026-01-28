#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Merge duplicate clients by consolidating foreign key references and removing duplicates.
"""

import os
import sys
import psycopg2
from decimal import Decimal
from datetime import datetime

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def find_duplicate_clients(cur):
    """Find groups of clients with same name (phone can be NULL)"""
    cur.execute("""
        SELECT name, phone, COUNT(*) as count, ARRAY_AGG(client_id ORDER BY client_id) as client_ids
        FROM clients
        WHERE name IS NOT NULL
        GROUP BY name, phone
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, name
    """)
    return cur.fetchall()

def merge_client_group(cur, name, phone, client_ids):
    """Merge a group of duplicate clients - keep first, migrate others"""
    keeper_id = client_ids[0]
    duplicate_ids = client_ids[1:]
    
    print(f"\n{'='*80}")
    print(f"Merging: {name} / {phone}")
    print(f"  Keeper: {keeper_id}")
    print(f"  Duplicates: {duplicate_ids}")
    
    # Count affected records in all tables with foreign keys to clients
    cur.execute("""
        SELECT COUNT(*) FROM charters WHERE client_id = ANY(%s)
    """, (duplicate_ids,))
    charter_count = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) FROM customer_name_mapping WHERE alms_client_id = ANY(%s)
    """, (duplicate_ids,))
    mapping_count = cur.fetchone()[0]
    
    print(f"  Charters: {charter_count}, Customer mappings: {mapping_count}")
    
    # Update foreign keys to point to keeper
    if charter_count > 0:
        cur.execute("""
            UPDATE charters 
            SET client_id = %s 
            WHERE client_id = ANY(%s)
        """, (keeper_id, duplicate_ids))
        print(f"  ✅ Updated {cur.rowcount} charters")
    
    if mapping_count > 0:
        cur.execute("""
            UPDATE customer_name_mapping 
            SET alms_client_id = %s 
            WHERE alms_client_id = ANY(%s)
        """, (keeper_id, duplicate_ids))
        print(f"  ✅ Updated {cur.rowcount} customer_name_mapping records")
    
    # Delete duplicate client records
    cur.execute("""
        DELETE FROM clients WHERE client_id = ANY(%s)
    """, (duplicate_ids,))
    print(f"  ✅ Deleted {cur.rowcount} duplicate client records")
    
    return {
        'keeper': keeper_id,
        'merged': duplicate_ids,
        'charters': charter_count,
        'mappings': mapping_count
    }

def main():
    print("="*80)
    print("DUPLICATE CLIENT MERGER")
    print("="*80)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        cur = conn.cursor()
        
        # Find duplicates
        print("\n📊 Finding duplicate clients...")
        duplicates = find_duplicate_clients(cur)
        
        if not duplicates:
            print("✅ No duplicate clients found!")
            return
        
        print(f"\n⚠️ Found {len(duplicates)} duplicate groups:")
        for name, phone, count, client_ids in duplicates:
            print(f"  • {name} / {phone}: {count} duplicates (IDs: {client_ids})")
        
        print(f"\n{'='*80}")
        response = input("Proceed with merge? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Merge cancelled")
            return
        
        # Merge each group
        results = []
        for name, phone, count, client_ids in duplicates:
            result = merge_client_group(cur, name, phone, client_ids)
            result['name'] = name
            result['phone'] = phone
            results.append(result)
        
        # Commit changes
        conn.commit()
        
        # Summary
        print(f"\n{'='*80}")
        print("✅ MERGE COMPLETE")
        print("="*80)
        print(f"Total duplicate groups merged: {len(results)}")
        print(f"Total duplicate records removed: {sum(len(r['merged']) for r in results)}")
        print(f"Total charters updated: {sum(r['charters'] for r in results)}")
        print(f"Total customer mappings updated: {sum(r['mappings'] for r in results)}")
        
        # Verify no duplicates remain
        print("\n🔍 Verifying cleanup...")
        remaining = find_duplicate_clients(cur)
        if remaining:
            print(f"⚠️ WARNING: {len(remaining)} duplicate groups still exist!")
        else:
            print("✅ No duplicates remain")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
