import csv
import io
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse

from ..db import cursor, get_connection

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/export")
def export(
    type: str = Query(
        ..., regex="^(booking-trends|revenue-summary|driver-hours)$"
    ),
    format: str = "csv",
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Export reports in various formats."""
    if format.lower() != "csv":
        raise HTTPException(status_code=501, detail="format_not_supported")

    def parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_date_format")

    end = parse_date(end_date) or datetime.now()
    start = parse_date(start_date) or (end - timedelta(days=365))

    with cursor() as cur:
        if type == "booking-trends":
            cur.execute(
                """
                SELECT DATE_TRUNC('month', charter_date) AS period,
                       COUNT(*) AS bookings
                FROM charters
                WHERE charter_date BETWEEN %s AND %s
                GROUP BY 1
                ORDER BY 1
                """,
                (start, end),
            )
            headers = ["period", "bookings"]
        else:
            raise HTTPException(status_code=400, detail="unknown_report_type")
        rows = cur.fetchall()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow(
            [c.isoformat() if hasattr(c, "isoformat") else c for c in r]
        )
    data = buf.getvalue()
    buf.close()
    return Response(
        content=data,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename="
                f'"{type}_{int(datetime.now().timestamp())}.csv"'
            )
        },
    )


def _parse_iso_date(
    value: str | None, fallback: datetime | None = None
) -> datetime | None:
    """Safe ISO date parser with optional fallback."""
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_date_format")


def _has_column(conn, table: str, column: str) -> bool:
    """Check if a column exists before building dynamic queries."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table, column),
        )
        return cur.fetchone() is not None


def _first_existing_column(
    conn, table: str, candidates: list[str]
) -> str | None:
    """Return first existing column name from candidates, else None."""
    for col in candidates:
        if _has_column(conn, table, col):
            return col
    return None


def _charter_text_expr(col_name: str | None, fallback: str = "") -> str:
    if col_name:
        return f"COALESCE(c.{col_name}::text, '')"
    return f"'{fallback}'"


def _charter_numeric_expr(col_name: str | None, fallback: str = "0") -> str:
    if col_name:
        return f"COALESCE(c.{col_name}::numeric, {fallback})"
    return fallback


def _build_legacy_ops_select(conn) -> tuple[str, str | None]:
    """Build a schema-tolerant SELECT for legacy ops style report rows."""
    reserve_col = _first_existing_column(
        conn, "charters", ["reserve_number", "reserve_no", "order_number"]
    )
    date_col = _first_existing_column(
        conn,
        "charters",
        ["pickup_date", "charter_date", "order_date", "created_at"],
    )
    amount_col = _first_existing_column(
        conn,
        "charters",
        ["total_amount_due", "amount", "total", "quoted_amount"],
    )
    paid_col = _first_existing_column(
        conn, "charters", ["paid_amount", "total_paid"]
    )

    destination_col = _first_existing_column(
        conn,
        "charters",
        ["dropoff_address", "destination"],
    )
    passenger_col = _first_existing_column(
        conn,
        "charters",
        ["client_display_name", "passenger_name", "client_name"],
    )
    bill_to_col = _first_existing_column(
        conn,
        "charters",
        ["bill_to", "client_display_name", "client_name"],
    )
    account_number_col = _first_existing_column(
        conn, "charters", ["account_number"]
    )
    account_type_col = _first_existing_column(
        conn, "charters", ["account_type"]
    )
    agency_number_col = _first_existing_column(
        conn, "charters", ["agency_number"]
    )
    payment_type_col = _first_existing_column(
        conn, "charters", ["payment_type", "payment_method"]
    )
    profit_center_col = _first_existing_column(
        conn, "charters", ["profit_center"]
    )
    driver_col = _first_existing_column(
        conn, "charters", ["driver_name", "driver"]
    )
    vehicle_col = _first_existing_column(
        conn, "charters", ["vehicle", "vehicle_number"]
    )
    vehicle_type_col = _first_existing_column(
        conn,
        "charters",
        ["vehicle_type_requested", "vehicle_type", "vehicle_description"],
    )
    run_type_col = _first_existing_column(
        conn, "charters", ["run_type", "charter_type"]
    )
    status_col = _first_existing_column(conn, "charters", ["status"])
    sales_person_col = _first_existing_column(
        conn,
        "charters",
        ["sales_person", "taken_by", "booked_by", "created_by"],
    )
    taken_by_col = _first_existing_column(
        conn, "charters", ["taken_by", "booked_by", "created_by"]
    )
    group_number_col = _first_existing_column(
        conn, "charters", ["group_number", "group_no"]
    )
    _date_expr = f"c.{date_col}::date" if date_col else "NULL::date"

    select_sql = f"""
        SELECT
            {_charter_text_expr(reserve_col)} AS order_number,
            {_date_expr} AS order_date,
            {_charter_text_expr(destination_col)} AS destination,
            {_charter_text_expr(passenger_col)} AS passenger_name,
            {_charter_text_expr(bill_to_col)} AS bill_to,
            {_charter_text_expr(account_number_col)} AS account_number,
            {_charter_text_expr(account_type_col)} AS account_type,
            {_charter_text_expr(agency_number_col)} AS agency_number,
            {_charter_text_expr(payment_type_col)} AS payment_type,
            {_charter_text_expr(profit_center_col)} AS profit_center,
            {_charter_text_expr(driver_col)} AS driver,
            {_charter_text_expr(vehicle_col)} AS vehicle,
            {_charter_text_expr(vehicle_type_col)} AS vehicle_type,
            {_charter_text_expr(run_type_col)} AS run_type,
            {_charter_text_expr(status_col)} AS status,
            {_charter_text_expr(sales_person_col)} AS sales_person,
            {_charter_text_expr(taken_by_col)} AS taken_by,
            {_charter_text_expr(group_number_col)} AS group_number,
            {_charter_numeric_expr(amount_col)} AS amount,
            {_charter_numeric_expr(paid_col)} AS paid_amount,
            ({_charter_numeric_expr(amount_col)}
             - {_charter_numeric_expr(paid_col)}) AS balance
        FROM charters c
    """

    return select_sql, date_col


