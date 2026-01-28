## Routes are defined after Flask app initialization below


import os
import pathlib
from flask import Flask, request, jsonify, g, Response, send_from_directory
import psycopg2, time, threading, logging, uuid, json as _json
from typing import Any, Dict, List, cast
from logging.handlers import RotatingFileHandler
from werkzeug.utils import secure_filename

# Load .env early so waitress-invoked processes receive DB credentials
from dotenv import load_dotenv  # type: ignore
load_dotenv(dotenv_path=str(pathlib.Path(__file__).resolve().parent / '.env'))
DIST_DIR = str(pathlib.Path(__file__).resolve().parent / "frontend" / "dist")
app = Flask(__name__, static_folder=DIST_DIR, static_url_path="/")

print(f'[DEBUG] DIST_DIR: {DIST_DIR}')
import os as _os
print(f'[DEBUG] Current working directory: {_os.getcwd()}')

# Directory for employee documents
EMPLOYEE_DOCS_DIR = os.path.join(os.path.dirname(__file__), 'employee_documents')
os.makedirs(EMPLOYEE_DOCS_DIR, exist_ok=True)

# Directory for business compliance documents
BUSINESS_DOCS_DIR = os.path.join(os.path.dirname(__file__), 'business_documents')
os.makedirs(BUSINESS_DOCS_DIR, exist_ok=True)

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Upload business compliance document
@app.route('/api/business/upload_document', methods=['POST'])
def upload_business_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    doc_type = request.form.get('doc_type', 'other')
    expiry = request.form.get('expiry', '')
    if file and allowed_file(file.filename or ""):
        # Save metadata as a JSON file alongside the document
        filename = secure_filename(f"business_{doc_type}_" + (file.filename or ""))
        save_path = os.path.join(BUSINESS_DOCS_DIR, filename)
        file.save(save_path)
        # Save metadata
        meta = {
            'name': filename,
            'doc_type': doc_type,
            'expiry': expiry,
        }
        meta_path = save_path + '.json'
        with open(meta_path, 'w', encoding='utf-8') as f:
            f.write(_json.dumps(meta))
        return jsonify({'success': True, 'filename': filename, 'meta': meta})
    return jsonify({'error': 'Invalid file type'}), 400


# List business compliance documents
@app.route('/api/business/documents', methods=['GET'])
def list_business_documents():
    docs = []
    for fname in os.listdir(BUSINESS_DOCS_DIR):
        if fname.endswith('.json'):
            try:
                with open(os.path.join(BUSINESS_DOCS_DIR, fname), 'r', encoding='utf-8') as f:
                    meta = _json.load(f)
                # Add download URL
                meta['url'] = f"/api/business/document/{meta['name']}"
                docs.append(meta)
            except Exception:
                continue
    return jsonify({'documents': docs})


# Serve business document (for preview or download)
@app.route('/api/business/document/<filename>', methods=['GET'])
def get_business_document(filename: str):
    return send_from_directory(BUSINESS_DOCS_DIR, filename)

# Delete business document and metadata
@app.route('/api/business/document/<filename>', methods=['DELETE'])
def delete_business_document(filename: str):
    file_path = os.path.join(BUSINESS_DOCS_DIR, filename)
    meta_path = file_path + '.json'
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
from flask import Flask, request, jsonify, g, Response, send_from_directory
import os
import psycopg2, time, os, threading, logging, uuid, json as _json
from typing import Any, Dict, List, cast
from logging.handlers import RotatingFileHandler

# Support running as a script (python new_system/api.py) and as a package (import new_system.api)
try:
    from .models import Customer, Vehicle, Employee, Driver, RunCharter  # type: ignore
    from .payroll import PayrollService, FinancialService  # type: ignore
    from .helpers import (
        get_available_vehicle, assign_vehicle_to_booking, update_vehicle_status, calculate_total_cost  # type: ignore
    )
except ImportError:
    from models import Customer, Vehicle, Employee, Driver, RunCharter  # type: ignore
    from payroll import PayrollService, FinancialService  # type: ignore
    from helpers import (
        get_available_vehicle, assign_vehicle_to_booking, update_vehicle_status, calculate_total_cost  # type: ignore
    )
try:
    # Allow relative or flat import of posting engine
    from ..posting_engine import post_event as pe_post_event, reverse_batch as pe_reverse_batch, PostingError as PEPostingError  # type: ignore
except Exception:
    try:
        from posting_engine import post_event as pe_post_event, reverse_batch as pe_reverse_batch, PostingError as PEPostingError  # type: ignore
    except Exception:
        pe_post_event = None  # type: ignore
        pe_reverse_batch = None  # type: ignore
        class PEPostingError(Exception):
            pass

# Logging configuration (rotating + console)
LOG_LEVEL = os.environ.get('API_LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.environ.get('API_LOG_FILE', 'api_runtime.log')
logger = logging.getLogger('arrow.api')
if not logger.handlers:
    logger.setLevel(LOG_LEVEL)
    log_format = os.environ.get('API_LOG_FORMAT','text').lower()
    if log_format == 'json':
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:  # type: ignore
                data = {
                    'ts': self.formatTime(record, '%Y-%m-%dT%H:%M:%S'),
                    'level': record.levelname,
                    'logger': record.name,
                    'msg': record.getMessage(),
                }
                if record.exc_info:
                    data['exc'] = self.formatException(record.exc_info)
                return _json.dumps(data, separators=(',',':'))
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    if LOG_FILE:
        rfh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
        rfh.setFormatter(formatter)
        logger.addHandler(rfh)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    logger.propagate = False
logger.info('loaded module file=%s log_file=%s', __file__, LOG_FILE)

import pathlib
from dotenv import load_dotenv  # type: ignore

# --- Optional Sentry initialization (if sentry-sdk installed and SENTRY_DSN configured) ---
_sentry_enabled = False
try:
    import sentry_sdk  # type: ignore
    from sentry_sdk.integrations.flask import FlaskIntegration  # type: ignore
    _SENTRY_DSN = os.environ.get('SENTRY_DSN')
    if _SENTRY_DSN:
        sentry_sdk.init(dsn=_SENTRY_DSN, integrations=[FlaskIntegration()], traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE','0.0')))  # type: ignore
        _sentry_enabled = True
        logger.info('Sentry initialized')
except Exception as _e:
    logger.debug('Sentry not initialized: %s', _e)

# Global variables for uptime tracking
START_TIME = time.time()
_UPTIME_LOG_INTERVAL = int(os.environ.get('API_UPTIME_LOG_INTERVAL_SECONDS','60'))

"""Database connection helper

Respects the following environment variables:
- DB_HOST (default 'localhost')
- DB_PORT (default '5432')
- DB_NAME (default 'postgres')
- DB_USER (default 'postgres')
- DB_PASSWORD (required for auth-enabled DBs)
"""
def get_db_connection():

    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '5432')),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )

