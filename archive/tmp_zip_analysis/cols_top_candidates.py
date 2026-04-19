import psycopg2
DB=dict(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
tables=['unified_general_ledger','banking_transactions','vendor_invoices','receipts','general_ledger']
conn=psycopg2.connect(**DB)
cur=conn.cursor()
for t in tables:
    cur.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",(t,))
    cols=cur.fetchall()
    amounts=[c for c,d in cols if any(k in c.lower() for k in ['amount','total','debit','credit','paid','balance'])]
    descs=[c for c,d in cols if any(k in c.lower() for k in ['desc','memo','note','details'])]
    refs=[c for c,d in cols if any(k in c.lower() for k in ['ref','reference','txn','transaction_id','sequence','bank_id'])]
    dates=[c for c,d in cols if d in ('date','timestamp without time zone','timestamp with time zone') or 'date' in c.lower()]
    print(f"table={t} date_cols={dates[:8]} amount_cols={amounts[:12]} desc_cols={descs[:8]} ref_cols={refs[:12]}")
cur.close(); conn.close()