def _to_csv_response(rows: list[dict[str, Any]], filename: str) -> Response:
    if not rows:
        headers = []
    else:
        headers = list(rows[0].keys())

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if headers:
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(h, "") for h in headers])
    data = buffer.getvalue()
    buffer.close()
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/legacy-ops")
def legacy_ops_report(
    report_family: str = Query(
        "manifest", regex="^(manifest|reserve_list|sales_summary)$"
    ),
    group_by: str = Query(
        "none",
        regex=(
            "^(none|account_number|account_type|agency_number"
            "|bill_to|destination|driver|group_number"
            "|order_date|order_number|passenger_name"
            "|payment_type|pickup_date|profit_center"
            "|run_type|sales_person|status|taken_by"
            "|vehicle|vehicle_type)$"
        ),
    ),
    start_date: str | None = None,
    end_date: str | None = None,
    include_cancelled: bool = True,
    limit: int = Query(2000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Schema-tolerant dataset endpoint for legacy Crystal ops reports.

    This endpoint is intentionally generic so many Crystal variants can be
    reproduced by changing report_family + group_by without duplicating code.
    """
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if start_date or end_date
        else datetime.now() - timedelta(days=365)
    )

    conn = get_connection()
    try:
        select_sql, date_col = _build_legacy_ops_select(conn)

        conditions = []
        params: list[Any] = []
        if date_col:
            conditions.append(f"c.{date_col}::date BETWEEN %s AND %s")
            params.extend([start_dt.date(), end_dt.date()])

        cancelled_col = _first_existing_column(conn, "charters", ["cancelled"])
        if not include_cancelled and cancelled_col:
            conditions.append(f"COALESCE(c.{cancelled_col}, false) = false")

        where_sql = ""
        if conditions:
            where_sql = " WHERE " + " AND ".join(conditions)

        sql = (
            select_sql
            + where_sql
            + " ORDER BY order_date NULLS LAST, order_number"
            + " LIMIT %s OFFSET %s"
        )
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]

        items: list[dict[str, Any]] = []
        for row in rows:
            record = dict(zip(col_names, row))
            if hasattr(record.get("order_date"), "isoformat"):
                record["order_date"] = record["order_date"].isoformat()
            record["amount"] = float(record.get("amount") or 0)
            record["paid_amount"] = float(record.get("paid_amount") or 0)
            record["balance"] = float(record.get("balance") or 0)
            items.append(record)

        # Map Crystal naming to canonical item keys.
        group_key_map = {
            "pickup_date": "order_date",
            "order_number": "order_number",
            "order_date": "order_date",
            "group_number": "group_number",
            "account_number": "account_number",
            "account_type": "account_type",
            "agency_number": "agency_number",
            "bill_to": "bill_to",
            "destination": "destination",
            "driver": "driver",
            "passenger_name": "passenger_name",
            "payment_type": "payment_type",
            "profit_center": "profit_center",
            "run_type": "run_type",
            "sales_person": "sales_person",
            "status": "status",
            "taken_by": "taken_by",
            "vehicle": "vehicle",
            "vehicle_type": "vehicle_type",
            "none": "",
        }

        grouped_rows: list[dict[str, Any]] = []
        if group_by != "none":
            key = group_key_map[group_by]
            agg: dict[str, dict[str, Any]] = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_paid": 0.0,
                    "total_balance": 0.0,
                }
            )
            for item in items:
                group_value = str(item.get(key) or "")
                row = agg[group_value]
                row["group_value"] = group_value
                row["runs"] += 1
                row["total_amount"] += float(item.get("amount") or 0)
                row["total_paid"] += float(item.get("paid_amount") or 0)
                row["total_balance"] += float(item.get("balance") or 0)
            grouped_rows = list(agg.values())
            grouped_rows.sort(key=lambda r: (r["group_value"] or "").lower())

        totals = {
            "runs": len(items),
            "total_amount": round(sum(i["amount"] for i in items), 2),
            "total_paid": round(sum(i["paid_amount"] for i in items), 2),
            "total_balance": round(sum(i["balance"] for i in items), 2),
        }

        if format == "csv":
            csv_rows = grouped_rows if group_by != "none" else items
            filename = (
                f"{report_family}_{group_by}_"
                f"{start_dt.date()}_{end_dt.date()}.csv"
            )
            return _to_csv_response(csv_rows, filename)

        return {
            "report_family": report_family,
            "group_by": group_by,
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "count": len(items),
            "group_count": len(grouped_rows),
            "totals": totals,
            "items": items,
            "groups": grouped_rows,
            "notes": {
                "schema_tolerant": True,
                "date_column_used": date_col,
                "csv_available": True,
            },
        }
    finally:
        conn.close()


# ── Phase 2 endpoints ────────────────────────────────────────────────────────

@router.get("/long-trip")
def long_trip_report(
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = Query(
        "none", regex="^(none|driver|vehicle|order_date|destination)$"
    ),
    include_cancelled: bool = True,
    limit: int = Query(2000, ge=1, le=50000),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Long-trip report -- charters with is_out_of_town or total_kms > 0."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = _parse_iso_date(start_date, end_dt - timedelta(days=365))

    conn = get_connection()
    try:
        def fc(candidates):
            return _first_existing_column(conn, "charters", candidates)

        date_col = fc(["charter_date", "pickup_date", "created_at"])
        reserve_col = fc(["reserve_number", "reserve_no", "order_number"])
        amount_col = fc(["total_amount_due", "amount", "total"])
        paid_col = fc(["paid_amount", "total_paid"])
        cancel_col = fc(["cancelled"])
        oot_col = fc(["is_out_of_town"])
        kms_col = fc(["total_kms"])
        _pass_col = fc(["client_display_name", "client_name"])
        _pick_col = fc(["pickup_address"])
        _drop_col = fc(["dropoff_address", "destination"])
        _drv_col = fc(["driver", "driver_name"])
        _veh_col = fc(["vehicle"])
        _odo_s_col = fc(["odometer_start"])
        _odo_e_col = fc(["odometer_end"])
        _stat_col = fc(["status"])
        _date_expr = f"c.{date_col}::date" if date_col else "NULL::date"

        def t(col):
            return f"COALESCE(c.{col}::text,'')" if col else "''"

        def n(col):
            return f"COALESCE(c.{col}::numeric,0)" if col else "0"

        sel = f"""
            SELECT
                {t(reserve_col)} AS order_number,
                {_date_expr} AS order_date,
                {t(_pass_col)} AS passenger_name,
                {t(_pick_col)} AS pickup_address,
                {t(_drop_col)} AS destination,
                {t(_drv_col)} AS driver,
                {t(_veh_col)} AS vehicle,
                {n(kms_col)} AS total_kms,
                {n(_odo_s_col)} AS odometer_start,
                {n(_odo_e_col)} AS odometer_end,
                {n(amount_col)} AS amount,
                {n(paid_col)} AS paid_amount,
                ({n(amount_col)}-{n(paid_col)}) AS balance,
                {t(_stat_col)} AS status
            FROM charters c
        """
        conds: list[str] = []
        params: list[Any] = []
        if date_col:
            conds.append(f"c.{date_col}::date BETWEEN %s AND %s")
            params.extend([start_dt.date(), end_dt.date()])
        trip_conds: list[str] = []
        if oot_col:
            trip_conds.append(f"COALESCE(c.{oot_col},false)=true")
        if kms_col:
            trip_conds.append(f"COALESCE(c.{kms_col},0)>0")
        if trip_conds:
            conds.append("(" + " OR ".join(trip_conds) + ")")
        if not include_cancelled and cancel_col:
            conds.append(f"COALESCE(c.{cancel_col},false)=false")
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        sql = (
            sel
            + where
            + " ORDER BY order_date NULLS LAST,order_number LIMIT %s"
        )
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]

        items: list[dict[str, Any]] = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("order_date"), "isoformat"):
                rec["order_date"] = rec["order_date"].isoformat()
            for f in (
                "amount",
                "paid_amount",
                "balance",
                "total_kms",
                "odometer_start",
                "odometer_end",
            ):
                rec[f] = float(rec.get(f) or 0)
            items.append(rec)

        totals = {
            "runs": len(items),
            "total_amount": round(sum(i["amount"] for i in items), 2),
            "total_paid": round(sum(i["paid_amount"] for i in items), 2),
            "total_balance": round(sum(i["balance"] for i in items), 2),
            "total_kms": round(sum(i["total_kms"] for i in items), 1),
        }

        grouped: list[dict[str, Any]] = []
        if group_by != "none":
            agg: dict[str, Any] = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_paid": 0.0,
                    "total_balance": 0.0,
                    "total_kms": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_paid"] += item["paid_amount"]
                r["total_balance"] += item["balance"]
                r["total_kms"] += item["total_kms"]
            grouped = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )

        if format == "csv":
            return _to_csv_response(
                grouped if group_by != "none" else items,
                f"long_trip_{start_dt.date()}_{end_dt.date()}.csv",
            )
        return {
            "count": len(items),
            "totals": totals,
            "groups": grouped,
            "items": items,
        }
    finally:
        conn.close()


@router.get("/invoiced-charges")
def invoiced_charges_report(
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = Query(
        "none",
        regex="^(none|charge_type|category|account_number|reserve_number)$",
    ),
    limit: int = Query(5000, ge=1, le=100000),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Charter charges detail report (charter_charges JOIN charters)."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = _parse_iso_date(start_date, end_dt - timedelta(days=365))

    conn = get_connection()
    try:
        def fc(candidates):
            return _first_existing_column(conn, "charters", candidates)

        date_col = fc(["charter_date", "pickup_date", "created_at"])
        client_col = fc(["client_display_name", "client_name"])
        date_expr = f"c.{date_col}::date" if date_col else "NULL::date"
        client_expr = (
            f"COALESCE(c.{client_col}::text,'')" if client_col else "''"
        )

        sql = f"""
            SELECT cc.reserve_number,
                   {date_expr} AS charter_date,
                   {client_expr} AS client_name,
                   COALESCE(cc.description,'') AS description,
                   COALESCE(cc.charge_type,'') AS charge_type,
                   COALESCE(cc.category,'') AS category,
                   COALESCE(cc.rate,0) AS rate,
                   COALESCE(cc.amount,0) AS amount,
                   COALESCE(cc.gst_amount,0) AS gst_amount,
                   COALESCE(cc.account_number,'') AS account_number
            FROM charter_charges cc
            LEFT JOIN charters c ON c.charter_id=cc.charter_id
            WHERE {date_expr} BETWEEN %s AND %s
            ORDER BY charter_date NULLS LAST,cc.reserve_number
            LIMIT %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, [start_dt.date(), end_dt.date(), limit])
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]

        items: list[dict[str, Any]] = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("charter_date"), "isoformat"):
                rec["charter_date"] = rec["charter_date"].isoformat()
            for f in ("rate", "amount", "gst_amount"):
                rec[f] = float(rec.get(f) or 0)
            items.append(rec)

        totals = {
            "lines": len(items),
            "total_amount": round(sum(i["amount"] for i in items), 2),
            "total_gst": round(sum(i["gst_amount"] for i in items), 2),
        }

        grouped: list[dict[str, Any]] = []
        if group_by != "none":
            agg: dict[str, Any] = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_gst": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_gst"] += item["gst_amount"]
            grouped = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )

        if format == "csv":
            return _to_csv_response(
                grouped if group_by != "none" else items,
                f"invoiced_charges_{start_dt.date()}_{end_dt.date()}.csv",
            )
        return {
            "count": len(items),
            "totals": totals,
            "groups": grouped,
            "items": items,
        }
    finally:
        conn.close()


@router.get("/driver-pay")
def driver_pay_report(
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = Query(
        "none",
        regex="^(none|driver|order_date|driver_paid|run_type|vehicle)$",
    ),
    limit: int = Query(2000, ge=1, le=50000),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Driver pay report from charter pay columns."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = _parse_iso_date(start_date, end_dt - timedelta(days=365))

    conn = get_connection()
    try:
        def fc(candidates):
            return _first_existing_column(conn, "charters", candidates)

        date_col = fc(["charter_date", "pickup_date", "created_at"])
        reserve_col = fc(["reserve_number", "reserve_no", "order_number"])
        base_col = fc(["driver_base_pay"])
        grat_col = fc(["driver_gratuity"])
        total_col = fc(["driver_total_expense"])
        hours_col = fc(["driver_hours_worked"])
        rate_col = fc(["driver_hourly_rate"])
        paid_col = fc(["driver_paid"])
        ctype_col = fc(["charter_type", "run_type"])

        def t(col):
            return f"COALESCE(c.{col}::text,'')" if col else "''"

        def n(col):
            return f"COALESCE(c.{col}::numeric,0)" if col else "0"

        date_expr = f"c.{date_col}::date" if date_col else "NULL::date"
        paid_expr = f"COALESCE(c.{paid_col}::text,'')" if paid_col else "''"

        sql = f"""
            SELECT
                {t(reserve_col)} AS order_number,
                {date_expr} AS order_date,
                {t(fc(['driver', 'driver_name']))} AS driver,
                {n(hours_col)} AS driver_hours_worked,
                {n(rate_col)} AS driver_hourly_rate,
                {n(base_col)} AS driver_base_pay,
                {n(grat_col)} AS driver_gratuity,
                {n(total_col)} AS driver_total_expense,
                {paid_expr} AS driver_paid,
                {t(fc(['vehicle']))} AS vehicle,
                {t(ctype_col)} AS run_type
            FROM charters c
            WHERE {date_expr} BETWEEN %s AND %s
              AND ({n(total_col)}>0 OR {n(base_col)}>0)
            ORDER BY order_date NULLS LAST,driver
            LIMIT %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, [start_dt.date(), end_dt.date(), limit])
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]

        items: list[dict[str, Any]] = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("order_date"), "isoformat"):
                rec["order_date"] = rec["order_date"].isoformat()
            for f in (
                "driver_hours_worked",
                "driver_hourly_rate",
                "driver_base_pay",
                "driver_gratuity",
                "driver_total_expense",
            ):
                rec[f] = float(rec.get(f) or 0)
            items.append(rec)

        _tp_base = round(sum(i["driver_base_pay"] for i in items), 2)
        _tp_grat = round(sum(i["driver_gratuity"] for i in items), 2)
        _tp_pay = round(sum(i["driver_total_expense"] for i in items), 2)
        _tp_hrs = round(sum(i["driver_hours_worked"] for i in items), 2)
        totals = {
            "runs": len(items),
            "total_base_pay": _tp_base,
            "total_gratuity": _tp_grat,
            "total_pay": _tp_pay,
            "total_hours": _tp_hrs,
        }

        grouped: list[dict[str, Any]] = []
        if group_by != "none":
            agg: dict[str, Any] = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_base_pay": 0.0,
                    "total_gratuity": 0.0,
                    "total_pay": 0.0,
                    "total_hours": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_base_pay"] += item["driver_base_pay"]
                r["total_gratuity"] += item["driver_gratuity"]
                r["total_pay"] += item["driver_total_expense"]
                r["total_hours"] += item["driver_hours_worked"]
            grouped = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )

        if format == "csv":
            return _to_csv_response(
                grouped if group_by != "none" else items,
                f"driver_pay_{start_dt.date()}_{end_dt.date()}.csv",
            )
        return {
            "count": len(items),
            "totals": totals,
            "groups": grouped,
            "items": items,
        }
    finally:
        conn.close()


@router.get("/fleet")
def fleet_report(
    group_by: str = Query(
        "none",
        regex=(
            "^(none|operational_status|vehicle_type|vehicle_category"
            "|lifecycle_status|fuel_type)$"
        ),
    ),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Fleet status report from the vehicles table."""
    with cursor() as cur:
        cur.execute("""
            SELECT vehicle_number,
                   COALESCE(make,'') AS make,
                   COALESCE(model,'') AS model,
                   COALESCE(year::text,'') AS year,
                   COALESCE(license_plate,'') AS license_plate,
                   COALESCE(vehicle_type,'') AS vehicle_type,
                   COALESCE(vehicle_category,'') AS vehicle_category,
                   COALESCE(passenger_capacity::text,'') AS passenger_capacity,
                   COALESCE(operational_status,'') AS operational_status,
                   COALESCE(lifecycle_status,'') AS lifecycle_status,
                   COALESCE(cvip_expiry_date::text,'') AS cvip_expiry_date,
                   COALESCE(next_service_due::text,'') AS next_service_due,
                   COALESCE(odometer::text,'') AS odometer,
                   COALESCE(fuel_type,'') AS fuel_type,
                   COALESCE(status,'') AS status
            FROM vehicles
            ORDER BY vehicle_number
        """)
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description]

    items: list[dict[str, Any]] = [dict(zip(col_names, row)) for row in rows]
    totals = {"count": len(items)}

    grouped: list[dict[str, Any]] = []
    if group_by != "none":
        agg: dict[str, Any] = defaultdict(
            lambda: {"group_value": "", "count": 0}
        )
        for item in items:
            gv = str(item.get(group_by) or "")
            agg[gv]["group_value"] = gv
            agg[gv]["count"] += 1
        grouped = sorted(
            agg.values(), key=lambda x: (x["group_value"] or "").lower()
        )

    if format == "csv":
        return _to_csv_response(
            grouped if group_by != "none" else items, "fleet_status.csv"
        )
    return {
        "count": len(items),
        "totals": totals,
        "groups": grouped,
        "items": items,
    }