# --- Invoices API ---
@app.route('/api/invoices', methods=['GET'])
def list_invoices():
    """Return a list of invoices for the accounting dashboard."""
    try:
        # Optional filters
        status = request.args.get('status')
        client = request.args.get('client')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = min(500, int(request.args.get('limit', 100)))
        offset = int(request.args.get('offset', 0))

        where = []
        params = []
        if status:
            where.append('status = %s')
            params.append(status)
        if client:
            where.append('(COALESCE(client_name, \'\') ILIKE %s OR COALESCE(client_id::text, \'\') ILIKE %s)')
            params.extend([f"%{client}%", f"%{client}%"])
        if start_date:
            where.append('invoice_date >= %s')
            params.append(start_date)
        if end_date:
            where.append('invoice_date <= %s')
            params.append(end_date)
        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

        sql = f"""
            SELECT invoice_id, invoice_number, COALESCE(client_name, client_id::text) AS client_name,
                   invoice_date, due_date, amount, gst, status
            FROM invoices
            {where_sql}
            ORDER BY invoice_date DESC, invoice_id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify({'results': data, 'limit': limit, 'offset': offset})
    except Exception as e:
        return jsonify({'error': 'Failed to fetch invoices', 'detail': str(e)}), 500

# --- Employees (basic list) ---
@app.route('/api/employees', methods=['GET'])
def list_employees():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('''
            SELECT id, employee_id, name, department, position, phone, email, hire_date, hourly_rate, status
            FROM employees
            ORDER BY name
        ''')
        rows = cur.fetchall()
        raw_cols = [d[0] for d in (cur.description or [])]
        cols = []
        for i, name in enumerate(raw_cols):
            if not name or name.startswith('?'):  # unnamed computed column fallback
                cols.append(f'unnamed_{i}')
            else:
                cols.append(name)
        res = [dict(zip(cols, r)) for r in rows] if cols else []
        cur.close(); conn.close()
        return jsonify(res)
    except Exception:
        # Fallback empty list if table not present
        return jsonify([])

# --- Beverage Orders: Always Editable Endpoints ---
@app.route('/api/charter/<string:run_id>/beverage_orders', methods=['GET'])
def get_beverage_orders(run_id: str):
    """Get the beverage order (itemized_liquor_orders) for a charter/run."""
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT itemized_liquor_orders FROM run_charters WHERE run_id=%s', (run_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row or row[0] is None:
            return jsonify({'beverage_orders': []})
        # If stored as JSON string, parse it
        try:
            orders = row[0] if isinstance(row[0], list) else _json.loads(row[0])
        except Exception:
            orders = []
        return jsonify({'beverage_orders': orders})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charter/<string:run_id>/beverage_orders', methods=['PUT'])
def update_beverage_orders(run_id: str):
    """Update the beverage order (itemized_liquor_orders) for a charter/run."""
    try:
        data = request.get_json(silent=True) or {}
        orders = data.get('beverage_orders', [])
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('UPDATE run_charters SET itemized_liquor_orders=%s WHERE run_id=%s', (_json.dumps(orders), run_id))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'success': True, 'beverage_orders': orders})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Charter-keyed beverage orders (preferred). Keeps legacy run_id endpoints above for compatibility.
@app.route('/api/charter/<int:charter_id>/beverage_orders', methods=['GET'])
def get_beverage_orders_by_charter(charter_id: int):
    """Get beverage orders keyed by charter_id with graceful fallbacks.

    Resolution order:
      1) run_charters.itemized_liquor_orders WHERE charter_id = :charter_id
      2) charters.itemized_liquor_orders WHERE charter_id = :charter_id (if column exists)
      3) run_charters.itemized_liquor_orders WHERE run_id = CAST(charter_id AS TEXT)
    """
    try:
        conn = get_db_connection(); cur = conn.cursor()
        orders = None
        # 1) run_charters by charter_id
        try:
            cur.execute('SELECT itemized_liquor_orders FROM run_charters WHERE charter_id=%s', (charter_id,))
            row = cur.fetchone()
            if row and row[0] is not None:
                try:
                    orders = row[0] if isinstance(row[0], list) else _json.loads(row[0])
                except Exception:
                    orders = []
        except Exception:
            pass
        # 2) charters table JSON column (if present)
        if orders is None:
            try:
                cur.execute('SELECT itemized_liquor_orders FROM charters WHERE charter_id=%s', (charter_id,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    try:
                        orders = row[0] if isinstance(row[0], list) else _json.loads(row[0])
                    except Exception:
                        orders = []
            except Exception:
                pass
        # 3) fallback: treat run_id == str(charter_id)
        if orders is None:
            try:
                cur.execute('SELECT itemized_liquor_orders FROM run_charters WHERE run_id=%s', (str(charter_id),))
                row = cur.fetchone()
                if row and row[0] is not None:
                    try:
                        orders = row[0] if isinstance(row[0], list) else _json.loads(row[0])
                    except Exception:
                        orders = []
            except Exception:
                pass
        cur.close(); conn.close()
        return jsonify({'beverage_orders': orders or []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charter/<int:charter_id>/beverage_orders', methods=['PUT'])
def update_beverage_orders_by_charter(charter_id: int):
    """Update beverage orders keyed by charter_id with best-effort persistence.

    Writes to run_charters if charter_id column exists; otherwise attempts charters.itemized_liquor_orders.
    As a last fallback, writes to run_charters where run_id == CAST(charter_id AS TEXT).
    """
    try:
        data = request.get_json(silent=True) or {}
        orders = data.get('beverage_orders', [])
        conn = get_db_connection(); cur = conn.cursor()
        serialized = _json.dumps(orders)
        updated = False
        # 1) Try run_charters by charter_id
        try:
            cur.execute('UPDATE run_charters SET itemized_liquor_orders=%s WHERE charter_id=%s', (serialized, charter_id))
            if getattr(cur, 'rowcount', 0) and cur.rowcount > 0:
                updated = True
        except Exception:
            pass
        # 2) Try charters table JSON column
        if not updated:
            try:
                cur.execute('UPDATE charters SET itemized_liquor_orders=%s WHERE charter_id=%s', (serialized, charter_id))
                if getattr(cur, 'rowcount', 0) and cur.rowcount > 0:
                    updated = True
            except Exception:
                pass
        # 3) Fallback: run_charters by run_id == charter_id
        if not updated:
            try:
                cur.execute('UPDATE run_charters SET itemized_liquor_orders=%s WHERE run_id=%s', (serialized, str(charter_id)))
                if getattr(cur, 'rowcount', 0) and cur.rowcount > 0:
                    updated = True
            except Exception:
                pass
        try:
            conn.commit()
        except Exception:
            conn.rollback()
        cur.close(); conn.close()
        return jsonify({'success': True, 'beverage_orders': orders, 'updated': updated})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/beverage_order/print_data', methods=['GET'])
def beverage_order_print_data():
    """Return printable beverage order details.

    Accepts either ?run_id=<id> (preferred for run_charters) or ?charter_id=<id>.
    Includes charter_number (reserve_number), client name, date/time, vehicle,
    and itemized beverage contents with pricing and totals.
    """
    run_id = request.args.get('run_id')
    charter_id_arg = request.args.get('charter_id')
    charter_id_val = None
    orders = []
    header = {
        'charter_id': None,
        'run_id': None,
        'charter_number': None,
        'client_name': None,
        'charter_date': None,
        'vehicle': None,
    }
    try:
        conn = get_db_connection(); cur = conn.cursor()

        # Prefer charter_id-based retrieval
        rc_row = None
        if charter_id_arg:
            try:
                cur.execute("""
                    SELECT run_id, itemized_liquor_orders, charter_id, vehicle_booked_id, booking_date
                    FROM run_charters WHERE charter_id=%s
                """, (charter_id_arg,))
                rc_row = cur.fetchone()
            except Exception:
                rc_row = None
            if not rc_row:
                # Some datasets store run_id equal to charter_id string
                try:
                    cur.execute("""
                        SELECT run_id, itemized_liquor_orders, charter_id, vehicle_booked_id, booking_date
                        FROM run_charters WHERE run_id=%s
                    """, (str(charter_id_arg),))
                    rc_row = cur.fetchone()
                except Exception:
                    rc_row = None
        # If a run_id is explicitly provided, try it as a secondary lookup
        if not rc_row and run_id:
            try:
                cur.execute("""
                    SELECT run_id, itemized_liquor_orders, charter_id, vehicle_booked_id, booking_date
                    FROM run_charters WHERE run_id=%s
                """, (run_id,))
                rc_row = cur.fetchone()
            except Exception:
                rc_row = None

        if rc_row:
            header['run_id'] = rc_row[0]
            raw_orders = rc_row[1]
            if raw_orders is not None:
                try:
                    orders = raw_orders if isinstance(raw_orders, list) else _json.loads(raw_orders)
                except Exception:
                    orders = []
            charter_id_val = rc_row[2]
            header['charter_id'] = charter_id_val
            # booking_date from run_charters if present
            if len(rc_row) >= 5 and rc_row[4]:
                header['charter_date'] = str(rc_row[4])

        # If we don't have a charter_id yet, adopt provided args
        if not charter_id_val and charter_id_arg:
            try:
                charter_id_val = int(charter_id_arg)
                header['charter_id'] = charter_id_val
            except Exception:
                pass

        # Enrich header from charters + clients + vehicles
        if charter_id_val:
            try:
                cur.execute(
                    """
                    SELECT 
                        c.charter_id,
                        c.reserve_number,
                        c.charter_date,
                        COALESCE(cl.client_name, c.client_id::text) AS client_name,
                        COALESCE(NULLIF(c.vehicle_description, ''), c.vehicle_booked_id::text) AS vehicle
                    FROM charters c
                    LEFT JOIN clients cl ON c.client_id = cl.client_id 
                    WHERE c.charter_id = %s
                    """,
                    (charter_id_val,)
                )
                ch = cur.fetchone()
                if ch:
                    header['charter_id'] = ch[0]
                    header['charter_number'] = ch[1]
                    header['charter_date'] = str(ch[2]) if ch[2] is not None else header['charter_date']
                    header['client_name'] = ch[3]
                    header['vehicle'] = ch[4]
            except Exception:
                pass
        else:
            # Last-resort: try to match charters by reserve_number == run_id
            if run_id:
                try:
                    cur.execute(
                        """
                        SELECT 
                            c.charter_id,
                            c.reserve_number,
                            c.charter_date,
                            COALESCE(cl.client_name, c.client_id::text) AS client_name,
                            COALESCE(NULLIF(c.vehicle_description, ''), c.vehicle_booked_id::text) AS vehicle
                        FROM charters c
                        LEFT JOIN clients cl ON c.client_id = cl.client_id 
                        WHERE CAST(c.reserve_number AS TEXT) = %s
                        LIMIT 1
                        """,
                        (str(run_id),)
                    )
                    ch = cur.fetchone()
                    if ch:
                        header['charter_id'] = ch[0]
                        header['charter_number'] = ch[1]
                        header['charter_date'] = str(ch[2]) if ch[2] is not None else header['charter_date']
                        header['client_name'] = ch[3]
                        header['vehicle'] = ch[4]
                except Exception:
                    pass

        # Normalize items and compute totals
        items = []
        subtotal = 0.0
        for i, it in enumerate(orders or []):
            try:
                name = (it.get('name') if isinstance(it, dict) else None) or str(it)
                qty = float(it.get('qty', 0)) if isinstance(it, dict) else 0.0
                price = float(it.get('price', 0)) if isinstance(it, dict) else 0.0
            except Exception:
                name = str(it)
                qty = 0.0
                price = 0.0
            line_total = round(price * qty, 2)
            subtotal += line_total
            items.append({'name': name, 'qty': qty, 'price': price, 'line_total': line_total})
        subtotal = round(subtotal, 2)

        cur.close(); conn.close()
        return jsonify({'header': header, 'items': items, 'totals': {'subtotal': subtotal, 'grand_total': subtotal}})
    except Exception as e:
        try:
            cur.close(); conn.close()
        except Exception:
            pass
        return jsonify({'error': str(e), 'header': header, 'items': [], 'totals': {'subtotal': 0.0, 'grand_total': 0.0}}), 500

# --- Payroll Aggregation Endpoint ---
from payroll import aggregate_employee_pay  # import here to avoid circular issues
from api_cibc_cards import *

@app.route('/api/employee/<int:employee_id>/payroll_summary', methods=['GET'])
def get_employee_payroll_summary(employee_id: int):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        summary = aggregate_employee_pay(employee_id, start_date, end_date)
        return jsonify({'payroll_summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Simple test route to verify Flask is working
@app.route('/test')
def test_route():
    return jsonify({'message': 'Flask app is working!', 'timestamp': time.time()})

# Temporary introspection route to help debug route registration during smoke tests
@app.route('/__routes')
def list_routes():
    try:
        rules = []
        for r in app.url_map.iter_rules():  # type: ignore[attr-defined]
            methods = ','.join(sorted(m for m in r.methods if m not in ('HEAD','OPTIONS')))  # type: ignore
            rules.append({'rule': str(r), 'endpoint': r.endpoint, 'methods': methods})
        # Sort by rule for readability
        rules.sort(key=lambda x: x['rule'])
        return jsonify({'routes': rules, 'count': len(rules)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Vehicle & Driver Availability API ---
@app.route('/api/availability')
def api_availability():
    """Return available vehicles and drivers for a given date and group."""
    date = request.args.get('date')
    group = request.args.get('group')
    try:
        # Example: Query real data from ALMSData (replace with actual queries)
        conn = get_db_connection(); cur = conn.cursor()
        # Vehicles by group
        cur.execute('SELECT vehicle_name FROM vehicles WHERE vehicle_group=%s AND operational_status != \'decommissioned\' AND is_active=TRUE', (group,))
        vehicles = [row[0] for row in cur.fetchall()]
        # Drivers by group
        cur.execute('''
            SELECT d.name FROM drivers d
            JOIN driver_qualifications q ON d.id=q.driver_id
            WHERE q.vehicle_group=%s AND d.is_active=TRUE
        ''', (group,))
        drivers = [row[0] for row in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify({'vehicles': vehicles, 'drivers': drivers, 'date': date, 'group': group})
    except Exception as e:
        logger.error(f'Database error in api_availability: {e}')
    return jsonify({'error': 'Database connection failed', 'vehicles': [], 'drivers': [], 'date': date, 'group': group})

@app.route('/charter/<string:run_id>/admin_unlock_paid', methods=['POST'])
def admin_unlock_paid_charter(run_id: str):
    """Admin-only: Unlock a paid charter for manual correction. Logs action for CRA audit."""
    data = request.get_json(silent=True) or {}
    reason = str(data.get('reason', ''))
    user = str(data.get('user', 'admin'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('UPDATE run_charters SET locked=FALSE WHERE run_id=%s', (run_id,))
    cur.execute('INSERT INTO charter_unlock_audit (run_id, user, reason, timestamp) VALUES (%s, %s, %s, NOW())', (run_id, user, reason))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'run_id': run_id, 'locked': False, 'admin_unlock': True, 'reason': reason, 'user': user})

@app.route('/charter/<string:run_id>/approve_hours', methods=['POST'])
def approve_charter_hours(run_id: str):
    """Dispatcher approves work hours for a charter run. Locks hours for payroll calculation."""
    data = request.get_json(silent=True) or {}
    approved_hours = float(data.get('approved_hours', 0))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('UPDATE run_charters SET approved_hours=%s, hours_locked=TRUE WHERE run_id=%s', (approved_hours, run_id))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'run_id': run_id, 'approved_hours': approved_hours, 'locked': True})

@app.route('/charter/<string:run_id>/unlock_hours', methods=['POST'])
def unlock_charter_hours(run_id: str):
    """Unlock work hours for manual correction. Requires explicit dispatcher action."""
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('UPDATE run_charters SET hours_locked=FALSE WHERE run_id=%s', (run_id,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'run_id': run_id, 'locked': False})

@app.route('/charter/<string:run_id>/lock_if_paid', methods=['POST'])
def lock_charter_if_paid(run_id: str):
    """Lock charter run if paid in full. Prevents further edits except by admin."""
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT payment_status FROM run_charters WHERE run_id=%s', (run_id,))
    row = cur.fetchone()
    status = row[0] if row else None
    if status == 'paid':
        cur.execute('UPDATE run_charters SET locked=TRUE WHERE run_id=%s', (run_id,))
        conn.commit(); locked = True
    else:
        locked = False
    cur.close(); conn.close()
    return jsonify({'run_id': run_id, 'locked': locked, 'payment_status': status})

@app.route('/payroll/map_pay_records', methods=['POST'])
def map_pay_records_to_trips():
    """Map historical pay records to actual charter trips. No auto-amendment; manual review only."""
    data = request.get_json(silent=True) or {}
    year = int(data.get('year', 0) or 0)
    month = int(data.get('month', 0) or 0)
    conn = get_db_connection(); cur = conn.cursor()
    # Example: join pay records to charters by driver and date
    cur.execute('''
        SELECT e.id AS employee_id, rc.run_id, rc.driver_id, rc.booking_date, emc.regular_hours, emc.gross_pay
        FROM employees e
        JOIN run_charters rc ON e.id = rc.driver_id
        JOIN employee_monthly_compensation emc ON e.id = emc.employee_id AND emc.year=%s AND emc.month=%s
        WHERE rc.booking_date BETWEEN %s AND %s
    ''', (year, month, f'{year}-{month:02d}-01', f'{year}-{month:02d}-31'))
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in rows]
    cur.close(); conn.close()
    return jsonify({'year': year, 'month': month, 'mapped_records': results})

@app.route('/beverage_orders/invoice_separately', methods=['POST'])
def invoice_beverage_orders():
    """Invoice beverage orders separately from charter runs if required."""
    data = request.get_json(silent=True) or {}
    charter_id = data.get('charter_id')
    invoice_sep = bool(data.get('invoice_separately', True))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT itemized_liquor_orders FROM run_charters WHERE run_id=%s', (charter_id,))
    fetch = cur.fetchone()
    orders = fetch[0] if fetch else []
    # Persist flag on primary charter record if column exists
    try:
        cur.execute('UPDATE charters SET beverage_invoice_separately=%s WHERE charter_id=%s', (invoice_sep, charter_id))
        conn.commit()
    except Exception:
        conn.rollback()
    # Example: create separate invoice (details omitted)
    # ...existing code for invoice creation...
    cur.close(); conn.close()
    return jsonify({'charter_id': charter_id, 'beverage_orders': orders, 'invoiced_separately': invoice_sep})

# API alias for frontend proxy compatibility
@app.route('/api/beverage_orders/invoice_separately', methods=['POST'])
def invoice_beverage_orders_api():
    return invoice_beverage_orders()

# --- Simple API Key Auth Middleware ---
_OPEN_PATHS = {'/', '/health'}
_ROLE_HEADER = 'X-Role'
_ROLE_PERMS = {
    'admin': {'*'},
    'ops': {'GET:/employees','GET:/drivers','GET:/vehicles','GET:/customers','GET:/clients','GET:/health','GET:/'},
    'read': {'GET:/employees','GET:/drivers','GET:/vehicles','GET:/customers','GET:/clients','GET:/health','GET:/'},
}

# Simple in-memory rate limiter (per IP+path, sliding window)
_RATE_LIMIT_ENABLED = os.environ.get('API_RATE_LIMIT','1') not in ('0','false')
_RL_BUCKET: dict[tuple[str,str], list[float]] = {}
_RL_COUNTER: dict[tuple[str,str], int] = {}

def _rate_limited(ip: str, path: str, method: str) -> bool:
    if not _RATE_LIMIT_ENABLED:
        return False
    now = time.time()
    key = (ip, method + ':' + path)
    strategy = os.environ.get('API_RATE_LIMIT_STRATEGY','sliding').lower()
    limit = int(os.environ.get('API_RATE_LIMIT_COUNT','60'))
    if strategy == 'counter':
        cnt = _RL_COUNTER.get(key,0) + 1
        _RL_COUNTER[key] = cnt
        return cnt > limit
    bucket = _RL_BUCKET.setdefault(key, [])
    window = int(os.environ.get('API_RATE_LIMIT_WINDOW','60'))
    cutoff = now - window
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False
def _load_api_keys() -> set[str]:
    raw = os.environ.get('API_KEY','').strip()
    if not raw:
        return set()
    return {k.strip() for k in raw.split(',') if k.strip()}
@app.before_request
def _api_key_guard():
    keys = _load_api_keys()  # dynamic so test fixtures/env changes take effect
    if request.path in _OPEN_PATHS or not keys:
        return None
    provided = request.headers.get('X-API-Key')
    if provided not in keys:
        logger.warning('auth_failed path=%s remote=%s provided=%s', request.path, request.remote_addr, provided)
        return jsonify({'error':'unauthorized'}), 401
    return None

@app.before_request
def _rbac_and_rate_limit():
    # Rate limit check first
    ip = request.remote_addr or 'unknown'
    if _rate_limited(ip, request.path, request.method):
        window = int(os.environ.get('API_RATE_LIMIT_WINDOW','60'))
        return jsonify({'error':'rate_limited','window_seconds': window}), 429
    # RBAC only if API keys active (otherwise open dev mode)
    if request.path in _OPEN_PATHS:
        return None
    if _load_api_keys():
        role = request.headers.get(_ROLE_HEADER, 'read')
        method_path = f"{request.method}:{request.path.rstrip('/')}" if request.path != '/' else f"{request.method}:/"
        allowed = _ROLE_PERMS.get(role, set())
        if '*' in allowed or method_path in allowed:
            return None
        logger.warning('rbac_denied role=%s path=%s method=%s', role, request.path, request.method)
        return jsonify({'error':'forbidden','required':'insufficient_role'}), 403
    return None

# --- Correlation / Request Logging Middleware ---
_REQUEST_LOG = os.environ.get('API_REQUEST_LOG', '1') not in ('0','false','no')

@app.before_request
def _request_start():
    if not _REQUEST_LOG:
        return None
    g._req_start = time.time()
    # allow client-provided request id, else generate
    rid = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:16]
    g._req_id = rid
    return None

@app.after_request
def _request_end(resp: Response):
    if _REQUEST_LOG:
        try:
            dur_ms = None
            if hasattr(g, '_req_start'):
                dur_ms = int((time.time()-g._req_start)*1000)
            rid = getattr(g, '_req_id', '-')
            resp.headers['X-Request-ID'] = rid
            logger.info('req id=%s method=%s path=%s status=%s dur_ms=%s ua="%s" ip=%s',
                        rid, request.method, request.path, resp.status_code, dur_ms, request.headers.get('User-Agent','-'), request.remote_addr)
        except Exception as e:
            logger.debug('request log failed: %s', e)
    return resp

# --- Global JSON error handler with correlation id ---
@app.errorhandler(Exception)
def _handle_unexpected_error(e: Exception):
    try:
        rid = getattr(g, '_req_id', uuid.uuid4().hex[:16])
        status = 500
        # Werkzeug/HTTPExceptions expose code
        try:
            from werkzeug.exceptions import HTTPException  # type: ignore
            if isinstance(e, HTTPException):
                status = int(getattr(e, 'code', 500) or 500)
        except Exception:
            pass
        if status >= 500:
            logger.exception('unhandled_exception id=%s', rid)
            # Capture to sentry if enabled
            if _sentry_enabled:
                try:
                    import sentry_sdk  # type: ignore
                    sentry_sdk.capture_exception(e)  # type: ignore
                except Exception:
                    pass
        else:
            logger.warning('http_error id=%s status=%s msg=%s', rid, status, str(e))
        payload = {'error': 'internal_error' if status >= 500 else 'error', 'message': str(e), 'request_id': rid}
        return jsonify(payload), status
    except Exception as _eh:
        # As a last resort, avoid breaking Flask's default handler
        logger.debug('error handler failed: %s', _eh)
        raise e

def _uptime_logger():
    while True:
        try:
            up = round(time.time()-START_TIME,2)
            logger.debug('uptime_seconds=%s', up)
            time.sleep(_UPTIME_LOG_INTERVAL)
        except Exception as e:
            logger.warning('uptime logger exception: %s', e)
            time.sleep(_UPTIME_LOG_INTERVAL)

threading.Thread(target=_uptime_logger, name='uptime-logger', daemon=True).start()

# Removed conflicting root route to allow static file serving at '/'

@app.route('/__routes', methods=['GET'])
def __list_routes():
    try:
        routes = []
        for rule in app.url_map.iter_rules():
            # skip static file route to reduce noise
            if rule.endpoint == 'static':
                continue
            methods = sorted([m for m in (rule.methods or []) if m not in ('HEAD','OPTIONS')])
            routes.append({
                'rule': str(rule),
                'endpoint': rule.endpoint,
                'methods': methods,
            })
        routes.sort(key=lambda r: r['rule'])
        return jsonify({'routes': routes})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    try:
        conn = get_db_connection(); cur = conn.cursor(); cur.execute('SELECT 1'); cur.fetchone(); cur.close(); conn.close(); db='up'
    except Exception as e:
        logger.error('health db check failed: %s', e)
        db='down'
    return jsonify({'status':'ok','db':db,'uptime_seconds': round(time.time()-START_TIME,2)})

@app.route('/api/receipts', methods=['GET'])
def search_receipts():
    """Search receipts with flexible filters

    Query params (all optional):
    - q: free-text vendor/description contains (case-insensitive)
    - vendor: exact or partial vendor match (ILIKE)
    - min_amount, max_amount: numeric filters
    - date: exact date (YYYY-MM-DD)
    - start_date, end_date: date range inclusive
    - limit: max rows (default 100)
    - offset: for pagination (default 0)
    """
    try:
        q = (request.args.get('q') or '').strip()
        vendor = (request.args.get('vendor') or '').strip()
        date = (request.args.get('date') or '').strip()
        start_date = (request.args.get('start_date') or '').strip()
        end_date = (request.args.get('end_date') or '').strip()
        min_amount = request.args.get('min_amount')
        max_amount = request.args.get('max_amount')
        try:
            limit = max(1, min(500, int(request.args.get('limit', '100'))))
        except Exception:
            limit = 100
        try:
            offset = max(0, int(request.args.get('offset', '0')))
        except Exception:
            offset = 0

        where: List[str] = []
        params: List[Any] = []
        if q:
            where.append('(COALESCE(vendor_name,\'\') ILIKE %s OR COALESCE(comment,\'\') ILIKE %s)')
            like = f"%{q}%"; params.extend([like, like])
        if vendor:
            where.append('COALESCE(vendor_name,\'\') ILIKE %s'); params.append(f"%{vendor}%")
        if date:
            where.append('receipt_date::date = %s'); params.append(date)
        if start_date:
            where.append('receipt_date::date >= %s'); params.append(start_date)
        if end_date:
            where.append('receipt_date::date <= %s'); params.append(end_date)
        if min_amount is not None:
            try:
                where.append('gross_amount >= %s'); params.append(float(min_amount))
            except Exception:
                pass
        if max_amount is not None:
            try:
                where.append('gross_amount <= %s'); params.append(float(max_amount))
            except Exception:
                pass

        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
        sql = f"""
            SELECT id,
                   receipt_date,
                   vendor_name AS vendor,
                   COALESCE(comment, '') AS description,
                   gross_amount AS amount
            FROM receipts
            {where_sql}
            ORDER BY receipt_date DESC, id DESC
            LIMIT %s OFFSET %s
        """

        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(sql, params + [limit, offset])
        rows = cur.fetchall(); cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]

        # total count for pagination
        cur.execute(f"SELECT COUNT(*) FROM receipts {where_sql}", params)
        total = cur.fetchone()[0]
        cur.close(); conn.close()
        return jsonify({'results': data, 'total': total, 'limit': limit, 'offset': offset})
    except Exception as e:
        logger.error('search_receipts error=%s', e)
        return jsonify({'error': 'Failed to search receipts', 'detail': str(e)}), 500

@app.route('/api/receipts/<int:receipt_id>', methods=['GET'])
def get_receipt(receipt_id: int):
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('''
            SELECT id,
                   receipt_date,
                   vendor_name AS vendor,
                   COALESCE(comment, '') AS description,
                   gross_amount AS amount
            FROM receipts WHERE id=%s
        ''', (receipt_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close(); return jsonify({'error': 'not_found'}), 404
        cols = [d[0] for d in cur.description]
        cur.close(); conn.close()
        return jsonify(dict(zip(cols, row)))
    except Exception as e:
        return jsonify({'error': 'Failed to get receipt', 'detail': str(e)}), 500


@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_stats():
    """Get new dashboard metrics: open quotes, open charters, balance owing, driver/vehicle warnings"""
    try:
        # Get date filter parameters
        date_filter = request.args.get('date_filter', '')
        
        conn = get_db_connection()
        cur = conn.cursor()

        # Build date filter clause based on quick filter selection
        date_clause = ""
        date_params = []
        
        if date_filter == 'today':
            date_clause = " AND DATE(charter_date) = CURRENT_DATE"
        elif date_filter == 'tomorrow':
            date_clause = " AND DATE(charter_date) = CURRENT_DATE + INTERVAL '1 day'"
        elif date_filter == 'this_week':
            date_clause = " AND charter_date >= DATE_TRUNC('week', CURRENT_DATE) AND charter_date < DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '7 days'"
        elif date_filter == 'last_week':
            date_clause = " AND charter_date >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '7 days' AND charter_date < DATE_TRUNC('week', CURRENT_DATE)"
        elif date_filter == 'this_month':
            date_clause = " AND DATE_TRUNC('month', charter_date) = DATE_TRUNC('month', CURRENT_DATE)"
        elif date_filter == 'not_closed':
            # Not closed means active/open statuses (not completed, cancelled, etc.)
            date_clause = " AND status NOT IN ('Completed', 'Cancelled', 'No Show', 'Billed')"

        # Open quotes (status indicates potential new bookings)
        quote_statuses = ['Waiting Deposit', 'Contract Recvd', 'Confirmed']
        quote_query = f"SELECT COUNT(*) FROM charters WHERE status IN ({','.join(['%s']*len(quote_statuses))}){date_clause}"
        cur.execute(quote_query, quote_statuses + date_params)
        row = cur.fetchone(); open_quotes = (row[0] if row else 0)

        # Open charters (active/in-progress charters)
        active_statuses = ['1 In Route', 'Confirmed', 'Deposit Recvd']
        active_query = f"SELECT COUNT(*) FROM charters WHERE status IN ({','.join(['%s']*len(active_statuses))}){date_clause}"
        cur.execute(active_query, active_statuses + date_params)
        row = cur.fetchone(); open_charters = (row[0] if row else 0)

        # Balance owing (unpaid/overdue amounts)
        balance_query = f"SELECT COUNT(*) as count, SUM(balance) as total FROM charters WHERE balance > 0{date_clause}"
        cur.execute(balance_query, date_params)
        balance_row = cur.fetchone()
        balance_count = balance_row[0] if balance_row else 0
        balance_total = float(balance_row[1]) if balance_row and balance_row[1] else 0.0

        # Vehicle availability by type (active vehicles only)
        cur.execute('SELECT COUNT(*) FROM vehicles WHERE operational_status != \'decommissioned\' AND is_active = TRUE')
        row = cur.fetchone(); total_vehicles = (row[0] if row else 0)
        
        # Driver availability warning (placeholder - no drivers table found)
        driver_warning = "No driver availability tracking available"
        
        # Vehicle availability warning by type
        vehicle_warning = f"{total_vehicles} vehicles available"

        cur.close(); conn.close()

        return jsonify({
            'open_quotes': open_quotes,
            'open_charters': open_charters,
            'balance_owing_count': balance_count,
            'balance_owing_total': balance_total,
            'driver_warning': driver_warning,
            'vehicle_warning': vehicle_warning
        })
    except Exception as e:
        return jsonify({
            'open_quotes': 0,
            'open_charters': 0,
            'balance_owing_count': 0,
            'balance_owing_total': 0.0,
            'driver_warning': f'Error: {str(e)}',
            'vehicle_warning': f'Error: {str(e)}',
            'error': str(e)
        }), 500

# --- Reports Export API (CSV-first) ---
@app.route('/api/reports/export', methods=['GET'])
def export_report():
    """Export common reports as CSV attachments.

    Query params:
      - type: report type (revenue-analysis, payment-analysis, receipts-expenses,
               charter-analysis, fleet-utilization, booking-trends)
      - format: csv (default). pdf may return 501 if not available.
      - start_date, end_date: ISO dates (optional); defaults to last 365 days
      - period/year and other params are ignored for now (future use)
    """
    import io, csv
    from datetime import datetime, timedelta

    rtype = (request.args.get('type') or '').strip().lower()
    ofmt = (request.args.get('format') or 'csv').strip().lower()
    if ofmt != 'csv':
        # PDF/others not yet implemented
        return jsonify({'error': 'format_not_supported', 'detail': f'Format {ofmt} not implemented; use csv'}), 501

    # Date range defaults
    def _parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    end = _parse_date(request.args.get('end_date')) or datetime.now()
    start = _parse_date(request.args.get('start_date')) or (end - timedelta(days=365))

    conn = get_db_connection(); cur = conn.cursor()
    from typing import Tuple
    rows: List[Tuple[Any, ...]] = []
    headers: List[str] = []
    try:
        if rtype == 'revenue-analysis':
            # Sum of charges by month within date range; fallback to charters.total_amount_due
            try:
                cur.execute(
                    """
                    SELECT DATE_TRUNC('month', c.charter_date) AS period, COALESCE(SUM(cc.amount),0) AS revenue
                    FROM charters c
                    LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
                    WHERE c.charter_date BETWEEN %s AND %s
                    GROUP BY 1
                    ORDER BY 1
                    """,
                    (start, end)
                )
                headers = ['period', 'revenue']
            except Exception:
                conn.rollback()
                cur.execute(
                    """
                    SELECT DATE_TRUNC('month', charter_date) AS period, COALESCE(SUM(total_amount_due),0) AS revenue
                    FROM charters
                    WHERE charter_date BETWEEN %s AND %s
                    GROUP BY 1
                    ORDER BY 1
                    """,
                    (start, end)
                )
                headers = ['period', 'revenue']
            rows = cur.fetchall()
        elif rtype == 'payment-analysis':
            cur.execute(
                """
                SELECT DATE_TRUNC('month', payment_date) AS period, COALESCE(SUM(amount),0) AS payments
                FROM payments
                WHERE payment_date BETWEEN %s AND %s
                GROUP BY 1
                ORDER BY 1
                """,
                (start, end)
            )
            headers = ['period', 'payments']
            rows = cur.fetchall()
        elif rtype == 'receipts-expenses':
            # Best-effort receipts table export by month, if available
            try:
                cur.execute(
                    """
                    SELECT DATE_TRUNC('month', receipt_date) AS period, COALESCE(SUM(amount),0) AS expenses
                    FROM receipts
                    WHERE receipt_date BETWEEN %s AND %s
                    GROUP BY 1
                    ORDER BY 1
                    """,
                    (start, end)
                )
                headers = ['period', 'expenses']
                rows = cur.fetchall()
            except Exception:
                conn.rollback()
                headers = ['note']
                rows = [("receipts table not available",)]
        elif rtype == 'charter-analysis':
            cur.execute(
                """
                SELECT c.charter_id, c.charter_date, COALESCE(cl.client_name, c.client_id::text) AS client, c.vehicle_booked_id, c.driver_name, c.status
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                WHERE c.charter_date BETWEEN %s AND %s
                ORDER BY c.charter_date DESC, c.charter_id DESC
                LIMIT 5000
                """,
                (start, end)
            )
            headers = ['charter_id', 'charter_date', 'client', 'vehicle_booked_id', 'driver_name', 'status']
            rows = cur.fetchall()
        elif rtype == 'fleet-utilization':
            cur.execute(
                """
                SELECT c.vehicle_booked_id AS vehicle, COUNT(*) AS trips
                FROM charters c
                WHERE c.charter_date BETWEEN %s AND %s AND COALESCE(c.vehicle_booked_id,'') <> ''
                GROUP BY 1
                ORDER BY trips DESC
                """,
                (start, end)
            )
            headers = ['vehicle', 'trips']
            rows = cur.fetchall()
        elif rtype == 'booking-trends':
            cur.execute(
                """
                SELECT DATE_TRUNC('month', charter_date) AS period, COUNT(*) AS bookings
                FROM charters
                WHERE charter_date BETWEEN %s AND %s
                GROUP BY 1
                ORDER BY 1
                """,
                (start, end)
            )
            headers = ['period', 'bookings']
            rows = cur.fetchall()
        else:
            return jsonify({'error': 'unknown_report_type', 'detail': rtype}), 400
    except Exception as e:
        cur.close(); conn.close()
        raise e

    # Stream CSV
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        out = []
        for v in r:
            if hasattr(v, 'isoformat'):
                try:
                    out.append(v.isoformat())
                except Exception:
                    out.append(str(v))
            else:
                out.append(v)
        writer.writerow(out)
    csv_data = buf.getvalue()
    buf.close()
    cur.close(); conn.close()

    filename = f"{rtype.replace(' ','_')}_{int(time.time())}.csv"
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


# --- QuickBooks Reports API ---
@app.route('/api/reports/qb/journal', methods=['GET'])
def qb_journal_report():
    """QuickBooks-style Journal report with entries and line items.
    
    Query params:
      - start_date, end_date: Filter by transaction date (ISO format)
      - account_id: Filter by specific account
      - limit: Max entries to return (default 1000)
    """
    from datetime import datetime, timedelta
    
    def _parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    
    end = _parse_date(request.args.get('end_date')) or datetime.now()
    start = _parse_date(request.args.get('start_date')) or (end - timedelta(days=90))
    account_id = request.args.get('account_id')
    limit = int(request.args.get('limit', 1000))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Build query based on filters
        where_clauses = ["je.transaction_date BETWEEN %s AND %s"]
        params: List[Any] = [start, end]
        
        if account_id:
            where_clauses.append("jl.account_id = %s")
            params.append(account_id)
        
        where_sql = " AND ".join(where_clauses)
        
        cur.execute(f"""
            SELECT 
                je.entry_id,
                je.transaction_date,
                je.entry_number,
                je.reference,
                je.memo,
                je.total_amount,
                je.is_adjusting_entry,
                COALESCE(array_agg(
                    json_build_object(
                        'line_id', jl.line_id,
                        'account_id', jl.account_id,
                        'account_name', ca.account_name,
                        'account_number', ca.account_number,
                        'debit', jl.debit_amount,
                        'credit', jl.credit_amount,
                        'memo', jl.memo,
                        'entity_type', jl.entity_type,
                        'entity_id', jl.entity_id,
                        'entity_name', jl.entity_name
                    ) ORDER BY jl.line_number
                ) FILTER (WHERE jl.line_id IS NOT NULL), '{{}}') as lines
            FROM qb_journal_entries je
            LEFT JOIN journal_lines jl ON je.entry_id = jl.entry_id
            LEFT JOIN chart_of_accounts ca ON jl.account_id = ca.account_id
            WHERE {where_sql}
            GROUP BY je.entry_id
            ORDER BY je.transaction_date DESC, je.entry_number DESC
            LIMIT %s
        """, params + [limit])
        
        entries = []
        for row in cur.fetchall():
            entries.append({
                'entry_id': row[0],
                'transaction_date': row[1].isoformat() if row[1] else None,
                'entry_number': row[2],
                'reference': row[3],
                'memo': row[4],
                'total_amount': float(row[5]) if row[5] else 0.0,
                'is_adjusting_entry': row[6],
                'lines': row[7] if row[7] else []
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'entries': entries,
            'count': len(entries),
            'start_date': start.isoformat(),
            'end_date': end.isoformat()
        })
        
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/qb/general-ledger', methods=['GET'])
def qb_general_ledger():
    """QuickBooks General Ledger report by account.
    
    Query params:
      - start_date, end_date: Filter by transaction date (ISO format)
      - account_id: Specific account (required)
    """
    from datetime import datetime, timedelta
    
    def _parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    
    account_id = request.args.get('account_id')
    if not account_id:
        return jsonify({'error': 'account_id is required'}), 400
    
    end = _parse_date(request.args.get('end_date')) or datetime.now()
    start = _parse_date(request.args.get('start_date')) or (end - timedelta(days=90))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get account info
        cur.execute("""
            SELECT account_id, account_number, account_name, account_type, 
                   opening_balance, current_balance, is_active
            FROM chart_of_accounts
            WHERE account_id = %s
        """, (account_id,))
        
        account_row = cur.fetchone()
        if not account_row:
            cur.close()
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        account_info = {
            'account_id': account_row[0],
            'account_number': account_row[1],
            'account_name': account_row[2],
            'account_type': account_row[3],
            'opening_balance': float(account_row[4]) if account_row[4] else 0.0,
            'current_balance': float(account_row[5]) if account_row[5] else 0.0,
            'is_active': account_row[6]
        }
        
        # Get transactions for this account
        cur.execute("""
            SELECT 
                je.transaction_date,
                je.entry_number,
                je.reference,
                jl.memo,
                jl.debit_amount,
                jl.credit_amount,
                jl.entity_type,
                jl.entity_name
            FROM journal_lines jl
            JOIN qb_journal_entries je ON jl.entry_id = je.entry_id
            WHERE jl.account_id = %s
              AND je.transaction_date BETWEEN %s AND %s
            ORDER BY je.transaction_date, je.entry_number
        """, (account_id, start, end))
        
        transactions = []
        running_balance = account_info['opening_balance']
        
        for row in cur.fetchall():
            debit = float(row[4]) if row[4] else 0.0
            credit = float(row[5]) if row[5] else 0.0
            
            # Calculate running balance based on account type
            if account_info['account_type'] in ['Asset', 'Expense']:
                running_balance += debit - credit
            else:
                running_balance += credit - debit
            
            transactions.append({
                'date': row[0].isoformat() if row[0] else None,
                'entry_number': row[1],
                'reference': row[2],
                'memo': row[3],
                'debit': debit,
                'credit': credit,
                'balance': running_balance,
                'entity_type': row[6],
                'entity_name': row[7]
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'account': account_info,
            'transactions': transactions,
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'ending_balance': running_balance
        })
        
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/qb/account-activity', methods=['GET'])
def qb_account_activity():
    """Account activity summary using QB view.
    
    Query params:
      - start_date, end_date: Filter by transaction date (ISO format)
      - account_type: Filter by account type (Asset, Liability, etc.)
    """
    from datetime import datetime, timedelta
    
    def _parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    
    end = _parse_date(request.args.get('end_date')) or datetime.now()
    start = _parse_date(request.args.get('start_date')) or (end - timedelta(days=90))
    account_type = request.args.get('account_type')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        where_clauses = ["first_transaction >= %s OR last_transaction <= %s"]
        params: List[Any] = [start, end]
        
        if account_type:
            where_clauses.append("account_type = %s")
            params.append(account_type)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        cur.execute(f"""
            SELECT 
                account_id,
                account_number,
                account_name,
                account_type,
                total_debits,
                total_credits,
                net_activity,
                transaction_count,
                first_transaction,
                last_transaction
            FROM qb_account_activity_summary
            WHERE {where_sql}
            ORDER BY account_number
        """, params)
        
        accounts = []
        for row in cur.fetchall():
            accounts.append({
                'account_id': row[0],
                'account_number': row[1],
                'account_name': row[2],
                'account_type': row[3],
                'total_debits': float(row[4]) if row[4] else 0.0,
                'total_credits': float(row[5]) if row[5] else 0.0,
                'net_activity': float(row[6]) if row[6] else 0.0,
                'transaction_count': row[7],
                'first_transaction': row[8].isoformat() if row[8] else None,
                'last_transaction': row[9].isoformat() if row[9] else None
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'accounts': accounts,
            'start_date': start.isoformat(),
            'end_date': end.isoformat()
        })
        
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/qb/income-statement', methods=['GET'])
def qb_income_statement():
    """QuickBooks-style Income Statement (Profit & Loss).
    
    Query params:
      - start_date, end_date: Report period (ISO format)
    """
    from datetime import datetime, timedelta
    
    def _parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    
    end = _parse_date(request.args.get('end_date')) or datetime.now()
    start = _parse_date(request.args.get('start_date')) or datetime(end.year, 1, 1)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Income accounts (4000-4999)
        cur.execute("""
            SELECT 
                ca.account_number,
                ca.account_name,
                COALESCE(SUM(jl.credit_amount - jl.debit_amount), 0) as amount
            FROM chart_of_accounts ca
            LEFT JOIN journal_lines jl ON ca.account_id = jl.account_id
            LEFT JOIN qb_journal_entries je ON jl.entry_id = je.entry_id
            WHERE ca.account_type = 'Income'
              AND ca.is_active = true
              AND (je.transaction_date IS NULL OR je.transaction_date BETWEEN %s AND %s)
            GROUP BY ca.account_id, ca.account_number, ca.account_name
            ORDER BY ca.account_number
        """, (start, end))
        
        income_accounts = []
        total_income = 0.0
        for row in cur.fetchall():
            amount = float(row[2]) if row[2] else 0.0
            income_accounts.append({
                'account_number': row[0],
                'account_name': row[1],
                'amount': amount
            })
            total_income += amount
        
        # Expense accounts (6000-6999)
        cur.execute("""
            SELECT 
                ca.account_number,
                ca.account_name,
                COALESCE(SUM(jl.debit_amount - jl.credit_amount), 0) as amount
            FROM chart_of_accounts ca
            LEFT JOIN journal_lines jl ON ca.account_id = jl.account_id
            LEFT JOIN qb_journal_entries je ON jl.entry_id = je.entry_id
            WHERE ca.account_type = 'Expense'
              AND ca.is_active = true
              AND (je.transaction_date IS NULL OR je.transaction_date BETWEEN %s AND %s)
            GROUP BY ca.account_id, ca.account_number, ca.account_name
            ORDER BY ca.account_number
        """, (start, end))
        
        expense_accounts = []
        total_expenses = 0.0
        for row in cur.fetchall():
            amount = float(row[2]) if row[2] else 0.0
            expense_accounts.append({
                'account_number': row[0],
                'account_name': row[1],
                'amount': amount
            })
            total_expenses += amount
        
        net_income = total_income - total_expenses
        
        cur.close()
        conn.close()
        
        return jsonify({
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'income': {
                'accounts': income_accounts,
                'total': total_income
            },
            'expenses': {
                'accounts': expense_accounts,
                'total': total_expenses
            },
            'net_income': net_income
        })
        
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/qb/balance-sheet', methods=['GET'])
def qb_balance_sheet():
    """QuickBooks-style Balance Sheet.
    
    Query params:
      - as_of_date: Report date (ISO format, defaults to today)
    """
    from datetime import datetime
    
    def _parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    
    as_of_date = _parse_date(request.args.get('as_of_date')) or datetime.now()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Assets (1000-1999)
        cur.execute("""
            SELECT 
                ca.account_number,
                ca.account_name,
                COALESCE(ca.current_balance, ca.opening_balance, 0) as balance
            FROM chart_of_accounts ca
            WHERE ca.account_type IN ('Asset', 'Bank', 'Other Current Asset', 'Fixed Asset', 'Other Asset')
              AND ca.is_active = true
            ORDER BY ca.account_number
        """)
        
        assets = []
        total_assets = 0.0
        for row in cur.fetchall():
            balance = float(row[2]) if row[2] else 0.0
            assets.append({
                'account_number': row[0],
                'account_name': row[1],
                'balance': balance
            })
            total_assets += balance
        
        # Liabilities (2000-2999)
        cur.execute("""
            SELECT 
                ca.account_number,
                ca.account_name,
                COALESCE(ca.current_balance, ca.opening_balance, 0) as balance
            FROM chart_of_accounts ca
            WHERE ca.account_type IN ('Liability', 'Accounts Payable', 'Credit Card', 'Other Current Liability', 'Long Term Liability')
              AND ca.is_active = true
            ORDER BY ca.account_number
        """)
        
        liabilities = []
        total_liabilities = 0.0
        for row in cur.fetchall():
            balance = float(row[2]) if row[2] else 0.0
            liabilities.append({
                'account_number': row[0],
                'account_name': row[1],
                'balance': balance
            })
            total_liabilities += balance
        
        # Equity (3000-3999)
        cur.execute("""
            SELECT 
                ca.account_number,
                ca.account_name,
                COALESCE(ca.current_balance, ca.opening_balance, 0) as balance
            FROM chart_of_accounts ca
            WHERE ca.account_type IN ('Equity', 'Retained Earnings')
              AND ca.is_active = true
            ORDER BY ca.account_number
        """)
        
        equity = []
        total_equity = 0.0
        for row in cur.fetchall():
            balance = float(row[2]) if row[2] else 0.0
            equity.append({
                'account_number': row[0],
                'account_name': row[1],
                'balance': balance
            })
            total_equity += balance
        
        total_liabilities_equity = total_liabilities + total_equity
        
        cur.close()
        conn.close()
        
        return jsonify({
            'as_of_date': as_of_date.isoformat(),
            'assets': {
                'accounts': assets,
                'total': total_assets
            },
            'liabilities': {
                'accounts': liabilities,
                'total': total_liabilities
            },
            'equity': {
                'accounts': equity,
                'total': total_equity
            },
            'total_liabilities_and_equity': total_liabilities_equity
        })
        
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/qb/ar-aging', methods=['GET'])
def qb_ar_aging():
    """Accounts Receivable Aging report using QB invoice view.
    
    Query params:
      - as_of_date: Report date (ISO format, defaults to today)
    """
    from datetime import datetime
    
    def _parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    
    as_of_date = _parse_date(request.args.get('as_of_date')) or datetime.now()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                customer_name,
                invoice_number,
                invoice_date,
                due_date,
                total_amount,
                balance_due,
                aging_days,
                CASE 
                    WHEN aging_days <= 0 THEN 'Current'
                    WHEN aging_days BETWEEN 1 AND 30 THEN '1-30 Days'
                    WHEN aging_days BETWEEN 31 AND 60 THEN '31-60 Days'
                    WHEN aging_days BETWEEN 61 AND 90 THEN '61-90 Days'
                    ELSE 'Over 90 Days'
                END as aging_bucket
            FROM qb_ar_aging
            WHERE status IN ('Open', 'Overdue')
            ORDER BY customer_name, invoice_date
        """)
        
        invoices = []
        aging_summary = {
            'current': 0.0,
            '1_30_days': 0.0,
            '31_60_days': 0.0,
            '61_90_days': 0.0,
            'over_90_days': 0.0,
            'total': 0.0
        }
        
        for row in cur.fetchall():
            balance = float(row[5]) if row[5] else 0.0
            aging_bucket = row[7]
            
            invoices.append({
                'customer_name': row[0],
                'invoice_number': row[1],
                'invoice_date': row[2].isoformat() if row[2] else None,
                'due_date': row[3].isoformat() if row[3] else None,
                'total_amount': float(row[4]) if row[4] else 0.0,
                'balance_due': balance,
                'aging_days': row[6],
                'aging_bucket': aging_bucket
            })
            
            # Update summary
            if aging_bucket == 'Current':
                aging_summary['current'] += balance
            elif aging_bucket == '1-30 Days':
                aging_summary['1_30_days'] += balance
            elif aging_bucket == '31-60 Days':
                aging_summary['31_60_days'] += balance
            elif aging_bucket == '61-90 Days':
                aging_summary['61_90_days'] += balance
            elif aging_bucket == 'Over 90 Days':
                aging_summary['over_90_days'] += balance
            
            aging_summary['total'] += balance
        
        cur.close()
        conn.close()
        
        return jsonify({
            'as_of_date': as_of_date.isoformat(),
            'invoices': invoices,
            'summary': aging_summary
        })
        
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500


