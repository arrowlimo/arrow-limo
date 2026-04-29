import re
import psycopg
from collections import Counter, defaultdict

CONN = "host=localhost dbname=almsdata user=postgres password=ArrowLimousine"
VALID_RE = re.compile(r'^[DHO]\d{3}$')


def clean(s):
    if s is None:
        return ""
    return re.sub(r"\s+", "", str(s).strip().upper())


def normalize(s):
    t = clean(s)
    if not t:
        return None

    m = re.fullmatch(r'(?:DR|D)(\d{1,3})', t)
    if m:
        return f"D{int(m.group(1)):03d}"

    m = re.fullmatch(r'H(\d{1,3})', t)
    if m:
        return f"H{int(m.group(1)):03d}"

    m = re.fullmatch(r'(?:OF|O)(\d{1,3})', t)
    if m:
        return f"O{int(m.group(1)):03d}"

    m = re.fullmatch(r'(\d{1,3})', t)
    if m:
        return f"D{int(m.group(1)):03d}"

    return None


def bucket_counts(values):
    c = Counter()
    for v in values:
        t = clean(v)
        if re.fullmatch(r'D\d{3}', t):
            c['D'] += 1
        elif re.fullmatch(r'H\d{3}', t):
            c['H'] += 1
        elif re.fullmatch(r'O\d{3}', t):
            c['O'] += 1
        else:
            c['invalid'] += 1
    return c


with psycopg.connect(CONN) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.employee_id,
                   COALESCE(e.employee_number, '') AS employee_number,
                   (
                     SELECT m.employee_number
                     FROM public.driver_employee_mapping m
                     WHERE m.employee_id = e.employee_id
                       AND m.employee_number IS NOT NULL
                       AND BTRIM(m.employee_number) <> ''
                     ORDER BY m.employee_number
                     LIMIT 1
                   ) AS map_employee_number
            FROM public.employees e
            ORDER BY e.employee_id
        """)
        rows = cur.fetchall()

    pre = bucket_counts([r[1] for r in rows])
    print(f"pre_check D={pre['D']} H={pre['H']} O={pre['O']} invalid={pre['invalid']}")

    proposals = []
    unmapped = []
    for employee_id, emp_num, map_num in rows:
        source = map_num if map_num is not None and clean(map_num) != "" else emp_num
        norm = normalize(source)
        if norm is None:
            unmapped.append((employee_id, emp_num, map_num))
            continue
        proposals.append((employee_id, norm))

    by_num = defaultdict(list)
    for eid, num in proposals:
        by_num[num].append(eid)
    collisions = {num: eids for num, eids in by_num.items() if len(eids) > 1}

    if collisions:
        print("collisions_detected; aborting")
        for num, eids in sorted(collisions.items()):
            print(f"{num}: {','.join(str(x) for x in sorted(eids))}")
        print("no_changes_applied")
    else:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE public.employees SET employee_number = %s WHERE employee_id = %s",
                    [(num, eid) for eid, num in proposals],
                )
        print(f"updated_rows={len(proposals)}")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT employee_id, COALESCE(employee_number, '')
            FROM public.employees
            ORDER BY employee_id
        """)
        post_rows = cur.fetchall()

    post = bucket_counts([r[1] for r in post_rows])
    print(f"post_check D={post['D']} H={post['H']} O={post['O']} invalid={post['invalid']}")

    invalid_rows = [(eid, num) for eid, num in post_rows if not VALID_RE.fullmatch(clean(num))]
    if invalid_rows:
        print("remaining_invalid_rows:")
        for eid, num in invalid_rows:
            print(f"{eid}\t{num}")
    else:
        print("remaining_invalid_rows: none")
