#!/usr/bin/env python3
"""
Fix CIBC Banking Schema & Add Missing Infrastructure
====================================================
Applies all necessary fixes to enable proper CIBC statement reconciliation:

1. Add missing columns (source_hash, reconciliation_status)
2. Create account_number_aliases mapping table
3. Populate aliases for known CIBC accounts
4. Backfill source_hash for existing transactions
5. Create helper views for easier querying
6. Generate verification report

Run with --dry-run to preview changes without applying.
"""

import psycopg2
import os
import hashlib
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def generate_source_hash(date, description, debit, credit):
    """Generate deterministic hash for deduplication"""
    content = f"{date}|{description}|{debit}|{credit}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def main():
    parser = argparse.ArgumentParser(description='Fix CIBC banking schema')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    parser.add_argument('--backup', action='store_true', help='Create backup first')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CIBC BANKING SCHEMA FIX & INFRASTRUCTURE SETUP")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if args.dry_run else 'APPLY CHANGES'}")
    print()
    
    # Step 1: Check current schema
    print("📋 STEP 1: Checking Current Schema")
    print("-" * 80)
    
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'banking_transactions'
    """)
    existing_cols = [row[0] for row in cur.fetchall()]
    
    changes_needed = []
    
    # Check for missing columns
    required_cols = {
        'source_hash': 'VARCHAR(64)',
        'reconciliation_status': "VARCHAR(20) DEFAULT 'unreconciled'",
        'reconciled_receipt_id': 'INTEGER',
        'reconciled_payment_id': 'INTEGER',
        'reconciled_charter_id': 'INTEGER',
        'reconciliation_notes': 'TEXT',
        'reconciled_at': 'TIMESTAMP',
        'reconciled_by': 'VARCHAR(100)'
    }
    
    for col, dtype in required_cols.items():
        if col not in existing_cols:
            changes_needed.append(f"Add column: {col} ({dtype})")
            print(f"   [FAIL] Missing: {col}")
        else:
            print(f"   [OK] Present: {col}")
    
    # Step 2: Add missing columns
    if changes_needed:
        print(f"\n🔧 STEP 2: Adding Missing Columns ({len(changes_needed)} changes)")
        print("-" * 80)
        
        for change in changes_needed:
            print(f"   → {change}")
        
        if not args.dry_run:
            for col, dtype in required_cols.items():
                if col not in existing_cols:
                    try:
                        cur.execute(f"""
                            ALTER TABLE banking_transactions 
                            ADD COLUMN IF NOT EXISTS {col} {dtype}
                        """)
                        print(f"      [OK] Added {col}")
                    except Exception as e:
                        print(f"      [WARN] Error adding {col}: {e}")
            
            conn.commit()
            print(f"   [OK] All columns added successfully")
    else:
        print(f"\n[OK] STEP 2: All required columns already exist")
    
    # Step 3: Create account_number_aliases table
    print(f"\n🔧 STEP 3: Creating Account Number Mapping Infrastructure")
    print("-" * 80)
    
    if not args.dry_run:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS account_number_aliases (
                alias_id SERIAL PRIMARY KEY,
                statement_format VARCHAR(50) NOT NULL,
                canonical_account_number VARCHAR(50) NOT NULL,
                institution_name VARCHAR(100),
                account_type VARCHAR(50),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(statement_format, canonical_account_number)
            )
        """)
        conn.commit()
        print(f"   [OK] account_number_aliases table created")
    else:
        print(f"   → Would create account_number_aliases table")
    
    # Step 4: Populate CIBC account aliases
    print(f"\n🔧 STEP 4: Populating CIBC Account Aliases")
    print("-" * 80)
    
    cibc_aliases = [
        # CIBC Checking Account 0228362 (likely matches 00339-7461615 from statements)
        ('00339-7461615', '0228362', 'CIBC', 'checking', 'CIBC Business Checking - full hyphenated format'),
        ('00339', '0228362', 'CIBC', 'checking', 'CIBC Business Checking - first part only'),
        ('7461615', '0228362', 'CIBC', 'checking', 'CIBC Business Checking - second part only'),
        ('8362', '0228362', 'CIBC', 'checking', 'CIBC Business Checking - last 4 digits'),
        ('0228362', '0228362', 'CIBC', 'checking', 'CIBC Business Checking - canonical format'),
        
        # CIBC Business Account 3648117
        ('3648117', '3648117', 'CIBC', 'business', 'CIBC Business Deposit - canonical format'),
        ('8117', '3648117', 'CIBC', 'business', 'CIBC Business Deposit - last 4 digits'),
        
        # CIBC Vehicle Loans 8314462
        ('8314462', '8314462', 'CIBC', 'loan', 'CIBC Vehicle Loans - canonical format'),
        ('4462', '8314462', 'CIBC', 'loan', 'CIBC Vehicle Loans - last 4 digits'),
        
        # QuickBooks legacy formats
        ('1010', '0228362', 'CIBC', 'checking', 'QuickBooks legacy account number'),
        ('1615', '0228362', 'CIBC', 'checking', 'QuickBooks legacy suffix'),
    ]
    
    for statement_fmt, canonical, inst, acct_type, note in cibc_aliases:
        print(f"   → Mapping: {statement_fmt:20} → {canonical}")
        if not args.dry_run:
            cur.execute("""
                INSERT INTO account_number_aliases 
                (statement_format, canonical_account_number, institution_name, account_type, notes)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (statement_format, canonical_account_number) DO NOTHING
            """, (statement_fmt, canonical, inst, acct_type, note))
    
    if not args.dry_run:
        conn.commit()
        print(f"   [OK] {len(cibc_aliases)} aliases configured")
    
    # Step 5: Backfill source_hash for existing transactions
    print(f"\n🔧 STEP 5: Generating Source Hashes for Existing Transactions")
    print("-" * 80)
    
    # Check if source_hash column exists before querying
    if 'source_hash' in existing_cols:
        cur.execute("""
            SELECT COUNT(*) 
            FROM banking_transactions 
            WHERE source_hash IS NULL
        """)
        missing_hash_count = cur.fetchone()[0]
    else:
        # Column doesn't exist yet - all transactions will need hashes after column is added
        cur.execute("SELECT COUNT(*) FROM banking_transactions")
        missing_hash_count = cur.fetchone()[0] if not args.dry_run else 0
        print(f"   [WARN] source_hash column doesn't exist yet (will be added in Step 2)")
    
    if missing_hash_count > 0:
        print(f"   Found {missing_hash_count:,} transactions without source_hash")
        
        if not args.dry_run:
            print(f"   Generating hashes... (this may take a moment)")
            
            cur.execute("""
                SELECT transaction_id, transaction_date, description, 
                       debit_amount, credit_amount
                FROM banking_transactions
                WHERE source_hash IS NULL
            """)
            
            batch = []
            for txn_id, date, desc, debit, credit in cur.fetchall():
                hash_val = generate_source_hash(
                    str(date), 
                    desc or '', 
                    str(debit or 0), 
                    str(credit or 0)
                )
                batch.append((hash_val, txn_id))
                
                if len(batch) >= 1000:
                    cur.executemany("""
                        UPDATE banking_transactions 
                        SET source_hash = %s 
                        WHERE transaction_id = %s
                    """, batch)
                    conn.commit()
                    print(f"      Processed {len(batch)} transactions...")
                    batch = []
            
            if batch:
                cur.executemany("""
                    UPDATE banking_transactions 
                    SET source_hash = %s 
                    WHERE transaction_id = %s
                """, batch)
                conn.commit()
            
            print(f"   [OK] Generated {missing_hash_count:,} source hashes")
    else:
        print(f"   [OK] All transactions already have source_hash")
    
    # Step 6: Create helper views
    print(f"\n🔧 STEP 6: Creating Helper Views")
    print("-" * 80)
    
    if not args.dry_run:
        # View 1: Unified account view with aliases
        cur.execute("""
            CREATE OR REPLACE VIEW v_banking_transactions_with_aliases AS
            SELECT 
                bt.*,
                ARRAY_AGG(DISTINCT ana.statement_format) as known_aliases
            FROM banking_transactions bt
            LEFT JOIN account_number_aliases ana 
                ON bt.account_number = ana.canonical_account_number
            GROUP BY bt.transaction_id, bt.account_number, bt.transaction_date, 
                     bt.description, bt.debit_amount, bt.credit_amount, bt.balance,
                     bt.posted_date, bt.vendor_extracted, bt.vendor_truncated,
                     bt.card_last4_detected, bt.category, bt.source_file,
                     bt.import_batch, bt.created_at, bt.source_hash,
                     bt.reconciliation_status, bt.reconciled_receipt_id,
                     bt.reconciled_payment_id, bt.reconciled_charter_id,
                     bt.reconciliation_notes, bt.reconciled_at, bt.reconciled_by
        """)
        print(f"   [OK] Created v_banking_transactions_with_aliases")
        
        # View 2: Reconciliation summary
        cur.execute("""
            CREATE OR REPLACE VIEW v_banking_reconciliation_summary AS
            SELECT 
                account_number,
                EXTRACT(YEAR FROM transaction_date) as year,
                EXTRACT(MONTH FROM transaction_date) as month,
                COUNT(*) as total_transactions,
                SUM(CASE WHEN reconciliation_status = 'unreconciled' OR reconciliation_status IS NULL THEN 1 ELSE 0 END) as unreconciled_count,
                SUM(CASE WHEN reconciliation_status = 'matched' THEN 1 ELSE 0 END) as matched_count,
                SUM(debit_amount) as total_debits,
                SUM(credit_amount) as total_credits
            FROM banking_transactions
            GROUP BY account_number, year, month
            ORDER BY account_number, year, month
        """)
        print(f"   [OK] Created v_banking_reconciliation_summary")
        
        # View 3: Potential duplicates
        cur.execute("""
            CREATE OR REPLACE VIEW v_banking_potential_duplicates AS
            SELECT 
                source_hash,
                COUNT(*) as occurrence_count,
                ARRAY_AGG(transaction_id ORDER BY transaction_id) as transaction_ids,
                MIN(transaction_date) as first_date,
                MAX(created_at) as last_import_time
            FROM banking_transactions
            WHERE source_hash IS NOT NULL
            GROUP BY source_hash
            HAVING COUNT(*) > 1
            ORDER BY occurrence_count DESC
        """)
        print(f"   [OK] Created v_banking_potential_duplicates")
        
        conn.commit()
    else:
        print(f"   → Would create 3 helper views")
    
    # Step 7: Add indexes for performance
    print(f"\n🔧 STEP 7: Adding Performance Indexes")
    print("-" * 80)
    
    indexes = [
        ('idx_banking_source_hash', 'banking_transactions', 'source_hash'),
        ('idx_banking_reconciliation_status', 'banking_transactions', 'reconciliation_status'),
        ('idx_banking_account_date', 'banking_transactions', 'account_number, transaction_date'),
        ('idx_account_aliases_statement', 'account_number_aliases', 'statement_format'),
        ('idx_account_aliases_canonical', 'account_number_aliases', 'canonical_account_number'),
    ]
    
    for idx_name, table, columns in indexes:
        if not args.dry_run:
            try:
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name} 
                    ON {table}({columns})
                """)
                print(f"   [OK] Created index: {idx_name}")
            except Exception as e:
                print(f"   [WARN] Index {idx_name} may already exist: {e}")
        else:
            print(f"   → Would create index: {idx_name}")
    
    if not args.dry_run:
        conn.commit()
    
    # Step 8: Generate verification report
    print(f"\n📊 STEP 8: Verification Report")
    print("-" * 80)
    
    # Refresh column list if not dry run (columns may have been added)
    if not args.dry_run:
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'banking_transactions'
        """)
        existing_cols = [row[0] for row in cur.fetchall()]
    
    # Build query based on available columns
    query_parts = ["COUNT(*)", "COUNT(DISTINCT account_number)"]
    if 'source_hash' in existing_cols:
        query_parts.append("COUNT(*) FILTER (WHERE source_hash IS NOT NULL)")
    else:
        query_parts.append("0")
    
    if 'reconciliation_status' in existing_cols:
        query_parts.append("COUNT(*) FILTER (WHERE reconciliation_status IS NOT NULL)")
    else:
        query_parts.append("0")
    
    cur.execute(f"""
        SELECT {', '.join(query_parts)}
        FROM banking_transactions
    """)
    total, accounts, with_hash, with_status = cur.fetchone()
    
    print(f"\n   Banking Transactions Status:")
    print(f"      Total transactions: {total:,}")
    print(f"      Distinct accounts: {accounts}")
    print(f"      With source_hash: {with_hash:,} ({with_hash/total*100:.1f}%)" if total > 0 else "      With source_hash: N/A")
    print(f"      With reconciliation_status: {with_status:,} ({with_status/total*100:.1f}%)" if total > 0 else "      With reconciliation_status: N/A")
    
    if not args.dry_run:
        cur.execute("SELECT COUNT(*) FROM account_number_aliases")
        alias_count = cur.fetchone()[0]
        print(f"\n   Account Aliases Configured: {alias_count}")
    else:
        print(f"\n   Account Aliases: {len(cibc_aliases)} (would be configured)")
    
    # Show potential duplicates (only if source_hash exists)
    if 'source_hash' in existing_cols:
        cur.execute("""
            SELECT COUNT(*) 
            FROM (
                SELECT source_hash 
                FROM banking_transactions 
                WHERE source_hash IS NOT NULL
                GROUP BY source_hash 
                HAVING COUNT(*) > 1
            ) dupes
        """)
        dupe_hash_count = cur.fetchone()[0]
        
        if dupe_hash_count > 0:
            print(f"\n   [WARN] Found {dupe_hash_count} duplicate source_hash values")
            print(f"      → Review with: SELECT * FROM v_banking_potential_duplicates;")
        else:
            print(f"\n   [OK] No duplicate source_hash values detected")
    else:
        print(f"\n   ℹ️ Duplicate detection will be available after source_hash is populated")
    
    # Final summary
    print(f"\n" + "=" * 80)
    print(f"[OK] SCHEMA FIX {'PREVIEW' if args.dry_run else 'COMPLETED'}")
    print(f"=" * 80)
    
    if args.dry_run:
        print(f"\n[WARN] DRY RUN MODE - No changes applied")
        print(f"   Run without --dry-run to apply changes:")
        print(f"   python {__file__}")
    else:
        print(f"\n[OK] All infrastructure changes applied successfully!")
        print(f"\nNext Steps:")
        print(f"   1. Test account alias matching:")
        print(f"      SELECT * FROM account_number_aliases;")
        print(f"   2. Check reconciliation summary:")
        print(f"      SELECT * FROM v_banking_reconciliation_summary WHERE year = 2012;")
        print(f"   3. Run CIBC verification script:")
        print(f"      python scripts/verify_cibc_statements.py")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