# Employee Management
@app.route('/employees', methods=['GET'])
@app.route('/api/employees', methods=['GET'])
def get_employees():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM employees')
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]  # type: ignore
        data = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Driver Management
@app.route('/drivers', methods=['GET'])
@app.route('/api/drivers', methods=['GET'])
def get_drivers():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        # Primary drivers: `employee_number` starts with 'Dr' and active/current
        cur.execute(
            """
            SELECT DISTINCT ON (employee_id) *
            FROM employees
            WHERE employee_number LIKE 'Dr%'
              AND COALESCE(status, 'active') IN ('active','current')
              AND COALESCE(TRIM(full_name), '') <> ''
            ORDER BY employee_id, id DESC
            """
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]  # type: ignore
        data = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Driver Numbers (from employees table only)
@app.route('/api/driver-numbers', methods=['GET'])
def get_driver_numbers():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(
            """
                        SELECT DISTINCT employee_number
                        FROM employees
                        WHERE employee_number IS NOT NULL
                            AND TRIM(employee_number) <> ''
                            AND employee_number LIKE 'Dr%'
                            AND COALESCE(status, 'active') IN ('active','current')
                        ORDER BY employee_number
            """
        )
        nums = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify({'count': len(nums), 'driver_numbers': nums})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Secondary drivers (occasional drivers, not primary Dr%)
