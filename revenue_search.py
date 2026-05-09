import psycopg2
try:
    conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
    cur = conn.cursor()
    
    print("REVENUE SEARCH IN chart_of_accounts:")
    # Searching for charter, trade, promo, or Revenue account types
    cur.execute("""
        SELECT account_code, account_name, account_type, description 
        FROM chart_of_accounts 
        WHERE (account_name ILIKE '%charter%' 
           OR account_name ILIKE '%trade%' 
           OR account_name ILIKE '%promo%'
           OR account_name ILIKE '%revenue%'
           OR account_type ILIKE '%Revenue%')
           AND is_active = True
        ORDER BY account_code
    """)
    rows = cur.fetchall()
    for r in rows:
        print(r)
        
    print("\nUNIQUE CATEGORIES IN income_ledger:")
    cur.execute("SELECT DISTINCT revenue_category, revenue_subcategory FROM income_ledger")
    cats = cur.fetchall()
    for c in cats:
        print(c)
        
    conn.close()
except Exception as e:
    print(f'ERR {e}')
