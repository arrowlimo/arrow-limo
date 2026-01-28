#!/usr/bin/env python3
"""
Insert All Missing Vehicles and Loan Records from Heffner Email Analysis
Complete database rebuild including paid off, sold, retired, collision write-offs
"""

import os
import csv
import json
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
import re

def connect_to_db():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="almsdata",
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', '')
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def parse_amount(amount_str):
    """Parse amount string to decimal."""
    if not amount_str or amount_str == '':
        return 0.00
    
    # Remove currency symbols and commas
    clean_amount = re.sub(r'[\$,]', '', str(amount_str))
    
    try:
        return float(clean_amount)
    except:
        return 0.00

def get_highest_amount(amounts_list):
    """Get the highest amount from a list of amount strings."""
    if not amounts_list:
        return 0.00
    
    max_amount = 0.00
    for amount_str in amounts_list:
        amount = parse_amount(amount_str)
        if amount > max_amount:
            max_amount = amount
    
    return max_amount

def insert_missing_vehicles():
    """Insert all missing vehicles found in email analysis."""
    
    conn = connect_to_db()
    if not conn:
        return
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Read vehicle registry
        with open('l:/limo/heffner_emails_complete/extracted_data/vehicle_registry_20251013_015045.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            vehicles_to_add = []
            
            for row in reader:
                if row['Needs Database Entry'] == 'Yes':
                    vehicles_to_add.append(row)
        
        print(f"=== Adding {len(vehicles_to_add)} Missing Vehicles ===")
        
        for vehicle in vehicles_to_add:
            vin = vehicle['VIN']
            first_year = vehicle['First Mentioned Year']
            descriptions = vehicle['Vehicle Descriptions'].split('; ')
            
            # Parse vehicle information from descriptions
            make = 'Unknown'
            model = 'Unknown'
            year = first_year
            vehicle_type = 'Limousine'
            
            # Extract make/model from descriptions
            for desc in descriptions:
                desc_lower = desc.lower()
                
                # Extract year
                year_match = re.search(r'(\d{4})', desc)
                if year_match:
                    year = int(year_match.group(1))
                
                # Extract make
                if 'ford' in desc_lower:
                    make = 'Ford'
                elif 'cadillac' in desc_lower:
                    make = 'Cadillac'
                elif 'toyota' in desc_lower:
                    make = 'Toyota'
                elif 'mercedes' in desc_lower:
                    make = 'Mercedes-Benz'
                elif 'lincoln' in desc_lower:
                    make = 'Lincoln'
                
                # Extract model
                if 'e350' in desc_lower:
                    model = 'E350'
                    vehicle_type = 'Shuttle'
                elif 'e450' in desc_lower:
                    model = 'E450'
                    vehicle_type = 'Shuttle'
                elif 'f550' in desc_lower:
                    model = 'F-550'
                    vehicle_type = 'Truck'
                elif 'transit' in desc_lower:
                    model = 'Transit'
                    vehicle_type = 'Van'
                elif 'camry' in desc_lower:
                    model = 'Camry'
                    vehicle_type = 'Sedan'
                elif 'stretch' in desc_lower:
                    model = 'Stretch'
                    vehicle_type = 'Limousine'
                elif any(x in desc_lower for x in ['limo', 'limousine']):
                    vehicle_type = 'Limousine'
                elif 'bus' in desc_lower:
                    vehicle_type = 'Bus'
                elif 'sedan' in desc_lower:
                    vehicle_type = 'Sedan'
            
            # Generate vehicle number
            vehicle_number = f"H{vin[-6:]}" if len(vin) >= 6 else f"H{vin}"
            
            # Insert vehicle
            insert_sql = """
                INSERT INTO vehicles (
                    vehicle_number, make, model, year, vin_number, 
                    type, operational_status, description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING vehicle_id
            """
            
            notes = f"Added from Heffner email analysis. Descriptions: {'; '.join(descriptions[:5])}"
            
            try:
                cur.execute(insert_sql, (
                    vehicle_number, make, model, year, vin,
                    vehicle_type, 'Historical', notes
                ))
                
                vehicle_id = cur.fetchone()[0]
                conn.commit()
                
                print(f"  ✓ Added {year} {make} {model} (VIN: {vin}) - Vehicle ID: {vehicle_id}")
                
            except Exception as e:
                print(f"  ✗ Error adding vehicle {vin}: {e}")
                conn.rollback()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error inserting vehicles: {e}")
        if conn:
            conn.close()

def insert_missing_loan_records():
    """Insert all missing loan records from lease registry."""
    
    conn = connect_to_db()
    if not conn:
        return
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Read lease registry
        with open('l:/limo/heffner_emails_complete/extracted_data/lease_registry_20251013_015045.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            leases_to_add = []
            
            for row in reader:
                if row['Needs Loan Record'] == 'Yes':
                    leases_to_add.append(row)
        
        print(f"\n=== Adding {len(leases_to_add)} Missing Loan Records ===")
        
        for lease in leases_to_add:
            lease_ref = lease['Lease Reference']
            first_year = int(lease['First Year']) if lease['First Year'].isdigit() else 2018
            last_year = int(lease['Last Year']) if lease['Last Year'].isdigit() else first_year
            
            # Parse amounts
            loan_amounts = lease['Loan Amounts'].split('; ') if lease['Loan Amounts'] else []
            payment_amounts = lease['Payment Amounts'].split('; ') if lease['Payment Amounts'] else []
            balance_amounts = lease['Outstanding Balances'].split('; ') if lease['Outstanding Balances'] else []
            buyout_amounts = lease['Buyout Amounts'].split('; ') if lease['Buyout Amounts'] else []
            
            # Get highest amounts
            principal = get_highest_amount(loan_amounts)
            monthly_payment = get_highest_amount(payment_amounts)
            current_balance = get_highest_amount(balance_amounts)
            buyout_value = get_highest_amount(buyout_amounts)
            
            # Determine status from status changes
            status_changes = lease['Status Changes'].split('; ') if lease['Status Changes'] else []
            status = 'Active'
            
            status_text = ' '.join(status_changes).lower()
            if any(x in status_text for x in ['paid off', 'buyout', 'bought out']):
                status = 'Paid Off'
            elif any(x in status_text for x in ['returned', 'repo']):
                status = 'Returned'
            elif 'collision' in status_text or 'write' in status_text:
                status = 'Written Off'
            
            # Try to find associated vehicle
            vehicle_descriptions = lease['Vehicles'].split('; ') if lease['Vehicles'] else []
            vehicle_id = None
            
            # Look for VIN in descriptions or try to match vehicle
            for desc in vehicle_descriptions:
                if len(desc) == 17:  # Could be VIN
                    cur.execute("SELECT vehicle_id FROM vehicles WHERE vin_number = %s", (desc,))
                    result = cur.fetchone()
                    if result:
                        vehicle_id = result[0]
                        break
            
            # If no VIN match, try to match by description
            if not vehicle_id and vehicle_descriptions:
                desc = vehicle_descriptions[0].lower()
                if 'e350' in desc:
                    cur.execute("SELECT vehicle_id FROM vehicles WHERE model = 'E350' LIMIT 1")
                elif 'e450' in desc:
                    cur.execute("SELECT vehicle_id FROM vehicles WHERE model = 'E450' LIMIT 1")
                elif 'f550' in desc:
                    cur.execute("SELECT vehicle_id FROM vehicles WHERE model LIKE '%550%' LIMIT 1")
                elif 'transit' in desc:
                    cur.execute("SELECT vehicle_id FROM vehicles WHERE model = 'Transit' LIMIT 1")
                elif 'camry' in desc:
                    cur.execute("SELECT vehicle_id FROM vehicles WHERE model = 'Camry' LIMIT 1")
                else:
                    cur.execute("SELECT vehicle_id FROM vehicles WHERE type = 'Limousine' LIMIT 1")
                
                result = cur.fetchone()
                if result:
                    vehicle_id = result[0]
            
            # Create loan record
            insert_sql = """
                INSERT INTO vehicle_loans (
                    vehicle_id, vehicle_name, lender, paid_by,
                    opening_balance, closing_balance, total_paid,
                    loan_start_date, loan_end_date, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            # Estimate dates
            start_date = f"{first_year}-01-01"
            end_date = f"{last_year}-12-31" if last_year > first_year else None
            
            # Determine vehicle name
            vehicle_name = f"Heffner {lease_ref}"
            if vehicle_descriptions:
                vehicle_name = vehicle_descriptions[0][:50]  # Limit length
            
            # Calculate loan amounts
            total_paid_amount = principal - current_balance if principal > current_balance else 0
            
            notes = f"Heffner lease {lease_ref}. Status: {status}. Vehicles: {'; '.join(vehicle_descriptions[:3])}. Status changes: {'; '.join(status_changes[:3])}"
            
            try:
                cur.execute(insert_sql, (
                    vehicle_id, vehicle_name, 'Heffner Financial', 'Limo Service',
                    principal, current_balance, total_paid_amount,
                    start_date, end_date, notes
                ))
                
                loan_id = cur.fetchone()[0]
                conn.commit()
                
                vehicle_info = f" (Vehicle ID: {vehicle_id})" if vehicle_id else " (No vehicle matched)"
                print(f"  ✓ Added lease {lease_ref}: ${principal:,.2f} principal, ${monthly_payment:,.2f}/month, {status}{vehicle_info}")
                
            except Exception as e:
                print(f"  ✗ Error adding loan {lease_ref}: {e}")
                conn.rollback()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error inserting loan records: {e}")
        if conn:
            conn.close()

def generate_final_report():
    """Generate final comprehensive report of all vehicles and loans."""
    
    conn = connect_to_db()
    if not conn:
        return
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Get complete vehicle inventory
        cur.execute("""
            SELECT 
                v.vehicle_id, v.vehicle_number, v.make, v.model, v.year,
                v.vin_number, v.type, v.operational_status,
                COUNT(vl.id) as loan_count,
                SUM(vl.closing_balance) as active_balance
            FROM vehicles v
            LEFT JOIN vehicle_loans vl ON v.vehicle_id = vl.vehicle_id
            GROUP BY v.vehicle_id, v.vehicle_number, v.make, v.model, v.year,
                     v.vin_number, v.type, v.operational_status
            ORDER BY v.year DESC, v.make, v.model
        """)
        
        vehicles = cur.fetchall()
        
        # Get complete loan summary
        cur.execute("""
            SELECT 
                CASE 
                    WHEN vl.closing_balance > 0 THEN 'Active'
                    WHEN vl.closing_balance = 0 AND vl.total_paid > 0 THEN 'Paid Off'
                    ELSE 'Unknown'
                END as status,
                COUNT(*) as loan_count,
                SUM(vl.opening_balance) as total_principal,
                SUM(vl.closing_balance) as total_balance,
                SUM(vl.total_paid) as total_paid
            FROM vehicle_loans vl
            GROUP BY CASE 
                WHEN vl.closing_balance > 0 THEN 'Active'
                WHEN vl.closing_balance = 0 AND vl.total_paid > 0 THEN 'Paid Off'
                ELSE 'Unknown'
            END
            ORDER BY status
        """)
        
        loan_summary = cur.fetchall()
        
        # Generate report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"l:/limo/reports/complete_vehicle_financial_rebuild_{timestamp}.txt"
        
        with open(report_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("COMPLETE VEHICLE FINANCIAL DATABASE REBUILD REPORT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("LOAN SUMMARY BY STATUS:\n")
            f.write("-" * 40 + "\n")
            total_principal = 0
            total_balance = 0
            total_monthly = 0
            
            for row in loan_summary:
                f.write(f"{row['status']:<15}: {row['loan_count']:>3} loans, ")
                f.write(f"${row['total_principal']:>12,.2f} principal, ")
                f.write(f"${row['total_balance']:>12,.2f} balance, ")
                f.write(f"${row['total_paid']:>10,.2f} paid\n")
                
                total_principal += row['total_principal'] or 0
                total_balance += row['total_balance'] or 0
                total_monthly += row['total_paid'] or 0
            
            f.write("-" * 80 + "\n")
            f.write(f"{'TOTALS':<15}: {sum(r['loan_count'] for r in loan_summary):>3} loans, ")
            f.write(f"${total_principal:>12,.2f} principal, ")
            f.write(f"${total_balance:>12,.2f} balance, ")
            f.write(f"${total_monthly:>10,.2f} paid\n\n")
            
            f.write("COMPLETE VEHICLE INVENTORY:\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Year':<6}{'Make':<12}{'Model':<15}{'Type':<12}{'Status':<12}{'Loans':<6}{'Balance':<12}\n")
            f.write("-" * 80 + "\n")
            
            for vehicle in vehicles:
                f.write(f"{vehicle['year'] or 'N/A':<6}")
                f.write(f"{vehicle['make']:<12}")
                f.write(f"{vehicle['model']:<15}")
                f.write(f"{vehicle['type']:<12}")
                f.write(f"{vehicle['operational_status']:<12}")
                f.write(f"{vehicle['loan_count']:<6}")
                f.write(f"${vehicle['active_balance'] or 0:>10,.2f}\n")
            
            f.write("-" * 80 + "\n")
            f.write(f"Total Vehicles: {len(vehicles)}\n")
        
        print(f"\n=== Final Report Generated ===")
        print(f"Complete report: {report_path}")
        print(f"Total vehicles in database: {len(vehicles)}")
        print(f"Total loan accounts: {sum(r['loan_count'] for r in loan_summary)}")
        print(f"Total outstanding balance: ${total_balance:,.2f}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error generating final report: {e}")
        if conn:
            conn.close()

def main():
    """Main execution function."""
    print("=== COMPLETE VEHICLE FINANCIAL DATABASE REBUILD ===")
    print("Adding ALL vehicles and loans including paid off, sold, retired, collision write-offs\n")
    
    # Step 1: Add missing vehicles
    insert_missing_vehicles()
    
    # Step 2: Add missing loan records
    insert_missing_loan_records()
    
    # Step 3: Generate comprehensive report
    generate_final_report()
    
    print("\n=== REBUILD COMPLETE ===")
    print("All historical vehicle financing records have been added to the database")
    print("This includes active leases, paid off loans, returned vehicles, and write-offs")

if __name__ == "__main__":
    main()