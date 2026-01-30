"""
Update "Unknown Client" records in clients table with real names from LMS.
Also update charters.client_display_name where linked to Unknown Client.

Strategy:
1. Match clients.account_number to lms2026_customers.account_no
2. Update clients.company_name from lms2026_customers (use company_name or primary_name)
3. Update charters.client_display_name for linked charters
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")

def analyze_matches():
    """Analyze how many Unknown Clients can be matched to LMS data."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        print("="*80)
        print("ANALYZING UNKNOWN CLIENT MATCHES")
        print("="*80)
        
        # Check Unknown Clients with account numbers
        print("\n1. Unknown Clients with account numbers that can match to LMS:")
        cur.execute("""
            SELECT COUNT(*) as matchable
            FROM clients c
            JOIN lms2026_customers lms ON c.account_number = lms.account_no
            WHERE c.company_name = 'Unknown Client'
              AND c.account_number IS NOT NULL
              AND c.account_number != ''
              AND (lms.company_name IS NOT NULL OR lms.primary_name IS NOT NULL);
        """)
        matchable = cur.fetchone()[0]
        print(f"   ✅ {matchable:,} Unknown Clients have matching LMS account numbers")
        
        # Check Unknown Clients without account numbers
        print("\n2. Unknown Clients without account numbers (cannot auto-match):")
        cur.execute("""
            SELECT COUNT(*)
            FROM clients
            WHERE company_name = 'Unknown Client'
              AND (account_number IS NULL OR account_number = '');
        """)
        no_account = cur.fetchone()[0]
        print(f"   ⚠️  {no_account:,} Unknown Clients have no account number")
        
        # Show sample matches
        print("\n3. Sample matches (LMS → ALMS):")
        print("-"*80)
        cur.execute("""
            SELECT 
                c.account_number,
                c.company_name as alms_name,
                COALESCE(lms.company_name, lms.primary_name) as lms_name,
                COUNT(ch.charter_id) as charter_count
            FROM clients c
            JOIN lms2026_customers lms ON c.account_number = lms.account_no
            LEFT JOIN charters ch ON c.client_id = ch.client_id AND ch.record_type = 'charter'
            WHERE c.company_name = 'Unknown Client'
              AND (lms.company_name IS NOT NULL OR lms.primary_name IS NOT NULL)
            GROUP BY c.account_number, c.company_name, lms.company_name, lms.primary_name
            ORDER BY charter_count DESC
            LIMIT 15;
        """)
        print(f"{'Account':<12} {'Current ALMS':<20} {'LMS Name':<35} {'Charters':>10}")
        print("-"*80)
        for row in cur.fetchall():
            acct, alms_name, lms_name, count = row
            print(f"{acct:<12} {alms_name:<20} {lms_name[:35]:<35} {count:>10,}")
        
        # Check blank company names
        print("\n4. Blank company names (not 'Unknown Client'):")
        cur.execute("""
            SELECT COUNT(*) as blank_count
            FROM clients c
            JOIN lms2026_customers lms ON c.account_number = lms.account_no
            WHERE (c.company_name IS NULL OR c.company_name = '')
              AND (lms.company_name IS NOT NULL OR lms.primary_name IS NOT NULL);
        """)
        blank_matchable = cur.fetchone()[0]
        print(f"   ✅ {blank_matchable:,} blank clients have matching LMS account numbers")
        
        print(f"\n{'='*80}")
        print(f"TOTAL UPDATEABLE: {matchable + blank_matchable:,} clients")
        print(f"{'='*80}\n")
        
        return matchable, no_account, blank_matchable
        
    finally:
        cur.close()
        conn.close()

def update_clients(dry_run=True):
    """Update clients table with LMS names."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        if dry_run:
            print("\n" + "="*80)
            print("DRY RUN - No changes will be committed")
            print("="*80)
            return
        
        print("\n" + "="*80)
        print("UPDATING CLIENTS TABLE")
        print("="*80)
        
        # Update Unknown Clients
        print("\n1. Updating 'Unknown Client' → LMS names...")
        cur.execute("""
            UPDATE clients c
            SET company_name = COALESCE(lms.company_name, lms.primary_name),
                updated_at = CURRENT_TIMESTAMP
            FROM lms2026_customers lms
            WHERE c.account_number = lms.account_no
              AND c.company_name = 'Unknown Client'
              AND (lms.company_name IS NOT NULL OR lms.primary_name IS NOT NULL);
        """)
        unknown_updated = cur.rowcount
        print(f"   ✅ Updated {unknown_updated:,} Unknown Clients")
        
        # Update blank company names
        print("\n2. Updating blank company names → LMS names...")
        cur.execute("""
            UPDATE clients c
            SET company_name = COALESCE(lms.company_name, lms.primary_name),
                updated_at = CURRENT_TIMESTAMP
            FROM lms2026_customers lms
            WHERE c.account_number = lms.account_no
              AND (c.company_name IS NULL OR c.company_name = '')
              AND (lms.company_name IS NOT NULL OR lms.primary_name IS NOT NULL);
        """)
        blank_updated = cur.rowcount
        print(f"   ✅ Updated {blank_updated:,} blank clients")
        
        # Update charters.client_display_name
        print("\n3. Updating charters.client_display_name...")
        cur.execute("""
            UPDATE charters ch
            SET client_display_name = c.company_name
            FROM clients c
            WHERE ch.client_id = c.client_id
              AND ch.record_type = 'charter'
              AND (ch.client_display_name IS NULL 
                   OR ch.client_display_name = '' 
                   OR ch.client_display_name = 'Unknown Client');
        """)
        charters_updated = cur.rowcount
        print(f"   ✅ Updated {charters_updated:,} charter display names")
        
        conn.commit()
        print(f"\n{'='*80}")
        print(f"✅ COMMITTED: {unknown_updated + blank_updated:,} clients + {charters_updated:,} charters")
        print(f"{'='*80}\n")
        
        # Show final stats
        print("="*80)
        print("FINAL CLIENT STATISTICS")
        print("="*80)
        cur.execute("""
            SELECT 
                CASE 
                    WHEN company_name = 'Unknown Client' THEN 'Unknown Client'
                    WHEN company_name IS NULL OR company_name = '' THEN 'Blank'
                    ELSE 'Named'
                END as category,
                COUNT(*) as count
            FROM clients
            GROUP BY category
            ORDER BY count DESC;
        """)
        for row in cur.fetchall():
            category, count = row
            print(f"   {category:<20} {count:>6,} clients")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def main():
    dry_run = '--write' not in sys.argv
    
    # Analyze matches
    matchable, no_account, blank_matchable = analyze_matches()
    
    if matchable + blank_matchable == 0:
        print("\n⚠️  No clients can be updated - all Unknown Clients lack account numbers")
        return
    
    # Update
    update_clients(dry_run)
    
    if dry_run:
        print(f"\nℹ️  Use --write to apply {matchable + blank_matchable:,} client name updates")

if __name__ == "__main__":
    main()
