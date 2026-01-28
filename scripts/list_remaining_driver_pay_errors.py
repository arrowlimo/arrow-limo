import os
import psycopg2
from collections import defaultdict

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    # Get only error files (not excluded)
    cur.execute("""
        SELECT file_path, file_type, error_message
        FROM staging_driver_pay_files
        WHERE status = 'error'
        ORDER BY file_type, file_path
    """)
    
    error_files = cur.fetchall()
    
    # Group by file type and error pattern
    by_type = defaultdict(list)
    by_error_pattern = defaultdict(list)
    
    for file_path, file_type, error_msg in error_files:
        by_type[file_type].append((file_path, error_msg))
        
        # Categorize error
        if 'NaT' in error_msg or 'nat' in error_msg.lower():
            by_error_pattern['Date parsing (NaT)'].append((file_path, file_type))
        elif 'required columns' in error_msg.lower() or 'missing' in error_msg.lower():
            by_error_pattern['Missing required columns'].append((file_path, file_type))
        elif 'no data' in error_msg.lower() or 'empty' in error_msg.lower():
            by_error_pattern['No valid data'].append((file_path, file_type))
        elif 'encoding' in error_msg.lower() or 'utf' in error_msg.lower():
            by_error_pattern['Encoding issues'].append((file_path, file_type))
        elif 'excel' in error_msg.lower() or 'xlsx' in error_msg.lower():
            by_error_pattern['Excel format issues'].append((file_path, file_type))
        elif 'pdf' in error_msg.lower():
            by_error_pattern['PDF parsing issues'].append((file_path, file_type))
        else:
            by_error_pattern['Other errors'].append((file_path, file_type))
    
    output = []
    output.append("=" * 80)
    output.append("REMAINING ERROR FILES REQUIRING REVIEW")
    output.append("=" * 80)
    output.append(f"Total error files: {len(error_files)}")
    output.append("")
    
    # Summary by type
    output.append("BY FILE TYPE:")
    output.append("-" * 80)
    for ftype in sorted(by_type.keys()):
        output.append(f"  {ftype}: {len(by_type[ftype])} files")
    output.append("")
    
    # Summary by error pattern
    output.append("BY ERROR PATTERN:")
    output.append("-" * 80)
    for pattern in sorted(by_error_pattern.keys()):
        output.append(f"  {pattern}: {len(by_error_pattern[pattern])} files")
    output.append("")
    
    # Detailed listing by error pattern
    output.append("=" * 80)
    output.append("DETAILED LISTING BY ERROR PATTERN")
    output.append("=" * 80)
    output.append("")
    
    for pattern in sorted(by_error_pattern.keys()):
        output.append(f"\n{'='*80}")
        output.append(f"{pattern.upper()} ({len(by_error_pattern[pattern])} files)")
        output.append('='*80)
        for file_path, file_type in sorted(by_error_pattern[pattern]):
            output.append(f"File: {file_path}")
            output.append(f"Type: {file_type}")
            # Get the error message
            for fp, ft, em in error_files:
                if fp == file_path:
                    output.append(f"Error: {em}")
                    break
            output.append("")
    
    # Write to file
    output_text = "\n".join(output)
    with open("driver_pay_remaining_errors.txt", "w", encoding="utf-8") as f:
        f.write(output_text)
    print(output_text)
    print(f"\nReport saved to: driver_pay_remaining_errors.txt")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
