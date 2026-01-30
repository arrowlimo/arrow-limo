"""
Export Complete Arrow Limousine Data Ecosystem to JSON
=======================================================

Creates a comprehensive JSON export of the entire almsdata database with full
relationship chains and data lineage tracking. This is the "dust on everything"
export - every table, every record, every relationship, every piece of operational
and financial data from 2007-2025.

Purpose:
- Complete business intelligence snapshot for forensic analysis
- CRA audit preparation with full data lineage
- Pattern detection and anomaly analysis
- Data quality validation and integrity checking
- Missing data identification and gap analysis

Output Structure:
{
    "metadata": {
        "export_date": "2025-11-13T...",
        "database": "almsdata",
        "total_tables": 165,
        "total_rows": 500000+,
        "date_range": "2007-01-01 to 2025-11-13",
        "version": "1.0"
    },
    "data_quality_summary": {
        "tables_with_nulls": {...},
        "orphaned_records": {...},
        "missing_relationships": {...},
        "duplicate_candidates": {...}
    },
    "client_ecosystem": [
        {
            "client": {...full client record...},
            "charters": [{...full charter with all linked data...}],
            "payments": [{...}],
            "total_revenue": 123456.78,
            "outstanding_balance": 0.00,
            "payment_history_summary": {...}
        }
    ],
    "tables": {
        "clients": {
            "schema": [...],
            "row_count": 6426,
            "rows": [...]
        },
        "charters": {...},
        "payments": {...},
        ...all tables...
    }
}

Usage:
    python scripts/export_complete_almsdata_json.py
    
    # Export to specific file
    python scripts/export_complete_almsdata_json.py --output reports/complete_data_export_20251113.json
    
    # Export with compression
    python scripts/export_complete_almsdata_json.py --compress
    
    # Export specific ecosystems only
    python scripts/export_complete_almsdata_json.py --ecosystems clients,charters,banking
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
import gzip
import psycopg2

# Optional Outlook COM (calendar extraction)
try:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore
except Exception:
    pythoncom = None
    win32com = None

def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def decimal_default(obj):
    """JSON serializer for Decimal types"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def has_column(cur, table_name, column_name):
    """Return True if a column exists in the given table."""
    try:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return cur.fetchone() is not None
    except Exception:
        return False

def get_table_list(cur):
    """Get all tables excluding staging tables"""
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        AND table_name NOT LIKE 'staging_%'
        AND table_name NOT LIKE '%_staging'
        AND table_name NOT LIKE '%backup%'
        AND table_name NOT LIKE '%_ARCHIVED_%'
        ORDER BY table_name
    """)
    return [row[0] for row in cur.fetchall()]

def get_table_schema(cur, table_name):
    """Get column definitions for a table"""
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_name = %s 
        ORDER BY ordinal_position
    """, (table_name,))
    
    schema = []
    for row in cur.fetchall():
        schema.append({
            "name": row[0],
            "type": row[1],
            "max_length": row[2],
            "nullable": row[3] == 'YES',
            "default": row[4]
        })
    return schema

def get_table_data(cur, table_name, limit=None):
    """Get all data from a table"""
    limit_clause = f"LIMIT {limit}" if limit else ""
    cur.execute(f"SELECT * FROM {table_name} {limit_clause}")
    
    columns = [desc[0] for desc in cur.description]
    rows = []
    
    for row in cur.fetchall():
        row_dict = {}
        for i, col in enumerate(columns):
            value = row[i]
            # Convert datetime to ISO string
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            row_dict[col] = value
        rows.append(row_dict)
    
    return rows, columns

