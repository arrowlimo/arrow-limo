from datetime import datetime

from charter_form_helpers import _encode_payment_key

_SCHEMA_COL_CACHE: dict = {}
_SENT_COLS_ENSURED: bool = False


def _col_exists(cur, table: str, column: str) -> bool:
    key = f"{table}.{column}"
    if key not in _SCHEMA_COL_CACHE:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_catalog.pg_attribute a
                JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = %s
                  AND a.attname = %s
                  AND a.attnum > 0
                  AND NOT a.attisdropped
            )
            """,
            (table, column),
        )
        _SCHEMA_COL_CACHE[key] = bool(cur.fetchone()[0])
    return _SCHEMA_COL_CACHE[key]


def _db_save_routes(cur, charter_id: int, route_rows: list) -> None:
    cur.execute("DELETE FROM charter_routes WHERE charter_id = %s", (charter_id,))
    for idx, row in enumerate(route_rows, 1):
        cur.execute(
            """
            INSERT INTO charter_routes
                (charter_id, route_sequence, event_type_code,
                 address, stop_time, route_notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                charter_id,
                idx,
                row["event_type_code"],
                row["address"],
                row.get("stop_time"),
                row["route_notes"],
            ),
        )


def _db_save_charges(cur, charter_id: int, reserve_number: str, charge_rows: list, dp_data: dict) -> None:
    rn = reserve_number or ""
    cid_str = str(charter_id)
    cur.execute("DELETE FROM charter_charges WHERE charter_id = %s", (charter_id,))
    for row in charge_rows:
        cur.execute(
            """
            INSERT INTO charter_charges
                (charter_id, reserve_number, description, amount, rate,
                 sequence, charge_type, category,
                 last_updated, last_updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), 'DESKTOP')
            """,
            (
                charter_id,
                rn,
                row["description"],
                row["amount"],
                row["rate"],
                row["sequence"],
                row["charge_type"],
                row["category"],
            ),
        )
    approved_hours = dp_data.get("approved_hours")
    approved_gratuity = dp_data.get("approved_gratuity")
    hourly_rate = dp_data.get("hourly_rate")
    cur.execute(
        """
        UPDATE charters
        SET grand_total = (
                SELECT COALESCE(SUM(amount), 0)
                FROM charter_charges WHERE charter_id = %s
            ),
            total_amount_due = (
                SELECT COALESCE(SUM(amount), 0)
                FROM charter_charges WHERE charter_id = %s
            ),
            subtotal = (
                SELECT COALESCE(SUM(amount), 0)
                FROM charter_charges
                WHERE charter_id = %s
                  AND charge_type NOT IN ('tax','gst','hst','gratuity')
            ),
            gst_amount = (
                SELECT COALESCE(SUM(amount), 0)
                FROM charter_charges
                WHERE charter_id = %s AND charge_type = 'tax'
            ),
            amount_paid = (
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM charter_payments
                        WHERE charter_id = %s OR charter_id = %s
                    ) THEN (
                        SELECT COALESCE(SUM(amount), 0)
                        FROM charter_payments
                        WHERE charter_id = %s OR charter_id = %s
                    )
                    ELSE (
                        SELECT COALESCE(SUM(amount), 0)
                        FROM payments
                        WHERE reserve_number = %s OR charter_id = %s
                    )
                END
            ),
            balance_owing = (
                SELECT COALESCE(SUM(amount), 0)
                FROM charter_charges WHERE charter_id = %s
            ) - (
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM charter_payments
                        WHERE charter_id = %s OR charter_id = %s
                    ) THEN (
                        SELECT COALESCE(SUM(amount), 0)
                        FROM charter_payments
                        WHERE charter_id = %s OR charter_id = %s
                    )
                    ELSE (
                        SELECT COALESCE(SUM(amount), 0)
                        FROM payments
                        WHERE reserve_number = %s OR charter_id = %s
                    )
                END
            ),
            driver_gratuity = (
                SELECT COALESCE(SUM(amount), 0)
                FROM charter_charges
                WHERE charter_id = %s AND charge_type = 'gratuity'
            ),
            approved_hours = %s,
            approved_gratuity = %s,
            driver_hourly_rate = %s,
            driver_total_expense = (
                COALESCE(%s, 0) * COALESCE(%s, 0)
                + COALESCE(%s, (
                    SELECT COALESCE(SUM(amount), 0)
                    FROM charter_charges
                    WHERE charter_id = %s AND charge_type = 'gratuity'
                ))
            ),
            updated_at = NOW()
        WHERE charter_id = %s
        """,
        (
            charter_id,
            charter_id,
            charter_id,
            charter_id,
            rn,
            cid_str,
            rn,
            cid_str,
            rn,
            charter_id,
            charter_id,
            rn,
            cid_str,
            rn,
            cid_str,
            rn,
            charter_id,
            charter_id,
            approved_hours,
            approved_gratuity,
            hourly_rate,
            approved_hours,
            hourly_rate,
            approved_gratuity,
            charter_id,
            charter_id,
        ),
    )


