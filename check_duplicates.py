import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)

cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
all_tables = sorted([r[0] for r in cur.fetchall()])

new_tables = [
    'vehicle_capacity_tiers',
    'charters_routing_times',
    'hos_log',
    'hos_14day_summary',
    'charter_receipts',
    'charter_beverage_orders',
    'charter_beverage_items',
    'charter_driver_pay',
    'dispatch_events',
    'driver_comms_log',
    'charter_incidents',
    'customer_comms_log',
    'customer_feedback',
    'invoices',
    'invoice_line_items'
]

existing_set = set(all_tables)
new_set = set(new_tables)
duplicates = new_set & existing_set

print(f'Total existing tables in almsdata: {len(all_tables)}')
print(f'Total new tables created: {len(new_tables)}')
print()

if duplicates:
    print(f'⚠️  DUPLICATES FOUND ({len(duplicates)}):')
    for t in sorted(duplicates):
        print(f'  - {t}')
else:
    print('✅ NO DUPLICATES - all new tables are unique')

# Also check for similar-named tables that might serve same purpose
similar_patterns = {
    'payment': ['payments', 'invoice_line_items', 'charter_driver_pay'],
    'receipt': ['receipts', 'charter_receipts'],
    'dispatch': ['dispatches', 'dispatch_events'],
    'hos': ['hos_log', 'hos_14day_summary'],
    'driver': ['driver_comms_log', 'charter_driver_pay'],
}

print()
print('Checking for overlapping functionality...')
for pattern, tables_to_check in similar_patterns.items():
    matching = [t for t in tables_to_check if t in existing_set]
    if len(matching) > 1:
        print(f'  ⚠️  "{pattern}" pattern: {matching}')

cur.close()
conn.close()