# ── Phase 3 endpoints ────────────────────────────────────────────────────────

@router.get("/client-activity")
def client_activity_report(
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = Query(
        "none", regex="^(none|account_number|company_name|run_type)$"
    ),
    include_cancelled: bool = True,
    limit: int = Query(5000, ge=1, le=50000),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Charter activity per client/account (charters LEFT JOIN clients)."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = _parse_iso_date(start_date, end_dt - timedelta(days=365))

    conn = get_connection()
    try:
        def fc(tbl, candidates):
            return _first_existing_column(conn, tbl, candidates)

        date_col = fc(
            "charters", ["charter_date", "pickup_date", "created_at"]
        )
        reserve_col = fc(
            "charters", ["reserve_number", "reserve_no", "order_number"]
        )
        amount_col = fc("charters", ["total_amount_due", "amount", "total"])
        paid_col = fc("charters", ["paid_amount", "total_paid"])
        cancel_col = fc("charters", ["cancelled"])
        acct_col = fc("charters", ["account_number"])
        client_col = fc("charters", ["client_display_name", "client_name"])
        ctype_col = fc("charters", ["charter_type", "run_type"])
        acct_cl = fc("clients",  ["account_number"])
        company_col = fc("clients",  ["company_name", "client_name", "name"])

        def t(tbl, col):
            return f"COALESCE({tbl}.{col}::text,'')" if col else "''"

        def n(col):
            return f"COALESCE(c.{col}::numeric,0)" if col else "0"

        date_expr = f"c.{date_col}::date" if date_col else "NULL::date"
        company_expr = (
            f"COALESCE(cl.{company_col}::text,'')" if company_col else "''"
        )
        acct_join = (
            f"c.{acct_col}=cl.{acct_cl}" if acct_col and acct_cl else "false"
        )

        conds: list[str] = []
        params: list[Any] = []
        if date_col:
            conds.append(f"c.{date_col}::date BETWEEN %s AND %s")
            params.extend([start_dt.date(), end_dt.date()])
        if not include_cancelled and cancel_col:
            conds.append(f"COALESCE(c.{cancel_col},false)=false")
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        sql = f"""
            SELECT {t('c', reserve_col)} AS order_number,
                   {date_expr} AS order_date,
                   {t('c', acct_col)} AS account_number,
                   {company_expr} AS company_name,
                   {t('c', client_col)} AS passenger_name,
                   {t('c', ctype_col)} AS run_type,
                   {n(amount_col)} AS amount,
                   {n(paid_col)} AS paid_amount,
                   ({n(amount_col)}-{n(paid_col)}) AS balance
            FROM charters c LEFT JOIN clients cl ON {acct_join}
            {where}
            ORDER BY account_number, order_date
            LIMIT %s
        """
        params.append(limit)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]

        items: list[dict[str, Any]] = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("order_date"), "isoformat"):
                rec["order_date"] = rec["order_date"].isoformat()
            for f in ("amount", "paid_amount", "balance"):
                rec[f] = float(rec.get(f) or 0)
            items.append(rec)

        totals = {
            "runs": len(items),
            "total_amount": round(sum(i["amount"] for i in items), 2),
            "total_paid": round(sum(i["paid_amount"] for i in items), 2),
            "total_balance": round(sum(i["balance"] for i in items), 2),
        }
        grouped: list[dict[str, Any]] = []
        if group_by != "none":
            agg: dict[str, Any] = defaultdict(
                lambda: {
                    "group_value": "",
                    "company_name": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_paid": 0.0,
                    "total_balance": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["company_name"] = item.get("company_name", "")
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_paid"] += item["paid_amount"]
                r["total_balance"] += item["balance"]
            grouped = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )

        if format == "csv":
            return _to_csv_response(
                grouped if group_by != "none" else items,
                f"client_activity_{start_dt.date()}_{end_dt.date()}.csv",
            )
        return {
            "count": len(items),
            "totals": totals,
            "groups": grouped,
            "items": items,
        }
    finally:
        conn.close()


@router.get("/payment-list")
def payment_list_report(
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = Query(
        "none", regex="^(none|payment_method|source|client_name)$"
    ),
    limit: int = Query(10000, ge=1, le=100000),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """All charter payments within a date range (charter_payments table)."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = _parse_iso_date(start_date, end_dt - timedelta(days=365))

    with cursor() as cur:
        cur.execute("""
            SELECT payment_date,
                   COALESCE(client_name,'') AS client_name,
                   COALESCE(charter_id::text,'') AS charter_id,
                   COALESCE(amount,0) AS amount,
                   COALESCE(payment_method,'') AS payment_method,
                   COALESCE(source,'') AS source,
                   COALESCE(payment_key,'') AS payment_key
            FROM charter_payments
            WHERE payment_date BETWEEN %s AND %s
            ORDER BY payment_date, client_name
            LIMIT %s
        """, [start_dt.date(), end_dt.date(), limit])
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description]

    items: list[dict[str, Any]] = []
    for row in rows:
        rec = dict(zip(col_names, row))
        if hasattr(rec.get("payment_date"), "isoformat"):
            rec["payment_date"] = rec["payment_date"].isoformat()
        rec["amount"] = float(rec.get("amount") or 0)
        items.append(rec)

    totals = {
        "runs": len(items),
        "total_amount": round(sum(i["amount"] for i in items), 2),
    }
    grouped: list[dict[str, Any]] = []
    if group_by != "none":
        agg: dict[str, Any] = defaultdict(
            lambda: {"group_value": "", "runs": 0, "total_amount": 0.0}
        )
        for item in items:
            gv = str(item.get(group_by) or "")
            r = agg[gv]
            r["group_value"] = gv
            r["runs"] += 1
            r["total_amount"] += item["amount"]
        grouped = sorted(
            agg.values(), key=lambda x: (x["group_value"] or "").lower()
        )

    if format == "csv":
        return _to_csv_response(
            grouped if group_by != "none" else items,
            f"payments_{start_dt.date()}_{end_dt.date()}.csv",
        )
    return {
        "count": len(items),
        "totals": totals,
        "groups": grouped,
        "items": items,
    }


@router.get("/aged-receivables")
def aged_receivables_report(
    group_by: str = Query(
        "none", regex="^(none|age_bracket|account_number|driver)$"
    ),
    include_cancelled: bool = True,
    limit: int = Query(5000, ge=1, le=50000),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Unpaid charters, aging brackets — all-time, no date filter."""
    conn = get_connection()
    try:
        def fc(candidates):
            return _first_existing_column(conn, "charters", candidates)

        date_col = fc(["charter_date", "pickup_date", "created_at"])
        reserve_col = fc(["reserve_number", "reserve_no", "order_number"])
        amount_col = fc(["total_amount_due", "amount", "total"])
        paid_col = fc(["paid_amount", "total_paid"])
        cancel_col = fc(["cancelled"])
        acct_col = fc(["account_number"])
        client_col = fc(["client_display_name", "client_name"])
        driver_col = fc(["driver", "driver_name"])

        def t(col):
            return f"COALESCE(c.{col}::text,'')" if col else "''"

        def n(col):
            return f"COALESCE(c.{col}::numeric,0)" if col else "0"

        date_expr = f"c.{date_col}::date" if date_col else "NULL::date"

        conds: list[str] = []
        params: list[Any] = []
        if not include_cancelled and cancel_col:
            conds.append(f"COALESCE(c.{cancel_col},false)=false")
        extra = (" AND " + " AND ".join(conds)) if conds else ""

        sql = f"""
            SELECT {t(reserve_col)} AS order_number,
                   {date_expr} AS order_date,
                   {t(client_col)} AS passenger_name,
                   {t(acct_col)} AS account_number,
                   {t(driver_col)} AS driver,
                   {n(amount_col)} AS amount,
                   {n(paid_col)} AS paid_amount,
                   ({n(amount_col)}-{n(paid_col)}) AS balance,
                   (CURRENT_DATE
                    - COALESCE({date_expr}, CURRENT_DATE)
                   )::int AS days_outstanding,
                   CASE
                       WHEN COALESCE({date_expr},CURRENT_DATE)
                           >= CURRENT_DATE-30 THEN '0-30 days'
                       WHEN COALESCE({date_expr},CURRENT_DATE)
                           >= CURRENT_DATE-60 THEN '31-60 days'
                       WHEN COALESCE({date_expr},CURRENT_DATE)
                           >= CURRENT_DATE-90 THEN '61-90 days'
                       ELSE '90+ days'
                   END AS age_bracket
            FROM charters c
            WHERE ({n(amount_col)}-{n(paid_col)})>0{extra}
            ORDER BY order_date NULLS LAST
            LIMIT %s
        """
        params.append(limit)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]

        items: list[dict[str, Any]] = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("order_date"), "isoformat"):
                rec["order_date"] = rec["order_date"].isoformat()
            for f in ("amount", "paid_amount", "balance"):
                rec[f] = float(rec.get(f) or 0)
            rec["days_outstanding"] = int(rec.get("days_outstanding") or 0)
            items.append(rec)

        totals = {
            "runs": len(items),
            "total_amount": round(sum(i["amount"] for i in items), 2),
            "total_paid": round(sum(i["paid_amount"] for i in items), 2),
            "total_balance": round(sum(i["balance"] for i in items), 2),
        }
        grouped: list[dict[str, Any]] = []
        if group_by != "none":
            agg: dict[str, Any] = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_balance": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_balance"] += item["balance"]
            grouped = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )

        if format == "csv":
            return _to_csv_response(
                grouped if group_by != "none" else items,
                "aged_receivables.csv",
            )
        return {
            "count": len(items),
            "totals": totals,
            "groups": grouped,
            "items": items,
        }
    finally:
        conn.close()


