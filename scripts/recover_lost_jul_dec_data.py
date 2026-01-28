"""
Check for any recoverable Jul-Dec 2012 data from various sources.

This script searches for:
1. Any CSV files with jul/dec 2012 data
2. Database banking_transactions for Jul-Dec 2012
3. VS Code workspace history
4. Temporary files
5. Git history (if repo exists)
"""
import os
import sys
import csv
import glob
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from api import get_db_connection
except ImportError:
    print("[WARN]  Could not import get_db_connection - will skip DB checks")
    get_db_connection = None


def search_csv_files():
    """Search for any CSV files containing jul-dec 2012 data."""
    print("\n📁 Searching CSV files for Jul-Dec 2012 data...")
    print("=" * 70)
    
    patterns = [
        'l:/limo/data/*2012*.csv',
        'l:/limo/reports/*2012*.csv',
        'l:/limo/reports/missing_banking_rows_*.csv',
        'l:/limo/reports/screenshot_rows_*.csv',
    ]
    
    found_files = []
    for pattern in patterns:
        for filepath in glob.glob(pattern):
            filename = os.path.basename(filepath)
            # Check for jul-dec patterns
            if any(month in filename.lower() for month in ['jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                size = os.path.getsize(filepath)
                modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                found_files.append((filepath, size, modified))
                
    if found_files:
        print(f"[OK] Found {len(found_files)} potential data files:")
        for filepath, size, modified in sorted(found_files, key=lambda x: x[2], reverse=True):
            print(f"   {os.path.basename(filepath):50s} | {size:>8,} bytes | {modified:%Y-%m-%d %H:%M}")
    else:
        print("[FAIL] No CSV files found with Jul-Dec 2012 patterns")
    
    return found_files


def check_database():
    """Check database for Jul-Dec 2012 transactions."""
    if not get_db_connection:
        return
    
    print("\n🗄️  Checking database for Jul-Dec 2012 transactions...")
    print("=" * 70)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check CIBC checking account (0228362)
        cur.execute("""
            SELECT 
                TO_CHAR(transaction_date, 'Mon') as month,
                COUNT(*) as count,
                SUM(debit_amount) as total_debits,
                SUM(credit_amount) as total_credits
            FROM banking_transactions
            WHERE account_number = '0228362'
              AND transaction_date >= '2012-07-01'
              AND transaction_date <= '2012-12-31'
            GROUP BY TO_CHAR(transaction_date, 'Mon'), EXTRACT(MONTH FROM transaction_date)
            ORDER BY EXTRACT(MONTH FROM transaction_date)
        """)
        
        cibc_rows = cur.fetchall()
        
        if cibc_rows:
            print("[OK] CIBC Checking (0228362) - Jul-Dec 2012:")
            print(f"   {'Month':>8} | {'Count':>6} | {'Debits':>12} | {'Credits':>12}")
            print("   " + "-" * 55)
            for month, count, debits, credits in cibc_rows:
                debits = debits or 0
                credits = credits or 0
                print(f"   {month:>8} | {count:>6} | ${debits:>11,.2f} | ${credits:>11,.2f}")
            
            total_count = sum(row[1] for row in cibc_rows)
            total_debits = sum(row[2] or 0 for row in cibc_rows)
            total_credits = sum(row[3] or 0 for row in cibc_rows)
            print("   " + "-" * 55)
            print(f"   {'TOTAL':>8} | {total_count:>6} | ${total_debits:>11,.2f} | ${total_credits:>11,.2f}")
        else:
            print("[FAIL] No CIBC transactions found in database for Jul-Dec 2012")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"[FAIL] Database check failed: {e}")


def check_validation_summaries():
    """Check for validation summary text files."""
    print("\n📄 Checking validation summary files...")
    print("=" * 70)
    
    summaries = glob.glob('l:/limo/reports/*2012*validation*.txt')
    
    if summaries:
        print(f"[OK] Found {len(summaries)} validation summaries:")
        for filepath in sorted(summaries):
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            print(f"   {filename:50s} | {size:>8,} bytes | {modified:%Y-%m-%d %H:%M}")
            
            # Show first few lines
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:5]
                    if lines:
                        print(f"      Preview: {lines[0].strip()[:70]}")
            except:
                pass
    else:
        print("[FAIL] No validation summary files found")
    
    return summaries


def check_screenshot_files():
    """Check for screenshot CSV files."""
    print("\n🖼️  Checking screenshot capture files...")
    print("=" * 70)
    
    screenshots = glob.glob('l:/limo/reports/screenshot_rows_*2012*.csv')
    
    if screenshots:
        print(f"[OK] Found {len(screenshots)} screenshot capture files:")
        for filepath in sorted(screenshots):
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            # Count rows
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    row_count = sum(1 for _ in csv.reader(f)) - 1  # Subtract header
            except:
                row_count = 0
            
            print(f"   {filename:50s} | {row_count:>4} rows | {modified:%Y-%m-%d %H:%M}")
    else:
        print("[FAIL] No screenshot capture files found")
    
    return screenshots


def main():
    print("\n🔍 RECOVERY SCAN: Jul-Dec 2012 CIBC Data")
    print("=" * 70)
    print("Searching for any recoverable data from yesterday's session...")
    
    csv_files = search_csv_files()
    summaries = check_validation_summaries()
    screenshots = check_screenshot_files()
    check_database()
    
    print("\n" + "=" * 70)
    print("📊 RECOVERY SUMMARY")
    print("=" * 70)
    print(f"CSV files found:         {len(csv_files)}")
    print(f"Validation summaries:    {len(summaries)}")
    print(f"Screenshot captures:     {len(screenshots)}")
    
    if csv_files or summaries or screenshots:
        print("\n[OK] Some data may be recoverable!")
        print("\nNext steps:")
        print("1. Review files listed above")
        print("2. Check database for existing Jul-Dec 2012 transactions")
        print("3. Re-verify any suspicious data before importing")
    else:
        print("\n[FAIL] No recoverable data files found")
        print("\nYou may need to re-enter Jul-Dec 2012 data from PDF screenshots")
    
    print("\n🛡️  PROTECTION RECOMMENDATION:")
    print("   Run this in a separate terminal BEFORE starting new work:")
    print("   python scripts/auto_save_session_work.py")


if __name__ == '__main__':
    main()
