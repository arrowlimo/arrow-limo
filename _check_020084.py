import sys
sys.path.insert(0, 'L:/limo')
from modern_backend.app.db import cursor

# Correct gratuity: 18% of $271.55 = $48.88
# 020084: gratuity charge_id=374898, charter_id=19229
# 020083: gratuity charge_id=374886, charter_id=19228
CORRECT_GRATUITY = 48.88
CORRECT_GRAND_TOTAL = 336.45  # 271.55 + 16.02 + 48.88

with cursor() as cur:
    for charge_id, charter_id, reserve in (
        (374898, 19229, '020084'),
        (374886, 19228, '020083'),
    ):
        cur.execute(
            "UPDATE charter_charges SET amount = %s WHERE charge_id = %s",
            (CORRECT_GRATUITY, charge_id)
        )
        cur.execute(
            "UPDATE charters SET grand_total = %s WHERE charter_id = %s",
            (CORRECT_GRAND_TOTAL, charter_id)
        )
        print(f'Fixed reserve {reserve} (charter_id {charter_id}): gratuity -> {CORRECT_GRATUITY}, grand_total -> {CORRECT_GRAND_TOTAL}')

    # Verify
    for reserve in ('020084', '020083'):
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
        cid = cur.fetchone()[0]
        cur.execute(
            "SELECT charge_type, amount FROM charter_charges WHERE charter_id = %s ORDER BY sequence",
            (cid,)
        )
        rows = cur.fetchall()
        cur.execute("SELECT grand_total FROM charters WHERE charter_id = %s", (cid,))
        gt = cur.fetchone()[0]
        print(f'\nVerify {reserve}: charges={rows}, grand_total={gt}')
