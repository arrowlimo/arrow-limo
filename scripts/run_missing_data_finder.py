import pandas as pd
import psycopg2
from pathlib import Path
import logging
from datetime import datetime
import hashlib
import os

print("Starting QuickBooks missing data analysis...")

# Configure paths
qb_path = Path('L:/limo/quickbooks')
report_path = Path('L:/limo/reports/missing_data')
report_path.mkdir(parents=True, exist_ok=True)

# Set up logging
logging.basicConfig(
    filename=report_path / 'missing_data.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Database configuration
db_config = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',  # Added default password
    'host': 'localhost'
}

print("Connecting to database...")
try:
    conn = psycopg2.connect(**db_config)
    print("Database connection successful")
except Exception as e:
    print(f"Database connection failed: {str(e)}")
    exit(1)

# Get database journal entries
cur = conn.cursor()
print("Retrieving journal entries from database...")
try:
    # Use correct case for column names
    cur.execute('SELECT "Date" as date, "Amount" as amount, "Name" as name, "Memo" as memo FROM journal')
    db_entries = cur.fetchall()
    print(f"Retrieved {len(db_entries)} journal entries from database")
except Exception as e:
    print(f"Error retrieving journal entries: {str(e)}")
    db_entries = []

# Create lookup set for comparison
db_lookup = set()
for entry in db_entries:
    date, amount, name, memo = entry
    key = f"{date}|{amount}|{name or ''}|{memo or ''}"
    db_lookup.add(hashlib.md5(key.encode()).hexdigest())

# Find and process journal files
print("Scanning QuickBooks files...")
missing_entries = []
journal_files = list(qb_path.glob('**/*.[xc]*'))
print(f"Found {len(journal_files)} potential QuickBooks files")

for file_path in journal_files[:5]:  # Start with just 5 files
    try:
        print(f"Processing {file_path.name}...")
        if file_path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        elif file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        else:
            continue
            
        # Find relevant columns
        date_col = None
        amount_col = None
        for col in df.columns:
            col_lower = str(col).lower()
            if 'date' in col_lower:
                date_col = col
            elif any(term in col_lower for term in ['amount', 'total', 'sum']):
                amount_col = col
                
        if not date_col or not amount_col:
            print(f"Skipping {file_path.name} - missing required columns")
            continue
            
        # Check each row
        file_missing = []
        for _, row in df.iterrows():
            try:
                entry_date = pd.to_datetime(row[date_col]).date()
                entry_amount = float(row[amount_col]) if pd.notna(row[amount_col]) else 0
                entry_name = str(row.get('Name', '')) if 'Name' in df.columns else ''
                entry_memo = str(row.get('Memo', '')) if 'Memo' in df.columns else ''
                
                # Create hash for comparison
                key = f"{entry_date}|{entry_amount}|{entry_name}|{entry_memo}"
                entry_hash = hashlib.md5(key.encode()).hexdigest()
                
                # Check if in database
                if entry_hash not in db_lookup:
                    file_missing.append({
                        'file': file_path.name,
                        'date': entry_date,
                        'amount': entry_amount,
                        'name': entry_name,
                        'memo': entry_memo
                    })
            except Exception as e:
                logging.error(f"Error processing row in {file_path.name}: {str(e)}")
        
        print(f"Found {len(file_missing)} missing entries in {file_path.name}")
        missing_entries.extend(file_missing)
        
    except Exception as e:
        print(f"Error processing file {file_path.name}: {str(e)}")

# Save missing entries report
print(f"Total missing entries found: {len(missing_entries)}")
if missing_entries:
    df_missing = pd.DataFrame(missing_entries)
    csv_path = report_path / 'missing_journal_entries.csv'
    df_missing.to_csv(csv_path, index=False)
    print(f"Missing entries saved to {csv_path}")
    
    # Generate markdown report
    md_report = [
        "# QuickBooks Missing Data Report",
        f"Generated: {datetime.now()}",
        "",
        f"## Summary",
        f"- Scanned files: {len(journal_files[:5])}",
        f"- Missing entries found: {len(missing_entries)}",
        "",
        "## Sample Missing Entries",
        "| File | Date | Amount | Name |",
        "|------|------|--------|------|"
    ]
    
    # Add sample entries
    for entry in missing_entries[:20]:
        md_report.append(
            f"| {entry['file']} | {entry['date']} | ${entry['amount']:.2f} | {entry['name']} |"
        )
    
    if len(missing_entries) > 20:
        md_report.append(f"\n*...and {len(missing_entries) - 20} more entries*")
    
    # Write report
    md_path = report_path / 'missing_data_summary.md'
    with open(md_path, 'w') as f:
        f.write('\n'.join(md_report))
    
    print(f"Summary report saved to {md_path}")
else:
    print("No missing entries found.")

print("Analysis complete!")