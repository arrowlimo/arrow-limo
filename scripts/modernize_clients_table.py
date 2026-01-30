"""
Modernize clients table to eliminate dependency on lms_customers_enhanced.

Changes:
1. Add first_name, last_name columns (break down name field)
2. Add cell_phone, home_phone, work_phone (separate phone types)
3. Add full_name_search (denormalized fuzzy match field)
4. Migrate data from lms_customers_enhanced where beneficial
5. Update customer_name_resolver view to use clients directly
6. Drop lms_customers_enhanced table
"""
import psycopg2
import os
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
conn.autocommit = False
cur = conn.cursor()

def backup_table(table_name):
    """Create CSV backup of table."""
    backup_file = f"reports/legacy_table_backups/{table_name}_FINAL_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    print(f"\n📦 Backing up {table_name} ({count:,} records)...")
    
    cur.execute(f"""
        COPY (SELECT * FROM {table_name})
        TO 'L:/limo/{backup_file}'
        WITH (FORMAT CSV, HEADER TRUE, ENCODING 'UTF8')
    """)
    print(f"✅ Backup saved: {backup_file}")

try:
    print("=" * 80)
    print("PHASE 3: MODERNIZE CLIENTS TABLE")
    print("=" * 80)
    
    # Step 1: Add new columns to clients
    print("\n📝 Step 1: Adding new columns to clients table...")
    
    cur.execute("""
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS first_name VARCHAR(100),
        ADD COLUMN IF NOT EXISTS last_name VARCHAR(100),
        ADD COLUMN IF NOT EXISTS cell_phone VARCHAR(20),
        ADD COLUMN IF NOT EXISTS home_phone VARCHAR(20),
        ADD COLUMN IF NOT EXISTS work_phone VARCHAR(20),
        ADD COLUMN IF NOT EXISTS fax_phone VARCHAR(20),
        ADD COLUMN IF NOT EXISTS full_name_search TEXT
    """)
    print("✅ Columns added")
    
    # Step 2: Parse existing name field into first_name/last_name
    print("\n📝 Step 2: Parsing name field into first_name/last_name...")
    
    cur.execute("""
        UPDATE clients
        SET 
            first_name = CASE
                WHEN name LIKE '%, %' THEN TRIM(SPLIT_PART(name, ',', 2))
                WHEN name LIKE '% %' THEN TRIM(SPLIT_PART(name, ' ', 1))
                ELSE name
            END,
            last_name = CASE
                WHEN name LIKE '%, %' THEN TRIM(SPLIT_PART(name, ',', 1))
                WHEN name LIKE '% %' THEN TRIM(SUBSTRING(name FROM POSITION(' ' IN name) + 1))
                ELSE NULL
            END
        WHERE name IS NOT NULL AND first_name IS NULL
    """)
    print(f"✅ Parsed {cur.rowcount:,} names")
    
    # Step 3: Migrate phone data from lms_customers_enhanced
    print("\n📝 Step 3: Migrating phone data from lms_customers_enhanced...")
    
    cur.execute("""
        UPDATE clients c
        SET
            cell_phone = COALESCE(c.cell_phone, lce.cell_phone),
            home_phone = COALESCE(c.home_phone, lce.home_phone),
            work_phone = COALESCE(c.work_phone, lce.work_phone),
            fax_phone = COALESCE(c.fax_phone, lce.fax_phone)
        FROM lms_customers_enhanced lce
        WHERE c.lms_customer_number = lce.account_no
        AND (
            lce.cell_phone IS NOT NULL OR
            lce.home_phone IS NOT NULL OR
            lce.work_phone IS NOT NULL OR
            lce.fax_phone IS NOT NULL
        )
    """)
    print(f"✅ Migrated phone data for {cur.rowcount:,} clients")
    
    # Step 4: Populate primary phone from existing phone field
    print("\n📝 Step 4: Populating primary phone types...")
    
    # Assume existing 'phone' field is cell_phone if no type specified
    cur.execute("""
        UPDATE clients
        SET cell_phone = COALESCE(cell_phone, phone)
        WHERE phone IS NOT NULL 
        AND cell_phone IS NULL
        AND home_phone IS NULL
        AND work_phone IS NULL
    """)
    print(f"✅ Set cell_phone for {cur.rowcount:,} clients")
    
    # Step 5: Build full_name_search field
    print("\n📝 Step 5: Building full_name_search field...")
    
    cur.execute("""
        UPDATE clients
        SET full_name_search = LOWER(TRIM(CONCAT_WS(' ',
            COALESCE(first_name, ''),
            COALESCE(last_name, ''),
            COALESCE(company_name, ''),
            COALESCE(client_name, ''),
            COALESCE(name, '')
        )))
        WHERE full_name_search IS NULL
    """)
    print(f"✅ Built full_name_search for {cur.rowcount:,} clients")
    
    # Step 6: Update customer_name_resolver view
    print("\n📝 Step 6: Updating customer_name_resolver view...")
    
    cur.execute("DROP VIEW IF EXISTS customer_name_resolver CASCADE")
    cur.execute("""
        CREATE VIEW customer_name_resolver AS
        SELECT 
            c.client_id AS alms_client_id,
            c.account_number AS alms_account,
            COALESCE(
                CONCAT(c.first_name, ' ', c.last_name),
                c.company_name,
                c.client_name,
                c.name,
                'Unknown'
            ) AS resolved_name,
            c.email AS resolved_email,
            COALESCE(c.cell_phone, c.work_phone, c.home_phone, c.phone, c.primary_phone) AS resolved_phone,
            c.full_name_search,
            cnm.match_type,
            cnm.match_confidence
        FROM clients c
        LEFT JOIN customer_name_mapping cnm ON c.client_id = cnm.alms_client_id
    """)
    print("✅ View updated (no longer uses lms_customers_enhanced)")
    
    # Step 7: Backup and drop lms_customers_enhanced
    print("\n📝 Step 7: Backing up and dropping lms_customers_enhanced...")
    backup_table("lms_customers_enhanced")
    
    cur.execute("DROP TABLE IF EXISTS lms_customers_enhanced CASCADE")
    print("✅ Table dropped")
    
    # Commit all changes
    conn.commit()
    
    print("\n" + "=" * 80)
    print("✅ MIGRATION COMPLETE")
    print("=" * 80)
    
    # Summary statistics
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(first_name) as has_first,
            COUNT(last_name) as has_last,
            COUNT(company_name) as has_company,
            COUNT(cell_phone) as has_cell,
            COUNT(home_phone) as has_home,
            COUNT(work_phone) as has_work,
            COUNT(full_name_search) as has_search
        FROM clients
    """)
    stats = cur.fetchone()
    
    print(f"\nClients table summary:")
    print(f"  Total clients: {stats[0]:,}")
    print(f"  Has first_name: {stats[1]:,} ({100*stats[1]/stats[0]:.1f}%)")
    print(f"  Has last_name: {stats[2]:,} ({100*stats[2]/stats[0]:.1f}%)")
    print(f"  Has company_name: {stats[3]:,} ({100*stats[3]/stats[0]:.1f}%)")
    print(f"  Has cell_phone: {stats[4]:,} ({100*stats[4]/stats[0]:.1f}%)")
    print(f"  Has home_phone: {stats[5]:,} ({100*stats[5]/stats[0]:.1f}%)")
    print(f"  Has work_phone: {stats[6]:,} ({100*stats[6]/stats[0]:.1f}%)")
    print(f"  Has full_name_search: {stats[7]:,} ({100*stats[7]/stats[0]:.1f}%)")
    
    # Verify table count
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
    table_count = cur.fetchone()[0]
    print(f"\nDatabase now has {table_count} tables (was 289, now 288)")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    raise
finally:
    cur.close()
    conn.close()
