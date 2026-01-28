#!/usr/bin/env python3
"""
Email Invoice Parser Framework
Extracts invoice data from vendor emails (PDFs, text, HTML).
"""
import os
import re
import email
from email import policy
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


class VendorInvoiceExtractor:
    """Base class for vendor-specific invoice extractors."""
    
    vendor_patterns = {
        'HEFFNER AUTO': {
            'from': r'heffner|service@heffnerauto',
            'subject': r'invoice|statement',
            'invoice_num': r'invoice\s*#?\s*([A-Z0-9-]+)',
            'amount': r'\$?\s*([0-9,]+\.\d{2})',
            'date': r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        },
        'LEASE FINANCE GROUP': {
            'from': r'lfg|leasefinance',
            'subject': r'payment|invoice|statement',
            'invoice_num': r'account\s*#?\s*([A-Z0-9-]+)',
            'amount': r'\$?\s*([0-9,]+\.\d{2})',
            'date': r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        },
        'ROYNAT': {
            'from': r'roynat|scotiabank',
            'subject': r'lease|payment',
            'invoice_num': r'agreement\s*#?\s*([A-Z0-9-]+)',
            'amount': r'\$?\s*([0-9,]+\.\d{2})',
            'date': r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        },
    }
    
    def __init__(self, email_path: Path):
        self.email_path = email_path
        self.msg = None
        self.vendor = None
        self.invoice_data = {}
    
    def parse(self):
        """Parse email and extract invoice data."""
        with open(self.email_path, 'rb') as f:
            self.msg = email.message_from_binary_file(f, policy=policy.default)
        
        # Identify vendor
        from_addr = self.msg.get('From', '').lower()
        subject = self.msg.get('Subject', '').lower()
        
        for vendor, patterns in self.vendor_patterns.items():
            if re.search(patterns['from'], from_addr) or re.search(patterns['subject'], subject):
                self.vendor = vendor
                self._extract_invoice_data(patterns)
                break
        
        return self.invoice_data if self.vendor else None
    
    def _extract_invoice_data(self, patterns):
        """Extract invoice details using vendor-specific patterns."""
        body = self._get_body_text()
        
        # Extract invoice number
        inv_match = re.search(patterns['invoice_num'], body, re.IGNORECASE)
        if inv_match:
            self.invoice_data['invoice_number'] = inv_match.group(1).strip()
        
        # Extract amount (try to find largest dollar amount)
        amounts = re.findall(patterns['amount'], body)
        if amounts:
            cleaned = [Decimal(a.replace(',', '')) for a in amounts]
            self.invoice_data['amount'] = max(cleaned)
        
        # Extract date
        date_match = re.search(patterns['date'], body)
        if date_match:
            self.invoice_data['invoice_date'] = self._parse_date(date_match.group(1))
        
        self.invoice_data['vendor'] = self.vendor
        self.invoice_data['email_subject'] = self.msg.get('Subject', '')
        self.invoice_data['email_date'] = self.msg.get('Date', '')
    
    def _get_body_text(self):
        """Extract plain text from email body."""
        body = ""
        if self.msg.is_multipart():
            for part in self.msg.walk():
                if part.get_content_type() == 'text/plain':
                    body += part.get_content()
        else:
            body = self.msg.get_content()
        return body
    
    def _parse_date(self, date_str: str):
        """Parse date from various formats."""
        for fmt in ('%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%m-%d-%Y'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None


def scan_email_folder(folder_path: str, output_csv: str = None):
    """Scan folder for .eml files and extract invoice data."""
    folder = Path(folder_path)
    results = []
    
    for eml_file in folder.rglob('*.eml'):
        try:
            extractor = VendorInvoiceExtractor(eml_file)
            data = extractor.parse()
            if data:
                data['email_file'] = str(eml_file)
                results.append(data)
                print(f"✅ Extracted: {data.get('vendor')} - {data.get('invoice_number', 'N/A')} - ${data.get('amount', 0)}")
            else:
                print(f"⏭️  Skipped: {eml_file.name}")
        except Exception as e:
            print(f"❌ Error parsing {eml_file.name}: {e}")
    
    # Write to CSV if requested
    if output_csv and results:
        import csv
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['vendor', 'invoice_number', 'invoice_date', 'amount', 'email_subject', 'email_date', 'email_file']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({k: r.get(k, '') for k in fieldnames})
        print(f"\n📄 Wrote {len(results)} invoices to {output_csv}")
    
    return results


def import_to_database(invoice_data: list, dry_run: bool = True):
    """Import extracted invoices to vendor_account_ledger."""
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    conn.autocommit = False
    cur = conn.cursor()
    
    imported = 0
    skipped = 0
    
    try:
        for inv in invoice_data:
            vendor = inv.get('vendor')
            inv_num = inv.get('invoice_number')
            inv_date = inv.get('invoice_date')
            amount = inv.get('amount')
            
            if not all([vendor, inv_date, amount]):
                skipped += 1
                continue
            
            # Get or create vendor account
            cur.execute(
                "SELECT account_id FROM vendor_accounts WHERE UPPER(canonical_vendor) = UPPER(%s)",
                (vendor,)
            )
            row = cur.fetchone()
            if not row:
                if dry_run:
                    print(f"[DRY-RUN] Would create vendor account: {vendor}")
                else:
                    cur.execute(
                        """
                        INSERT INTO vendor_accounts (canonical_vendor, display_name)
                        VALUES (%s, %s) RETURNING account_id
                        """,
                        (vendor, vendor)
                    )
                    row = cur.fetchone()
            
            account_id = row[0] if row else None
            
            if dry_run:
                print(f"[DRY-RUN] Would import: {vendor} | {inv_num} | {inv_date} | ${amount}")
            else:
                # Check for duplicate
                cur.execute(
                    """
                    SELECT 1 FROM vendor_account_ledger 
                    WHERE account_id = %s AND external_ref = %s AND entry_type = 'INVOICE'
                    """,
                    (account_id, inv_num)
                )
                if cur.fetchone():
                    skipped += 1
                    continue
                
                cur.execute(
                    """
                    INSERT INTO vendor_account_ledger 
                    (account_id, entry_date, entry_type, amount, external_ref, notes)
                    VALUES (%s, %s, 'INVOICE', %s, %s, %s)
                    """,
                    (account_id, inv_date, amount, inv_num, inv.get('email_subject'))
                )
            imported += 1
        
        if not dry_run:
            conn.commit()
        
        print(f"\n{'[DRY-RUN] ' if dry_run else ''}Imported {imported}, skipped {skipped}")
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Import failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def main():
    """Example usage."""
    import argparse
    parser = argparse.ArgumentParser(description="Parse vendor invoices from emails")
    parser.add_argument("folder", help="Path to folder containing .eml files")
    parser.add_argument("--output-csv", help="Save extracted data to CSV")
    parser.add_argument("--import-db", action="store_true", help="Import to database")
    parser.add_argument("--apply", action="store_true", help="Apply DB changes (default is dry-run)")
    args = parser.parse_args()
    
    results = scan_email_folder(args.folder, args.output_csv)
    
    if args.import_db and results:
        dry_run = not args.apply
        import_to_database(results, dry_run=dry_run)


if __name__ == "__main__":
    main()
