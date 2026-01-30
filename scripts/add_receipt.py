#!/usr/bin/env python3
"""
Receipt entry tool for adding missing cash receipts.
Supports individual entry and CSV bulk import with proper GST calculation.

Usage:
  # Single receipt entry (interactive)
  python scripts/add_receipt.py

  # Command-line entry
  python scripts/add_receipt.py --date 2012-12-31 --vendor "Liquor Barn" --amount 204.26 --gst 9.56 --category hospitality_supplies

  # CSV bulk import
  python scripts/add_receipt.py --csv receipts_2012.csv

CSV Format: date,vendor,amount,gst,category,description
Example: 2012-12-31,Liquor Barn,204.26,9.56,hospitality_supplies,Holiday beverages
"""
import os
import sys
import csv
import argparse
import hashlib
from datetime import datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

def connect():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    )

def calculate_gst(gross_amount, gst_amount=None, province='AB'):
    """Calculate GST if not provided, or validate if provided."""
    TAX_RATES = {
        'AB': 0.05, 'SK': 0.11, 'BC': 0.12, 'MB': 0.12, 
        'ON': 0.13, 'QC': 0.14975, 'NB': 0.15, 'NS': 0.15, 
        'PE': 0.15, 'NL': 0.15, 'YT': 0.05, 'NT': 0.05, 'NU': 0.05
    }
    rate = TAX_RATES.get(province, 0.05)
    
    if gst_amount is None:
        # Calculate GST included in gross
        gst = gross_amount * rate / (1 + rate)
    else:
        gst = Decimal(str(gst_amount))
    
    net = gross_amount - gst
    return round(gst, 2), round(net, 2)

def generate_source_hash(date, vendor, amount, description=''):
    """Generate deterministic hash for duplicate detection."""
    key = f"{date}|{vendor}|{amount}|{description}".lower().strip()
    return hashlib.sha256(key.encode()).hexdigest()

def check_duplicate(cur, source_hash):
    """Check if receipt already exists."""
    cur.execute("""
        SELECT id, receipt_date, vendor_name, gross_amount
        FROM receipts
        WHERE source_hash = %s
    """, (source_hash,))
    return cur.fetchone()