@app.route('/api/driver-numbers/secondary', methods=['GET'])
def get_secondary_driver_numbers():
        try:
                conn = get_db_connection(); cur = conn.cursor()
                cur.execute(
                        """
                        SELECT DISTINCT employee_number
                        FROM employees
                        WHERE employee_number IS NOT NULL
                            AND TRIM(employee_number) <> ''
                            AND employee_number NOT LIKE 'Dr%'
                            AND (
                                        COALESCE(is_chauffeur, false) = true
                                 OR LOWER(COALESCE(position,'')) = 'driver'
                                 OR LOWER(COALESCE(employee_type,'')) = 'driver'
                                 OR LOWER(COALESCE(role,'')) = 'driver'
                            )
                            AND COALESCE(status, 'active') IN ('active','current')
                        ORDER BY employee_number
                        """
                )
                nums = [r[0] for r in cur.fetchall()]
                cur.close(); conn.close()
                return jsonify({'count': len(nums), 'driver_numbers': nums})
        except Exception as e:
                return jsonify({'error': str(e)}), 500

# NOTE: DB connection helper is defined once near the top of this file.

# ---------------- Posting Engine Endpoints ---------------- #
def _posting_engine_available():
    return pe_post_event is not None and pe_reverse_batch is not None

@app.route('/posting/events', methods=['POST'])
def posting_create_event():
    if not _posting_engine_available():
        return jsonify({'error':'posting_engine_unavailable'}), 503
    data = request.get_json(silent=True) or {}
    event_code = data.get('event_code')
    payload = data.get('payload')
    event_id = data.get('event_id')
    if not isinstance(event_code, str) or not isinstance(payload, dict):
        return jsonify({'error':'invalid_request','detail':'event_code (str) and payload (object) required'}), 400
    try:
        batch_id = pe_post_event(event_code, payload, event_id=event_id)
        return jsonify({'status':'posted','batch_id': batch_id})
    except PEPostingError as e:
        return jsonify({'error':'posting_error','detail': str(e)}), 400
    except Exception as e:
        logger.exception('posting_event_unhandled')
        return jsonify({'error':'internal_error','detail': str(e)}), 500