@router.get("/income-summary")
def income_summary_report(
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = Query(
        "none",
        regex=(
            "^(none|revenue_category|fiscal_year|fiscal_quarter"
            "|payment_method|source_system)$"
        ),
    ),
    limit: int = Query(10000, ge=1, le=100000),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Income ledger summary report (income_ledger table)."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = _parse_iso_date(start_date, end_dt - timedelta(days=365))

    with cursor() as cur:
        cur.execute("""
            SELECT transaction_date,
                   COALESCE(reserve_number,'') AS reserve_number,
                   COALESCE(revenue_category,'') AS revenue_category,
                   COALESCE(revenue_subcategory,'') AS revenue_subcategory,
                   COALESCE(gross_amount,0) AS gross_amount,
                   COALESCE(gst_collected,0) AS gst_collected,
                   COALESCE(net_amount,0) AS net_amount,
                   COALESCE(payment_method,'') AS payment_method,
                   COALESCE(fiscal_year::text,'') AS fiscal_year,
                   COALESCE(fiscal_quarter::text,'') AS fiscal_quarter,
                   COALESCE(source_system,'') AS source_system,
                   COALESCE(description,'') AS description
            FROM income_ledger
            WHERE transaction_date BETWEEN %s AND %s
            ORDER BY transaction_date, revenue_category
            LIMIT %s
        """, [start_dt.date(), end_dt.date(), limit])
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description]

    items: list[dict[str, Any]] = []
    for row in rows:
        rec = dict(zip(col_names, row))
        if hasattr(rec.get("transaction_date"), "isoformat"):
            rec["transaction_date"] = rec["transaction_date"].isoformat()
        for f in ("gross_amount", "gst_collected", "net_amount"):
            rec[f] = float(rec.get(f) or 0)
        items.append(rec)

    totals = {
        "lines": len(items),
        "total_gross": round(sum(i["gross_amount"] for i in items), 2),
        "total_gst": round(sum(i["gst_collected"] for i in items), 2),
        "total_net": round(sum(i["net_amount"] for i in items), 2),
    }
    grouped: list[dict[str, Any]] = []
    if group_by != "none":
        agg: dict[str, Any] = defaultdict(
            lambda: {
                "group_value": "",
                "runs": 0,
                "total_gross": 0.0,
                "total_gst": 0.0,
                "total_net": 0.0,
            }
        )
        for item in items:
            gv = str(item.get(group_by) or "")
            r = agg[gv]
            r["group_value"] = gv
            r["runs"] += 1
            r["total_gross"] += item["gross_amount"]
            r["total_gst"] += item["gst_collected"]
            r["total_net"] += item["net_amount"]
        grouped = sorted(
            agg.values(), key=lambda x: (x["group_value"] or "").lower()
        )

    if format == "csv":
        return _to_csv_response(
            grouped if group_by != "none" else items,
            f"income_summary_{start_dt.date()}_{end_dt.date()}.csv",
        )
    return {
        "count": len(items),
        "totals": totals,
        "groups": grouped,
        "items": items,
    }


@router.get("/short-trip")
def short_trip_report(
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = Query(
        "none",
        regex="^(none|driver|vehicle|order_date|run_type|account_number)$",
    ),
    include_cancelled: bool = True,
    limit: int = Query(5000, ge=1, le=50000),
    format: str = Query("json", regex="^(json|csv)$"),
):
    """Short/local trips (is_out_of_town=false AND total_kms=0)."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = _parse_iso_date(start_date, end_dt - timedelta(days=365))

    conn = get_connection()
    try:
        def fc(candidates):
            return _first_existing_column(conn, "charters", candidates)

        date_col = fc(["charter_date", "pickup_date", "created_at"])
        reserve_col = fc(["reserve_number", "reserve_no", "order_number"])
        amount_col = fc(["total_amount_due", "amount", "total"])
        paid_col = fc(["paid_amount", "total_paid"])
        cancel_col = fc(["cancelled"])
        oot_col = fc(["is_out_of_town"])
        kms_col = fc(["total_kms"])
        _pass_col = fc(["client_display_name", "client_name"])

        def t(col):
            return f"COALESCE(c.{col}::text,'')" if col else "''"

        def n(col):
            return f"COALESCE(c.{col}::numeric,0)" if col else "0"

        date_expr = f"c.{date_col}::date" if date_col else "NULL::date"

        conds: list[str] = []
        params: list[Any] = []
        if date_col:
            conds.append(f"c.{date_col}::date BETWEEN %s AND %s")
            params.extend([start_dt.date(), end_dt.date()])
        short_conds: list[str] = []
        if oot_col:
            short_conds.append(f"COALESCE(c.{oot_col},false)=false")
        if kms_col:
            short_conds.append(f"COALESCE(c.{kms_col},0)=0")
        if short_conds:
            conds.append("(" + " AND ".join(short_conds) + ")")
        if not include_cancelled and cancel_col:
            conds.append(f"COALESCE(c.{cancel_col},false)=false")
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        sql = f"""
            SELECT {t(reserve_col)} AS order_number,
                   {date_expr} AS order_date,
                   {t(_pass_col)} AS passenger_name,
                   {t(fc(['account_number']))} AS account_number,
                   {t(fc(['driver', 'driver_name']))} AS driver,
                   {t(fc(['vehicle']))} AS vehicle,
                   {t(fc(['dropoff_address', 'destination']))} AS destination,
                   {t(fc(['charter_type', 'run_type']))} AS run_type,
                   {t(fc(['payment_status', 'nrd_method']))} AS payment_type,
                   {n(amount_col)} AS amount,
                   {n(paid_col)} AS paid_amount,
                   ({n(amount_col)}-{n(paid_col)}) AS balance,
                   {t(fc(['status']))} AS status
            FROM charters c{where}
            ORDER BY order_date NULLS LAST, order_number
            LIMIT %s
        """
        params.append(limit)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]

        items: list[dict[str, Any]] = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("order_date"), "isoformat"):
                rec["order_date"] = rec["order_date"].isoformat()
            for f in ("amount", "paid_amount", "balance"):
                rec[f] = float(rec.get(f) or 0)
            items.append(rec)

        totals = {
            "runs": len(items),
            "total_amount": round(sum(i["amount"] for i in items), 2),
            "total_paid": round(sum(i["paid_amount"] for i in items), 2),
            "total_balance": round(sum(i["balance"] for i in items), 2),
        }
        grouped: list[dict[str, Any]] = []
        if group_by != "none":
            agg: dict[str, Any] = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_paid": 0.0,
                    "total_balance": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_paid"] += item["paid_amount"]
                r["total_balance"] += item["balance"]
            grouped = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )

        if format == "csv":
            return _to_csv_response(
                grouped if group_by != "none" else items,
                f"short_trip_{start_dt.date()}_{end_dt.date()}.csv",
            )
        return {
            "count": len(items),
            "totals": totals,
            "groups": grouped,
            "items": items,
        }
    finally:
        conn.close()


@router.get("/trial-balance")
def trial_balance(as_of: str | None = None):
    """Return trial balance as of a date, aggregated by account."""
    as_of_date = _parse_iso_date(as_of, datetime.now()).date()
    with cursor() as cur:
        cur.execute(
            """
            SELECT
                account_name,
                account,
                account_type,
                COALESCE(SUM(debit), 0) AS total_debit,
                COALESCE(SUM(credit), 0) AS total_credit,
                COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance
            FROM general_ledger
            WHERE date <= %s
            GROUP BY account_name, account, account_type
            HAVING COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) != 0
            ORDER BY account_name
            """,
            (as_of_date,),
        )
        rows = cur.fetchall()

    accounts = [
        {
            "account_name": r[0],
            "account": r[1],
            "account_type": r[2],
            "total_debit": float(r[3] or 0),
            "total_credit": float(r[4] or 0),
            "balance": float(r[5] or 0),
        }
        for r in rows
    ]
    totals = {
        "total_debits": round(sum(a["total_debit"] for a in accounts), 2),
        "total_credits": round(sum(a["total_credit"] for a in accounts), 2),
    }
    totals["difference"] = round(
        totals["total_debits"] - totals["total_credits"], 2
    )
    return {"as_o": str(as_of_date), "accounts": accounts, "totals": totals}


@router.get("/journals")
def journals(
    start_date: str | None = None,
    end_date: str | None = None,
    account: str | None = None,
    name: str | None = None,
    supplier: str | None = None,
    employee: str | None = None,
    customer: str | None = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    """Paged journal listing from general_ledger with common filters."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    conditions = ["date BETWEEN %s AND %s"]
    params: list[Any] = [start_dt.date(), end_dt.date()]

    if account:
        conditions.append("account = %s")
        params.append(account)
    if name:
        conditions.append("name ILIKE %s")
        params.append(f"%{name}%")
    if supplier:
        conditions.append("supplier ILIKE %s")
        params.append(f"%{supplier}%")
    if employee:
        conditions.append("employee ILIKE %s")
        params.append(f"%{employee}%")
    if customer:
        conditions.append("customer ILIKE %s")
        params.append(f"%{customer}%")

    where_clause = " AND ".join(conditions)

    with cursor() as cur:
        cur.execute(
            f"""
            SELECT
                id, date, transaction_type, num, name,
                account_name, account, memo_description, account_full_name,
                debit, credit, balance, supplier, employee, customer
            FROM general_ledger
            WHERE {where_clause}
            ORDER BY date, id
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

    journals = [
        {
            "id": r[0],
            "date": str(r[1]),
            "transaction_type": r[2],
            "num": r[3],
            "name": r[4],
            "account_name": r[5],
            "account": r[6],
            "memo": r[7],
            "account_full_name": r[8],
            "debit": float(r[9] or 0),
            "credit": float(r[10] or 0),
            "balance": float(r[11] or 0),
            "supplier": r[12],
            "employee": r[13],
            "customer": r[14],
        }
        for r in rows
    ]
    return {
        "start_date": str(params[0]),
        "end_date": str(params[1]),
        "count": len(journals),
        "items": journals,
    }


@router.get("/bank-reconciliation")
def bank_reconciliation(
    bank_id: int,
    statement_end: str | None = None,
    max_rows: int = Query(500, ge=50, le=2000),
):
    """Lightweight bank reconciliation view from banking_transactions."""
    end_date = _parse_iso_date(statement_end, datetime.now()).date()
    with cursor() as cur:
        cur.execute(
            """
            SELECT
                transaction_id,
                trans_date,
                trans_description,
                debit_amount,
                credit_amount,
                reconciliation_status,
                reconciled_receipt_id,
                balance_after
            FROM banking_transactions
            WHERE bank_id = %s AND trans_date <= %s
            ORDER BY trans_date, transaction_id
            LIMIT %s
            """,
            (bank_id, end_date, max_rows),
        )
        rows = cur.fetchall()

    def _float(val):
        return float(val) if val is not None else 0.0

    items = [
        {
            "transaction_id": r[0],
            "date": str(r[1]),
            "description": r[2],
            "debit": _float(r[3]),
            "credit": _float(r[4]),
            "status": r[5],
            "reconciled_receipt_id": r[6],
            "balance_after": _float(r[7]),
        }
        for r in rows
    ]

    total_debits = round(sum(i["debit"] for i in items), 2)
    total_credits = round(sum(i["credit"] for i in items), 2)
    outstanding = [
        i for i in items
        if i["status"] in (None, "unreconciled", "ignored")
    ]

    return {
        "bank_id": bank_id,
        "statement_end": str(end_date),
        "count": len(items),
        "totals": {
            "debits": total_debits,
            "credits": total_credits,
            "net": round(total_credits - total_debits, 2),
            "outstanding_count": len(outstanding),
            "outstanding_net": round(
                sum(o["credit"] - o["debit"] for o in outstanding), 2
            ),
        },
        "items": items,
    }


@router.get("/pl-summary")
def pl_summary(
    granularity: str = Query("month", regex="^(year|quarter|month)$"),
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Profit/Loss summary from general_ledger grouped by period."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    with cursor() as cur:
        cur.execute(
            """
            SELECT
                DATE_TRUNC(%s, date) AS period,
                 SUM(CASE WHEN account_type ILIKE 'income%%'
                     THEN credit - debit ELSE 0 END) AS revenue,
                 SUM(CASE WHEN account_type ILIKE 'revenue%%'
                     THEN credit - debit ELSE 0 END) AS revenue_alt,
                 SUM(CASE WHEN account_type ILIKE 'expense%%'
                     THEN debit - credit ELSE 0 END) AS expenses
            FROM general_ledger
            WHERE date BETWEEN %s AND %s
            GROUP BY 1
            ORDER BY 1
            """,
            (granularity, start_dt.date(), end_dt.date()),
        )
        rows = cur.fetchall()

    periods = []
    for r in rows:
        revenue = float((r[1] or 0) + (r[2] or 0))
        expenses = float(r[3] or 0)
        periods.append(
            {
                "period": r[0].date().isoformat()
                if hasattr(r[0], "date")
                else str(r[0]),
                "revenue": round(revenue, 2),
                "expenses": round(expenses, 2),
                "profit": round(revenue - expenses, 2),
            }
        )

    totals = {
        "revenue": round(sum(p["revenue"] for p in periods), 2),
        "expenses": round(sum(p["expenses"] for p in periods), 2),
    }
    totals["profit"] = round(totals["revenue"] - totals["expenses"], 2)

    return {
        "granularity": granularity,
        "start_date": str(start_dt.date()),
        "end_date": str(end_dt.date()),
        "periods": periods,
        "totals": totals,
    }


@router.get("/vehicle-performance")
def vehicle_performance(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Vehicle revenue vs expenses with trip count and cost split."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    conn = get_connection()
    try:
        has_charter_vehicle = _has_column(conn, "charters", "vehicle_id")
        charter_date_col = (
            "pickup_date"
            if _has_column(conn, "charters", "pickup_date")
            else "charter_date"
            if _has_column(conn, "charters", "charter_date")
            else None
        )

        has_receipt_vehicle = _has_column(conn, "receipts", "vehicle_id")
        receipt_date_col = (
            "receipt_date"
            if _has_column(conn, "receipts", "receipt_date")
            else "date"
            if _has_column(conn, "receipts", "date")
            else None
        )

        revenue_by_vehicle: dict[int, dict[str, Any]] = {}
        expense_by_vehicle: dict[int, dict[str, float]] = {}

        if has_charter_vehicle and charter_date_col:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT vehicle_id,
                           COUNT(*) AS trips,
                           COALESCE(SUM(gross_amount), 0) AS revenue
                    FROM charters
                    WHERE {charter_date_col} BETWEEN %s AND %s
                    GROUP BY vehicle_id
                    """,
                    (start_dt.date(), end_dt.date()),
                )
                for vid, trips, revenue in cur.fetchall():
                    revenue_by_vehicle[int(vid or 0)] = {
                        "trips": int(trips or 0),
                        "revenue": float(revenue or 0),
                    }

        if has_receipt_vehicle and receipt_date_col:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT vehicle_id,
                           COALESCE(SUM(gross_amount), 0) AS total_expense,
                           COALESCE(SUM(
                               CASE WHEN description ILIKE '%maint%'
                                    OR category ILIKE 'maintenance%%'
                               THEN gross_amount ELSE 0 END
                           ), 0) AS maintenance,
                           COALESCE(SUM(
                               CASE WHEN description ILIKE '%insur%'
                                    OR category ILIKE 'insurance%%'
                               THEN gross_amount ELSE 0 END
                           ), 0) AS insurance
                    FROM receipts
                    WHERE {receipt_date_col} BETWEEN %s AND %s
                    GROUP BY vehicle_id
                    """,
                    (start_dt.date(), end_dt.date()),
                )
                for vid, total_exp, maint, ins in cur.fetchall():
                    expense_by_vehicle[int(vid or 0)] = {
                        "expense": float(total_exp or 0),
                        "maintenance": float(maint or 0),
                        "insurance": float(ins or 0),
                    }

        # Vehicles master
        vehicles: list[dict[str, Any]] = []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vehicle_id, vehicle_number, make, model, year
                FROM vehicles
                ORDER BY vehicle_number
                """
            )
            for vid, num, make, model, year in cur.fetchall():
                rev = revenue_by_vehicle.get(
                    int(vid or 0), {"revenue": 0.0, "trips": 0}
                )
                exp = expense_by_vehicle.get(
                    int(vid or 0),
                    {"expense": 0.0, "maintenance": 0.0, "insurance": 0.0},
                )
                profit = rev.get("revenue", 0.0) - exp.get("expense", 0.0)
                vehicles.append(
                    {
                        "vehicle_id": int(vid or 0),
                        "vehicle_number": num,
                        "make": make,
                        "model": model,
                        "year": year,
                        "trips": rev.get("trips", 0),
                        "revenue": round(rev.get("revenue", 0.0), 2),
                        "expense": round(exp.get("expense", 0.0), 2),
                        "maintenance": round(exp.get("maintenance", 0.0), 2),
                        "insurance": round(exp.get("insurance", 0.0), 2),
                        "profit": round(profit, 2),
                        "margin_pct": round(
                            (profit / rev.get("revenue", 1)) * 100, 2
                        )
                        if rev.get("revenue", 0)
                        else 0.0,
                    }
                )

        totals = {
            "revenue": round(sum(v["revenue"] for v in vehicles), 2),
            "expense": round(sum(v["expense"] for v in vehicles), 2),
            "maintenance": round(sum(v["maintenance"] for v in vehicles), 2),
            "insurance": round(sum(v["insurance"] for v in vehicles), 2),
        }
        totals["profit"] = round(totals["revenue"] - totals["expense"], 2)

        return {
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "vehicles": vehicles,
            "totals": totals,
            "notes": {
                "charter_vehicle_join": has_charter_vehicle,
                "receipt_vehicle_join": has_receipt_vehicle,
                "charter_date_column": charter_date_col,
                "receipt_date_column": receipt_date_col,
            },
        }
    finally:
        conn.close()


