#!/usr/bin/env python3
"""
Bulk GlobalPayments Merchant Statement Processor
Processes hundreds of GlobalPayments merchant statement PDFs automatically.

This script:
1. Scans directories for GlobalPayments merchant statement PDFs
2. Extracts transaction data using OCR and pattern matching
3. Consolidates all data into comprehensive CSV files
4. Handles multi-page statements and various formats
5. Creates reconciliation-ready output files

Usage:
    python scripts/bulk_process_globalpayments_statements.py --scan --write
"""

import argparse
import json
import csv
import re
import os
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
import PyPDF2
import pdfplumber
from concurrent.futures import ThreadPoolExecutor
import logging


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GlobalPaymentsProcessor:
    def __init__(self):
        self.processed_statements = []
        self.all_transactions = []
        self.processing_errors = []
        
        # Common patterns for GlobalPayments statements
        self.patterns = {
            'statement_date': [
                r'Statement Date\s+(\d{1,2}/\d{1,2}/\d{2,4})',
                r'Statement\s+Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})',
                r'Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})'
            ],
            'merchant_number': [
                r'Merchant Number\s+(\d+)',
                r'Merchant\s+Number:\s*(\d+)',
                r'MID:\s*(\d+)'
            ],
            'chain_number': [
                r'Chain Number\s+([\d-]+)',
                r'Chain\s+Number:\s*([\d-]+)'
            ],
            'deposits_section': [
                r'Day\s+Ref\.?\s*No\.?\s+Items\s+Sales\s+Returns\s+(?:Non-?funded|Nonfunded)\s+Discount\s+Net\s+Deposit\s*((?:\d{2}\s+\d+\s+\d+\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s*\n?)+)',
                r'DEPOSITS?\s*\n.*?Day.*?Net\s+Deposit\s*((?:\d{1,2}\s+\d+\s+\d+\s+[\d,]+\.?\d*(?:\s+[\d,]+\.?\d*){4,}\s*\n?)+)'
            ],
            'deposit_line': [
                r'(\d{1,2})\s+(\d{8,})\s+(\d+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)',
                r'(\d{1,2})\s+(\d+)\s+(\d+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)'
            ]
        }
    
    def find_globalpayments_pdfs(self, search_paths):
        """Find all GlobalPayments merchant statement PDFs."""
        pdf_files = []
        
        for search_path in search_paths:
            path = Path(search_path)
            if not path.exists():
                logger.warning(f"Path does not exist: {search_path}")
                continue
            
            # Search for PDFs with GlobalPayments-related names
            patterns = [
                "*global*payment*",
                "*merchant*statement*",
                "*globalpayments*",
                "*gp_statement*",
                "*merchant_stmt*"
            ]
            
            for pattern in patterns:
                for pdf_file in path.rglob(pattern + ".pdf"):
                    if pdf_file.is_file():
                        pdf_files.append(pdf_file)
                        logger.info(f"Found PDF: {pdf_file}")
        
        # Remove duplicates
        unique_pdfs = list(set(pdf_files))
        logger.info(f"Found {len(unique_pdfs)} unique GlobalPayments PDFs")
        
        return unique_pdfs
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF using multiple methods."""
        text_content = ""
        
        try:
            # Method 1: PyPDF2
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
        except Exception as e:
            logger.warning(f"PyPDF2 failed for {pdf_path}: {e}")
        
        if not text_content.strip():
            try:
                # Method 2: pdfplumber (better for tables)
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n"
            except Exception as e:
                logger.warning(f"pdfplumber failed for {pdf_path}: {e}")
        
        return text_content
    
    def extract_statement_info(self, text):
        """Extract basic statement information."""
        info = {}
        
        # Extract statement date
        for pattern in self.patterns['statement_date']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['statement_date'] = match.group(1)
                break
        
        # Extract merchant number
        for pattern in self.patterns['merchant_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['merchant_number'] = match.group(1)
                break
        
        # Extract chain number
        for pattern in self.patterns['chain_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['chain_number'] = match.group(1)
                break
        
        return info
    
    def extract_deposit_transactions(self, text, statement_info):
        """Extract deposit transactions from statement text."""
        transactions = []
        
        # Look for deposits sections
        for deposits_pattern in self.patterns['deposits_section']:
            deposits_match = re.search(deposits_pattern, text, re.MULTILINE | re.IGNORECASE)
            
            if deposits_match:
                deposits_text = deposits_match.group(1)
                logger.debug(f"Found deposits section: {deposits_text[:200]}...")
                
                # Extract individual deposit lines
                for line_pattern in self.patterns['deposit_line']:
                    deposit_lines = re.findall(line_pattern, deposits_text)
                    
                    for line in deposit_lines:
                        try:
                            day, ref_no, items, sales, returns, non_funded, discount, net_deposit = line
                            
                            # Convert statement date + day to full date
                            transaction_date = self.calculate_transaction_date(
                                statement_info.get('statement_date'), int(day)
                            )
                            
                            transaction = {
                                'source_file': statement_info.get('source_file', ''),
                                'statement_date': statement_info.get('statement_date', ''),
                                'merchant_number': statement_info.get('merchant_number', ''),
                                'chain_number': statement_info.get('chain_number', ''),
                                'transaction_date': transaction_date,
                                'day': int(day),
                                'ref_number': ref_no,
                                'item_count': int(items),
                                'gross_sales': float(sales.replace(',', '')),
                                'returns': float(returns.replace(',', '')),
                                'non_funded': float(non_funded.replace(',', '')),
                                'discount_fees': float(discount.replace(',', '')),
                                'net_deposit': float(net_deposit.replace(',', ''))
                            }
                            
                            transactions.append(transaction)
                            
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Error parsing deposit line {line}: {e}")
                            continue
                
                if transactions:
                    logger.info(f"Extracted {len(transactions)} transactions from deposits section")
                    break
        
        return transactions
    
    def calculate_transaction_date(self, statement_date_str, day):
        """Calculate full transaction date from statement date and day."""
        if not statement_date_str:
            return f"UNKNOWN-{day:02d}"
        
        try:
            # Parse statement date (various formats)
            for fmt in ['%m/%d/%y', '%m/%d/%Y', '%d/%m/%y', '%d/%m/%Y']:
                try:
                    stmt_date = datetime.strptime(statement_date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return f"UNKNOWN-{day:02d}"
            
            # Create transaction date with same year/month, specific day
            transaction_date = stmt_date.replace(day=day)
            return transaction_date.strftime('%Y-%m-%d')
            
        except ValueError as e:
            logger.warning(f"Date calculation error for {statement_date_str}, day {day}: {e}")
            return f"UNKNOWN-{day:02d}"
    
    def process_single_pdf(self, pdf_path):
        """Process a single GlobalPayments PDF."""
        logger.info(f"Processing: {pdf_path}")
        
        try:
            # Extract text content
            text = self.extract_text_from_pdf(pdf_path)
            
            if not text.strip():
                logger.error(f"No text extracted from {pdf_path}")
                return None
            
            # Extract basic statement info
            statement_info = self.extract_statement_info(text)
            statement_info['source_file'] = str(pdf_path)
            
            # Extract transactions
            transactions = self.extract_deposit_transactions(text, statement_info)
            
            if not transactions:
                logger.warning(f"No transactions found in {pdf_path}")
                return None
            
            result = {
                'pdf_path': str(pdf_path),
                'statement_info': statement_info,
                'transactions': transactions,
                'transaction_count': len(transactions),
                'total_gross_sales': sum(t['gross_sales'] for t in transactions),
                'total_net_deposits': sum(t['net_deposit'] for t in transactions)
            }
            
            logger.info(f"Successfully processed {pdf_path}: {len(transactions)} transactions, "
                       f"${result['total_gross_sales']:,.2f} gross, ${result['total_net_deposits']:,.2f} net")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            self.processing_errors.append({
                'file': str(pdf_path),
                'error': str(e)
            })
            return None
    
    def process_all_pdfs(self, pdf_files, max_workers=4):
        """Process all PDFs with parallel processing."""
        logger.info(f"Processing {len(pdf_files)} PDFs with {max_workers} workers...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(self.process_single_pdf, pdf_files))
        
        # Filter successful results
        successful_results = [r for r in results if r is not None]
        
        # Consolidate all transactions
        for result in successful_results:
            self.processed_statements.append(result)
            self.all_transactions.extend(result['transactions'])
        
        logger.info(f"Successfully processed {len(successful_results)} PDFs")
        logger.info(f"Total transactions extracted: {len(self.all_transactions)}")
        logger.info(f"Processing errors: {len(self.processing_errors)}")
        
        return successful_results
    
    def save_consolidated_data(self, output_dir):
        """Save all extracted data to files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save all transactions as CSV
        if self.all_transactions:
            transactions_csv = output_path / f'globalpayments_all_transactions_{timestamp}.csv'
            df = pd.DataFrame(self.all_transactions)
            df = df.sort_values(['transaction_date', 'day'])
            df.to_csv(transactions_csv, index=False)
            logger.info(f"Saved {len(self.all_transactions)} transactions to {transactions_csv}")
        
        # Save processing summary
        summary_json = output_path / f'globalpayments_processing_summary_{timestamp}.json'
        summary = {
            'processing_date': datetime.now().isoformat(),
            'total_pdfs_processed': len(self.processed_statements),
            'total_transactions': len(self.all_transactions),
            'total_gross_sales': sum(t['gross_sales'] for t in self.all_transactions),
            'total_net_deposits': sum(t['net_deposit'] for t in self.all_transactions),
            'date_range': self.get_date_range(),
            'processed_files': [s['pdf_path'] for s in self.processed_statements],
            'processing_errors': self.processing_errors
        }
        
        with open(summary_json, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"Saved processing summary to {summary_json}")
        
        # Save monthly summary
        monthly_csv = output_path / f'globalpayments_monthly_summary_{timestamp}.csv'
        self.create_monthly_summary(monthly_csv)
        
        return {
            'transactions_csv': transactions_csv,
            'summary_json': summary_json,
            'monthly_csv': monthly_csv
        }
    
    def get_date_range(self):
        """Get the date range of processed transactions."""
        if not self.all_transactions:
            return None
        
        dates = [t['transaction_date'] for t in self.all_transactions if 'UNKNOWN' not in t['transaction_date']]
        if not dates:
            return None
        
        return {
            'earliest': min(dates),
            'latest': max(dates)
        }
    
    def create_monthly_summary(self, output_file):
        """Create monthly summary of transactions."""
        if not self.all_transactions:
            return
        
        # Group by year-month
        monthly_data = {}
        for transaction in self.all_transactions:
            if 'UNKNOWN' in transaction['transaction_date']:
                continue
            
            try:
                date_obj = datetime.strptime(transaction['transaction_date'], '%Y-%m-%d')
                month_key = date_obj.strftime('%Y-%m')
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        'month': month_key,
                        'transaction_count': 0,
                        'total_gross_sales': 0,
                        'total_net_deposits': 0,
                        'total_returns': 0,
                        'total_fees': 0
                    }
                
                monthly_data[month_key]['transaction_count'] += 1
                monthly_data[month_key]['total_gross_sales'] += transaction['gross_sales']
                monthly_data[month_key]['total_net_deposits'] += transaction['net_deposit']
                monthly_data[month_key]['total_returns'] += transaction['returns']
                monthly_data[month_key]['total_fees'] += transaction['discount_fees']
                
            except ValueError:
                continue
        
        # Save monthly summary
        monthly_df = pd.DataFrame(list(monthly_data.values()))
        monthly_df = monthly_df.sort_values('month')
        monthly_df.to_csv(output_file, index=False)
        logger.info(f"Saved monthly summary to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Bulk process GlobalPayments merchant statements')
    parser.add_argument('--scan', action='store_true',
                       help='Scan for GlobalPayments PDFs in common directories')
    parser.add_argument('--paths', nargs='+', 
                       default=['l:/limo/CIBC UPLOADS', 'l:/limo/pdf', 'l:/limo/docs'],
                       help='Paths to search for PDFs')
    parser.add_argument('--output', default='l:/limo/staging/globalpayments_bulk_processed',
                       help='Output directory for processed data')
    parser.add_argument('--write', action='store_true',
                       help='Write processed data to files')
    parser.add_argument('--max-workers', type=int, default=4,
                       help='Maximum number of parallel workers')
    
    args = parser.parse_args()
    
    print("🏦 GlobalPayments Bulk Merchant Statement Processor")
    print("=" * 60)
    
    processor = GlobalPaymentsProcessor()
    
    if args.scan:
        # Find all GlobalPayments PDFs
        pdf_files = processor.find_globalpayments_pdfs(args.paths)
        
        if not pdf_files:
            print("[FAIL] No GlobalPayments PDFs found")
            return
        
        print(f"📁 Found {len(pdf_files)} GlobalPayments PDFs")
        
        # Process all PDFs
        results = processor.process_all_pdfs(pdf_files, args.max_workers)
        
        # Display summary
        print(f"\n📊 BULK PROCESSING SUMMARY")
        print("-" * 40)
        print(f"PDFs processed successfully: {len(results)}")
        print(f"Total transactions extracted: {len(processor.all_transactions)}")
        print(f"Processing errors: {len(processor.processing_errors)}")
        
        if processor.all_transactions:
            total_gross = sum(t['gross_sales'] for t in processor.all_transactions)
            total_net = sum(t['net_deposit'] for t in processor.all_transactions)
            print(f"Total gross sales: ${total_gross:,.2f}")
            print(f"Total net deposits: ${total_net:,.2f}")
            
            date_range = processor.get_date_range()
            if date_range:
                print(f"Date range: {date_range['earliest']} to {date_range['latest']}")
        
        if args.write:
            print(f"\n💾 SAVING DATA to {args.output}")
            files = processor.save_consolidated_data(args.output)
            print("[OK] Bulk processing completed successfully!")
            
            print(f"\n📁 Files created:")
            for file_type, file_path in files.items():
                print(f"  {file_type}: {file_path}")
        else:
            print("\n[WARN] Dry run mode - use --write to save files")
    
    else:
        print("Use --scan to find and process GlobalPayments PDFs")


if __name__ == "__main__":
    main()