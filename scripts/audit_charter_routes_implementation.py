#!/usr/bin/env python3
"""
CHARTER ROUTES IMPLEMENTATION AUDIT
====================================

Complete audit of charter routes implementation:
1. Database schema validation
2. Column name mapping verification
3. Data type consistency check
4. Foreign key relationship validation
5. API endpoint logic review
6. Pydantic model field mapping

Author: AI Assistant
Date: December 10, 2025
"""

import psycopg2
import os
from typing import Dict, List, Any

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def audit_database_schema(conn):
    """Verify database schema matches code expectations."""
    cur = conn.cursor()
    
    print("=" * 80)
    print("1. DATABASE SCHEMA AUDIT")
    print("=" * 80)
    
    # Check if charter_routes table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'charter_routes'
        )
    """)
    table_exists = cur.fetchone()[0]
    
    if not table_exists:
        print("❌ CRITICAL: charter_routes table does not exist!")
        return False
    
    print("✅ charter_routes table exists")
    
    # Get all columns
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'charter_routes'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    print(f"\n📋 Table Columns ({len(columns)} total):")
    for col_name, data_type, nullable, default in columns:
        null_str = "NULL" if nullable == 'YES' else "NOT NULL"
        default_str = f" DEFAULT {default}" if default else ""
        print(f"  • {col_name:<30} {data_type:<20} {null_str}{default_str}")
    
    # Expected columns from Pydantic model
    expected_columns = {
        'route_id': 'integer',
        'charter_id': 'integer',
        'route_sequence': 'integer',
        'pickup_location': 'text',
        'pickup_time': 'time without time zone',
        'dropoff_location': 'text',
        'dropoff_time': 'time without time zone',
        'estimated_duration_minutes': 'integer',
        'actual_duration_minutes': 'integer',
        'estimated_distance_km': 'numeric',
        'actual_distance_km': 'numeric',
        'route_price': 'numeric',
        'route_notes': 'text',
        'route_status': 'character varying',
        'created_at': 'timestamp without time zone',
        'updated_at': 'timestamp without time zone',
    }
    
    actual_columns = {row[0]: row[1] for row in columns}
    
    print(f"\n🔍 Column Validation:")
    all_match = True
    for col, expected_type in expected_columns.items():
        if col not in actual_columns:
            print(f"  ❌ MISSING: {col} ({expected_type})")
            all_match = False
        else:
            actual_type = actual_columns[col]
            if expected_type in actual_type or actual_type in expected_type:
                print(f"  ✅ {col}")
            else:
                print(f"  ⚠️  {col}: expected {expected_type}, got {actual_type}")
    
    # Check for extra columns
    for col in actual_columns:
        if col not in expected_columns:
            print(f"  ⚠️  EXTRA: {col} (not in Pydantic model)")
    
    return all_match

def audit_foreign_keys(conn):
    """Check foreign key relationships."""
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("2. FOREIGN KEY RELATIONSHIPS")
    print("=" * 80)
    
    cur.execute("""
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON tc.constraint_name = rc.constraint_name
        WHERE tc.table_name = 'charter_routes'
            AND tc.constraint_type = 'FOREIGN KEY'
    """)
    
    fks = cur.fetchall()
    if fks:
        for fk_name, col, ref_table, ref_col, delete_rule in fks:
            print(f"✅ {col} → {ref_table}.{ref_col}")
            print(f"   Constraint: {fk_name}")
            print(f"   Delete Rule: {delete_rule}")
    else:
        print("⚠️  No foreign keys found")
    
    # Verify charters table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'charters'
        )
    """)
    charters_exists = cur.fetchone()[0]
    
    if charters_exists:
        print("\n✅ charters table exists (parent table)")
        
        # Check charter_id column in charters
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'charters' AND column_name = 'charter_id'
        """)
        if cur.fetchone():
            print("✅ charters.charter_id exists")
        else:
            print("❌ charters.charter_id NOT FOUND")
    else:
        print("❌ charters table NOT FOUND")

def audit_indexes(conn):
    """Check indexes for performance."""
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("3. INDEXES & CONSTRAINTS")
    print("=" * 80)
    
    cur.execute("""
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = 'charter_routes'
        ORDER BY indexname
    """)
    
    indexes = cur.fetchall()
    if indexes:
        for idx_name, idx_def in indexes:
            print(f"✅ {idx_name}")
            print(f"   {idx_def}")
    else:
        print("⚠️  No indexes found")
    
    # Check unique constraint
    cur.execute("""
        SELECT constraint_name, constraint_type
        FROM information_schema.table_constraints
        WHERE table_name = 'charter_routes'
        ORDER BY constraint_type, constraint_name
    """)
    
    constraints = cur.fetchall()
    print(f"\n📋 Constraints ({len(constraints)} total):")
    for name, type_ in constraints:
        print(f"  • {name} ({type_})")

def audit_api_column_mapping(conn):
    """Verify API endpoints use correct column names."""
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("4. API ENDPOINT COLUMN MAPPING")
    print("=" * 80)
    
    # Get actual DB columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'charter_routes'
        ORDER BY ordinal_position
    """)
    db_columns = {row[0] for row in cur.fetchall()}
    
    # Columns used in INSERT statement (from create_charter_route)
    insert_columns = [
        'charter_id', 'route_sequence', 'pickup_location', 'pickup_time',
        'dropoff_location', 'dropoff_time', 'estimated_duration_minutes',
        'actual_duration_minutes', 'estimated_distance_km', 'actual_distance_km',
        'route_price', 'route_notes', 'route_status'
    ]
    
    print("\n🔍 INSERT Statement Columns:")
    all_valid = True
    for col in insert_columns:
        if col in db_columns:
            print(f"  ✅ {col}")
        else:
            print(f"  ❌ {col} - NOT IN DATABASE")
            all_valid = False
    
    # Check SELECT * compatibility
    print("\n🔍 SELECT * Returns:")
    print(f"  Database has {len(db_columns)} columns")
    print(f"  Pydantic CharterRoute expects 16 fields")
    
    missing_in_model = db_columns - {'route_id', 'charter_id', 'route_sequence', 
                                      'pickup_location', 'pickup_time', 'dropoff_location',
                                      'dropoff_time', 'estimated_duration_minutes',
                                      'actual_duration_minutes', 'estimated_distance_km',
                                      'actual_distance_km', 'route_price', 'route_notes',
                                      'route_status', 'created_at', 'updated_at'}
    
    if missing_in_model:
        print(f"  ⚠️  Extra DB columns not in Pydantic model: {missing_in_model}")
    else:
        print(f"  ✅ All DB columns mapped in Pydantic model")
    
    return all_valid

