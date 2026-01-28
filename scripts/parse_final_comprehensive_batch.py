#!/usr/bin/env python3
"""
Parse final comprehensive batch of Heffner and CMB Insurance communications
Includes insurance renewal details, lease buyout information, returned payments, and e-Transfer confirmations
"""

import os
import sys
import psycopg2
from datetime import datetime
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection using environment variables"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'lms'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        port=os.getenv('DB_PORT', '5432')
    )

def extract_heffner_communications():
    """Extract Heffner lease events from various communications"""
    
    events = []
    
    # Screenshot 1: Returned Lease Payment (F1811005)
    # Vanessa Thomas - lease payment F1811005 $2,116 returned as NSF, amount to clear $2,164.97
    events.append({
        'source': 'manual_email_parsing',
        'email_date': datetime(2023, 11, 19),  # From screenshot timestamp
        'event_type': 'nsf_charge',
        'entity': 'HEFFNER AUTO SALES & LEASING INC',
        'notes': 'Vanessa Thomas: Lease payment F1811005 $2,116 Cadillac returned as NSF. Amount to clear: $2,164.97.',
        'amount': 2164.97,
        'vin': None,
        'license_plate': None,
        'loan_external_id': 'F1811005'
    })
    
    # Screenshot 2: Heffner Lease Buyouts
    # Multiple lease buyout amounts mentioned
    lease_buyouts = [
        {'lease_id': 'H4552-B-2011', 'amount': 9027.04, 'note': 'Ford F-450'},
        {'lease_id': 'H4551A-2011', 'amount': 719.90, 'note': 'Ford F-450 (addressed ASAP)'},
        {'lease_id': 'H4491-2011', 'amount': 21629.18, 'note': 'Mercedes S-Class'},
        {'lease_id': 'F2551AA-2014', 'amount': 84475.96, 'note': 'Cadillac Stretch Limo'},
        {'lease_id': 'F1811005-2013', 'amount': 242332.73, 'note': 'Ford F-550'},
        {'lease_id': 'F1811005-2016', 'amount': 33415.74, 'note': 'Cadillac XTS'}
    ]
    
    for buyout in lease_buyouts:
        events.append({
            'source': 'manual_email_parsing',
            'email_date': datetime(2024, 1, 15),  # Estimated date from screenshot context
            'event_type': 'lease_buyout',
            'entity': 'HEFFNER AUTO SALES & LEASING INC',
            'notes': f"Vanessa Thomas: Lease buyout {buyout['lease_id']} - {buyout['note']}. Buyout amount: ${buyout['amount']:,.2f}",
            'amount': buyout['amount'],
            'vin': None,
            'license_plate': None,
            'loan_external_id': buyout['lease_id']
        })
    
    # Latest communication: 2014 Cadillac buyout arrears payment
    events.append({
        'source': 'manual_email_parsing',
        'email_date': datetime(2025, 10, 12),  # Current date
        'event_type': 'amount_owing',
        'entity': 'HEFFNER AUTO SALES & LEASING INC',
        'notes': 'Vanessa Thomas: Arrears payment needed for 2014 Cadillac buyout paperwork. Amount: $2,690.35 (provided 12th payments clear).',
        'amount': 2690.35,
        'vin': None,
        'license_plate': None,
        'loan_external_id': '2014_CADILLAC_BUYOUT'
    })
    
    # Returned lease payment from screenshot
    events.append({
        'source': 'manual_email_parsing',
        'email_date': datetime(2024, 4, 27),  # From screenshot date
        'event_type': 'nsf_charge',
        'entity': 'HEFFNER AUTO SALES & LEASING INC',
        'notes': 'Vanessa Thomas: 2 of your lease payments from May 12th returned as NSF. Amount to clear: $568.13.',
        'amount': 568.13,
        'vin': None,
        'license_plate': None,
        'loan_external_id': None
    })
    
    return events

def extract_cmb_insurance_events():
    """Extract CMB Insurance renewal events"""
    
    events = []
    
    # CMB Insurance renewal - November 1, 2023
    events.append({
        'source': 'manual_email_parsing',
        'email_date': datetime(2023, 11, 1),
        'event_type': 'insurance_renewal',
        'entity': 'CMB INSURANCE',
        'notes': 'Renee Lynn Flamand: Commercial Auto Policy with Nordic ($54,556) + General Liability with CanSure ($2,500 + $250 fee). Aurora Premium Financing setup.',
        'amount': 57306.00,  # $54,556 + $2,500 + $250
        'vin': None,
        'license_plate': None,
        'loan_external_id': 'CMB_2023_RENEWAL'
    })
    
    # Aurora Premium Financing (APF) setup
    events.append({
        'source': 'manual_email_parsing',
        'email_date': datetime(2023, 11, 1),
        'event_type': 'financing_setup',
        'entity': 'AURORA PREMIUM FINANCING',
        'notes': 'CMB Insurance: APF contract 10 equal payments. Downpayment: $6,191.63, Monthly payment: $6,091.63',
        'amount': 6191.63,  # Downpayment amount
        'vin': None,
        'license_plate': None,
        'loan_external_id': 'APF_2023_CONTRACT'
    })
    
    return events