@router.get("/driver-costs")
def driver_costs(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Driver payroll cost summary grouped by driver for a period."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    conn = get_connection()
    try:
        has_pay_date = _has_column(conn, "driver_payroll", "pay_date")
        if not has_pay_date:
            raise HTTPException(
                status_code=400, detail="driver_payroll_missing_pay_date"
            )

        columns = []
        if _has_column(conn, "driver_payroll", "employee_id"):
            columns.append("employee_id")
        if _has_column(conn, "driver_payroll", "driver_id"):
            columns.append("driver_id")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'driver_payroll'
                """
            )
            payroll_cols = [r[0] for r in cur.fetchall()]

        has_net = "net_pay" in payroll_cols
        has_gross = "gross_pay" in payroll_cols
        _net_col = "net_pay" if has_net else "gross_pay"
        _gross_col = "gross_pay" if has_gross else "net_pay"

        id_col = columns[0] if columns else None
        name_join = (
            """LEFT JOIN employees e ON e.employee_id = dp.employee_id"""
            if id_col == "employee_id"
            else ""
        )

        if not id_col:
            raise HTTPException(
                status_code=400, detail="driver_payroll_missing_driver_id"
            )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {id_col}, COALESCE(e.full_name, '') AS name,
                       COUNT(*) AS payruns,
                       COALESCE(SUM({_net_col}), 0) AS total_cost,
                       COALESCE(SUM({_gross_col}), 0) AS gross_total
                FROM driver_payroll dp
                {name_join}
                WHERE pay_date BETWEEN %s AND %s
                GROUP BY {id_col}, name
                ORDER BY total_cost DESC
                """,
                (start_dt.date(), end_dt.date()),
            )
            rows = cur.fetchall()

        drivers = [
            {
                "driver_id": r[0],
                "name": r[1] or "",
                "payruns": int(r[2] or 0),
                "total_cost": round(float(r[3] or 0), 2),
                "gross_total": round(float(r[4] or 0), 2),
            }
            for r in rows
        ]

        totals = {
            "total_cost": round(sum(d["total_cost"] for d in drivers), 2),
            "payruns": sum(d["payruns"] for d in drivers),
        }
        return {
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "drivers": drivers,
            "totals": totals,
        }
    finally:
        conn.close()