@app.route('/posting/reversals', methods=['POST'])
def posting_reverse_batch():
    if not _posting_engine_available():
        return jsonify({'error':'posting_engine_unavailable'}), 503
    data = request.get_json(silent=True) or {}
    original_batch_id = data.get('original_batch_id')
    reason = data.get('reason') or 'API reversal'
    if not isinstance(original_batch_id, int):
        return jsonify({'error':'invalid_request','detail':'original_batch_id (int) required'}), 400
    try:
        reversal_batch_id = pe_reverse_batch(original_batch_id, reason)
        return jsonify({'status':'reversed','original_batch_id': original_batch_id, 'reversal_batch_id': reversal_batch_id})
    except PEPostingError as e:
        return jsonify({'error':'posting_error','detail': str(e)}), 400
    except Exception as e:
        logger.exception('posting_reversal_unhandled')
        return jsonify({'error':'internal_error','detail': str(e)}), 500

@app.route('/posting/batches/<int:batch_id>', methods=['GET'])
def posting_get_batch(batch_id:int):
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT id,event_code,event_id,event_hash,created_at,source_payload FROM journal_batches WHERE id=%s', (batch_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close(); return jsonify({'error':'not_found'}), 404
        batch_cols = [d[0] for d in cur.description]
        batch = dict(zip(batch_cols, row))
        cur.execute('SELECT line_number,account_code,description,debit,credit,currency FROM journal_lines WHERE batch_id=%s ORDER BY line_number', (batch_id,))
        lines_rows = cur.fetchall(); line_cols = [d[0] for d in cur.description]
        lines = [dict(zip(line_cols, r)) for r in lines_rows]
        cur.close(); conn.close()
        total_debits = sum(float(l['debit']) for l in lines)
        total_credits = sum(float(l['credit']) for l in lines)
        batch['lines'] = lines
        batch['totals'] = {'debits': total_debits, 'credits': total_credits, 'balanced': round(total_debits-total_credits,2)==0}
        return jsonify(batch)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/posting/trial_balance', methods=['GET'])
def posting_trial_balance():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT account_code, SUM(debit) AS debits, SUM(credit) AS credits, SUM(debit-credit) AS net FROM journal_lines GROUP BY account_code ORDER BY account_code')
        rows = cur.fetchall(); cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close(); return jsonify({'trial_balance': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Employee Payroll
@app.route('/employee/<int:employee_id>/net_pay', methods=['GET'])
def get_employee_net_pay(employee_id):
    # Dummy implementation
    return jsonify({'employee_id': employee_id, 'net_pay': 1000})

# Trip Gratuity
@app.route('/trip/<string:run_id>/gratuity', methods=['POST'])
def calculate_trip_gratuity(run_id):
    data = request.json
    total_fare = data.get('total_fare', 0)
    charged_gratuity_percentage = data.get('charged_gratuity_percentage', 0)
    paid_gratuity_adjustments = data.get('paid_gratuity_adjustments', 0)
    # Use FinancialService for gratuity (PayrollService has no gratuity method)
    gratuity = FinancialService.calculate_gratuity(total_fare, charged_gratuity_percentage, paid_gratuity_adjustments)
    return jsonify({'run_id': run_id, 'gratuity': gratuity})

# RunCharter Management
@app.route('/run_charter/create', methods=['POST'])
def create_run_charter():
    # Dummy implementation
    # Create RunCharter, generate invoice, and post event
    data: dict = request.get_json(silent=True) or {}
    customer_id: str = str(data.get('customer_id', ''))
    driver_id: str = str(data.get('driver_id', ''))
    vehicle_id: str = str(data.get('vehicle_id', ''))
    pickup_location: str = str(data.get('pickup_location', ''))
    dropoff_location: str = str(data.get('dropoff_location', ''))
    booking_date: str = str(data.get('booking_date', ''))
    run_type: str = str(data.get('run_type', ''))
    total_cost: float = float(data.get('total_cost', 0))
    # Determine booking status based on retainer
    retainer = float(data.get('retainer', 0))
    booking_status = 'booked' if retainer > 0 else 'quote'
    run_charter = RunCharter(
        run_id=str(uuid.uuid4()),
        customer_id=customer_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        pickup_location=pickup_location,
        dropoff_location=dropoff_location,
        booking_date=booking_date,
        run_type=run_type,
        total_cost=total_cost,
        payment_status='unpaid',
        retainer=retainer
    )
    # Insert into database (use client_id column to match existing schema)
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('''
        INSERT INTO charters (client_id, driver_id, vehicle_id, pickup_location, dropoff_location, booking_date, run_type, total_amount_due, payment_status, retainer, booking_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING charter_id
    ''', (customer_id, driver_id, vehicle_id, pickup_location, dropoff_location, booking_date, run_type, total_cost, 'unpaid', retainer, booking_status))
    charter_id = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    run_charter.run_id = charter_id
    # Determine GST exemption from clients table (source of truth)
    gst_exempt = False
    try:
        conn = get_db_connection(); cur = conn.cursor()
        # Prefer direct lookup by provided id against both client_id and id
        if customer_id:
            try:
                cur.execute(
                    """
                    SELECT COALESCE(is_gst_exempt, FALSE)
                    FROM clients
                    WHERE CAST(client_id AS TEXT) = %s OR CAST(COALESCE(id, client_id) AS TEXT) = %s
                    LIMIT 1
                    """,
                    (str(customer_id), str(customer_id))
                )
                row = cur.fetchone()
                if row is not None:
                    gst_exempt = bool(row[0])
            except Exception:
                pass
        # If not found, resolve via the newly created charter record
        if not gst_exempt:
            try:
                cur.execute(
                    """
                    SELECT COALESCE(cl.is_gst_exempt, FALSE)
                    FROM charters c
                    LEFT JOIN clients cl ON c.client_id = cl.client_id
                    WHERE c.charter_id = %s
                    """,
                    (charter_id,)
                )
                row = cur.fetchone()
                if row is not None:
                    gst_exempt = bool(row[0])
            except Exception:
                pass
        cur.close(); conn.close()
    except Exception:
        try:
            cur.close(); conn.close()
        except Exception:
            pass
    # Attach gst_exempt to run_charter so FinancialService can use it
    try:
        setattr(run_charter, 'gst_exempt', bool(gst_exempt))
    except Exception:
        pass
    # Generate invoice
    invoice = FinancialService.generate_invoice(run_charter)
    # Post invoice event
    if _posting_engine_available():
        payload = {
            'invoice_id': invoice['run_id'],
            'lines': [
                # Revenue is the taxable subtotal
                {'account_code': 'REV_CHARTER', 'amount': invoice['subtotal'], 'type': 'revenue'},
                # GST calculated on subtotal only
                {'account_code': 'GST_PAYABLE', 'amount': invoice['gst'], 'type': 'tax'},
                # Gratuity added at the end, non-GST
                {'account_code': 'GRATUITY_PAYABLE', 'amount': invoice['gratuity'], 'type': 'gratuity'}
            ]
        }
        try:
            batch_id = pe_post_event('INVOICE_ISSUED', payload, event_id=invoice['run_id'])
        except Exception as e:
            logger.error('Invoice posting failed: %s', e)
            batch_id = None
    else:
        batch_id = None
    return jsonify({'status': 'created', 'run_charter': run_charter.__dict__, 'invoice': invoice, 'batch_id': batch_id})

@app.route('/run_charters', methods=['GET'])
def get_run_charters():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM charters')
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    charters = [dict(zip(columns, row)) for row in rows]
    cur.close()
    conn.close()
    return jsonify(charters)

@app.route('/run_charter/<int:run_id>', methods=['GET'])
def get_run_charter(run_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM charters WHERE charter_id=%s', (run_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close(); return jsonify({'error': 'not_found'}), 404
    columns = [desc[0] for desc in cur.description]
    charter = dict(zip(columns, row))
    cur.close(); conn.close(); return jsonify(charter)

# Vehicle Management
@app.route('/vehicles', methods=['GET'])
@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    # Check if user wants to include decommissioned vehicles
    include_decommissioned = request.args.get('include_decommissioned', 'false').lower() == 'true'
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if include_decommissioned:
        cur.execute('SELECT * FROM vehicles ORDER BY vehicle_id')
    else:
        # Only return active vehicles by default
        cur.execute("SELECT * FROM vehicles WHERE operational_status != 'decommissioned' AND is_active = TRUE ORDER BY vehicle_id")
    
    rows = cur.fetchall()
    columns = [desc[0] for desc in (cur.description or [])]
    vehicles = [dict(zip(columns, row)) for row in rows]
    cur.close()
    conn.close()
    return jsonify(vehicles)

@app.route('/vehicles', methods=['POST'])
@app.route('/api/vehicles', methods=['POST'])
def save_vehicle():
    """Minimal vehicle upsert placeholder.

    Accepts JSON and attempts best-effort insert/update into vehicles.
    If schema mismatch prevents DB write, we still return 200 and echo payload
    so the UI flow doesn't break. Logs any DB errors for follow-up.
    """
    payload = request.get_json(silent=True) or {}
    status = 'accepted'
    detail = None
    try:
        # Try dynamic column intersection insert
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='vehicles'")
        cols = [r[0] for r in cur.fetchall()]
        data = {k: v for k, v in payload.items() if k in cols}
        if data:
            columns = ','.join(data.keys())
            placeholders = ','.join(['%s']*len(data))
            values = list(data.values())
            cur.execute(f"INSERT INTO vehicles ({columns}) VALUES ({placeholders})", values)
            conn.commit()
            status = 'saved'
        cur.close(); conn.close()
    except Exception as e:
        logger.warning('save_vehicle fallback (schema mismatch?): %s', e)
        detail = str(e)
    return jsonify({'status': status, 'vehicle': payload, 'detail': detail})

@app.route('/vehicle/inspection', methods=['POST'])
def add_vehicle_inspection():
    # Dummy implementation
    return jsonify({'status': 'inspection added'})

# Bookings Management
@app.route('/bookings', methods=['GET'])
@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Query charters table with correct column names that actually exist
        cur.execute("""
        SELECT 
            c.charter_id, 
            c.charter_date, 
            c.client_id,
            c.reserve_number,
            c.passenger_load, 
            c.vehicle_booked_id, 
            c.vehicle_description, 
            c.vehicle_type_requested,
            c.driver_name,
            c.retainer, 
            c.odometer_start, 
            c.odometer_end, 
            c.fuel_added, 
            c.vehicle_notes,
            c.notes,
            c.pickup_address,
            c.dropoff_address,
            c.status,
            cl.client_name,
            v.passenger_capacity AS vehicle_capacity
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id 
    LEFT JOIN vehicles v ON CAST(c.vehicle_booked_id AS TEXT) = CAST(v.vehicle_number AS TEXT)
        ORDER BY c.charter_date DESC, c.charter_id DESC 
        LIMIT 50
        """);
        rows = cur.fetchall()
        raw_cols = [d[0] for d in (cur.description or [])]
        cols = []
        for i, name in enumerate(raw_cols):
            if not name or name.startswith('?'):
                cols.append(f'unnamed_{i}')
            else:
                cols.append(name)
        
        items = []
        for row in rows:
            rec = dict(zip(cols, row))
            # Patch: ensure all fields are non-empty strings or reasonable defaults
            def safe(val, default='(unknown)'):
                if val is None or (isinstance(val, str) and not val.strip()):
                    return default
                return str(val)
            items.append({
                'charter_id': safe(rec.get('charter_id'), ''),
                'charter_date': safe(rec.get('charter_date'), ''),
                'client_name': safe(rec.get('client_name')) if rec.get('client_name') else safe(rec.get('client_id')),
                'vehicle_type_requested': safe(rec.get('vehicle_type_requested')),
                'vehicle_booked_id': safe(rec.get('vehicle_booked_id')),
                'driver_name': safe(rec.get('driver_name')),
                'vehicle_description': safe(rec.get('vehicle_description')),
                'passenger_load': rec.get('passenger_load') if rec.get('passenger_load') is not None else 0,
                'vehicle_capacity': rec.get('vehicle_capacity') if rec.get('vehicle_capacity') is not None else 0,
                'retainer': float(rec.get('retainer', 0)) if rec.get('retainer') else 0.0,
                'odometer_start': safe(rec.get('odometer_start'), ''),
                'odometer_end': safe(rec.get('odometer_end'), ''),
                'fuel_added': safe(rec.get('fuel_added'), ''),
                'vehicle_notes': safe(rec.get('vehicle_notes')) if rec.get('vehicle_notes') else safe(rec.get('notes')),
                'itinerary_stops': 0,  # Not in charters table, will add later
                'reserve_number': safe(rec.get('reserve_number')),
                'pickup_address': safe(rec.get('pickup_address')),
                'dropoff_address': safe(rec.get('dropoff_address')),
                'status': safe(rec.get('status'), '')
            })
        
        cur.close(); conn.close()
        return jsonify({'bookings': items})
    except Exception as e:
        return jsonify({'error': str(e), 'bookings': []}), 500

@app.route('/bookings', methods=['POST'])
@app.route('/api/bookings', methods=['POST'])
def create_booking():
    """Accept booking/quote submissions.

    For now, perform a best-effort insert into 'bookings' if columns match; otherwise
    log and return success to keep UI responsive. Follow-up can wire exact schema.
    """
    payload = request.get_json(silent=True) or {}
    status = 'accepted'
    booking_id = None
    detail = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bookings'")
        cols = [r[0] for r in cur.fetchall()]
        data = {k: v for k, v in payload.items() if k in cols}
        if data:
            columns = ','.join(data.keys())
            placeholders = ','.join(['%s']*len(data))
            values = list(data.values())
            cur.execute(f"INSERT INTO bookings ({columns}) VALUES ({placeholders}) RETURNING id", values)
            booking_id_row = cur.fetchone()
            booking_id = booking_id_row[0] if booking_id_row else None
            conn.commit()
            status = 'saved'
        cur.close(); conn.close()
    except Exception as e:
        logger.warning('create_booking fallback (schema mismatch?): %s', e)
        detail = str(e)
    return jsonify({'status': status, 'id': booking_id, 'detail': detail, 'booking': payload})

@app.route('/api/bookings/<int:charter_id>', methods=['GET'])
def get_booking(charter_id: int):
    """Fetch a single charter by id from charters table with joined client/vehicle info."""
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(
            """
            SELECT 
                c.charter_id,
                c.charter_date,
                c.client_id,
                c.reserve_number,
                c.passenger_load,
                c.vehicle_booked_id,
                c.vehicle_description,
                c.vehicle_type_requested,
                c.driver_name,
                c.retainer,
                c.odometer_start,
                c.odometer_end,
                c.fuel_added,
                c.vehicle_notes,
                c.notes,
                c.pickup_address,
                c.dropoff_address,
                c.status,
                cl.client_name,
                v.passenger_capacity AS vehicle_capacity
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id 
            LEFT JOIN vehicles v ON CAST(c.vehicle_booked_id AS TEXT) = CAST(v.vehicle_number AS TEXT)
            WHERE c.charter_id = %s
            """,
            (charter_id,)
        )
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close(); return jsonify({'error': 'not_found'}), 404
        cols = [d[0] for d in (cur.description or [])]
        rec = dict(zip(cols, row))
        cur.close(); conn.close()
        return jsonify(rec)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bookings/search', methods=['GET'])
def search_bookings():
    """Search recent charters by reserve number or client name (case-insensitive)."""
    try:
        q = (request.args.get('q') or '').strip()
        limit = int(request.args.get('limit', '25') or '25')
        limit = max(1, min(limit, 200))
        if not q:
            return jsonify({'results': []})
        conn = get_db_connection(); cur = conn.cursor()
        like = f"%{q}%"
        cur.execute(
            """
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                COALESCE(cl.client_name, c.client_id::text) AS client_name
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE CAST(c.reserve_number AS TEXT) ILIKE %s
               OR COALESCE(cl.client_name, '') ILIKE %s
            ORDER BY c.charter_date DESC, c.charter_id DESC
            LIMIT %s
            """,
            (like, like, limit)
        )
        rows = cur.fetchall(); raw_cols = [d[0] for d in (cur.description or [])]
        cols = []
        for i, name in enumerate(raw_cols):
            if not name or name.startswith('?'):
                cols.append(f'unnamed_{i}')
            else:
                cols.append(name)
        results = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e), 'results': []}), 500

