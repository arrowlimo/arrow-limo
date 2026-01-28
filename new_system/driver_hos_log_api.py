from flask import request, jsonify
from datetime import datetime, timedelta
import psycopg2
import os
import json

def get_db_connection():
    return psycopg2.connect(
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
        host=os.environ.get('DB_HOST', 'localhost')
    )

# API endpoint: /driver_hos_log?driver_name=...&days=14
@app.route('/driver_hos_log')
def driver_hos_log():
    driver_name = request.args.get('driver_name')
    days = int(request.args.get('days', 14))
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days-1)
    conn = get_db_connection(); cur = conn.cursor()
    query = '''
        SELECT workshift_start, workshift_end, duty_log, created_at::date
        FROM bookings
        WHERE driver_name = %s AND created_at::date BETWEEN %s AND %s
        ORDER BY created_at DESC
    '''
    cur.execute(query, (driver_name, start_date, end_date))
    rows = cur.fetchall()
    hos_log = []
    for workshift_start, workshift_end, duty_log, date in rows:
        try:
            duty_log_data = json.loads(duty_log) if duty_log else []
        except Exception:
            duty_log_data = []
        # Calculate totals
        total_on_duty = sum(
            (datetime.strptime(d['end'], '%H:%M') - datetime.strptime(d['start'], '%H:%M')).seconds/3600
            for d in duty_log_data if d['status'] in ['on duty not driving', 'on duty driving']
        )
        total_driving = sum(
            (datetime.strptime(d['end'], '%H:%M') - datetime.strptime(d['start'], '%H:%M')).seconds/3600
            for d in duty_log_data if d['status'] == 'on duty driving'
        )
        total_off_duty = sum(
            (datetime.strptime(d['end'], '%H:%M') - datetime.strptime(d['start'], '%H:%M')).seconds/3600
            for d in duty_log_data if d['status'] == 'off duty'
        )
        breaks = sum(
            (datetime.strptime(d['end'], '%H:%M') - datetime.strptime(d['start'], '%H:%M')).seconds/3600
            for d in duty_log_data if d['status'] == 'off duty' and d.get('is_break')
        )
        hos_log.append({
            'date': str(date),
            'workshift_start': workshift_start,
            'workshift_end': workshift_end,
            'duty_log': duty_log_data,
            'total_on_duty': round(total_on_duty, 2),
            'total_driving': round(total_driving, 2),
            'total_off_duty': round(total_off_duty, 2),
            'breaks': round(breaks, 2)
        })
    cur.close(); conn.close()
    return jsonify(hos_log)