def extract_additional_etransfers():
    """Extract additional e-Transfer confirmations from screenshots"""
    
    # Additional e-Transfer confirmations visible in latest screenshots
    etransfer_data = [
        # Latest screenshot e-Transfers
        {'amount': 267.39, 'ref': 'C1AWdiElppeTy', 'message': ''},
        {'amount': 1000.00, 'ref': 'C1AJHqHH547Y', 'message': ''},
    ]
    
    events = []
    
    print(f"Found {len(etransfer_data)} additional e-Transfer confirmations from latest screenshots")
    
    for transfer in etransfer_data:
        amount = transfer['amount']
        message = transfer['message']
        reference_num = transfer['ref']
        
        print(f"  - ${amount:,.2f} (Ref: {reference_num}, Message: '{message}')")
        
        # Create event
        event = {
            'source': 'manual_email_parsing',
            'email_date': datetime(2025, 10, 12),  # Current date for screenshot processing
            'event_type': 'etransfer_payment',
            'entity': 'HEFFNER AUTO SALES AND LEASINGINC',
            'notes': f"e-Transfer payment to HEFFNER AUTO SALES AND LEASINGINC. Message: '{message}'. Reference: {reference_num}",
            'amount': amount,
            'vin': None,
            'license_plate': None,
            'loan_external_id': reference_num
        }
        
        events.append(event)
    
    return events

def insert_events_to_db(events, event_type_description):
    """Insert events into email_financial_events table"""
    
    if not events:
        print(f"No {event_type_description} events to insert")
        return
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        inserted = 0
        skipped = 0
        
        for event in events:
            # Check for duplicates based on event type and key identifiers
            if event['event_type'] == 'etransfer_payment':
                # For e-transfers, check by reference number
                ref_check = event['loan_external_id']
                cursor.execute("""
                    SELECT id FROM email_financial_events 
                    WHERE loan_external_id = %s AND event_type = 'etransfer_payment'
                """, (ref_check,))
            elif event['loan_external_id']:
                # For lease events, check by external ID and event type
                cursor.execute("""
                    SELECT id FROM email_financial_events 
                    WHERE loan_external_id = %s AND event_type = %s
                """, (event['loan_external_id'], event['event_type']))
            else:
                # For other events, check by amount, date, and type
                cursor.execute("""
                    SELECT id FROM email_financial_events 
                    WHERE amount = %s AND event_type = %s AND email_date = %s
                """, (event['amount'], event['event_type'], event['email_date']))
            
            if cursor.fetchone():
                identifier = event['loan_external_id'] or f"{event['event_type']} ${event['amount']:,.2f}"
                print(f"  Skipping duplicate: {identifier}")
                skipped += 1
                continue
            
            # Insert event
            cursor.execute("""
                INSERT INTO email_financial_events 
                (source, email_date, event_type, entity, notes, amount, vin, license_plate, loan_external_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                event['source'],
                event['email_date'],
                event['event_type'],
                event['entity'],
                event['notes'],
                event['amount'],
                event['vin'],
                event['license_plate'],
                event['loan_external_id']
            ))
            
            inserted += 1
            identifier = event['loan_external_id'] or f"{event['event_type']} ${event['amount']:,.2f}"
            print(f"  Inserted: {identifier}")
        
        conn.commit()
        
        print(f"\n[OK] Successfully processed {event_type_description}:")
        print(f"   Inserted: {inserted} new events")
        print(f"   Skipped: {skipped} duplicates")
        
        if events:
            print(f"   Total amount: ${sum(e['amount'] for e in events):,.2f}")
        
    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Database error: {e}")
        raise
    finally:
        conn.close()

def main():
    """Main execution function"""
    
    print("🔄 Processing final comprehensive batch of financial communications...")
    
    # Extract Heffner communications
    print("\n📧 Processing Heffner lease communications...")
    heffner_events = extract_heffner_communications()
    if heffner_events:
        insert_events_to_db(heffner_events, "Heffner lease events")
    
    # Extract CMB Insurance events
    print("\n🏢 Processing CMB Insurance renewal communications...")
    cmb_events = extract_cmb_insurance_events()
    if cmb_events:
        insert_events_to_db(cmb_events, "CMB Insurance events")
    
    # Extract additional e-Transfers
    print("\n📱 Processing additional e-Transfer confirmations...")
    etransfer_events = extract_additional_etransfers()
    if etransfer_events:
        insert_events_to_db(etransfer_events, "additional e-Transfers")

if __name__ == "__main__":
    main()