@router.get("/driver-monthly-costs")
def driver_monthly_costs(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Driver payroll cost grouped by driver and month."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    conn = get_connection()
    try:
        if not _has_column(conn, "driver_payroll", "pay_date"):
            raise HTTPException(
                status_code=400, detail="driver_payroll_missing_pay_date"
            )

        id_col = (
            "employee_id"
            if _has_column(conn, "driver_payroll", "employee_id")
            else "driver_id"
            if _has_column(conn, "driver_payroll", "driver_id")
            else None
        )
        if not id_col:
            raise HTTPException(
                status_code=400, detail="driver_payroll_missing_driver_id"
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DATE_TRUNC('month', pay_date) AS period,
                       {id_col},
                       COALESCE(e.full_name, '') AS name,
                       COUNT(*) AS payruns,
                       COALESCE(SUM(net_pay), 0) AS total_cost,
                       COALESCE(SUM(gross_pay), 0) AS gross_total
                FROM driver_payroll dp
                LEFT JOIN employees e ON e.employee_id = dp.employee_id
                WHERE pay_date BETWEEN %s AND %s
                GROUP BY period, {id_col}, name
                ORDER BY period, name
                """,
                (start_dt.date(), end_dt.date()),
            )
            rows = cur.fetchall()

        periods: dict[str, list[dict[str, Any]]] = {}
        for period, did, name, payruns, total_cost, gross_total in rows:
            key = (
                period.date().isoformat() if hasattr(period, "date")
                else str(period)
            )
            periods.setdefault(key, []).append(
                {
                    "driver_id": did,
                    "name": name,
                    "payruns": int(payruns or 0),
                    "total_cost": round(float(total_cost or 0), 2),
                    "gross_total": round(float(gross_total or 0), 2),
                }
            )

        return {
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "periods": periods,
        }
    finally:
        conn.close()


@router.get("/vehicle-insurance-yearly")
def vehicle_insurance_yearly(years: int = Query(5, ge=1, le=15)):
    """Insurance cost per vehicle per year (description ~ 'insur%')."""
    end_dt = datetime.now().date()
    start_dt = end_dt.replace(year=end_dt.year - years + 1, month=1, day=1)

    conn = get_connection()
    try:
        _has_rdate = _has_column(conn, "receipts", "receipt_date")
        _has_date = _has_column(conn, "receipts", "date")
        if not _has_rdate and not _has_date:
            raise HTTPException(
                status_code=400, detail="receipts_missing_date"
            )
        date_col = "receipt_date" if _has_rdate else "date"

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT vehicle_id,
                       EXTRACT(YEAR FROM {date_col}) AS yr,
                       COALESCE(
                           SUM(CASE WHEN description ILIKE '%insur%'
                               THEN gross_amount ELSE 0 END),
                           0
                       ) AS insurance_cost
                FROM receipts
                WHERE {date_col} BETWEEN %s AND %s
                GROUP BY vehicle_id, yr
                ORDER BY yr DESC, vehicle_id
                """,
                (start_dt, end_dt),
            )
            rows = cur.fetchall()

        data = [
            {
                "vehicle_id": r[0],
                "year": int(r[1]) if r[1] is not None else None,
                "insurance_cost": round(float(r[2] or 0), 2),
            }
            for r in rows
        ]
        return {
            "start_year": int(start_dt.year),
            "end_year": int(end_dt.year),
            "years": years,
            "items": data,
        }
    finally:
        conn.close()


@router.get("/vehicle-damage-summary")
def vehicle_damage_summary(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Damage/claim cost count and totals per vehicle."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    conn = get_connection()
    try:
        date_col = (
            "receipt_date"
            if _has_column(conn, "receipts", "receipt_date")
            else "date"
            if _has_column(conn, "receipts", "date")
            else None
        )
        if not date_col:
            raise HTTPException(
                status_code=400, detail="receipts_missing_date"
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vehicle_id,
                       COUNT(*) AS damage_count,
                       COALESCE(SUM(gross_amount), 0) AS damage_total
                FROM receipts
                WHERE ({date_col} BETWEEN %s AND %s)
                  AND (description ILIKE '%damage%'
                    OR description ILIKE '%claim%'
                    OR description ILIKE '%collision%'
                    OR description ILIKE '%accident%')
                GROUP BY vehicle_id
                ORDER BY damage_total DESC
                """,
                (start_dt.date(), end_dt.date()),
            )
            rows = cur.fetchall()

        data = [
            {
                "vehicle_id": r[0],
                "damage_count": int(r[1] or 0),
                "damage_total": round(float(r[2] or 0), 2),
            }
            for r in rows
        ]

        totals = {
            "damage_count": sum(d["damage_count"] for d in data),
            "damage_total": round(sum(d["damage_total"] for d in data), 2),
        }
        return {
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "items": data,
            "totals": totals,
        }
    finally:
        conn.close()


@router.get("/pl-categories")
def pl_categories(
    start_date: str | None = None,
    end_date: str | None = None,
    granularity: str = Query("month", regex="^(year|quarter|month)$"),
):
    """P&L grouped by account_name and period."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    with cursor() as cur:
        cur.execute(
            """
            SELECT DATE_TRUNC(%s, date) AS period,
                   account_type,
                   account_name,
                   SUM(credit - debit) AS net
            FROM general_ledger
            WHERE date BETWEEN %s AND %s
              AND account_type IS NOT NULL
            GROUP BY 1, account_type, account_name
            ORDER BY 1, account_type, account_name
            """,
            (granularity, start_dt.date(), end_dt.date()),
        )
        rows = cur.fetchall()

    periods: dict[str, list[dict[str, Any]]] = {}
    for period, acct_type, acct_name, net in rows:
        key = (
            period.date().isoformat() if hasattr(period, "date")
            else str(period)
        )
        periods.setdefault(key, []).append(
            {
                "account_type": acct_type,
                "account_name": acct_name,
                "net": round(float(net or 0), 2),
            }
        )

    totals = {
        "revenue": round(
            sum(
                r[3]
                for r in rows
                if (r[1] or "").lower().startswith("income")
                or (r[1] or "").lower().startswith("revenue")
            ),
            2,
        ),
        "expenses": round(
            sum(
                -r[3] for r in rows
                if (r[1] or "").lower().startswith("expense")
            ),
            2,
        ),
    }
    totals["profit"] = round(totals["revenue"] - totals["expenses"], 2)

    return {
        "granularity": granularity,
        "start_date": str(start_dt.date()),
        "end_date": str(end_dt.date()),
        "periods": periods,
        "totals": totals,
    }


@router.get("/vehicle-revenue")
def vehicle_revenue(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Revenue and trip counts per vehicle from charters (defensive joins)."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    conn = get_connection()
    try:
        if not _has_column(conn, "charters", "vehicle_id"):
            raise HTTPException(
                status_code=400, detail="charters_missing_vehicle_id"
            )

        # Prefer pickup_date; fallback to charter_date
        charter_date_col = (
            "pickup_date"
            if _has_column(conn, "charters", "pickup_date")
            else "charter_date"
            if _has_column(conn, "charters", "charter_date")
            else None
        )
        if not charter_date_col:
            raise HTTPException(
                status_code=400, detail="charters_missing_date"
            )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT vehicle_id,
                       COUNT(*) AS trips,
                       COALESCE(SUM(gross_amount), 0) AS revenue
                FROM charters
                WHERE {charter_date_col} BETWEEN %s AND %s
                GROUP BY vehicle_id
                ORDER BY revenue DESC
                """,
                (start_dt.date(), end_dt.date()),
            )
            rows = cur.fetchall()

        data = [
            {
                "vehicle_id": r[0],
                "trips": int(r[1] or 0),
                "revenue": round(float(r[2] or 0), 2),
            }
            for r in rows
        ]
        totals = {
            "trips": sum(d["trips"] for d in data),
            "revenue": round(sum(d["revenue"] for d in data), 2),
        }
        return {
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "vehicles": data,
            "totals": totals,
        }
    finally:
        conn.close()


@router.get("/driver-revenue-vs-pay")
def driver_revenue_vs_pay(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Driver revenue (charters) vs payroll cost (driver_payroll)."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    conn = get_connection()
    try:
        # Determine driver key
        driver_col = (
            "driver_id"
            if _has_column(conn, "charters", "driver_id")
            else "employee_id"
            if _has_column(conn, "charters", "employee_id")
            else None
        )
        if not driver_col:
            raise HTTPException(
                status_code=400, detail="charters_missing_driver"
            )

        date_col = (
            "pickup_date"
            if _has_column(conn, "charters", "pickup_date")
            else "charter_date"
            if _has_column(conn, "charters", "charter_date")
            else None
        )
        if not date_col:
            raise HTTPException(
                status_code=400, detail="charters_missing_date"
            )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                  SELECT {driver_col},
                      COALESCE(SUM(gross_amount), 0) AS revenue,
                      COUNT(*) AS trips
                FROM charters
                WHERE {date_col} BETWEEN %s AND %s
                GROUP BY {driver_col}
                """,
                (start_dt.date(), end_dt.date()),
            )
            rev_rows = cur.fetchall()

        revenue_map = {
            int(r[0] or 0): {
                "revenue": float(r[1] or 0),
                "trips": int(r[2] or 0),
            }
            for r in rev_rows
        }

        # Payroll
        if not _has_column(conn, "driver_payroll", "pay_date"):
            raise HTTPException(
                status_code=400, detail="driver_payroll_missing_pay_date"
            )
        pay_driver_col = (
            "employee_id"
            if _has_column(conn, "driver_payroll", "employee_id")
            else "driver_id"
            if _has_column(conn, "driver_payroll", "driver_id")
            else None
        )
        if not pay_driver_col:
            raise HTTPException(
                status_code=400, detail="driver_payroll_missing_driver_id"
            )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {pay_driver_col},
                       COALESCE(SUM(net_pay), 0) AS net_cost,
                       COALESCE(SUM(gross_pay), 0) AS gross_cost,
                       COUNT(*) AS payruns
                FROM driver_payroll
                WHERE pay_date BETWEEN %s AND %s
                GROUP BY {pay_driver_col}
                """,
                (start_dt.date(), end_dt.date()),
            )
            pay_rows = cur.fetchall()

        data = []
        for did, net_cost, gross_cost, payruns in pay_rows:
            rid = int(did or 0)
            rev = revenue_map.pop(rid, {"revenue": 0.0, "trips": 0})
            profit = rev.get("revenue", 0.0) - float(net_cost or 0)
            data.append(
                {
                    "driver_id": rid,
                    "revenue": round(rev.get("revenue", 0.0), 2),
                    "trips": rev.get("trips", 0),
                    "net_pay": round(float(net_cost or 0), 2),
                    "gross_pay": round(float(gross_cost or 0), 2),
                    "payruns": int(payruns or 0),
                    "profit_after_pay": round(profit, 2),
                    "margin_pct": (
                        round(
                            (profit / rev.get("revenue", 1)) * 100, 2
                        )
                        if rev.get("revenue", 0)
                        else 0.0
                    ),
                }
            )

        # Drivers with revenue but no payroll rows
        for rid, rev in revenue_map.items():
            profit = rev.get("revenue", 0.0)
            data.append(
                {
                    "driver_id": rid,
                    "revenue": round(rev.get("revenue", 0.0), 2),
                    "trips": rev.get("trips", 0),
                    "net_pay": 0.0,
                    "gross_pay": 0.0,
                    "payruns": 0,
                    "profit_after_pay": round(profit, 2),
                    "margin_pct": 100.0,
                }
            )

        totals = {
            "revenue": round(sum(d["revenue"] for d in data), 2),
            "net_pay": round(sum(d["net_pay"] for d in data), 2),
            "profit_after_pay": round(
                sum(d["profit_after_pay"] for d in data), 2
            ),
        }
        return {
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "drivers": data,
            "totals": totals,
        }
    finally:
        conn.close()


@router.get("/bank-reconciliation-suggestions")
def bank_reconciliation_suggestions(
    bank_id: int,
    window_days: int = Query(1, ge=0, le=7),
    max_results: int = Query(200, ge=1, le=1000),
):
    """Suggest receipt matches for unreconciled banking transactions
    by amount/date proximity.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT transaction_id, trans_date, trans_description,
                       COALESCE(debit_amount, 0)
                       - COALESCE(credit_amount, 0) AS amount
                FROM banking_transactions
                WHERE bank_id = %s
                  AND (reconciliation_status IS NULL
                   OR reconciliation_status IN ('unreconciled','ignored'))
                ORDER BY trans_date DESC
                LIMIT %s
                """,
                (bank_id, max_results),
            )
            bank_rows = cur.fetchall()

        suggestions = []
        with conn.cursor() as cur:
            for txn_id, tdate, desc, amt in bank_rows:
                amt = float(amt or 0)
                # Match receipts with same amount (abs) within window
                cur.execute(
                    """
                    SELECT receipt_id, receipt_date, description, gross_amount
                    FROM receipts
                    WHERE ABS(gross_amount) = ABS(%s)
                      AND receipt_date BETWEEN %s AND %s
                    LIMIT 5
                    """,
                    (
                        amt,
                        tdate - timedelta(days=window_days),
                        tdate + timedelta(days=window_days),
                    ),
                )
                recs = cur.fetchall()
                if recs:
                    suggestions.append(
                        {
                            "transaction_id": txn_id,
                            "transaction_date": str(tdate),
                            "amount": round(amt, 2),
                            "description": desc,
                            "candidates": [
                                {
                                    "receipt_id": r[0],
                                    "receipt_date": str(r[1]),
                                    "description": r[2],
                                    "gross_amount": float(r[3] or 0),
                                }
                                for r in recs
                            ],
                        }
                    )
        return {
            "bank_id": bank_id,
            "window_days": window_days,
            "items": suggestions,
        }
    finally:
        conn.close()


@router.get("/fleet-maintenance-summary")
def fleet_maintenance_summary(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Maintenance and insurance cost breakdown per vehicle."""
    end_dt = _parse_iso_date(end_date, datetime.now())
    start_dt = (
        _parse_iso_date(start_date, end_dt - timedelta(days=365))
        if end_date or start_date
        else datetime.now() - timedelta(days=365)
    )

    conn = get_connection()
    try:
        has_vehicle = _has_column(conn, "receipts", "vehicle_id")
        receipt_date_col = (
            "receipt_date"
            if _has_column(conn, "receipts", "receipt_date")
            else "date"
            if _has_column(conn, "receipts", "date")
            else None
        )
        if not has_vehicle or not receipt_date_col:
            raise HTTPException(
                status_code=400, detail="receipts_missing_vehicle_or_date"
            )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT vehicle_id,
                       COALESCE(SUM(gross_amount), 0) AS total_expense,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%maint%'
                                OR category ILIKE 'maintenance%%'
                           THEN gross_amount ELSE 0 END
                       ), 0) AS maintenance,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%repair%'
                           THEN gross_amount ELSE 0 END
                       ), 0) AS repairs,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%insur%'
                                OR category ILIKE 'insurance%%'
                           THEN gross_amount ELSE 0 END
                       ), 0) AS insurance,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%damage%'
                                OR description ILIKE '%claim%'
                           THEN gross_amount ELSE 0 END
                       ), 0) AS damage
                FROM receipts
                WHERE {receipt_date_col} BETWEEN %s AND %s
                GROUP BY vehicle_id
                """,
                (start_dt.date(), end_dt.date()),
            )
            rows = cur.fetchall()

        data = [
            {
                "vehicle_id": r[0],
                "total_expense": round(float(r[1] or 0), 2),
                "maintenance": round(float(r[2] or 0), 2),
                "repairs": round(float(r[3] or 0), 2),
                "insurance": round(float(r[4] or 0), 2),
                "damage": round(float(r[5] or 0), 2),
            }
            for r in rows
        ]

        totals = {
            "total_expense": round(sum(d["total_expense"] for d in data), 2),
            "maintenance": round(sum(d["maintenance"] for d in data), 2),
            "repairs": round(sum(d["repairs"] for d in data), 2),
            "insurance": round(sum(d["insurance"] for d in data), 2),
            "damage": round(sum(d["damage"] for d in data), 2),
        }

        return {
            "start_date": str(start_dt.date()),
            "end_date": str(end_dt.date()),
            "vehicles": data,
            "totals": totals,
        }
    finally:
        conn.close()


@router.get("/cra-audit-export")
def cra_audit_export(
    start_date: str | None = None,
    end_date: str | None = None,
    export_type: str = "full",
):
    """
    Generate CRA audit format export from database

    Args:
        start_date: Start date (YYYY-MM-DD) for transactions
                    (optional, defaults to earliest)
        end_date: End date (YYYY-MM-DD) for transactions
                  (optional, defaults to latest)
        export_type: Type of export - 'full' (all files),
                    'transactions' (transactions only),
                    'summary' (accounts, vendors, employees, trial balance)

    Returns:
        ZIP file containing XML exports in CRA audit format
    """
    import xml.etree.ElementTree as ET
    import zipfile
    from decimal import Decimal
    from xml.dom import minidom

    def prettify_xml(elem):
        """Return a pretty-printed XML string"""
        rough_string = ET.tostring(elem, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Create temporary directory for export files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Build date filter
            date_filter = ""
            date_params = []
            if start_date or end_date:
                if start_date and end_date:
                    date_filter = " WHERE date BETWEEN %s AND %s"
                    date_params = [start_date, end_date]
                elif start_date:
                    date_filter = " WHERE date >= %s"
                    date_params = [start_date]
                elif end_date:
                    date_filter = " WHERE date <= %s"
                    date_params = [end_date]

            # Export accounts if not transactions-only
            if export_type != "transactions":
                cur.execute(
                    """
                    SELECT DISTINCT
                        account_name, account, account_full_name,
                        account_number, account_type
                    FROM general_ledger
                    {date_filter}
                    ORDER BY account_name
                """,
                    date_params,
                )
                accounts = cur.fetchall()

                root = ET.Element("Accounts")
                root.set(
                    "exportDate",
                    datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                )
                root.set("company", "Arrow Limousine & Sedan Ltd.")
                if start_date:
                    root.set("startDate", start_date)
                if end_date:
                    root.set("endDate", end_date)

                for acc in accounts:
                    acc_elem = ET.SubElement(root, "Account")
                    ET.SubElement(acc_elem, "Name").text = str(acc[0] or "")
                    ET.SubElement(
                        acc_elem, "AccountCode"
                    ).text = str(acc[1] or "")
                    ET.SubElement(
                        acc_elem, "FullName"
                    ).text = str(acc[2] or "")
                    ET.SubElement(acc_elem, "Number").text = str(acc[3] or "")
                    ET.SubElement(acc_elem, "Type").text = str(acc[4] or "")

                with open(
                    tmppath / "Accounts.xml", "w", encoding="utf-8"
                ) as f:
                    f.write(prettify_xml(root))

                # Export vendors
                cur.execute(
                    """
                    SELECT DISTINCT
                        supplier,
                        COUNT(*) as transaction_count,
                        MIN(date) as first_transaction,
                        MAX(date) as last_transaction,
                        SUM(debit) as total_debit,
                        SUM(credit) as total_credit
                    FROM general_ledger
                    WHERE supplier IS NOT NULL
                    {' AND date BETWEEN %s AND %s' if start_date and end_date
                     else ' AND date >= %s' if start_date
                     else ' AND date <= %s' if end_date else ''}
                    GROUP BY supplier
                    ORDER BY supplier
                """,
                    date_params if date_params else [],
                )
                vendors = cur.fetchall()

                root = ET.Element("Vendors")
                root.set(
                    "exportDate",
                    datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                )
                root.set("company", "Arrow Limousine & Sedan Ltd.")

                for vendor in vendors:
                    vendor_elem = ET.SubElement(root, "Vendor")
                    ET.SubElement(vendor_elem, "Name").text = str(vendor[0])
                    ET.SubElement(
                        vendor_elem, "TransactionCount"
                    ).text = str(vendor[1])
                    ET.SubElement(
                        vendor_elem, "FirstTransaction"
                    ).text = str(vendor[2])
                    ET.SubElement(
                        vendor_elem, "LastTransaction"
                    ).text = str(vendor[3])
                    ET.SubElement(
                        vendor_elem, "TotalDebit"
                    ).text = str(vendor[4] or 0)
                    ET.SubElement(
                        vendor_elem, "TotalCredit"
                    ).text = str(vendor[5] or 0)

                with open(tmppath / "Vendors.xml", "w", encoding="utf-8") as f:
                    f.write(prettify_xml(root))

                # Export employees
                cur.execute(
                    """
                    SELECT DISTINCT
                        employee,
                        COUNT(*) as transaction_count,
                        MIN(date) as first_transaction,
                        MAX(date) as last_transaction,
                        SUM(debit) as total_debit,
                        SUM(credit) as total_credit
                    FROM general_ledger
                    WHERE employee IS NOT NULL
                    {' AND date BETWEEN %s AND %s' if start_date and end_date
                     else ' AND date >= %s' if start_date
                     else ' AND date <= %s' if end_date else ''}
                    GROUP BY employee
                    ORDER BY employee
                """,
                    date_params if date_params else [],
                )
                employees = cur.fetchall()

                root = ET.Element("Employees")
                root.set(
                    "exportDate",
                    datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                )
                root.set("company", "Arrow Limousine & Sedan Ltd.")

                for emp in employees:
                    emp_elem = ET.SubElement(root, "Employee")
                    ET.SubElement(emp_elem, "Name").text = str(emp[0])
                    ET.SubElement(
                        emp_elem, "TransactionCount"
                    ).text = str(emp[1])
                    ET.SubElement(
                        emp_elem, "FirstTransaction"
                    ).text = str(emp[2])
                    ET.SubElement(
                        emp_elem, "LastTransaction"
                    ).text = str(emp[3])
                    ET.SubElement(
                        emp_elem, "TotalDebit"
                    ).text = str(emp[4] or 0)
                    ET.SubElement(
                        emp_elem, "TotalCredit"
                    ).text = str(emp[5] or 0)

                with open(
                    tmppath / "Employees.xml", "w", encoding="utf-8"
                ) as f:
                    f.write(prettify_xml(root))

                # Export trial balance
                as_of_date = end_date if end_date else datetime.now().date()
                cur.execute(
                    """
                    SELECT
                        account_name, account, account_type,
                        SUM(debit) as total_debit,
                        SUM(credit) as total_credit,
                        SUM(debit) - SUM(credit) as balance
                    FROM general_ledger
                    WHERE date <= %s
                    GROUP BY account_name, account, account_type
                    HAVING SUM(debit) - SUM(credit) != 0
                    ORDER BY account_name
                """,
                    (as_of_date,),
                )
                balances = cur.fetchall()

                root = ET.Element("TrialBalance")
                root.set(
                    "exportDate",
                    datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                )
                root.set("asOfDate", str(as_of_date))
                root.set("company", "Arrow Limousine & Sedan Ltd.")

                total_debits = Decimal(0)
                total_credits = Decimal(0)

                for balance in balances:
                    balance_elem = ET.SubElement(root, "AccountBalance")
                    ET.SubElement(balance_elem, "AccountName").text = str(
                        balance[0] or ""
                    )
                    ET.SubElement(balance_elem, "AccountCode").text = str(
                        balance[1] or ""
                    )
                    ET.SubElement(balance_elem, "AccountType").text = str(
                        balance[2] or ""
                    )
                    ET.SubElement(balance_elem, "TotalDebit").text = str(
                        balance[3] or 0
                    )
                    ET.SubElement(balance_elem, "TotalCredit").text = str(
                        balance[4] or 0
                    )
                    ET.SubElement(
                        balance_elem, "Balance"
                    ).text = str(balance[5] or 0)

                    total_debits += Decimal(balance[3] or 0)
                    total_credits += Decimal(balance[4] or 0)

                summary = ET.SubElement(root, "Summary")
                ET.SubElement(summary, "TotalDebits").text = str(total_debits)
                ET.SubElement(
                    summary, "TotalCredits"
                ).text = str(total_credits)
                ET.SubElement(summary, "Difference").text = str(
                    total_debits - total_credits
                )

                with open(
                    tmppath / "TrialBalance.xml", "w", encoding="utf-8"
                ) as f:
                    f.write(prettify_xml(root))

            # Export transactions if not summary-only
            if export_type != "summary":
                cur.execute(
                    """
                    SELECT
                        id, date, transaction_type, num,
                        name, account_name, account,
                        memo_description, account_full_name,
                        debit, credit, balance,
                        supplier, employee, customer
                    FROM general_ledger
                    {date_filter}
                    ORDER BY date, id
                """,
                    date_params,
                )

                root = ET.Element("Transactions")
                root.set(
                    "exportDate",
                    datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                )
                root.set("company", "Arrow Limousine & Sedan Ltd.")
                if start_date:
                    root.set("startDate", start_date)
                if end_date:
                    root.set("endDate", end_date)

                chunk_size = 10000
                total_exported = 0

                while True:
                    transactions = cur.fetchmany(chunk_size)
                    if not transactions:
                        break

                    for txn in transactions:
                        txn_elem = ET.SubElement(root, "Transaction")
                        ET.SubElement(txn_elem, "ID").text = str(txn[0])
                        ET.SubElement(txn_elem, "Date").text = str(txn[1])
                        ET.SubElement(
                            txn_elem, "Type"
                        ).text = str(txn[2] or "")
                        ET.SubElement(
                            txn_elem, "Number"
                        ).text = str(txn[3] or "")
                        ET.SubElement(
                            txn_elem, "Name"
                        ).text = str(txn[4] or "")
                        ET.SubElement(
                            txn_elem, "AccountName"
                        ).text = str(txn[5] or "")
                        ET.SubElement(
                            txn_elem, "Account"
                        ).text = str(txn[6] or "")
                        ET.SubElement(
                            txn_elem, "Memo"
                        ).text = str(txn[7] or "")
                        ET.SubElement(txn_elem, "AccountFullName").text = str(
                            txn[8] or ""
                        )
                        ET.SubElement(
                            txn_elem, "Debit"
                        ).text = str(txn[9] or 0)
                        ET.SubElement(
                            txn_elem, "Credit"
                        ).text = str(txn[10] or 0)
                        ET.SubElement(
                            txn_elem, "Balance"
                        ).text = str(txn[11] or 0)
                        ET.SubElement(
                            txn_elem, "Supplier"
                        ).text = str(txn[12] or "")
                        ET.SubElement(
                            txn_elem, "Employee"
                        ).text = str(txn[13] or "")
                        ET.SubElement(
                            txn_elem, "Customer"
                        ).text = str(txn[14] or "")

                        total_exported += 1

                with open(
                    tmppath / "Transactions.xml", "w", encoding="utf-8"
                ) as f:
                    f.write(prettify_xml(root))

            # Create README
            cur.execute(
                "SELECT MIN(date), MAX(date), COUNT(*)"
                f" FROM general_ledger{date_filter}",
                date_params,
            )
            min_date, max_date, total_txns = cur.fetchone()

            readme = """CRA AUDIT EXPORT FROM ALMSDATA DATABASE
{'=' * 70}

Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Company: Arrow Limousine & Sedan Ltd.
Database: almsdata (PostgreSQL)
Export Type: {export_type.upper()}