@app.route('/api/bookings/<int:charter_id>', methods=['PATCH'])
def update_booking(charter_id):
    """Update specific fields of a charter (for dispatch editing)"""
    try:
        payload = request.get_json(silent=True) or {}
        
        # Only allow certain fields to be updated
        allowed_fields = [
            'vehicle_booked_id',
            'vehicle_number',
            'driver_name',
            'notes'
        ]
        updates = {k: v for k, v in payload.items() if k in allowed_fields}
        
        if not updates:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build dynamic UPDATE query
        set_clauses = [f"{field} = %s" for field in updates.keys()]
        values = list(updates.values()) + [charter_id]
        
        update_query = f"""
        UPDATE charters 
        SET {', '.join(set_clauses)}
        WHERE charter_id = %s
        """
        
        cur.execute(update_query, values)
        
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({'error': 'Charter not found'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'updated': updates})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Charter Charges & Payments API ---

# Create a new charter (best-effort dynamic insert)
@app.route('/api/charters', methods=['POST'])
def create_charter():
    """Create a new charter by intersecting provided fields with charters table columns.

    Returns new charter_id when available. If schema mismatches, returns accepted with echo payload.
    """
    payload = request.get_json(silent=True) or {}
    status = 'accepted'
    new_id = None
    detail = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters'")
        cols = [r[0] for r in cur.fetchall()]
        data = {k: v for k, v in payload.items() if k in cols}
        # Normalize cash_tip_amount if provided
        if 'cash_tip_amount' in data and data['cash_tip_amount'] in ('', None):
            data['cash_tip_amount'] = 0
        # Allow secondary driver by name if id not provided
        if 'secondary_driver_name' in data and 'secondary_driver_id' not in data:
            # Attempt to resolve by name (best-effort)
            try:
                cur.execute("SELECT employee_id FROM employees WHERE LOWER(full_name)=LOWER(%s) LIMIT 1", (data['secondary_driver_name'],))
                row = cur.fetchone()
                if row:
                    data['secondary_driver_id'] = row[0]
            except Exception:
                pass
        if data:
            columns = ','.join(data.keys())
            placeholders = ','.join(['%s']*len(data))
            values = list(data.values())
            # Prefer returning charter_id if present, else RETURNING * and map
            try:
                cur.execute(f"INSERT INTO charters ({columns}) VALUES ({placeholders}) RETURNING charter_id", values)
                row = cur.fetchone(); new_id = row[0] if row else None
            except Exception:
                conn.rollback()
                cur.execute(f"INSERT INTO charters ({columns}) VALUES ({placeholders})", values)
            conn.commit(); status = 'saved'
        cur.close(); conn.close()
    except Exception as e:
        detail = str(e)
    return jsonify({'status': status, 'charter_id': new_id, 'detail': detail, 'charter': payload})

