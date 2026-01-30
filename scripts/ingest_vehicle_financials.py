#!/usr/bin/env python3
"""
Ingest extracted vehicle financial data into existing vehicle_loans and vehicle_loan_payments tables.
Maps extracted CSVs to existing database schema with deduplication and reconciliation.
"""
import os
import csv
import psycopg2
from datetime import datetime, date
from decimal import Decimal

REPORTS_DIR = r"L:\\limo\\reports"
HEFFNER_CSV = os.path.join(REPORTS_DIR, 'heffner_payments.csv')
AGREEMENTS_CSV = os.path.join(REPORTS_DIR, 'vehicle_agreements.csv')

DB = dict(
    dbname=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    host=os.environ.get('DB_HOST', 'localhost'),
    port=int(os.environ.get('DB_PORT', '5432')),
)

def parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    try:
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None
    except Exception:
        return None

def parse_decimal(amount_str: str) -> Decimal | None:
    if not amount_str:
        return None
    try:
        # Clean up amount string
        cleaned = amount_str.replace('$', '').replace(',', '').strip()
        if cleaned:
            return Decimal(cleaned)
        return None
    except Exception:
        return None

def get_or_create_vehicle_id(cur, vin: str, make_model: str, year: str) -> int | None:
    """Get existing vehicle_id or create a placeholder entry"""
    if not vin:
        return None
    
    # First try to find existing vehicle by VIN
    cur.execute("SELECT vehicle_id FROM vehicles WHERE vin_number = %s LIMIT 1", (vin,))
    row = cur.fetchone()
    if row:
        return row[0]
    
    # If vehicle doesn't exist, we'll return None for now
    # In a real system, you might want to create a placeholder vehicle record
    print(f"Warning: Vehicle with VIN {vin} not found in vehicles table")
    return None

