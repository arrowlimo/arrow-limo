import psycopg2, psycopg2.extras

PG = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
pg = psycopg2.connect(PG)
cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# 1. 009583 Papp: insert missing +$1700 that was reversed in LMS
#    LMS key 0009820, 2014-06-03.  Without this, ALMS net = -$1700 (wrong).
cur.execute("""
    INSERT INTO charter_payments
        (charter_id, amount, payment_date, payment_method, payment_key, source, client_name)
    VALUES ('009583', 1700.00, '2014-06-03', 'unknown', '0009820',
            'lms_negative_import', 'Papp, Kendall')
""")
print("Inserted 009583 Papp +$1700")

# 2. 013886 Gamash: delete fix_script $326.38 id=24567 — no LMS basis
cur.execute("DELETE FROM charter_payments WHERE id = 24567")
print("Deleted 013886 Gamash fix_script $326.38 id=24567")

# 013603 Mathieson — LMS has literally $0 in payments (net zero after reversals)
# but ALMS has $3150. This may be a genuine bank payment never entered in LMS.
# Leave it — note in output.
print("013603 Mathieson: $3150 in ALMS, $0 in LMS — left for manual review (possible bank payment never entered in LMS)")

pg.commit()
pg.close()
print("Done.")