# Patch / update charter to set cash tip or secondary driver details
@app.route('/api/charters/<int:charter_id>/cash-tip', methods=['PATCH'])
def update_charter_cash_tip(charter_id: int):
    payload = request.get_json(silent=True) or {}
    tip = payload.get('cash_tip_amount')
    if tip is None:
        return jsonify({'error': 'cash_tip_amount required'}), 400
    try:
        tip_val = float(tip)
    except Exception:
        return jsonify({'error': 'cash_tip_amount must be numeric'}), 400
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("UPDATE charters SET cash_tip_amount=%s WHERE charter_id=%s", (tip_val, charter_id))
        if cur.rowcount == 0:
            conn.rollback(); cur.close(); conn.close()
            return jsonify({'error': 'Charter not found'}), 404
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success': True, 'charter_id': charter_id, 'cash_tip_amount': tip_val})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charters/<int:charter_id>/secondary-driver', methods=['PATCH'])
def update_charter_secondary_driver(charter_id: int):
    payload = request.get_json(silent=True) or {}
    sec_id = payload.get('secondary_driver_id')
    sec_name = payload.get('secondary_driver_name')
    if sec_id is None and not sec_name:
        return jsonify({'error': 'secondary_driver_id or secondary_driver_name required'}), 400
    try:
        conn = get_db_connection(); cur = conn.cursor()
        resolved_id = None
        if sec_id is not None:
            try:
                resolved_id = int(sec_id)
            except Exception:
                return jsonify({'error': 'secondary_driver_id must be int'}), 400
        elif sec_name:
            cur.execute("SELECT employee_id FROM employees WHERE LOWER(full_name)=LOWER(%s) LIMIT 1", (sec_name,))
            row = cur.fetchone()
            resolved_id = row[0] if row else None
        cur.execute("UPDATE charters SET secondary_driver_id=%s, secondary_driver_name=%s WHERE charter_id=%s", (resolved_id, sec_name, charter_id))
        if cur.rowcount == 0:
            conn.rollback(); cur.close(); conn.close()
            return jsonify({'error': 'Charter not found'}), 404
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success': True, 'charter_id': charter_id, 'secondary_driver_id': resolved_id, 'secondary_driver_name': sec_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charters/<int:charter_id>/charges', methods=['GET'])
def list_charges(charter_id: int):
    """Return all charges for a charter."""
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(
            """
            SELECT charge_id, charter_id, charge_type, amount, description, created_at
            FROM charter_charges
            WHERE charter_id = %s
            ORDER BY created_at ASC, charge_id ASC
            """,
            (charter_id,)
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        items = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify({'charges': items})
    except Exception as e:
        return jsonify({'error': str(e), 'charges': []}), 500


@app.route('/api/charters/<int:charter_id>/charges', methods=['POST'])
def create_charge(charter_id: int):
    """Create a new charge for a charter."""
    try:
        payload = request.get_json(silent=True) or {}
        charge_type = str(payload.get('charge_type') or 'extra')
        amount = payload.get('amount')
        description = payload.get('description')
        if amount is None:
            return jsonify({'error': 'amount is required'}), 400
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO charter_charges (charter_id, charge_type, amount, description)
            VALUES (%s, %s, %s, %s)
            RETURNING charge_id, charter_id, charge_type, amount, description, created_at
            """,
            (charter_id, charge_type, amount, description)
        )
        row = cur.fetchone(); conn.commit()
        cols = [d[0] for d in cur.description]
        item = dict(zip(cols, row)) if row else None
        cur.close(); conn.close()
        return jsonify({'charge': item}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/charges/<int:charge_id>', methods=['PATCH', 'DELETE'])
def mutate_charge(charge_id: int):
    """Update or delete a charge."""
    try:
        conn = get_db_connection(); cur = conn.cursor()
        if request.method == 'DELETE':
            cur.execute('DELETE FROM charter_charges WHERE charge_id = %s', (charge_id,))
            deleted = cur.rowcount
            conn.commit(); cur.close(); conn.close()
            if not deleted:
                return jsonify({'error': 'Charge not found'}), 404
            return jsonify({'deleted': True})
        # PATCH
        payload = request.get_json(silent=True) or {}
        allowed = {k: v for k, v in payload.items() if k in {'charge_type', 'amount', 'description'}}
        if not allowed:
            return jsonify({'error': 'No valid fields'}), 400
        sets = ', '.join([f"{k} = %s" for k in allowed.keys()])
        values = list(allowed.values()) + [charge_id]
        cur.execute(f'UPDATE charter_charges SET {sets} WHERE charge_id = %s RETURNING charge_id, charter_id, charge_type, amount, description, created_at', values)
        row = cur.fetchone(); conn.commit()
        if not row:
            cur.close(); conn.close()
            return jsonify({'error': 'Charge not found'}), 404
        cols = [d[0] for d in cur.description]
        item = dict(zip(cols, row))
        cur.close(); conn.close()
        return jsonify({'charge': item})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/charters/<int:charter_id>/payments', methods=['GET'])
def list_payments(charter_id: int):
    """Return all payments for a charter."""
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(
            """
            SELECT payment_id, charter_id, amount, payment_date, payment_method, payment_key, notes, created_at, last_updated
            FROM payments
            WHERE charter_id = %s
            ORDER BY payment_date DESC, payment_id DESC
            """,
            (charter_id,)
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        items = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify({'payments': items})
    except Exception as e:
        return jsonify({'error': str(e), 'payments': []}), 500


@app.route('/api/charters/<int:charter_id>/payments', methods=['POST'])
def create_payment(charter_id: int):
    """Create a new payment for a charter."""
    try:
        payload = request.get_json(silent=True) or {}
        amount = payload.get('amount')
        if amount is None:
            return jsonify({'error': 'amount is required'}), 400
        payment_date = payload.get('payment_date')  # ISO date string
        payment_method = payload.get('payment_method') or 'credit_card'
        payment_key = payload.get('payment_key')
        notes = payload.get('notes')
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO payments (charter_id, amount, payment_date, payment_method, payment_key, notes, last_updated)
            VALUES (%s, %s, COALESCE(%s, CURRENT_DATE), %s, %s, %s, NOW())
            RETURNING payment_id, charter_id, amount, payment_date, payment_method, payment_key, notes, created_at, last_updated
            """,
            (charter_id, amount, payment_date, payment_method, payment_key, notes)
        )
        row = cur.fetchone(); conn.commit()
        cols = [d[0] for d in cur.description]
        item = dict(zip(cols, row)) if row else None
        cur.close(); conn.close()
        return jsonify({'payment': item}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/payments/<int:payment_id>', methods=['PATCH', 'DELETE'])
def mutate_payment(payment_id: int):
    """Update or delete a payment."""
    try:
        conn = get_db_connection(); cur = conn.cursor()
        if request.method == 'DELETE':
            cur.execute('DELETE FROM payments WHERE payment_id = %s', (payment_id,))
            deleted = cur.rowcount
            conn.commit(); cur.close(); conn.close()
            if not deleted:
                return jsonify({'error': 'Payment not found'}), 404
            return jsonify({'deleted': True})
        # PATCH
        payload = request.get_json(silent=True) or {}
        allowed = {k: v for k, v in payload.items() if k in {'amount','payment_date','payment_method','payment_key','notes','charter_id'}}
        if not allowed:
            return jsonify({'error': 'No valid fields'}), 400
        sets = ', '.join([f"{k} = %s" for k in allowed.keys()])
        values = list(allowed.values()) + [payment_id]
        cur.execute(f'UPDATE payments SET {sets}, last_updated = NOW() WHERE payment_id = %s RETURNING payment_id, charter_id, amount, payment_date, payment_method, payment_key, notes, created_at, last_updated', values)
        row = cur.fetchone(); conn.commit()
        if not row:
            cur.close(); conn.close()
            return jsonify({'error': 'Payment not found'}), 404
        cols = [d[0] for d in cur.description]
        item = dict(zip(cols, row))
        cur.close(); conn.close()
        return jsonify({'payment': item})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/charters/<int:charter_id>/financials', methods=['GET'])
def charter_financials(charter_id: int):
    """Return financial summary for a charter: charges, payments, retainer, balance."""
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT COALESCE(SUM(amount),0) FROM charter_charges WHERE charter_id = %s', (charter_id,))
        charges_total = float(cur.fetchone()[0] or 0)
        cur.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE charter_id = %s', (charter_id,))
        payments_total = float(cur.fetchone()[0] or 0)
        cur.execute('SELECT COALESCE(retainer,0) FROM charters WHERE charter_id = %s', (charter_id,))
        retainer = float((cur.fetchone() or [0])[0] or 0)
        balance_due = round(charges_total - payments_total, 2)
        cur.close(); conn.close()
        return jsonify({
            'charter_id': charter_id,
            'charges_total': round(charges_total, 2),
            'payments_total': round(payments_total, 2),
            'retainer': round(retainer, 2),
            'balance_due': balance_due
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Customer Management
@app.route('/customers', methods=['GET'])
@app.route('/clients', methods=['GET'])
@app.route('/api/customers', methods=['GET'])
@app.route('/api/clients', methods=['GET'])
def get_customers():  # keeping function name for compatibility
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM clients')  # actual table name
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        clients = [dict(zip(columns, row)) for row in rows]
        cur.close()
        conn.close()
        return jsonify(clients)
    except Exception as e:
        # Basic error handling; in future add logging
        return jsonify({'error': str(e)}), 500

@app.route('/clients', methods=['POST'])
@app.route('/api/clients', methods=['POST'])
def create_client():
    """Create a new client (best-effort).

    Tries to insert provided fields into 'clients' table using dynamic column intersection.
    If fails, returns accepted with echo payload so UI flow isn't blocked.
    """
    payload = request.get_json(silent=True) or {}
    status = 'accepted'
    client_id = None
    detail = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='clients'")
        cols = [r[0] for r in cur.fetchall()]
        data = {k: v for k, v in payload.items() if k in cols}
        if data:
            columns = ','.join(data.keys())
            placeholders = ','.join(['%s']*len(data))
            values = list(data.values())
            cur.execute(f"INSERT INTO clients ({columns}) VALUES ({placeholders}) RETURNING id")
            row = cur.fetchone(); client_id = row[0] if row else None
            conn.commit(); status = 'saved'
        cur.close(); conn.close()
    except Exception as e:
        logger.warning('create_client fallback (schema mismatch?): %s', e)
        detail = str(e)
    return jsonify({'status': status, 'id': client_id, 'detail': detail, 'client': payload})

# Lightweight client search for autocomplete
@app.route('/clients/search', methods=['GET'])
@app.route('/api/clients/search', methods=['GET'])
def search_clients():
    """Search clients by name/id/phone/email for autocomplete.

    Query params:
    - query or q: search string
    - limit: optional, default 20, max 100
    Returns: { results: [ { client_id, client_name, phone, email } ] }
    """
    try:
        q = (request.args.get('query') or request.args.get('q') or '').strip()
        limit = int(request.args.get('limit', '20') or '20')
        limit = max(1, min(limit, 100))
        if not q:
            return jsonify({'results': []})
        like = f"%{q}%"
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute(
            """
            SELECT client_id, client_name, phone, email
            FROM clients
            WHERE COALESCE(client_name,'') ILIKE %s
               OR CAST(client_id AS TEXT) ILIKE %s
               OR COALESCE(phone,'') ILIKE %s
               OR COALESCE(email,'') ILIKE %s
            ORDER BY client_name ASC
            LIMIT %s
            """,
            (like, like, like, like, limit)
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
        results = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e), 'results': []}), 500

@app.route('/driver_hos_log', methods=['GET'])
@app.route('/api/driver_hos_log', methods=['GET'])
def driver_hos_log():
    """Return a synthetic 14-day HOS log for display/printing.

    Parameters:
    - days: number of days (default 14)
    """
    try:
        from datetime import datetime, timedelta
        days = int(request.args.get('days', '14') or '14')
        days = max(1, min(days, 31))
        today = datetime.now().date()
        entries = []
        for i in range(days):
            d = today - timedelta(days=i)
            # Simple pattern: 9h driving, 3h on-duty-not-driving, 12h off
            entry = {
                'date': d.isoformat(),
                'workshift_start': '08:00',
                'workshift_end': '20:00',
                'duty_log': [
                    {'status': 'on duty not driving', 'start': '08:00', 'end': '09:00', 'duration': '1.00'},
                    {'status': 'on duty driving', 'start': '09:00', 'end': '13:00', 'duration': '4.00'},
                    {'status': 'off duty', 'start': '13:00', 'end': '14:00', 'duration': '1.00'},
                    {'status': 'on duty driving', 'start': '14:00', 'end': '18:00', 'duration': '4.00'},
                    {'status': 'on duty not driving', 'start': '18:00', 'end': '20:00', 'duration': '2.00'}
                ],
                'total_on_duty': '13.00',
                'total_driving': '8.00',
                'total_off_duty': '11.00',
                'breaks': '1.00',
                'deferral': False,
                'deferral_hours': 0,
                'emergency': False,
                'emergency_reason': ''
            }
            entries.append(entry)
        # Maintain chronological order oldest -> newest (or newest first depending on UI)
        return jsonify(list(reversed(entries)))
    except Exception as e:
        return jsonify([]), 200

@app.route('/send_letter', methods=['POST'])
@app.route('/api/send_letter', methods=['POST'])
def send_letter():
    """Placeholder email sender for quotes/charters.

    Accepts JSON with { email, booking }. Logs payload and returns ok.
    """
    data = request.get_json(silent=True) or {}
    try:
        logger.info('send_letter request: to=%s subject=Quote/Charter', data.get('email'))
        # In production, integrate with SMTP or transactional email API.
        return jsonify({'status': 'sent'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/customer/create', methods=['POST'])
def create_customer():
    # Dummy implementation
    return jsonify({'status': 'customer created'})

# --- Payroll Compensation Endpoints ---
@app.route('/compensation/<int:employee_id>/<int:year>', methods=['GET'])
def get_employee_annual_compensation(employee_id:int, year:int):
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT * FROM employee_annual_compensation WHERE employee_id=%s AND year=%s', (employee_id, year))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close(); return jsonify({'error':'not_found'}), 404
        if not cur.description:
            cur.close(); conn.close(); return jsonify({'error':'no_columns'}), 500
        columns = [desc[0] for desc in cur.description]  # type: ignore
        data = dict(zip(columns, row))  # type: ignore
        cur.close(); conn.close(); return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/compensation/monthly/<int:employee_id>/<int:year>/<int:month>', methods=['GET'])
def get_employee_monthly_compensation(employee_id:int, year:int, month:int):
    try:
        if month < 1 or month > 12:
            return jsonify({'error':'invalid_month'}), 400
        conn = get_db_connection(); cur = conn.cursor()
        # Prefer effective view (zeros WCB for exempt employees); fall back to base table if view missing
        try:
            cur.execute('SELECT * FROM employee_monthly_compensation_effective WHERE employee_id=%s AND year=%s AND month=%s', (employee_id, year, month))
        except Exception:
            cur.execute('SELECT * FROM employee_monthly_compensation WHERE employee_id=%s AND year=%s AND month=%s', (employee_id, year, month))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close(); return jsonify({'error':'not_found'}), 404
        if not cur.description:
            cur.close(); conn.close(); return jsonify({'error':'no_columns'}), 500
        columns = [desc[0] for desc in cur.description]  # type: ignore
        data = dict(zip(columns, row))  # type: ignore
        cur.close(); conn.close(); return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Payslip Generation (Monthly) ---
@app.route('/payslip/<int:employee_id>/<int:year>/<int:month>', methods=['GET'])
def get_employee_payslip(employee_id:int, year:int, month:int):
    """Return a structured monthly payslip (Alberta CA style) for an employee.

    Includes required items:
    - Employer name & address (from env COMPANY_NAME / COMPANY_ADDRESS)
    - Employee identifier & name (best-effort)
    - Pay period (calendar month) and payment date (assumed last day of month)
    - Hours (regular, overtime, stat) and earnings components
    - Deductions (CPP/CPP2, EI, Federal/Prov tax, other)
    - Employer contributions (CPP/EI/WCB)
    - Vacation earned / paid
    - Advances issued / recovered
    - Net pay & YTD summaries
    """
    try:
        if month < 1 or month > 12:
            return jsonify({'error': 'invalid_month'}), 400
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('SELECT * FROM employee_monthly_compensation WHERE employee_id=%s AND year=%s AND month=%s', (employee_id, year, month))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close(); return jsonify({'error': 'not_found'}), 404
        cols = [cast(str, d[0]) for d in (cur.description or [])]  # type: ignore
        comp: Dict[str, Any] = dict(zip(cols, row))  # type: ignore[arg-type]
        emp: Dict[str, Any] = {'employee_id': employee_id}
        # Attempt to enrich employee info
        try:
            cur.execute('SELECT * FROM employees WHERE id=%s', (employee_id,))
            er = cur.fetchone()
            if er and cur.description:
                ecols = [cast(str, d[0]) for d in cur.description]  # type: ignore
                ed: Dict[str, Any] = dict(zip(ecols, er))  # type: ignore[arg-type]
                first = ed.get('first_name') or ed.get('firstname') or ed.get('given_name')
                last = ed.get('last_name') or ed.get('lastname') or ed.get('family_name')
                if first or last:
                    emp['name'] = ' '.join(p for p in [first, last] if p)
                pos = ed.get('position') or ed.get('role') or ed.get('employee_type')
                if pos:
                    emp['position'] = pos
        except Exception:
            pass
        def nz(v: Any) -> float:
            try:
                return float(v if v not in (None, '') else 0)
            except Exception:
                return 0.0
        def add_items(defs: List[tuple[str,str,str|None]], target: List[Dict[str,Any]]):
            for label, key, hours_key in defs:
                amt = comp.get(key)
                if amt is None or nz(amt) == 0:
                    continue
                item: Dict[str, Any] = {'label': label, 'amount': nz(amt)}
                if hours_key:
                    hrs = comp.get(hours_key)
                    if hrs is not None and nz(hrs) != 0:
                        item['hours'] = nz(hrs)
                target.append(item)
        earnings: List[Dict[str, Any]] = []
        deductions: List[Dict[str, Any]] = []
        employer_contribs: List[Dict[str, Any]] = []
        allowances: List[Dict[str, Any]] = []
        add_items([
            ('Regular Wages','regular_wages','regular_hours'),
            ('Overtime Wages','overtime_wages','overtime_hours'),
            ('Stat Holiday Wages','stat_holiday_wages','stat_holiday_hours'),
            ('Vacation Payout','vacation_payout_amount',None),
            ('Vacation Accrued','vacation_accrued_amount',None),
            ('Shift Premiums','shift_premiums_amount',None),
            ('Bonus','bonus_amount',None),
            ('Commission','commission_amount',None),
            ('Controlled Tips','gratuities_received_controlled',None),
            ('Direct Tips (Non-source)','gratuities_received_direct',None),
            ('Taxable Benefits','taxable_benefits_amount',None)
        ], earnings)
        for label, key in [
            ('CPP','employee_cpp_deduction'),('CPP2','employee_cpp2_deduction'),('EI','employee_ei_deduction'),
            ('Federal Tax','income_tax_withheld_federal'),('Alberta Tax','income_tax_withheld_alberta'),
            ('Union Dues','union_dues'),('RRSP','rrsp_deduction'),('Other Deductions','other_deductions')]:
            amt = comp.get(key)
            if amt is not None and nz(amt) != 0:
                deductions.append({'label': label, 'amount': nz(amt)})
        # Prefer the effective WCB premium column if available from the view
        wcb_keys = ['employer_wcb_premium_effective', 'employer_wcb_premium']
        for label, key in [
            ('Employer CPP','employer_cpp_contribution'),('Employer EI','employer_ei_contribution'),
            ('WCB Premium', next((k for k in wcb_keys if k in comp), 'employer_wcb_premium')),
            ('Other Employer Benefits','employer_other_benefits')]:
            amt = comp.get(key)
            if amt is not None and nz(amt) != 0:
                employer_contribs.append({'label': label, 'amount': nz(amt)})
        for label, key in [
            ('Auto Allowance (Non-taxable)','auto_allowance_non_taxable'),('Auto Allowance (Taxable)','auto_allowance_taxable'),
            ('Meal Allowance (Non-taxable)','meal_allowance_non_taxable'),('Expense Reimbursements','expense_reimbursements'),
            ('Cash Advances Issued','cash_advances_issued'),('Cash Advances Recovered','cash_advances_recovered')]:
            amt = comp.get(key)
            if amt is not None and nz(amt) != 0:
                allowances.append({'label': label, 'amount': nz(amt)})
        gross_pay = nz(comp.get('gross_pay'))
        net_pay = nz(comp.get('net_pay'))
        ytd_keys = ['ytd_gross_pay','ytd_cpp','ytd_cpp2','ytd_ei','ytd_tax_federal','ytd_tax_alberta','ytd_insurable_hours','ytd_pensionable_earnings']
        ytd = {k: nz(comp.get(k)) for k in ytd_keys}
        employer = {'name': os.environ.get('COMPANY_NAME','(Set COMPANY_NAME)'), 'address': os.environ.get('COMPANY_ADDRESS','(Set COMPANY_ADDRESS)')}
        from calendar import monthrange
        pay_date = f"{year}-{month:02d}-{monthrange(year, month)[1]:02d}"
        lines = [
            f"Employer: {employer['name']}",
            f"Employee: {emp.get('name','ID '+str(employee_id))}",
            f"Period: {year}-{month:02d}",
            f"Pay Date: {pay_date}",
            '--- Earnings ---'
        ]
        for e in earnings:
            hrs = f" ({e['hours']}h)" if 'hours' in e else ''
            lines.append(f"{e['label']}: {e['amount']:.2f}{hrs}")
        lines.append('--- Deductions ---')
        for d in deductions:
            lines.append(f"{d['label']}: -{d['amount']:.2f}")
        lines.append('--- Employer Contributions (Not in Net) ---')
        for ec in employer_contribs:
            lines.append(f"{ec['label']}: {ec['amount']:.2f}")
        if allowances:
            lines.append('--- Allowances / Reimbursements / Advances ---')
            for a in allowances:
                lines.append(f"{a['label']}: {a['amount']:.2f}")
        lines.append(f"Gross Pay: {gross_pay:.2f}")
        lines.append(f"Net Pay: {net_pay:.2f}")
        lines.append('--- YTD ---')
        for k, v in ytd.items():
            lines.append(f"{k}: {v:.2f}")
        lines.append('--- Disclaimer: For internal use; verify statutory calculations before issuing T4/T4A.')
        rendered_text = '\n'.join(lines)
        payload: Dict[str, Any] = {
            'payslip': {
                'employer': employer,
                'employee': emp,
                'period': {'year': year, 'month': month, 'pay_date': pay_date},
                'earnings': earnings,
                'deductions': deductions,
                'employer_contributions': employer_contribs,
                'other_items': allowances,
                'totals': {'gross_pay': gross_pay, 'net_pay': net_pay},
                'ytd': ytd,
                'metadata': {'finalized': bool(comp.get('finalized')), 'generated_at': int(time.time())},
                'rendered_text': rendered_text
            }
        }
        cur.close(); conn.close(); return jsonify(payload)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Serve specific dashboard route
@app.route('/dashboard')
def serve_dashboard():
    static_folder = app.static_folder or ''
    print(f'[DEBUG] Dashboard route hit, serving index.html from {static_folder}')
    try:
        return send_from_directory(static_folder, 'index.html')
    except Exception as e:
        print(f'[DEBUG] Dashboard error: {e}')
        return jsonify({'error': 'Dashboard error', 'detail': str(e)}), 500

# Serve specific dispatch route
@app.route('/dispatch')
def serve_dispatch():
    static_folder = app.static_folder or ''
    print(f'[DEBUG] Dispatch route hit, serving index.html from {static_folder}')
    try:
        return send_from_directory(static_folder, 'index.html')
    except Exception as e:
        print(f'[DEBUG] Dispatch error: {e}')
        return jsonify({'error': 'Dispatch error', 'detail': str(e)}), 500

# Serve other Vue routes
@app.route('/accounting')
@app.route('/reports')
@app.route('/documents')
@app.route('/owe-david')
@app.route('/admin')
@app.route('/drivers')
@app.route('/driver-hos')
@app.route('/charter')
@app.route('/vehicles')
@app.route('/employees')
@app.route('/customers')
def serve_vue_routes():
    static_folder = app.static_folder or ''
    print(f'[DEBUG] Vue route hit, serving index.html from {static_folder}')
    try:
        return send_from_directory(static_folder, 'index.html')
    except Exception as e:
        print(f'[DEBUG] Vue route error: {e}')
        return jsonify({'error': 'Route error', 'detail': str(e)}), 500

@app.route('/api/reserve-numbers', methods=['GET'])
def get_reserve_numbers():
    """
    Get all unique reserve numbers for dropdown selection
    """
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT reserve_number 
            FROM charters 
            WHERE reserve_number IS NOT NULL 
            AND reserve_number != ''
            ORDER BY reserve_number DESC
            LIMIT 1000
        """)
        reserve_numbers = [row[0] for row in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify(reserve_numbers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# DEFERRED WAGE & OWNER EQUITY API ENDPOINTS
# =============================================================================
# Integrated deferred wage management system for cash flow optimization
# Features: Michael Richard deferred wages, Paul's CIBC business card tracking,
# wage allocation pools, T4 compliance corrections (2013 owner salary issue)

@app.route('/api/deferred-wages/accounts', methods=['GET'])
def get_deferred_accounts():
    """Get all deferred wage accounts with calculated balances"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                dwa.account_id,
                dwa.employee_id,
                e.full_name as employee_name,
                dwa.account_name,
                dwa.account_type,
                dwa.account_status,
                dwa.current_balance,
                dwa.accumulated_interest,
                dwa.max_deferred_amount,
                dwa.interest_rate,
                dwa.minimum_payment_frequency,
                dwa.auto_payment_enabled,
                dwa.auto_payment_amount,
                dwa.created_at,
                dwa.updated_at
            FROM deferred_wage_accounts dwa
            JOIN employees e ON dwa.employee_id = e.employee_id
            WHERE dwa.account_status != 'deleted'
            ORDER BY dwa.current_balance DESC, dwa.account_name
        """)
        
        accounts = []
        current_year = 2025  # Current year for YTD calculations
        
        for row in cur.fetchall():
            account_id = row[0]
            
            # Calculate YTD deferred amount
            cur.execute("""
                SELECT COALESCE(SUM(deferred_amount), 0) 
                FROM deferred_wage_transactions 
                WHERE account_id = %s 
                AND transaction_type = 'deferral'
                AND EXTRACT(YEAR FROM transaction_date) = %s
            """, (account_id, current_year))
            ytd_deferred = cur.fetchone()[0] or 0
            
            # Calculate YTD paid amount
            cur.execute("""
                SELECT COALESCE(SUM(paid_amount), 0) 
                FROM deferred_wage_transactions 
                WHERE account_id = %s 
                AND transaction_type = 'payment'
                AND EXTRACT(YEAR FROM transaction_date) = %s
            """, (account_id, current_year))
            ytd_paid = cur.fetchone()[0] or 0
            
            # Calculate lifetime deferred
            cur.execute("""
                SELECT COALESCE(SUM(deferred_amount), 0) 
                FROM deferred_wage_transactions 
                WHERE account_id = %s 
                AND transaction_type = 'deferral'
            """, (account_id,))
            lifetime_deferred = cur.fetchone()[0] or 0
            
            account = {
                'account_id': row[0],
                'employee_id': row[1],
                'employee_name': row[2],
                'account_name': row[3],
                'account_type': row[4],
                'account_status': row[5],
                'current_balance': float(row[6]),
                'ytd_deferred_amount': float(ytd_deferred),
                'ytd_paid_amount': float(ytd_paid),
                'lifetime_deferred': float(lifetime_deferred),
                'accumulated_interest': float(row[7]),
                'max_deferred_amount': float(row[8]) if row[8] else None,
                'interest_rate': float(row[9]),
                'minimum_payment_frequency': row[10],
                'auto_payment_enabled': row[11],
                'auto_payment_amount': float(row[12]) if row[12] else None,
                'created_at': row[13].isoformat() if row[13] else None,
                'updated_at': row[14].isoformat() if row[14] else None
            }
            accounts.append(account)
        
        cur.close()
        conn.close()
        return jsonify(accounts)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deferred-wages/accounts', methods=['POST'])
def create_deferred_account():
    """Create a new deferred wage account"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify employee exists
        cur.execute("SELECT employee_id FROM employees WHERE employee_id = %s", (data['employee_id'],))
        if not cur.fetchone():
            return jsonify({'error': 'Employee not found'}), 404
        
        # Check if employee already has an active deferred account
        cur.execute("""
            SELECT account_id FROM deferred_wage_accounts 
            WHERE employee_id = %s AND account_status = 'active'
        """, (data['employee_id'],))
        if cur.fetchone():
            return jsonify({'error': 'Employee already has an active deferred wage account'}), 400
        
        # Create the account
        cur.execute("""
            INSERT INTO deferred_wage_accounts (
                employee_id, account_name, account_type, max_deferred_amount,
                interest_rate, minimum_payment_frequency, auto_payment_enabled,
                auto_payment_amount, current_balance, account_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING account_id
        """, (
            data['employee_id'],
            data['account_name'],
            data.get('account_type', 'employee_deferred'),
            data.get('max_deferred_amount'),
            data.get('interest_rate', 0),
            data.get('minimum_payment_frequency', 'monthly'),
            data.get('auto_payment_enabled', False),
            data.get('auto_payment_amount'),
            0.00,  # Starting balance
            'active'
        ))
        
        account_id = cur.fetchone()[0]
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'account_id': account_id, 'message': 'Deferred wage account created successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deferred-wages/owner-transactions', methods=['GET'])
def get_owner_transactions():
    """Get recent owner expense transactions (Paul's CIBC business card)"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                oet.transaction_id,
                oet.equity_account_id,
                oet.transaction_date,
                oet.transaction_type,
                oet.gross_amount,
                oet.business_portion,
                oet.personal_portion,
                oet.description,
                oet.vendor_name,
                oet.expense_category,
                oet.card_used,
                oet.receipt_reference,
                oet.approved_by,
                oet.approved_at,
                oet.created_at
            FROM owner_expense_transactions oet
            ORDER BY oet.transaction_date DESC, oet.created_at DESC
            LIMIT %s
        """, (limit,))
        
        transactions = []
        for row in cur.fetchall():
            transaction = {
                'transaction_id': row[0],
                'account_id': row[1],
                'transaction_date': row[2].isoformat() if row[2] else None,
                'transaction_type': row[3],
                'gross_amount': float(row[4]),
                'business_portion': float(row[5]),
                'personal_portion': float(row[6]),
                'description': row[7],
                'vendor_name': row[8],
                'expense_category': row[9],
                'card_used': row[10],
                'receipt_reference': row[11],
                'approved_by': row[12],
                'approved_at': row[13].isoformat() if row[13] else None,
                'created_at': row[14].isoformat() if row[14] else None
            }
            transactions.append(transaction)
        
        cur.close()
        conn.close()
        return jsonify(transactions)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deferred-wages/owner-expenses', methods=['POST'])
def create_owner_expense():
    """Record a new owner expense (Paul's CIBC business card transaction)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get Paul Heffner's owner equity account (business expenses type)
        cur.execute("""
            SELECT equity_account_id FROM owner_equity_accounts 
            WHERE LOWER(owner_name) LIKE '%paul%heffner%' 
            AND account_type = 'business_expenses'
            AND account_status = 'active'
            LIMIT 1
        """)
        account_result = cur.fetchone()
        if not account_result:
            return jsonify({'error': 'Paul Heffner business expense account not found'}), 404
        
        equity_account_id = account_result[0]
        
        # Determine transaction type based on business/personal split
        business_portion = float(data.get('business_portion', 0))
        personal_portion = float(data.get('personal_portion', 0))
        
        if business_portion > 0 and personal_portion == 0:
            transaction_type = "business_expense"
        elif personal_portion > 0 and business_portion == 0:
            transaction_type = "personal_allocation"
        else:
            transaction_type = "mixed_expense"
        
        # Create the owner expense transaction
        cur.execute("""
            INSERT INTO owner_expense_transactions (
                equity_account_id, transaction_date, transaction_type, gross_amount,
                business_portion, personal_portion, description, vendor_name,
                expense_category, card_used, receipt_reference
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING transaction_id
        """, (
            equity_account_id,
            data['transaction_date'],
            transaction_type,
            data['gross_amount'],
            business_portion,
            personal_portion,
            data['description'],
            data.get('vendor_name'),
            data.get('expense_category', 'fuel'),
            data.get('card_used'),
            data.get('receipt_reference')
        ))
        
        transaction_id = cur.fetchone()[0]
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'transaction_id': transaction_id, 
            'message': 'Owner expense recorded successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deferred-wages/allocation-pools', methods=['GET'])
def get_allocation_pools():
    """Get all wage allocation pools"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                wap.pool_id,
                wap.pool_name,
                wap.pool_type,
                wap.pool_status,
                wap.total_available,
                wap.allocated_amount,
                wap.remaining_balance,
                wap.allocation_period_start,
                wap.allocation_period_end,
                wap.allocation_frequency,
                wap.created_at
            FROM wage_allocation_pool wap
            ORDER BY wap.pool_status, wap.created_at DESC
        """)
        
        pools = []
        for row in cur.fetchall():
            pool_id = row[0]
            
            # Count employees and allocations
            cur.execute("""
                SELECT COUNT(DISTINCT employee_id) 
                FROM wage_allocation_decisions 
                WHERE pool_id = %s
            """, (pool_id,))
            employees_allocated = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM wage_allocation_decisions 
                WHERE pool_id = %s
            """, (pool_id,))
            total_allocations = cur.fetchone()[0] or 0
            
            pool = {
                'pool_id': row[0],
                'pool_name': row[1],
                'pool_type': row[2],
                'pool_status': row[3],
                'total_available': float(row[4]),
                'allocated_amount': float(row[5]),
                'remaining_balance': float(row[6]),
                'allocation_period_start': row[7].isoformat() if row[7] else None,
                'allocation_period_end': row[8].isoformat() if row[8] else None,
                'allocation_frequency': row[9],
                'created_at': row[10].isoformat() if row[10] else None,
                'employees_allocated': employees_allocated,
                'total_allocations': total_allocations
            }
            pools.append(pool)
        
        cur.close()
        conn.close()
        return jsonify(pools)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deferred-wages/t4-corrections', methods=['GET'])
def get_t4_corrections():
    """Get all T4 corrections including Paul's 2013 correction"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                t4c.correction_id,
                t4c.employee_id,
                e.full_name as employee_name,
                t4c.tax_year,
                t4c.correction_type,
                t4c.correction_status,
                t4c.original_employment_income,
                t4c.original_cpp_contributions,
                t4c.original_ei_contributions,
                t4c.original_income_tax,
                t4c.corrected_employment_income,
                t4c.corrected_cpp_contributions,
                t4c.corrected_ei_contributions,
                t4c.corrected_income_tax,
                t4c.correction_reason,
                t4c.filed_date,
                t4c.created_at
            FROM t4_compliance_corrections t4c
            JOIN employees e ON t4c.employee_id = e.employee_id
            ORDER BY t4c.tax_year DESC, t4c.correction_status, t4c.created_at DESC
        """)
        
        corrections = []
        for row in cur.fetchall():
            correction = {
                'correction_id': row[0],
                'employee_id': row[1],
                'employee_name': row[2],
                'tax_year': row[3],
                'correction_type': row[4],
                'correction_status': row[5],
                'original_employment_income': float(row[6]) if row[6] else None,
                'original_cpp_contributions': float(row[7]) if row[7] else None,
                'original_ei_contributions': float(row[8]) if row[8] else None,
                'original_income_tax': float(row[9]) if row[9] else None,
                'corrected_employment_income': float(row[10]) if row[10] else None,
                'corrected_cpp_contributions': float(row[11]) if row[11] else None,
                'corrected_ei_contributions': float(row[12]) if row[12] else None,
                'corrected_income_tax': float(row[13]) if row[13] else None,
                'correction_reason': row[14],
                'filed_date': row[15].isoformat() if row[15] else None,
                'created_at': row[16].isoformat() if row[16] else None
            }
            corrections.append(correction)
        
        cur.close()
        conn.close()
        return jsonify(corrections)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deferred-wages/metrics', methods=['GET'])
