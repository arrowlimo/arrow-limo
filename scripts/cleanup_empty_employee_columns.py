if __name__ == "__main__":
    import sys
    
    # Check for --force flag to skip confirmation
    force = '--force' in sys.argv
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        print(f"\n{'='*80}")
        print("CLEANUP: DELETE 16 EMPTY COLUMNS FROM EMPLOYEES TABLE")
        print(f"{'='*80}\n")
        
        print(f"Columns to delete (all completely empty):\n")
        for i, col in enumerate(EMPTY_COLUMNS, 1):
            print(f"  {i:2d}. {col}")
        
        print(f"\n{'='*80}")
        print("IMPACT:")
        print(f"  Current: 58 columns")
        print(f"  After:   42 columns")
        print(f"  Deleted: 16 empty columns")
        print(f"  Data loss: ZERO (all columns are empty)")
        print(f"{'='*80}\n")
        
        # Confirm (skip if --force flag)
        if not force:
            response = input("Proceed with cleanup? (yes/no): ").strip().lower()
            if response != 'yes':
                print("❌ Cancelled")
                conn.close()
                exit(0)
        else:
            print("🚀 Running with --force (skipping confirmation)\n")
        
        cur = conn.cursor()
        
        print("[DELETING] Empty columns...\n")
        for col in EMPTY_COLUMNS:
            try:
                cur.execute(f'ALTER TABLE employees DROP COLUMN "{col}" CASCADE')
                conn.commit()
                print(f"  ✓ Deleted: {col}")
            except Exception as e:
                print(f"  ❌ Failed to delete {col}: {e}")
                conn.rollback()
        
        # Verify new column count
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'employees'
        """)
        new_col_count = cur.fetchone()[0]
        
        print(f"\n✅ Cleanup complete!")
        print(f"  New column count: {new_col_count}")
        print(f"  Columns removed: {58 - new_col_count}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