def ingest_vehicle_agreements(cur) -> tuple[int, int]:
    """Ingest vehicle agreements into vehicle_loans table"""
    if not os.path.exists(AGREEMENTS_CSV):
        print(f"Vehicle agreements CSV not found: {AGREEMENTS_CSV}")
        return 0, 0
    
    inserted = 0
    skipped = 0
    
    with open(AGREEMENTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vin = row.get('vin', '').strip()
            make_model = row.get('make_model', '').strip()
            year = row.get('year', '').strip()
            agreement_type = row.get('agreement_type', '').strip()
            
            if not vin:
                print(f"Skipping agreement without VIN: {row.get('source_file', '')}")
                skipped += 1
                continue
            
            # Check if loan already exists for this VIN and date
            date_signed = parse_date(row.get('date_signed', ''))
            cur.execute("""
                SELECT id FROM vehicle_loans 
                WHERE vehicle_name LIKE %s AND loan_start_date = %s
            """, (f'%{vin}%', date_signed))
            
            if cur.fetchone():
                print(f"Loan already exists for VIN {vin} on {date_signed}")
                skipped += 1
                continue
            
            # Get vehicle_id (if vehicle exists in system)
            vehicle_id = get_or_create_vehicle_id(cur, vin, make_model, year)
            if not vehicle_id:
                # Use a placeholder - you might want to create vehicle records first
                vehicle_id = 1  # Default placeholder
            
            # Parse financial terms
            principal = parse_decimal(row.get('principal_amount', ''))
            down_payment = parse_decimal(row.get('down_payment', ''))
            monthly_payment = parse_decimal(row.get('monthly_payment', ''))
            
            # Map to existing schema
            vehicle_name = f"{vin} - {make_model} {year}".strip()
            lender = row.get('dealer', '') or 'Unknown Lender'
            paid_by = 'Company'  # Default, can be updated later
            
            cur.execute("""
                INSERT INTO vehicle_loans 
                (vehicle_id, vehicle_name, lender, paid_by, opening_balance, 
                 loan_start_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                vehicle_id,
                vehicle_name,
                lender,
                paid_by,
                principal,
                date_signed,
                f"Agreement type: {agreement_type}, Monthly: {monthly_payment}, "
                f"Term: {row.get('term_months', '')} months, "
                f"Rate: {row.get('interest_rate', '')}, "
                f"Source: {row.get('source_file', '')}"
            ))
            
            loan_id = cur.fetchone()[0]
            inserted += 1
            print(f"Inserted loan {loan_id} for VIN {vin}")
    
    return inserted, skipped

def ingest_heffner_payments(cur) -> tuple[int, int]:
    """Ingest Heffner payments into vehicle_loan_payments table"""
    if not os.path.exists(HEFFNER_CSV):
        print(f"Heffner payments CSV not found: {HEFFNER_CSV}")
        return 0, 0
    
    inserted = 0
    skipped = 0
    
    with open(HEFFNER_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vin = row.get('vin', '').strip()
            payment_date = parse_date(row.get('date', ''))
            amount = parse_decimal(row.get('amount', ''))
            
            if not payment_date or not amount:
                print(f"Skipping payment with missing date/amount: {row.get('source_file', '')}")
                skipped += 1
                continue
            
            # Find matching loan by VIN
            loan_id = None
            if vin:
                cur.execute("""
                    SELECT id FROM vehicle_loans 
                    WHERE vehicle_name LIKE %s 
                    ORDER BY loan_start_date DESC 
                    LIMIT 1
                """, (f'%{vin}%',))
                row_result = cur.fetchone()
                if row_result:
                    loan_id = row_result[0]
            
            if not loan_id:
                print(f"No matching loan found for VIN {vin}, skipping payment")
                skipped += 1
                continue
            
            # Check if payment already exists
            cur.execute("""
                SELECT id FROM vehicle_loan_payments 
                WHERE loan_id = %s AND payment_date = %s AND payment_amount = %s
            """, (loan_id, payment_date, amount))
            
            if cur.fetchone():
                print(f"Payment already exists for loan {loan_id} on {payment_date}")
                skipped += 1
                continue
            
            # Determine payment breakdown based on payment type
            payment_type = row.get('payment_type', 'payment')
            interest_amount = None
            fee_amount = None
            
            if payment_type == 'interest':
                interest_amount = amount
                amount = Decimal('0')  # Interest-only payment
            elif payment_type == 'fee' or 'nsf' in payment_type.lower():
                fee_amount = amount
                amount = Decimal('0')  # Fee-only payment
            
            cur.execute("""
                INSERT INTO vehicle_loan_payments 
                (loan_id, payment_date, payment_amount, interest_amount, 
                 fee_amount, paid_by, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                loan_id,
                payment_date,
                amount,
                interest_amount,
                fee_amount,
                'Heffner',
                f"Type: {payment_type}, Invoice: {row.get('invoice_ref', '')}, "
                f"Source: {row.get('source_file', '')}"
            ))
            
            payment_id = cur.fetchone()[0]
            inserted += 1
            print(f"Inserted payment {payment_id} for loan {loan_id}")
    
    return inserted, skipped

def update_loan_totals(cur):
    """Recalculate loan totals from payments"""
    cur.execute("""
        UPDATE vehicle_loans SET
            total_paid = COALESCE((
                SELECT SUM(payment_amount) FROM vehicle_loan_payments 
                WHERE loan_id = vehicle_loans.id
            ), 0),
            total_interest = COALESCE((
                SELECT SUM(interest_amount) FROM vehicle_loan_payments 
                WHERE loan_id = vehicle_loans.id
            ), 0),
            total_fees = COALESCE((
                SELECT SUM(fee_amount) FROM vehicle_loan_payments 
                WHERE loan_id = vehicle_loans.id
            ), 0),
            closing_balance = GREATEST(0, COALESCE(opening_balance, 0) - COALESCE((
                SELECT SUM(payment_amount) FROM vehicle_loan_payments 
                WHERE loan_id = vehicle_loans.id
            ), 0))
    """)
    
    print(f"Updated totals for {cur.rowcount} loans")

def main():
    conn = psycopg2.connect(**DB)
    try:
        with conn:
            with conn.cursor() as cur:
                print("=== Ingesting Vehicle Financial Data ===")
                
                # Ingest agreements first
                print("\n1. Processing vehicle agreements...")
                agreements_inserted, agreements_skipped = ingest_vehicle_agreements(cur)
                print(f"   Inserted: {agreements_inserted}, Skipped: {agreements_skipped}")
                
                # Then ingest payments
                print("\n2. Processing Heffner payments...")
                payments_inserted, payments_skipped = ingest_heffner_payments(cur)
                print(f"   Inserted: {payments_inserted}, Skipped: {payments_skipped}")
                
                # Update calculated totals
                print("\n3. Updating loan totals...")
                update_loan_totals(cur)
                
                print(f"\n=== Summary ===")
                print(f"Vehicle agreements: {agreements_inserted} inserted, {agreements_skipped} skipped")
                print(f"Payments: {payments_inserted} inserted, {payments_skipped} skipped")
                
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    raise SystemExit(main())