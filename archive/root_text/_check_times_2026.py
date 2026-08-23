from _db_connect import connect_db

conn = connect_db()
cur = conn.cursor()

# All 2026 charters with times, sorted by date
cur.execute("""
    SELECT
        reserve_number,
        charter_date,
        pickup_time,
        dropoff_time,
        charter_data->>'planned_end_time' AS json_end_time,
        status,
        cancelled
    FROM charters
    WHERE charter_date >= '2026-01-01' AND charter_date < '2027-01-01'
      AND cancelled = FALSE
    ORDER BY charter_date, pickup_time
""")
rows = cur.fetchall()
cols = ['reserve_number', 'charter_date', 'pickup_time', 'dropoff_time',
        'json_end_time', 'status', 'cancelled']

print(f"Total 2026 active charters: {len(rows)}\n")
print(f"{'Reserve':>8}  {'Date':>12}  {'Pickup':>7}  {'Dropoff':>8}  {'JSON_end':>10}  {'Status'}")
print("-" * 75)

suspicious = []
for r in rows:
    rn, dt, pu, do, je, st, canc = r
    pu_str = str(pu) if pu else "N/A"
    do_str = str(do) if do else "N/A"
    je_str = je if je else ""

    # Flag times in 01:00-11:59 range as potentially suspect
    suspect = False
    if pu and pu.hour in range(1, 12):
        suspect = True
    if do and do.hour in range(1, 12):
        suspect = True

    flag = " <<< SUSPECT (possible AM/PM error)" if suspect else ""
    print(f"{rn:>8}  {dt!s:>12}  {pu_str:>7}  {do_str:>8}  {je_str:>10}  {st}{flag}")
    if suspect:
        suspicious.append((rn, dt, pu_str, do_str))

print()
print(f"Suspect charters (times 01:00-11:59, possibly should be PM): {len(suspicious)}")
for s in suspicious:
    print(f"  Reserve {s[0]}  date={s[1]}  pickup={s[2]}  dropoff={s[3]}")

conn.close()