def add_receipt(cur, date, vendor, gross_amount, gst_amount=None, category='expense', 
                description='', payment_method='cash', dry_run=False):
    """Add a single receipt to the database."""
    
    # Calculate GST and net
    gst, net = calculate_gst(Decimal(str(gross_amount)), gst_amount)
    
    # Generate hash for duplicate check
    source_hash = generate_source_hash(date, vendor, gross_amount, description)
    
    # Check for duplicate
    existing = check_duplicate(cur, source_hash)
    if existing:
        print(f"[FAIL] DUPLICATE: Receipt already exists (id={existing['id']}, {existing['receipt_date']}, {existing['vendor_name']}, ${existing['gross_amount']})")
        return None
    
    if dry_run:
        print(f"✓ Would add: {date} | {vendor:<30} | Gross: ${gross_amount:>8.2f} | GST: ${gst:>6.2f} | Net: ${net:>8.2f} | {category}")
        return None
    
    # Insert receipt
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            category, description, payment_method, source_hash, 
            source_system, created_from_banking, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual_entry', false, NOW()
        )
        RETURNING id
    """, (date, vendor, gross_amount, gst, net, category, description, payment_method, source_hash))
    
    result = cur.fetchone()
    receipt_id = result['id'] if isinstance(result, dict) else result[0]
    print(f"[OK] Added receipt #{receipt_id}: {date} | {vendor} | ${gross_amount:.2f}")
    return receipt_id

def interactive_entry():
    """Interactive receipt entry mode."""
    print("\n" + "=" * 80)
    print("INTERACTIVE RECEIPT ENTRY")
    print("=" * 80)
    print("Enter receipt details (or 'q' to quit)\n")
    
    receipts = []
    while True:
        try:
            date_str = input("Date (YYYY-MM-DD): ").strip()
            if date_str.lower() == 'q':
                break
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            vendor = input("Vendor name: ").strip()
            if not vendor:
                print("[FAIL] Vendor name required")
                continue
            
            amount_str = input("Total amount (gross): $").strip()
            gross_amount = Decimal(amount_str)
            
            gst_str = input("GST amount (press Enter to auto-calculate): $").strip()
            gst_amount = Decimal(gst_str) if gst_str else None
            
            category = input("Category (default: expense): ").strip() or 'expense'
            description = input("Description (optional): ").strip()
            payment_method = input("Payment method (default: cash): ").strip() or 'cash'
            
            receipts.append({
                'date': date,
                'vendor': vendor,
                'gross_amount': gross_amount,
                'gst_amount': gst_amount,
                'category': category,
                'description': description,
                'payment_method': payment_method
            })
            
            another = input("\nAdd another receipt? (y/n): ").strip().lower()
            if another != 'y':
                break
        except KeyboardInterrupt:
            print("\n\nCancelled by user")
            return []
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            continue
    
    return receipts

def bulk_import_csv(csv_path, dry_run=False):
    """Import receipts from CSV file."""
    receipts = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                try:
                    receipts.append({
                        'date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
                        'vendor': row['vendor'].strip(),
                        'gross_amount': Decimal(row['amount']),
                        'gst_amount': Decimal(row['gst']) if row.get('gst') else None,
                        'category': row.get('category', 'expense').strip(),
                        'description': row.get('description', '').strip(),
                        'payment_method': row.get('payment_method', 'cash').strip()
                    })
                except Exception as e:
                    print(f"[FAIL] Error on line {i}: {e}")
                    continue
    except FileNotFoundError:
        print(f"[FAIL] File not found: {csv_path}")
        return []
    except Exception as e:
        print(f"[FAIL] Error reading CSV: {e}")
        return []
    
    return receipts

def main():
    parser = argparse.ArgumentParser(description='Add missing receipts to database')
    parser.add_argument('--date', help='Receipt date (YYYY-MM-DD)')
    parser.add_argument('--vendor', help='Vendor name')
    parser.add_argument('--amount', type=float, help='Gross amount')
    parser.add_argument('--gst', type=float, help='GST amount (auto-calculated if omitted)')
    parser.add_argument('--category', default='expense', help='Expense category')
    parser.add_argument('--description', default='', help='Receipt description')
    parser.add_argument('--payment-method', default='cash', help='Payment method')
    parser.add_argument('--csv', help='Import from CSV file')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--apply', action='store_true', help='Apply changes (required for write)')
    args = parser.parse_args()
    
    # Collect receipts
    receipts = []
    if args.csv:
        print(f"📁 Reading CSV: {args.csv}")
        receipts = bulk_import_csv(args.csv, dry_run=args.dry_run or not args.apply)
    elif args.date and args.vendor and args.amount:
        # Command-line entry
        receipts = [{
            'date': datetime.strptime(args.date, '%Y-%m-%d').date(),
            'vendor': args.vendor,
            'gross_amount': Decimal(str(args.amount)),
            'gst_amount': Decimal(str(args.gst)) if args.gst else None,
            'category': args.category,
            'description': args.description,
            'payment_method': args.payment_method
        }]
    else:
        # Interactive mode
        receipts = interactive_entry()
    
    if not receipts:
        print("No receipts to process")
        return
    
    # Process receipts
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    dry_run = args.dry_run or not args.apply
    mode = "DRY RUN" if dry_run else "APPLYING"
    
    print(f"\n{'=' * 80}")
    print(f"{mode}: Adding {len(receipts)} receipt(s)")
    print("=" * 80)
    
    added_count = 0
    duplicate_count = 0
    error_count = 0
    
    for receipt in receipts:
        try:
            result = add_receipt(cur, dry_run=dry_run, **receipt)
            if result is not None:
                added_count += 1
            elif result is None and not dry_run:
                duplicate_count += 1
        except Exception as e:
            import traceback
            print(f"[FAIL] Error adding receipt: {e}")
            traceback.print_exc()
            error_count += 1
    
    if not dry_run and added_count > 0:
        conn.commit()
        print(f"\n[OK] Successfully added {added_count} receipt(s)")
    elif dry_run:
        print(f"\n💡 Run with --apply to write {len(receipts)} receipt(s) to database")
    
    if duplicate_count > 0:
        print(f"[WARN]  Skipped {duplicate_count} duplicate(s)")
    if error_count > 0:
        print(f"[FAIL] Failed {error_count} receipt(s)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