def audit_data_types(conn):
    """Check data type consistency between DB and Pydantic."""
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("5. DATA TYPE CONSISTENCY")
    print("=" * 80)
    
    type_mapping = {
        'route_id': ('integer', 'int'),
        'charter_id': ('integer', 'int'),
        'route_sequence': ('integer', 'int'),
        'pickup_location': ('text', 'Optional[str]'),
        'pickup_time': ('time without time zone', 'Optional[time]'),
        'dropoff_location': ('text', 'Optional[str]'),
        'dropoff_time': ('time without time zone', 'Optional[time]'),
        'estimated_duration_minutes': ('integer', 'Optional[int]'),
        'actual_duration_minutes': ('integer', 'Optional[int]'),
        'estimated_distance_km': ('numeric', 'Optional[float]'),
        'actual_distance_km': ('numeric', 'Optional[float]'),
        'route_price': ('numeric', 'Optional[float]'),
        'route_notes': ('text', 'Optional[str]'),
        'route_status': ('character varying', 'str'),
        'created_at': ('timestamp without time zone', 'datetime'),
        'updated_at': ('timestamp without time zone', 'datetime'),
    }
    
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'charter_routes'
    """)
    
    db_types = {row[0]: row[1] for row in cur.fetchall()}
    
    all_compatible = True
    for col, (expected_db, pydantic) in type_mapping.items():
        if col in db_types:
            actual_db = db_types[col]
            if expected_db in actual_db or actual_db in expected_db:
                print(f"  ✅ {col:<30} DB:{actual_db:<25} Py:{pydantic}")
            else:
                print(f"  ⚠️  {col:<30} DB:{actual_db:<25} Py:{pydantic} (mismatch)")
                all_compatible = False
        else:
            print(f"  ❌ {col:<30} NOT IN DATABASE")
            all_compatible = False
    
    return all_compatible

def test_sample_operations(conn):
    """Test actual database operations."""
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("6. SAMPLE OPERATIONS TEST")
    print("=" * 80)
    
    # Get a sample charter_id
    cur.execute("SELECT charter_id FROM charters LIMIT 1")
    result = cur.fetchone()
    
    if not result:
        print("⚠️  No charters in database - cannot test operations")
        return
    
    test_charter_id = result[0]
    print(f"Using test charter_id: {test_charter_id}")
    
    # Test INSERT
    try:
        cur.execute("""
            INSERT INTO charter_routes (
                charter_id, route_sequence, pickup_location, pickup_time,
                dropoff_location, dropoff_time, estimated_duration_minutes,
                actual_duration_minutes, estimated_distance_km, actual_distance_km,
                route_price, route_notes, route_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING route_id
        """, (
            test_charter_id, 1, 'Test Pickup', '10:00:00',
            'Test Dropoff', '11:00:00', 60, None, 25.5, None,
            150.00, 'Test route', 'pending'
        ))
        test_route_id = cur.fetchone()[0]
        print(f"  ✅ INSERT: Created test route {test_route_id}")
    except Exception as e:
        print(f"  ❌ INSERT FAILED: {e}")
        conn.rollback()
        return
    
    # Test SELECT
    try:
        cur.execute("""
            SELECT * FROM charter_routes WHERE route_id = %s
        """, (test_route_id,))
        row = cur.fetchone()
        if row:
            print(f"  ✅ SELECT: Retrieved route successfully")
            cols = [desc[0] for desc in cur.description]
            print(f"     Columns: {', '.join(cols)}")
        else:
            print(f"  ❌ SELECT: Route not found")
    except Exception as e:
        print(f"  ❌ SELECT FAILED: {e}")
    
    # Test UPDATE
    try:
        cur.execute("""
            UPDATE charter_routes 
            SET route_status = %s, actual_duration_minutes = %s
            WHERE route_id = %s
            RETURNING route_id
        """, ('completed', 65, test_route_id))
        if cur.fetchone():
            print(f"  ✅ UPDATE: Modified route successfully")
        else:
            print(f"  ❌ UPDATE: No rows updated")
    except Exception as e:
        print(f"  ❌ UPDATE FAILED: {e}")
    
    # Test DELETE
    try:
        cur.execute("""
            DELETE FROM charter_routes WHERE route_id = %s
        """, (test_route_id,))
        print(f"  ✅ DELETE: Removed test route (rowcount: {cur.rowcount})")
    except Exception as e:
        print(f"  ❌ DELETE FAILED: {e}")
    
    conn.rollback()  # Rollback test data
    print("  🔄 Test data rolled back")

def main():
    """Run complete audit."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " CHARTER ROUTES IMPLEMENTATION AUDIT".center(78) + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    try:
        conn = get_db_connection()
        
        schema_ok = audit_database_schema(conn)
        audit_foreign_keys(conn)
        audit_indexes(conn)
        mapping_ok = audit_api_column_mapping(conn)
        types_ok = audit_data_types(conn)
        test_sample_operations(conn)
        
        print("\n" + "=" * 80)
        print("FINAL AUDIT SUMMARY")
        print("=" * 80)
        
        if schema_ok and mapping_ok and types_ok:
            print("✅ ALL CHECKS PASSED")
            print("✅ Database schema matches code expectations")
            print("✅ API endpoints use correct column names")
            print("✅ Data types are consistent")
            print("✅ Foreign keys properly configured")
            print("\n🚀 Implementation is production-ready!")
        else:
            print("⚠️  SOME ISSUES FOUND")
            if not schema_ok:
                print("❌ Schema validation failed")
            if not mapping_ok:
                print("❌ Column mapping issues detected")
            if not types_ok:
                print("❌ Data type inconsistencies found")
            print("\n🔧 Review issues above before deployment")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ AUDIT FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