DATA COVERAGE
{'=' * 70}
Transaction Period: {min_date} to {max_date}
Total Transactions: {total_txns:,}
{f'Filter Start Date: {start_date}' if start_date else ''}
{f'Filter End Date: {end_date}' if end_date else ''}

EXPORTED FILES
{'=' * 70}
{'Accounts.xml - Chart of Accounts' if export_type != 'transactions' else ''}
{'Vendors.xml - Vendor List' if export_type != 'transactions' else ''}
{'Employees.xml - Employee List' if export_type != 'transactions' else ''}
{'Transactions.xml - Transaction History' if export_type != 'summary' else ''}
{'TrialBalance.xml - Balances' if export_type != 'transactions' else ''}

FORMAT: XML (QuickBooks CRA audit export compatible)
CURRENCY: CAD (Canadian Dollars)
DATE FORMAT: YYYY-MM-DD

Generated via Arrow Limousine Reports Dashboard
"""

            with open(
                tmppath / "README.txt", "w", encoding="utf-8"
            ) as f:
                f.write(readme)

            # Create ZIP file
            zip_filename = (
                f"CRA_Audit_Export_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            )
            zip_path = tmppath / zip_filename

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file in tmppath.glob("*.xml"):
                    zipf.write(file, file.name)
                zipf.write(tmppath / "README.txt", "README.txt")

            # Return ZIP file
            return FileResponse(
                path=str(zip_path),
                media_type="application/zip",
                filename=zip_filename,
            )

    finally:
        cur.close()
        conn.close()


@router.get("/quickbooks/views")
def get_quickbooks_export_views():
    """Get list of available QuickBooks export views with record counts."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Check if QuickBooks export views exist
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            AND table_name LIKE 'qb_export_%'
            ORDER BY table_name
        """
        )
        views = [row[0] for row in cur.fetchall()]

        if not views:
            return {
                "status": "not_initialized",
                "message": (
                    "QuickBooks export views not found."
                    " Run the migration script first."
                ),
                "migration_script": (
                    "migrations/create_quickbooks_export_views.sql"
                ),
            }

        # Get record count for each view
        view_info = []
        for view_name in views:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {view_name}")
                count = cur.fetchone()[0]

                # Get friendly name
                friendly_name = (
                    view_name
                    .replace("qb_export_", "")
                    .replace("_", " ")
                    .title()
                )

                view_info.append(
                    {
                        "view_name": view_name,
                        "friendly_name": friendly_name,
                        "record_count": count,
                        "export_filename": (
                            f"{friendly_name.replace(' ', '_')}.csv"
                        ),
                    }
                )
            except Exception as e:
                view_info.append(
                    {
                        "view_name": view_name,
                        "friendly_name": view_name,
                        "record_count": 0,
                        "error": str(e),
                    }
                )

        return {
            "status": "ready",
            "views": view_info,
            "total_views": len(view_info),
        }

    finally:
        cur.close()
        conn.close()


@router.get("/quickbooks/export/{view_name}")
def export_quickbooks_view(
    view_name: str,
    format: str = "csv",
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Export a specific QuickBooks view to CSV or Excel format."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Validate view name (security)
        if not view_name.startswith("qb_export_"):
            return Response(
                status_code=400,
                content="Invalid view name. Must start with 'qb_export_'",
            )

        # Check if view exists
        cur.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM information_schema.views
                WHERE table_schema = 'public'
                AND table_name = %s)
        """,
            (view_name,),
        )

        if not cur.fetchone()[0]:
            return Response(
                status_code=404,
                content=f"View '{view_name}' not found",
            )

        # Build query with optional date filtering
        query = f"SELECT * FROM {view_name}"
        params = []

        # Check if view has a "Date" column
        cur.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = %s AND column_name = 'Date'",
            (view_name,),
        )
        has_date_column = cur.fetchone() is not None

        if has_date_column and (start_date or end_date):
            conditions = []
            if start_date:
                conditions.append('"Date" >= %s')
                params.append(start_date)
            if end_date:
                conditions.append('"Date" <= %s')
                params.append(end_date)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        # Execute query
        cur.execute(query, params)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

        if format.lower() == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            writer.writerows(rows)

            # Create filename
            date_suffix = ""
            if start_date and end_date:
                date_suffix = f"_{start_date}_to_{end_date}"
            elif start_date:
                date_suffix = f"_from_{start_date}"
            elif end_date:
                date_suffix = f"_to_{end_date}"

            filename = f"{view_name}{date_suffix}.csv"

            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{filename}"'
                    )
                },
            )

        else:
            return Response(
                status_code=400,
                content="Only CSV format is currently supported",
            )

    finally:
        cur.close()
        conn.close()