def _db_sync_payments(cur, charter_id: int, reserve_number: str, charter_date, client_name: str, payment_rows: list, effective_nrr: float) -> None:
    has_gl = _col_exists(cur, "charter_payments", "gl_code")
    rn = str(reserve_number or "")
    cid_str = str(charter_id or "")
    cur.execute(
        "SELECT id FROM charter_payments" " WHERE charter_id = %s OR charter_id = %s",
        (rn, cid_str),
    )
    existing_ids = {int(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None}
    kept_ids: set = set()
    for row in payment_rows:
        row_id = row.get("row_id")
        type_txt = row.get("type_txt", "")
        method_txt = row["method_txt"]
        note_txt = row["note_txt"]
        gl_code = row.get("gl_code", "")
        nrr_portion = float(row.get("nrr_portion") or 0.0)
        payment_key_txt = _encode_payment_key(type_txt, note_txt, nrr_portion, gl_code if not has_gl else "")
        if row_id:
            if has_gl:
                cur.execute(
                    """
                    UPDATE charter_payments
                    SET amount = %s, payment_method = %s,
                        payment_date = %s, client_name = %s,
                        charter_date = %s,
                        source = COALESCE(source, 'MANUAL_DESKTOP'),
                        payment_key = COALESCE(NULLIF(%s,''), payment_key),
                        gl_code = NULLIF(%s,''),
                        imported_at = COALESCE(imported_at, NOW())
                    WHERE id = %s
                    """,
                    (row["amount"], method_txt, row["pay_date"], client_name or "", charter_date, payment_key_txt, gl_code, int(row_id)),
                )
            else:
                cur.execute(
                    """
                    UPDATE charter_payments
                    SET amount = %s, payment_method = %s,
                        payment_date = %s, client_name = %s,
                        charter_date = %s,
                        source = COALESCE(source, 'MANUAL_DESKTOP'),
                        payment_key = COALESCE(NULLIF(%s,''), payment_key),
                        imported_at = COALESCE(imported_at, NOW())
                    WHERE id = %s
                    """,
                    (row["amount"], method_txt, row["pay_date"], client_name or "", charter_date, payment_key_txt, int(row_id)),
                )
            kept_ids.add(int(row_id))
        else:
            if has_gl:
                cur.execute(
                    """
                    INSERT INTO charter_payments
                        (charter_id, client_name, charter_date, amount,
                         payment_date, payment_method, payment_key,
                         gl_code, source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (rn, client_name or "", charter_date, row["amount"], row["pay_date"], method_txt, payment_key_txt or None, gl_code or None, "MANUAL_DESKTOP"),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO charter_payments
                        (charter_id, client_name, charter_date, amount,
                         payment_date, payment_method, payment_key, source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (rn, client_name or "", charter_date, row["amount"], row["pay_date"], method_txt, payment_key_txt or None, "MANUAL_DESKTOP"),
                )
            new_id = cur.fetchone()[0]
            kept_ids.add(int(new_id))
    for pid in sorted(existing_ids - kept_ids):
        cur.execute("DELETE FROM charter_payments WHERE id = %s", (pid,))
    cur.execute(
        """
        UPDATE charters
        SET nrr_amount = %s, nrr_received = %s, updated_at = NOW()
        WHERE charter_id = %s
        """,
        (float(effective_nrr), bool(effective_nrr > 0), charter_id),
    )


def _db_save_notes(cur, charter_id: int, client_notes: str, booking_notes: str, legacy_notes: str) -> None:
    existing = {c for c in ("client_notes", "booking_notes", "notes") if _col_exists(cur, "charters", c)}
    if not existing:
        return
    sets, params = [], []
    if "client_notes" in existing:
        sets.append("client_notes = %s")
        params.append((client_notes or "").strip())
    if "booking_notes" in existing:
        sets.append("booking_notes = %s")
        params.append((booking_notes or "").strip())
    if "notes" in existing:
        sets.append("notes = %s")
        params.append(legacy_notes or "")
    params.append(charter_id)
    cur.execute(f"UPDATE charters SET {', '.join(sets)}, updated_at=NOW()" f" WHERE charter_id=%s", tuple(params))


def _db_save_delivery_dates(cur, charter_id: int, charter_sent_at, invoice_sent_at) -> None:
    global _SENT_COLS_ENSURED
    has_charter_sent = _col_exists(cur, "charters", "charter_sent_at")
    has_invoice_sent = _col_exists(cur, "charters", "invoice_sent_at")
    if has_charter_sent and has_invoice_sent:
        _SENT_COLS_ENSURED = True
    sets, params = [], []
    if has_charter_sent:
        sets.append("charter_sent_at=%s")
        params.append(charter_sent_at)
    if has_invoice_sent:
        sets.append("invoice_sent_at=%s")
        params.append(invoice_sent_at)
    if not sets:
        return
    params.append(charter_id)
    cur.execute("UPDATE charters" f" SET {', '.join(sets)}" " WHERE charter_id=%s", tuple(params))


def _db_sync_charter_role_work_items(cur, charter_id: int, reserve_number: str, p: dict) -> None:
    # Keep logic in the widget file; this helper exists as a pass-through boundary.
    return


def _db_sync_charter_tip_split(cur, charter_id: int, p: dict) -> None:
    return