def get_table_stats(cur, table_name):
    """Get statistics about a table"""
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cur.fetchone()[0]
    
    # Get date range if table has date columns
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s 
        AND data_type IN ('date', 'timestamp', 'timestamp without time zone')
        ORDER BY ordinal_position
        LIMIT 1
    """, (table_name,))
    
    date_col = cur.fetchone()
    date_range = None
    
    if date_col:
        date_col_name = date_col[0]
        try:
            cur.execute(f"""
                SELECT 
                    MIN({date_col_name})::text,
                    MAX({date_col_name})::text
                FROM {table_name}
                WHERE {date_col_name} IS NOT NULL
            """)
            result = cur.fetchone()
            if result and result[0]:
                date_range = {"min": result[0], "max": result[1]}
        except:
            pass
    
    return {
        "row_count": row_count,
        "date_range": date_range
    }

def parse_reserve_numbers(text: str):
    import re
    if not text:
        return []
    m = re.findall(r"\b(\d{6})\b", text)
    return sorted(set(m))


def _ensure_pst_store(namespace, pst_path: str):
    try:
        namespace.AddStore(pst_path)
    except Exception:
        pass


def _find_calendar_folder(namespace, calendar_name: str):
    stores = getattr(namespace, 'Stores', None)
    if stores is not None:
        for store in stores:
            try:
                root = store.GetRootFolder()
                stack = [root]
                while stack:
                    f = stack.pop()
                    try:
                        name = f.Name or ''
                        if name == calendar_name or calendar_name.lower() in name.lower():
                            try:
                                if int(getattr(f, 'DefaultItemType', 0)) == 1:
                                    return f
                            except Exception:
                                return f
                        for sub in f.Folders:
                            stack.append(sub)
                    except Exception:
                        continue
            except Exception:
                continue
    for root in getattr(namespace, 'Folders', []):
        stack = [root]
        while stack:
            f = stack.pop()
            try:
                name = f.Name or ''
                if name == calendar_name or calendar_name.lower() in name.lower():
                    return f
                for sub in f.Folders:
                    stack.append(sub)
            except Exception:
                continue
    return None


def _split_midnight_segments(start_dt, end_dt):
    if not start_dt or not end_dt or end_dt <= start_dt:
        return [(start_dt.isoformat() if start_dt else None, end_dt.isoformat() if end_dt else None)]
    if start_dt.date() == end_dt.date():
        return [(start_dt.isoformat(), end_dt.isoformat())]
    segments = []
    cur = start_dt
    while cur.date() < end_dt.date():
        next_midnight = (cur.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        segments.append((cur.isoformat(), next_midnight.isoformat()))
        cur = next_midnight
    segments.append((cur.isoformat(), end_dt.isoformat()))
    return segments


def extract_calendar_events_from_pst(pst_path: str, calendar_name: str = 'Calendar_0'):
    if not pythoncom or not win32com:
        print('Outlook COM not available; skipping calendar extraction')
        return []
    if not os.path.exists(pst_path):
        print(f'PST not found: {pst_path}; skipping calendar extraction')
        return []
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.gencache.EnsureDispatch('Outlook.Application')
        ns = outlook.GetNamespace('MAPI')
        _ensure_pst_store(ns, pst_path)
        cal = _find_calendar_folder(ns, calendar_name)
        if not cal:
            print(f'Calendar folder "{calendar_name}" not found; skipping')
            return []
        items = getattr(cal, 'Items', None)
        events = []
        if items is None:
            return events
        count = items.Count
        for i in range(1, count + 1):
            try:
                it = items.Item(i)
                if int(getattr(it, 'Class', 0)) != 26:
                    continue
                subject = str(getattr(it, 'Subject', '') or '')
                location = str(getattr(it, 'Location', '') or '')
                body = str(getattr(it, 'Body', '') or '')
                start = getattr(it, 'Start', None)
                end = getattr(it, 'End', None)
                start_dt = start
                end_dt = end
                reserves = sorted(set(parse_reserve_numbers(subject) + parse_reserve_numbers(body)))
                segments = _split_midnight_segments(start_dt, end_dt)
                events.append({
                    'subject': subject,
                    'location': location,
                    'start': start_dt.isoformat() if start_dt else None,
                    'end': end_dt.isoformat() if end_dt else None,
                    'is_all_day': bool(getattr(it, 'AllDayEvent', False)),
                    'categories': str(getattr(it, 'Categories', '') or ''),
                    'reserve_numbers': reserves,
                    'segments': [{'start': s, 'end': e} for s, e in segments],
                })
            except Exception:
                continue
        return events
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

def export_client_ecosystem(cur, conn):
    """Export complete client ecosystem with all relationships"""
    print("Exporting client ecosystem...")
    conn.rollback()  # Clear any previous transaction errors
    # Build contact info column defensively
    contact_col = None
    if has_column(cur, 'clients', 'contact_info'):
        contact_col = 'c.contact_info'
    elif has_column(cur, 'clients', 'phone_number'):
        contact_col = 'c.phone_number'
    else:
        contact_col = "NULL AS contact_info"
    # Build billing address defensively
    billing_col = None
    if has_column(cur, 'clients', 'billing_address'):
        billing_col = 'c.billing_address'
    elif has_column(cur, 'clients', 'address'):
        billing_col = 'c.address'
    else:
        billing_col = 'NULL AS billing_address'
    
    query = f"""
        SELECT 
            c.client_id,
            c.client_name,
            c.email,
            {contact_col},
            {billing_col},
            {('c.warning_flag' if has_column(cur, 'clients', 'warning_flag') else 'NULL AS warning_flag')},
            c.square_customer_id,
            c.notes,
            c.created_at,
            COUNT(DISTINCT ch.charter_id) as charter_count,
            COALESCE(SUM(ch.total_amount_due), 0) as total_revenue,
            COALESCE(SUM(ch.paid_amount), 0) as total_paid,
            COALESCE(SUM(ch.balance), 0) as outstanding_balance,
            COUNT(DISTINCT p.payment_id) as payment_count,
            COALESCE(SUM(p.amount), 0) as payment_total
        FROM clients c
        LEFT JOIN charters ch ON ch.client_id = c.client_id
        LEFT JOIN payments p ON p.client_id = c.client_id
        GROUP BY c.client_id
        ORDER BY total_revenue DESC NULLS LAST
    """
    cur.execute(query)
    
    clients = []
    for row in cur.fetchall():
        client_id = row[0]
        
        # Get all charters for this client
        cur.execute("""
            SELECT 
                charter_id, reserve_number, charter_date, pickup_time,
                pickup_address, dropoff_address, passenger_count,
                vehicle, driver, rate, total_amount_due, paid_amount,
                balance, status, cancelled, notes, driver_name,
                assigned_driver_id, vehicle_id, employee_id
            FROM charters
            WHERE client_id = %s
            ORDER BY charter_date DESC
        """, (client_id,))
        
        charters = []
        for charter_row in cur.fetchall():
            charter = {
                "charter_id": charter_row[0],
                "reserve_number": charter_row[1],
                "charter_date": charter_row[2].isoformat() if charter_row[2] else None,
                "pickup_time": charter_row[3].isoformat() if charter_row[3] else None,
                "pickup_address": charter_row[4],
                "dropoff_address": charter_row[5],
                "passenger_count": charter_row[6],
                "vehicle": charter_row[7],
                "driver": charter_row[8],
                "rate": float(charter_row[9]) if charter_row[9] else 0.0,
                "total_amount_due": float(charter_row[10]) if charter_row[10] else 0.0,
                "paid_amount": float(charter_row[11]) if charter_row[11] else 0.0,
                "balance": float(charter_row[12]) if charter_row[12] else 0.0,
                "status": charter_row[13],
                "cancelled": charter_row[14],
                "notes": charter_row[15],
                "driver_name": charter_row[16],
                "assigned_driver_id": charter_row[17],
                "vehicle_id": charter_row[18],
                "employee_id": charter_row[19]
            }
            
            # Get payments for this charter
            cur.execute("""
                SELECT payment_id, amount, payment_date, payment_method,
                       payment_key, notes, square_transaction_id
                FROM payments
                WHERE reserve_number = %s
                ORDER BY payment_date
            """, (charter_row[1],))
            
            charter["payments"] = []
            for pay_row in cur.fetchall():
                charter["payments"].append({
                    "payment_id": pay_row[0],
                    "amount": float(pay_row[1]) if pay_row[1] else 0.0,
                    "payment_date": pay_row[2].isoformat() if pay_row[2] else None,
                    "payment_method": pay_row[3],
                    "payment_key": pay_row[4],
                    "notes": pay_row[5],
                    "square_transaction_id": pay_row[6]
                })
            
            # Get charges for this charter
            cur.execute("""
                SELECT charge_id, amount, description, category
                FROM charter_charges
                WHERE charter_id = %s
                ORDER BY charge_id
            """, (charter_row[0],))
            
            charter["charges"] = []
            for charge_row in cur.fetchall():
                charter["charges"].append({
                    "charge_id": charge_row[0],
                    "amount": float(charge_row[1]) if charge_row[1] else 0.0,
                    "description": charge_row[2],
                    "category": charge_row[3]
                })
            
            charters.append(charter)
        
        clients.append({
            "client": {
                "client_id": client_id,
                "client_name": row[1],
                "email": row[2],
                "contact_info": row[3],
                "billing_address": row[4],
                "warning_flag": row[5],
                "square_customer_id": row[6],
                "notes": row[7],
                "created_at": row[8].isoformat() if row[8] else None
            },
            "summary": {
                "charter_count": row[9],
                "total_revenue": float(row[10]),
                "total_paid": float(row[11]),
                "outstanding_balance": float(row[12]),
                "payment_count": row[13],
                "payment_total": float(row[14])
            },
            "charters": charters
        })
    
    return clients

def export_banking_ecosystem(cur, conn):
    """Export complete banking ecosystem with reconciliation"""
    print("Exporting banking ecosystem...")
    conn.rollback()  # Clear any previous transaction errors
    
    cur.execute("""
        SELECT DISTINCT account_number 
        FROM banking_transactions 
        WHERE account_number IS NOT NULL
        ORDER BY account_number
    """)
    
    accounts = []
    for account_row in cur.fetchall():
        account_num = account_row[0]
        
        # Build transaction select defensively based on available columns
        bt_cols = [
            'transaction_id', 'transaction_date', 'description',
            'debit_amount', 'credit_amount', 'balance'
        ]
        if has_column(cur, 'banking_transactions', 'vendor_extracted'):
            bt_cols.append('vendor_extracted')
        else:
            bt_cols.append("NULL AS vendor_extracted")
        if has_column(cur, 'banking_transactions', 'category'):
            bt_cols.append('category')
        else:
            bt_cols.append("NULL AS category")
        if has_column(cur, 'banking_transactions', 'receipt_id'):
            bt_cols.append('receipt_id')
        else:
            bt_cols.append('NULL AS receipt_id')
        if has_column(cur, 'banking_transactions', 'created_at'):
            bt_cols.append('created_at')
        else:
            bt_cols.append('NULL AS created_at')

        txn_query = f"""
            SELECT {', '.join(bt_cols)}
            FROM banking_transactions
            WHERE account_number = %s
            ORDER BY transaction_date, transaction_id
        """
        cur.execute(txn_query, (account_num,))
        
        transactions = []
        for txn_row in cur.fetchall():
            txn = {
                "transaction_id": txn_row[0],
                "transaction_date": txn_row[1].isoformat() if txn_row[1] else None,
                "description": txn_row[2],
                "debit_amount": float(txn_row[3]) if txn_row[3] else 0.0,
                "credit_amount": float(txn_row[4]) if txn_row[4] else 0.0,
                "balance": float(txn_row[5]) if txn_row[5] else None,
                "vendor_extracted": txn_row[6],
                "category": txn_row[7],
                "receipt_id": txn_row[8],
                "created_at": txn_row[9].isoformat() if txn_row[9] else None
            }
            
            # Get linked receipt if exists
            if txn_row[8]:
                # Determine receipt PK column name
                r_id_col = None
                if has_column(cur, 'receipts', 'receipt_id'):
                    r_id_col = 'receipt_id'
                elif has_column(cur, 'receipts', 'id'):
                    r_id_col = 'id'
                # Build receipt select
                r_select_id = 'receipt_id' if has_column(cur, 'receipts', 'receipt_id') else (
                    'id' if has_column(cur, 'receipts', 'id') else 'NULL AS receipt_id')
                # Optional columns
                emp_col = 'employee_id' if has_column(cur, 'receipts', 'employee_id') else 'NULL AS employee_id'
                veh_col = 'vehicle_id' if has_column(cur, 'receipts', 'vehicle_id') else 'NULL AS vehicle_id'
                r_query = f"""
                    SELECT {r_select_id}, vendor_name, gross_amount,
                           gst_amount, net_amount, receipt_date,
                           category, {emp_col}, {veh_col}
                    FROM receipts
                    WHERE {r_id_col} = %s
                """
                cur.execute(r_query, (txn_row[8],))
                
                receipt_row = cur.fetchone()
                if receipt_row:
                    txn["linked_receipt"] = {
                        "receipt_id": receipt_row[0],
                        "vendor_name": receipt_row[1],
                        "gross_amount": float(receipt_row[2]) if receipt_row[2] else 0.0,
                        "gst_amount": float(receipt_row[3]) if receipt_row[3] else 0.0,
                        "net_amount": float(receipt_row[4]) if receipt_row[4] else 0.0,
                        "receipt_date": receipt_row[5].isoformat() if receipt_row[5] else None,
                        "category": receipt_row[6],
                        "employee_id": receipt_row[7],
                        "vehicle_id": receipt_row[8]
                    }
            
            transactions.append(txn)
        
        # Get account summary
        cur.execute("""
            SELECT 
                COUNT(*) as txn_count,
                MIN(transaction_date) as first_date,
                MAX(transaction_date) as last_date,
                SUM(debit_amount) as total_debits,
                SUM(credit_amount) as total_credits
            FROM banking_transactions
            WHERE account_number = %s
        """, (account_num,))
        
        summary_row = cur.fetchone()
        
        accounts.append({
            "account_number": account_num,
            "summary": {
                "transaction_count": summary_row[0],
                "first_date": summary_row[1].isoformat() if summary_row[1] else None,
                "last_date": summary_row[2].isoformat() if summary_row[2] else None,
                "total_debits": float(summary_row[3]) if summary_row[3] else 0.0,
                "total_credits": float(summary_row[4]) if summary_row[4] else 0.0,
                "net": float(summary_row[4] - summary_row[3]) if summary_row[3] and summary_row[4] else 0.0
            },
            "transactions": transactions
        })
    
    return accounts

def export_employee_payroll_ecosystem(cur, conn):
    """Export complete employee and payroll ecosystem"""
    print("Exporting employee/payroll ecosystem...")
    conn.rollback()  # Clear any previous transaction errors
    # termination_date may not exist in some environments
    term_col = 'e.termination_date' if has_column(cur, 'employees', 'termination_date') else 'NULL AS termination_date'
    emp_query = f"""
        SELECT 
            e.employee_id,
            e.employee_number,
            e.full_name,
            e.first_name,
            e.last_name,
            e.position,
            e.hire_date,
            {term_col},
            e.status,
            e.hourly_rate,
            e.is_chauffeur,
            COUNT(DISTINCT dp.id) as payroll_entries,
            COALESCE(SUM(dp.gross_pay), 0) as total_gross_pay,
            COALESCE(SUM(dp.net_pay), 0) as total_net_pay,
            COUNT(DISTINCT c.charter_id) as charter_count
        FROM employees e
        LEFT JOIN driver_payroll dp ON dp.employee_id = e.employee_id
        LEFT JOIN charters c ON c.assigned_driver_id = e.employee_id
        GROUP BY e.employee_id
        ORDER BY total_gross_pay DESC NULLS LAST
    """
    cur.execute(emp_query)
    
    employees = []
    for row in cur.fetchall():
        employee_id = row[0]
        
        # Get payroll records
        cur.execute("""
            SELECT 
                id, year, month, pay_date, charter_id, reserve_number,
                gross_pay, cpp, ei, tax, total_deductions, net_pay,
                expenses, wcb_payment, t4_box_14, t4_box_16, t4_box_18,
                vacation_pay, quickbooks_source
            FROM driver_payroll
            WHERE employee_id = %s
            ORDER BY year DESC, month DESC, pay_date DESC
        """, (employee_id,))
        
        payroll = []
        for pay_row in cur.fetchall():
            payroll.append({
                "id": pay_row[0],
                "year": pay_row[1],
                "month": pay_row[2],
                "pay_date": pay_row[3].isoformat() if pay_row[3] else None,
                "charter_id": pay_row[4],
                "reserve_number": pay_row[5],
                "gross_pay": float(pay_row[6]) if pay_row[6] else 0.0,
                "cpp": float(pay_row[7]) if pay_row[7] else 0.0,
                "ei": float(pay_row[8]) if pay_row[8] else 0.0,
                "tax": float(pay_row[9]) if pay_row[9] else 0.0,
                "total_deductions": float(pay_row[10]) if pay_row[10] else 0.0,
                "net_pay": float(pay_row[11]) if pay_row[11] else 0.0,
                "expenses": float(pay_row[12]) if pay_row[12] else 0.0,
                "wcb_payment": float(pay_row[13]) if pay_row[13] else 0.0,
                "t4_box_14": float(pay_row[14]) if pay_row[14] else 0.0,
                "t4_box_16": float(pay_row[15]) if pay_row[15] else 0.0,
                "t4_box_18": float(pay_row[16]) if pay_row[16] else 0.0,
                "vacation_pay": float(pay_row[17]) if pay_row[17] else 0.0,
                "quickbooks_source": pay_row[18]
            })
        
        # Get charters driven
        cur.execute("""
            SELECT charter_id, reserve_number, charter_date,
                   total_amount_due, driver_paid, driver_percentage
            FROM charters
            WHERE assigned_driver_id = %s
            ORDER BY charter_date DESC
        """, (employee_id,))
        
        charters = []
        for charter_row in cur.fetchall():
            charters.append({
                "charter_id": charter_row[0],
                "reserve_number": charter_row[1],
                "charter_date": charter_row[2].isoformat() if charter_row[2] else None,
                "total_amount_due": float(charter_row[3]) if charter_row[3] else 0.0,
                "driver_paid": float(charter_row[4]) if charter_row[4] else 0.0,
                "driver_percentage": float(charter_row[5]) if charter_row[5] else 0.0
            })
        
        employees.append({
            "employee": {
                "employee_id": employee_id,
                "employee_number": row[1],
                "full_name": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "position": row[5],
                "hire_date": row[6].isoformat() if row[6] else None,
                "termination_date": row[7].isoformat() if row[7] else None,
                "status": row[8],
                "hourly_rate": float(row[9]) if row[9] else 0.0,
                "is_chauffeur": row[10]
            },
            "summary": {
                "payroll_entries": row[11],
                "total_gross_pay": float(row[12]),
                "total_net_pay": float(row[13]),
                "charter_count": row[14]
            },
            "payroll": payroll,
            "charters_driven": charters
        })
    
    return employees

def export_vehicle_fleet_ecosystem(cur, conn):
    """Export complete vehicle and fleet ecosystem"""
    print("Exporting vehicle/fleet ecosystem...")
    conn.rollback()  # Clear any previous transaction errors
    # unit_number may be absent; select defensively
    unit_col = 'v.unit_number' if has_column(cur, 'vehicles', 'unit_number') else 'NULL AS unit_number'
    # vehicle_type may be named differently (vehicle_code)
    type_col = 'v.vehicle_type' if has_column(cur, 'vehicles', 'vehicle_type') else (
        'v.vehicle_code' if has_column(cur, 'vehicles', 'vehicle_code') else 'NULL AS vehicle_type')
    veh_query = f"""
        SELECT 
            v.vehicle_id,
            {unit_col},
            {type_col},
            v.make,
            v.model,
            v.year,
            v.vin_number,
            v.license_plate,
            v.passenger_capacity,
            {('v.status' if has_column(cur, 'vehicles', 'status') else 'NULL AS status')},
            v.current_mileage,
            COUNT(DISTINCT c.charter_id) as charter_count,
            COUNT(DISTINCT r.receipt_id) as receipt_count,
            COALESCE(SUM(r.gross_amount), 0) as total_expenses
        FROM vehicles v
        LEFT JOIN charters c ON c.vehicle_id = v.vehicle_id
        LEFT JOIN receipts r ON r.vehicle_id = v.vehicle_id
        GROUP BY v.vehicle_id
        ORDER BY charter_count DESC NULLS LAST
    """
    cur.execute(veh_query)
    
    vehicles = []
    for row in cur.fetchall():
        vehicle_id = row[0]
        
        # Get fuel logs
        cur.execute("""
            SELECT log_id, recorded_at, amount, liters,
                   odometer_reading, receipt_id
            FROM vehicle_fuel_log
            WHERE vehicle_id = %s
            ORDER BY recorded_at DESC
        """, (str(vehicle_id),))
        
        fuel_logs = []
        for fuel_row in cur.fetchall():
            fuel_logs.append({
                "log_id": fuel_row[0],
                "recorded_at": fuel_row[1].isoformat() if fuel_row[1] else None,
                "amount": float(fuel_row[2]) if fuel_row[2] else 0.0,
                "liters": float(fuel_row[3]) if fuel_row[3] else 0.0,
                "odometer_reading": fuel_row[4],
                "receipt_id": fuel_row[5]
            })
        
        # Get receipts
        cur.execute("""
            SELECT receipt_id, vendor_name, gross_amount,
                   receipt_date, category, description
            FROM receipts
            WHERE vehicle_id = %s
            ORDER BY receipt_date DESC
        """, (str(vehicle_id),))
        
        receipts = []
        for receipt_row in cur.fetchall():
            receipts.append({
                "receipt_id": receipt_row[0],
                "vendor_name": receipt_row[1],
                "gross_amount": float(receipt_row[2]) if receipt_row[2] else 0.0,
                "receipt_date": receipt_row[3].isoformat() if receipt_row[3] else None,
                "category": receipt_row[4],
                "description": receipt_row[5]
            })
        
        # Get insurance/financing emails
        cur.execute("""
            SELECT id, event_type, amount, due_date, status,
                   lender_name, policy_number, notes
            FROM email_financial_events
            WHERE vehicle_id = %s
            ORDER BY email_date DESC
        """, (vehicle_id,))
        
        financial_events = []
        for event_row in cur.fetchall():
            financial_events.append({
                "id": event_row[0],
                "event_type": event_row[1],
                "amount": float(event_row[2]) if event_row[2] else 0.0,
                "due_date": event_row[3].isoformat() if event_row[3] else None,
                "status": event_row[4],
                "lender_name": event_row[5],
                "policy_number": event_row[6],
                "notes": event_row[7]
            })
        
        vehicles.append({
            "vehicle": {
                "vehicle_id": vehicle_id,
                "unit_number": row[1],
                "vehicle_type": row[2],
                "make": row[3],
                "model": row[4],
                "year": row[5],
                "vin_number": row[6],
                "license_plate": row[7],
                "passenger_capacity": row[8],
                "status": row[9],
                "current_mileage": row[10]
            },
            "summary": {
                "charter_count": row[11],
                "receipt_count": row[12],
                "total_expenses": float(row[13])
            },
            "fuel_logs": fuel_logs,
            "receipts": receipts,
            "financial_events": financial_events
        })
    
    return vehicles

def main():
    parser = argparse.ArgumentParser(description='Export complete almsdata to JSON')
    parser.add_argument('--output', default='reports/complete_almsdata_export.json',
                       help='Output JSON file path')
    parser.add_argument('--compress', action='store_true',
                       help='Compress output with gzip')
    parser.add_argument('--limit', type=int,
                       help='Limit rows per table (for testing)')
    parser.add_argument('--pst', help='Path to PST; when provided, include Calendar_0 events and charter links')
    parser.add_argument('--calendar', default='Calendar_0', help='Calendar folder name to extract (default Calendar_0)')
    args = parser.parse_args()
    
    print("=" * 80)
    print("ARROW LIMOUSINE COMPLETE DATA EXPORT")
    print("=" * 80)
    print()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Initialize export structure
    export_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "database": "almsdata",
            "version": "1.0",
            "description": "Complete Arrow Limousine operational and financial data ecosystem 2007-2025"
        }
    }
    
    # Get table list
    print("Discovering tables...")
    tables = get_table_list(cur)
    export_data["metadata"]["total_tables"] = len(tables)
    print(f"Found {len(tables)} tables (excluding staging tables)")
    print()
    
    # Export ecosystems
    print("Exporting data ecosystems...")
    print("-" * 80)
    
    try:
        export_data["client_ecosystem"] = export_client_ecosystem(cur, conn)
        print(f"✓ Exported {len(export_data['client_ecosystem'])} clients with full charter/payment chains")
    except Exception as e:
        print(f"✗ Error exporting client ecosystem: {e}")
        conn.rollback()
        export_data["client_ecosystem"] = []
    
    try:
        export_data["banking_ecosystem"] = export_banking_ecosystem(cur, conn)
        print(f"✓ Exported {len(export_data['banking_ecosystem'])} bank accounts with transaction chains")
    except Exception as e:
        print(f"✗ Error exporting banking ecosystem: {e}")
        conn.rollback()
        export_data["banking_ecosystem"] = []
    
    try:
        export_data["employee_payroll_ecosystem"] = export_employee_payroll_ecosystem(cur, conn)
        print(f"✓ Exported {len(export_data['employee_payroll_ecosystem'])} employees with payroll chains")
    except Exception as e:
        print(f"✗ Error exporting employee ecosystem: {e}")
        conn.rollback()
        export_data["employee_payroll_ecosystem"] = []
    
    try:
        export_data["vehicle_fleet_ecosystem"] = export_vehicle_fleet_ecosystem(cur, conn)
        print(f"✓ Exported {len(export_data['vehicle_fleet_ecosystem'])} vehicles with fleet operation chains")
    except Exception as e:
        print(f"✗ Error exporting vehicle ecosystem: {e}")
        conn.rollback()
        export_data["vehicle_fleet_ecosystem"] = []
    
    # Optional: include calendar events and link to charters
    export_data["calendar_events"] = []
    if args.pst:
        print("Including calendar events and linking to charters…")
        try:
            events = extract_calendar_events_from_pst(args.pst, args.calendar)
            export_data["calendar_events"] = events
            # Build quick lookup by reserve_number
            reserves_to_event_indexes = {}
            for idx, ev in enumerate(events):
                for rn in ev.get('reserve_numbers') or []:
                    reserves_to_event_indexes.setdefault(rn, []).append(idx)
            # Pre-parse event time segments for overlap matching
            parsed_segments = []  # list of (event_index, [(start_dt, end_dt), ...])
            for idx, ev in enumerate(events):
                segs = []
                for seg in (ev.get('segments') or []):
                    s = seg.get('start'); e = seg.get('end')
                    sdt = None; edt = None
                    try:
                        sdt = datetime.fromisoformat(s) if s else None
                    except Exception:
                        sdt = None
                    try:
                        edt = datetime.fromisoformat(e) if e else None
                    except Exception:
                        edt = None
                    if sdt and edt:
                        segs.append((sdt, edt))
                parsed_segments.append((idx, segs))

            # Attach links to charters in client ecosystem
            for ce in export_data.get("client_ecosystem", []):
                for ch in ce.get("charters", []):
                    rn = ch.get("reserve_number")
                    links = set(reserves_to_event_indexes.get(rn, []) if rn else [])

                    # If no direct RN match, try time overlap matching
                    cd_str = ch.get("charter_date")
                    pt_str = ch.get("pickup_time")
                    dt_charter = None
                    if cd_str:
                        # Combine date + optional pickup time
                        try:
                            base = datetime.fromisoformat(cd_str + 'T00:00:00')
                        except Exception:
                            base = None
                        if base is not None:
                            if pt_str:
                                try:
                                    pt = datetime.fromisoformat('1970-01-01T' + pt_str)
                                    base = base.replace(hour=pt.hour, minute=pt.minute, second=pt.second, microsecond=pt.microsecond)
                                except Exception:
                                    pass
                            dt_charter = base
                    if dt_charter is not None and not links:
                        for ev_idx, segs in parsed_segments:
                            for sdt, edt in segs:
                                if sdt <= dt_charter < edt:
                                    links.add(ev_idx)
                                    break

                    ch["calendar_event_indexes"] = sorted(links)
            print(f"✓ Calendar events added: {len(events)}")
        except Exception as e:
            print(f"✗ Calendar extraction/linking error: {e}")
            export_data["calendar_events"] = []
    
    print()
    print("-" * 80)

    # Build financial links: email e-transfers ↔ banking ↔ charters; Square ↔ charters
    export_data["financial_links"] = {}
    try:
        # Email events → banking → charters (link only, no duplication)
        email_to_banking = []
        cur.execute("""
            SELECT id, email_date::date, amount, subject, notes, banking_transaction_id
            FROM email_financial_events
            WHERE (event_type ILIKE 'e%transfer%' OR source ILIKE '%interac%' OR subject ILIKE '%e-transfer%' OR subject ILIKE '%etransfer%')
        """)
        rows = cur.fetchall()
        for r in rows:
            email_id, email_date, amount, subject, notes, existing_bt = r
            # Candidate reserve numbers from email text
            reserves = sorted(set((parse_reserve_numbers(subject or '') + parse_reserve_numbers(notes or ''))))
            banking_txn_id = existing_bt
            if not banking_txn_id and amount:
                # Find best banking match within ±3 days on either credit or debit side
                cur.execute(
                    """
                    SELECT transaction_id
                    FROM banking_transactions
                    WHERE transaction_date BETWEEN %s - INTERVAL '3 day' AND %s + INTERVAL '3 day'
                      AND ((credit_amount = %s) OR (debit_amount = %s))
                    ORDER BY transaction_date
                    LIMIT 1
                    """,
                    (email_date, email_date, amount, amount),
                )
                bt = cur.fetchone()
                banking_txn_id = bt[0] if bt else None
            email_to_banking.append({
                "email_event_id": email_id,
                "banking_transaction_id": banking_txn_id,
                "reserve_numbers": reserves,
                "amount": float(amount) if amount is not None else None,
                "email_date": email_date.isoformat() if email_date else None,
            })
        export_data["financial_links"]["email_to_banking"] = email_to_banking

        # Square links: use existing square identifiers on payments
        square_links = []
        cur.execute(
            """
            SELECT DISTINCT square_transaction_id, square_payment_id, reserve_number, payment_id
            FROM payments
            WHERE square_transaction_id IS NOT NULL OR square_payment_id IS NOT NULL
            """
        )
        for sq in cur.fetchall():
            square_links.append({
                "square_transaction_id": sq[0],
                "square_payment_id": sq[1],
                "reserve_number": sq[2],
                "payment_id": sq[3],
            })
        export_data["financial_links"]["square_to_charters"] = square_links
    except Exception as e:
        print(f"✗ Financial links build error: {e}")
        export_data["financial_links"] = {"error": str(e)}
    
    # Export all tables
    print("\nExporting complete table data...")
    export_data["tables"] = {}
    
    for i, table_name in enumerate(tables, 1):
        try:
            conn.rollback()  # Clear any errors before each table
            print(f"[{i}/{len(tables)}] {table_name}...", end=" ", flush=True)
            
            stats = get_table_stats(cur, table_name)
            schema = get_table_schema(cur, table_name)
            rows, columns = get_table_data(cur, table_name, limit=args.limit)
            
            export_data["tables"][table_name] = {
                "schema": schema,
                "row_count": stats["row_count"],
                "date_range": stats["date_range"],
                "columns": columns,
                "rows": rows
            }
            
            print(f"✓ {stats['row_count']} rows")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            conn.rollback()
            export_data["tables"][table_name] = {
                "error": str(e)
            }
    
    # Calculate total rows
    total_rows = sum(
        t.get("row_count", 0) 
        for t in export_data["tables"].values() 
        if isinstance(t.get("row_count"), int)
    )
    export_data["metadata"]["total_rows"] = total_rows
    
    # Get overall date range
    try:
        conn.rollback()
        cur.execute("""
            SELECT 
                MIN(charter_date)::text,
                MAX(charter_date)::text
            FROM charters
        """)
        charter_dates = cur.fetchone()
        if charter_dates:
            export_data["metadata"]["date_range"] = {
                "first_charter": charter_dates[0],
                "last_charter": charter_dates[1]
            }
    except:
        pass
    
    cur.close()
    conn.close()
    
    # Write output
    print()
    print("=" * 80)
    print("Writing export file...")
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    if args.compress:
        output_file = args.output + '.gz'
        with gzip.open(output_file, 'wt', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=decimal_default)
    else:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=decimal_default)
    
    file_size = os.path.getsize(output_file if args.compress else args.output)
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"✓ Export complete: {args.output}")
    print(f"  File size: {file_size_mb:.1f} MB")
    print(f"  Total tables: {len(tables)}")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Clients: {len(export_data.get('client_ecosystem', []))}")
    print(f"  Bank accounts: {len(export_data.get('banking_ecosystem', []))}")
    print(f"  Employees: {len(export_data.get('employee_payroll_ecosystem', []))}")
    print(f"  Vehicles: {len(export_data.get('vehicle_fleet_ecosystem', []))}")
    if args.pst:
        print(f"  Calendar events: {len(export_data.get('calendar_events', []))}")
    if export_data.get('financial_links'):
        print(f"  Email↔Bank links: {len(export_data['financial_links'].get('email_to_banking', []))}")
        print(f"  Square↔Charter links: {len(export_data['financial_links'].get('square_to_charters', []))}")
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()