@router.get("/quickbooks/export-all")
def export_all_quickbooks_views(
    start_date: str | None = None, end_date: str | None = None
):
    """Export all QuickBooks views to a single ZIP file."""
    import zipfile

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Get all QuickBooks export views
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            AND table_name LIKE 'qb_export_%'
            ORDER BY table_name
        """
        )
        views = [row[0] for row in cur.fetchall()]

        if not views:
            return Response(
                status_code=404,
                content="No QuickBooks export views found",
            )

        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Export each view to CSV
            for view_name in views:
                # Build query with optional date filtering
                query = f"SELECT * FROM {view_name}"
                params = []

                # Check if view has a "Date" column
                cur.execute(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = %s AND column_name = 'Date'",
                    (view_name,),
                )
                has_date_column = cur.fetchone() is not None

                if has_date_column and (start_date or end_date):
                    conditions = []
                    if start_date:
                        conditions.append('"Date" >= %s')
                        params.append(start_date)
                    if end_date:
                        conditions.append('"Date" <= %s')
                        params.append(end_date)

                    if conditions:
                        query += " WHERE " + " AND ".join(conditions)

                # Execute query
                cur.execute(query, params)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]

                # Write to CSV
                csv_filename = f"{view_name}.csv"
                csv_path = tmppath / csv_filename

                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(rows)

            # Create README
            if start_date and end_date:
                date_range_text = f"\nDate Range: {start_date} to {end_date}"
            elif start_date:
                date_range_text = f"\nDate Range: From {start_date}"
            elif end_date:
                date_range_text = f"\nDate Range: Up to {end_date}"
            else:
                date_range_text = ""

            readme = f"""QUICKBOOKS EXPORT FROM ALMSDATA DATABASE
{'=' * 70}

Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Company: Arrow Limousine & Sedan Ltd.
Database: almsdata (PostgreSQL)
Export Type: QuickBooks CSV Import Format{date_range_text}

EXPORTED FILES
{'=' * 70}
"""
            for view_name in views:
                cur.execute(f"SELECT COUNT(*) FROM {view_name}")
                count = cur.fetchone()[0]
                friendly_name = (
                    view_name
                    .replace("qb_export_", "")
                    .replace("_", " ")
                    .title()
                )
                readme += (
                    f"✓ {view_name}.csv - "
                    f"{friendly_name} ({count:,} records)\n"
                )

            readme += """
{'=' * 70}

IMPORT INSTRUCTIONS
{'=' * 70}
1. Open QuickBooks Desktop
2. Go to: File → Utilities → Import → Excel Files
3. Select the CSV file you want to import
4. Follow the import wizard
5. Column names already match QuickBooks format

Note: Import each file separately based on your needs.
Start with Chart of Accounts, then Customers/Vendors, then Transactions.

Generated via Arrow Limousine QuickBooks Dashboard
"""

            with open(
                tmppath / "README.txt", "w", encoding="utf-8"
            ) as f:
                f.write(readme)

            # Create ZIP file
            date_suffix = ""
            if start_date and end_date:
                date_suffix = f"_{start_date}_to_{end_date}"

            zip_filename = (
                f"QuickBooks_Export_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}{date_suffix}.zip"
            )
            zip_path = tmppath / zip_filename

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file in tmppath.glob("*.csv"):
                    zipf.write(file, file.name)
                zipf.write(tmppath / "README.txt", "README.txt")

            # Return ZIP file
            return FileResponse(
                path=str(zip_path),
                media_type="application/zip",
                filename=zip_filename,
            )

    finally:
        cur.close()
        conn.close()


@router.get("/company-snapshot")
def get_company_snapshot(
    date_range: str = "mtd",
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Get company financial snapshot with live data from database."""
    from datetime import datetime, timedelta

    with cursor() as cur:
        # Calculate date range
        end_dt = datetime.now()
        if date_range == "today":
            start_dt = end_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif date_range == "wtd":
            start_dt = end_dt - timedelta(days=end_dt.weekday())
        elif date_range == "mtd":
            start_dt = end_dt.replace(day=1)
        elif date_range == "ytd":
            start_dt = end_dt.replace(month=1, day=1)
        elif (
            date_range == "custom"
            and start_date
            and end_date
        ):
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
        else:
            start_dt = datetime(2000, 1, 1)

        # Get revenue from charters (paid_amount + balance = gross_amount)
        cur.execute(
            """
            SELECT
                COUNT(*) as charter_count,
                COALESCE(SUM(gross_amount), 0) as total_revenue,
                COALESCE(SUM(paid_amount), 0) as paid_revenue,
                COALESCE(SUM(balance), 0) as outstanding_revenue
            FROM charters
            WHERE pickup_date BETWEEN %s AND %s
        """,
            (start_dt.date(), end_dt.date()),
        )
        revenue_data = cur.fetchone()

        # Get expenses from receipts
        cur.execute(
            """
            SELECT
                COUNT(*) as receipt_count,
                COALESCE(SUM(gross_amount), 0) as total_expenses
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
        """,
            (start_dt.date(), end_dt.date()),
        )
        expense_data = cur.fetchone()

        # Get active vehicles
        cur.execute(
            """
            SELECT COUNT(*) as active_vehicles
            FROM vehicles
            WHERE status = 'active' OR status IS NULL
        """
        )
        vehicle_data = cur.fetchone()

        # Calculate totals
        total_revenue = float(revenue_data[1] or 0)
        total_expenses = float(expense_data[1] or 0)
        profit = total_revenue - total_expenses
        profit_margin = (
            (profit / total_revenue * 100) if total_revenue > 0 else 0
        )
        charter_count = int(revenue_data[0] or 0)
        active_vehicles = int(vehicle_data[0] or 0)

        return {
            "sections": [],  # Optional detailed breakdown sections.
            "grandTotals": {
                "name": "NET PROFIT",
                "amount": round(profit, 2),
                "count": charter_count,
                "percent": 100,
                "avgAmount": round(profit / charter_count, 2)
                if charter_count > 0
                else 0,
            },
            "totals": {
                "revenue": round(total_revenue, 2),
                "expenses": round(total_expenses, 2),
                "profit": round(profit, 2),
                "profitMargin": round(profit_margin, 2),
                "revenueChange": 0,  # Needs historical comparison.
                "expensesChange": 0,  # Needs historical comparison.
                "charters": charter_count,
                "activeVehicles": active_vehicles,
            },
        }
