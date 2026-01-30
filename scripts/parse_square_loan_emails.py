#!/usr/bin/env python3
"""
Parse Square Loan emails to extract loan approvals and daily payment summaries.
Identifies missing loans and adds them to square_capital_loans table.
"""

import os
import psycopg2
from datetime import datetime
from decimal import Decimal

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Email data parsed from user's inbox
LOAN_EMAILS = [
    # Format: (date, subject, type)
    ("2025-01-07", "Approved: Your money is on the way", "approval"),
    ("2025-01-05", "A $68,600 loan offer for Arrow Limousine", "offer"),
    
    ("2025-09-29", "Approved: Your money is on the way", "approval"),
    ("2025-09-26", "A $65,500 loan offer for Arrow Limousine", "offer"),
]

# Daily payment summaries (sampling - user has hundreds)
PAYMENT_SUMMARIES = [
    "2026-01-28", "2026-01-27", "2026-01-24", "2026-01-23", "2026-01-22",
    "2026-01-21", "2026-01-20", "2026-01-19", "2026-01-17", "2026-01-16",
    # ... many more dates available
]


def extract_loan_amount(subject):
    """Extract dollar amount from loan offer subject line."""
    import re
    match = re.search(r'\$([0-9,]+)', subject)
    if match:
        amount_str = match.group(1).replace(',', '')
        return Decimal(amount_str)
    return None


def identify_loans():
    """Parse emails to identify all loan approvals and amounts."""
    loans = []
    
    # Group by approval date
    approvals = [e for e in LOAN_EMAILS if e[2] == "approval"]
    offers = {e[0]: e[1] for e in LOAN_EMAILS if e[2] == "offer"}
    
    for approval_date, subject, _ in approvals:
        # Find closest offer before approval date
        approval_dt = datetime.strptime(approval_date, "%Y-%m-%d")
        
        # Look for offers within 7 days before approval
        matching_amount = None
        for offer_date, offer_subject in offers.items():
            offer_dt = datetime.strptime(offer_date, "%Y-%m-%d")
            days_diff = (approval_dt - offer_dt).days
            if 0 <= days_diff <= 7:
                matching_amount = extract_loan_amount(offer_subject)
                break
        
        if matching_amount:
            loans.append({
                'approval_date': approval_date,
                'amount': matching_amount,
                'loan_id': f"SQ-LOAN-{approval_date.replace('-', '')}-EMAIL"
            })
    
    return loans


def check_existing_loans(conn):
    """Check which loans are already in database."""
    cur = conn.cursor()
    cur.execute("""
        SELECT square_loan_id, loan_amount, received_date, status
        FROM square_capital_loans
        ORDER BY received_date
    """)
    
    existing = []
    for row in cur.fetchall():
        existing.append({
            'loan_id': row[0],
            'amount': row[1],
            'date': row[2].strftime("%Y-%m-%d") if row[2] else None,
            'status': row[3]
        })
    
    cur.close()
    return existing


def add_missing_loan(conn, loan, dry_run=True):
    """Add a missing loan to the database."""
    cur = conn.cursor()
    
    try:
        # Check if loan already exists by date and amount
        cur.execute("""
            SELECT square_loan_id FROM square_capital_loans
            WHERE received_date = %s AND loan_amount = %s
        """, (loan['approval_date'], loan['amount']))
        
        if cur.fetchone():
            print(f"⚠️  Loan already exists: {loan['approval_date']} ${loan['amount']:,.2f}")
            return False
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Adding loan:")
        print(f"  Date: {loan['approval_date']}")
        print(f"  Amount: ${loan['amount']:,.2f}")
        print(f"  Loan ID: {loan['loan_id']}")
        
        if not dry_run:
            cur.execute("""
                INSERT INTO square_capital_loans (
                    square_loan_id, loan_amount, received_date,
                    status, description, created_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW())
                RETURNING loan_id
            """, (
                loan['loan_id'],
                loan['amount'],
                loan['approval_date'],
                'active',  # Will update status based on payment records
                f"Square Capital loan from email approval {loan['approval_date']}"
            ))
            
            new_id = cur.fetchone()[0]
            conn.commit()
            print(f"✓ Inserted loan record (loan_id={new_id})")
            return True
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error adding loan: {e}")
        return False
    finally:
        cur.close()


def main():
    import sys
    dry_run = '--write' not in sys.argv
    
    print("=" * 70)
    print("SQUARE LOAN EMAIL PARSER")
    print("=" * 70)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Use --write to apply changes\n")
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        # Identify all loans from emails
        print("\n📧 Parsing loan emails...")
        email_loans = identify_loans()
        
        print(f"\nFound {len(email_loans)} loan approvals in emails:")
        for loan in email_loans:
            print(f"  • {loan['approval_date']}: ${loan['amount']:,.2f}")
        
        # Check what's already in database
        print("\n💾 Checking database...")
        existing_loans = check_existing_loans(conn)
        
        print(f"\nFound {len(existing_loans)} loans in database:")
        for loan in existing_loans:
            print(f"  • {loan['date']}: ${loan['amount']:,.2f} ({loan['status']})")
        
        # Find missing loans
        missing = []
        for email_loan in email_loans:
            found = False
            for db_loan in existing_loans:
                if (email_loan['approval_date'] == db_loan['date'] and 
                    email_loan['amount'] == db_loan['amount']):
                    found = True
                    break
            if not found:
                missing.append(email_loan)
        
        print(f"\n🔍 Analysis:")
        print(f"  Loans in emails: {len(email_loans)}")
        print(f"  Loans in database: {len(existing_loans)}")
        print(f"  Missing from database: {len(missing)}")
        
        if missing:
            print(f"\n{'[DRY RUN] ' if dry_run else ''}MISSING LOANS:")
            for loan in missing:
                add_missing_loan(conn, loan, dry_run)
        else:
            print("\n✅ All email loans are already in the database!")
        
        print("\n" + "=" * 70)
        print("✓ PARSING COMPLETE")
        print("=" * 70)
        
        if dry_run and missing:
            print("\n💡 Run with --write to add missing loans to database")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