def get_deferred_wage_metrics():
    """Get key financial metrics for the dashboard"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Total deferred balance across all accounts
        cur.execute("""
            SELECT COALESCE(SUM(current_balance), 0) 
            FROM deferred_wage_accounts 
            WHERE account_status = 'active'
        """)
        total_deferred_balance = cur.fetchone()[0] or 0
        
        # Owner equity balance (Paul's account)
        cur.execute("""
            SELECT COALESCE(SUM(current_balance), 0)
            FROM owner_equity_accounts 
            WHERE account_status = 'active'
        """)
        owner_equity_balance = cur.fetchone()[0] or 0
        
        # Available allocation funds
        cur.execute("""
            SELECT COALESCE(SUM(remaining_balance), 0) 
            FROM wage_allocation_pool 
            WHERE pool_status = 'active'
        """)
        available_allocation_funds = cur.fetchone()[0] or 0
        
        # Owner business expenses (YTD)
        current_year = 2025
        cur.execute("""
            SELECT COALESCE(SUM(business_portion), 0)
            FROM owner_expense_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
        """, (current_year,))
        owner_business_expenses = cur.fetchone()[0] or 0
        
        # Owner personal allocation (YTD)
        cur.execute("""
            SELECT COALESCE(SUM(personal_portion), 0)
            FROM owner_expense_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
        """, (current_year,))
        owner_personal_allocation = cur.fetchone()[0] or 0
        
        # Owner salary equivalent calculation (rough estimate)
        owner_salary_equivalent = float(owner_personal_allocation) + (float(owner_business_expenses) * 0.3)
        
        cur.close()
        conn.close()
        
        return jsonify({
            'total_deferred_balance': float(total_deferred_balance),
            'owner_equity_balance': float(owner_equity_balance),
            'available_allocation_funds': float(available_allocation_funds),
            'owner_business_expenses': float(owner_business_expenses),
            'owner_personal_allocation': float(owner_personal_allocation),
            'owner_salary_equivalent': owner_salary_equivalent
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Special endpoints for key business users
@app.route('/api/deferred-wages/michael-richard-account', methods=['GET'])
def get_michael_richard_account():
    """Get Michael Richard's deferred wage account (biggest deferred wage user)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Find Michael Richard's account
        cur.execute("""
            SELECT dwa.account_id, e.full_name, dwa.current_balance
            FROM deferred_wage_accounts dwa
            JOIN employees e ON dwa.employee_id = e.employee_id
            WHERE LOWER(e.full_name) LIKE '%michael%richard%'
            AND dwa.account_status = 'active'
            LIMIT 1
        """)
        result = cur.fetchone()
        
        if not result:
            return jsonify({'found': False, 'message': 'Michael Richard deferred wage account not found'})
        
        account_id, employee_name, current_balance = result
        
        cur.close()
        conn.close()
        
        return jsonify({
            'found': True, 
            'account_id': account_id,
            'employee_name': employee_name,
            'current_balance': float(current_balance),
            'message': 'Michael Richard account located - primary deferred wage user'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deferred-wages/paul-2013-t4-correction', methods=['GET'])
def get_paul_2013_t4_correction():
    """Get Paul Heffner's 2013 T4 correction (owner should not have received T4)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Find Paul's 2013 T4 correction
        cur.execute("""
            SELECT t4c.correction_id, e.full_name, t4c.correction_status
            FROM t4_compliance_corrections t4c
            JOIN employees e ON t4c.employee_id = e.employee_id
            WHERE LOWER(e.full_name) LIKE '%paul%heffner%'
            AND t4c.tax_year = 2013
            LIMIT 1
        """)
        result = cur.fetchone()
        
        if not result:
            return jsonify({'found': False, 'message': 'Paul Heffner 2013 T4 correction not found'})
        
        correction_id, employee_name, correction_status = result
        
        cur.close()
        conn.close()
        
        return jsonify({
            'found': True, 
            'correction_id': correction_id,
            'employee_name': employee_name,
            'tax_year': 2013,
            'correction_status': correction_status,
            'issue': 'Owner received T4 but operates on salary equity system',
            'message': 'Paul 2013 T4 correction located - requires CRA filing'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Serve Vue app for all non-API, non-static routes (must be last)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_vue_app(path: str = ''):
    print(f'[DEBUG] Static file request: path="{path}", static_folder="{app.static_folder}"')
    # Skip API routes
    if path.startswith('api/'):
        print('[DEBUG] API route, returning 404')
        return jsonify({'error': 'Not found'}), 404
    # Check for static assets (css, js, images, etc.)
    static_folder = app.static_folder or ''
    from pathlib import Path
    # If path has an extension, it's likely a static asset
    if path and '.' in path:
        full_path = Path(static_folder) / path
        print(f'[DEBUG] Checking static asset: {full_path}, exists: {full_path.exists()}')
        if full_path.exists() and not full_path.is_dir():
            try:
                print(f'[DEBUG] Serving static asset: {path}')
                return send_from_directory(static_folder, path)
            except Exception as e:
                print(f'[DEBUG] Static file error: {e}')
                return jsonify({'error': 'Static file error', 'detail': str(e)}), 500
    # For all other routes (Vue router), serve index.html
    try:
        index_path = Path(static_folder) / 'index.html'
        print(f'[DEBUG] Serving index.html for Vue router: {path}, index exists: {index_path.exists()}')
        return send_from_directory(static_folder, 'index.html')
    except Exception as e:
        print(f'[DEBUG] Index.html error: {e}')
        return jsonify({'error': 'Index.html error', 'detail': str(e), 'static_folder': static_folder}), 500

# Initialize Float Management API
try:
    from api_float_management import init_float_api
    init_float_api(app, get_db_connection)
    print("✅ Float Management API initialized")
except Exception as e:
    print(f"❌ Failed to initialize Float Management API: {e}")

if __name__ == '__main__':
    host = os.environ.get('API_HOST', '127.0.0.1')
    port = int(os.environ.get('API_PORT', '5000'))
    debug = os.environ.get('API_DEBUG', 'false').lower() == 'true'
    logger.info('starting server host=%s port=%s debug=%s', host, port, debug)
    app.run(host=host, port=port, debug=debug)
