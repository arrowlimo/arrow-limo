"""
Crystal Reports Reproduction Widget  (Phase 1 + Phase 2)

Families implemented:
  Phase 1: Operations Manifest, Reserve List, Sales Summary
  Phase 2: Long Trip, Invoiced Charges, Driver Pay, Fleet

Queries the DB directly (consistent with all other desktop widgets).
No Crystal Reports license required.
"""

import csv
import logging
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from PyQt6.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# Per-family configuration
FAMILY_CONFIG = {
    "Operations Manifest": {
        "key": "manifest",
        "has_date_filter": True,
        "has_cancelled_filter": True,
        "detail_columns": [
            ("Reserve #", "order_number"),
            ("Date", "order_date"),
            ("Client", "passenger_name"),
            ("Account #", "account_number"),
            ("Driver", "driver"),
            ("Vehicle", "vehicle"),
            ("Destination", "destination"),
            ("Charter Type", "run_type"),
            ("Pmt Status", "payment_type"),
            ("Amount Due", "amount"),
            ("Paid", "paid_amount"),
            ("Balance", "balance"),
            ("Status", "status"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Driver": "driver",
            "Vehicle": "vehicle",
            "Pickup Date": "order_date",
            "Payment Status": "payment_type",
            "Account Number": "account_number",
            "Charter Type": "run_type",
            "Status": "status",
            "Destination": "destination",
            "Passenger / Client": "passenger_name",
        },
    },
    "Reserve List": {
        "key": "reserve_list",
        "has_date_filter": True,
        "has_cancelled_filter": True,
        "detail_columns": [
            ("Reserve #", "order_number"),
            ("Date", "order_date"),
            ("Client", "passenger_name"),
            ("Account #", "account_number"),
            ("Driver", "driver"),
            ("Vehicle", "vehicle"),
            ("Destination", "destination"),
            ("Charter Type", "run_type"),
            ("Pmt Status", "payment_type"),
            ("Amount Due", "amount"),
            ("Paid", "paid_amount"),
            ("Balance", "balance"),
            ("Status", "status"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Driver": "driver",
            "Vehicle": "vehicle",
            "Pickup Date": "order_date",
            "Payment Status": "payment_type",
            "Account Number": "account_number",
            "Charter Type": "run_type",
            "Status": "status",
            "Destination": "destination",
            "Passenger / Client": "passenger_name",
        },
    },
    "Sales Summary": {
        "key": "sales_summary",
        "has_date_filter": True,
        "has_cancelled_filter": True,
        "detail_columns": [
            ("Reserve #", "order_number"),
            ("Date", "order_date"),
            ("Client", "passenger_name"),
            ("Account #", "account_number"),
            ("Driver", "driver"),
            ("Charter Type", "run_type"),
            ("Amount Due", "amount"),
            ("Paid", "paid_amount"),
            ("Balance", "balance"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Driver": "driver",
            "Pickup Date": "order_date",
            "Account Number": "account_number",
            "Charter Type": "run_type",
            "Payment Status": "payment_type",
            "Passenger / Client": "passenger_name",
        },
    },
    "Long Trip": {
        "key": "long_trip",
        "has_date_filter": True,
        "has_cancelled_filter": True,
        "detail_columns": [
            ("Reserve #", "order_number"),
            ("Date", "order_date"),
            ("Client", "passenger_name"),
            ("Pickup", "pickup_address"),
            ("Destination", "destination"),
            ("Driver", "driver"),
            ("Vehicle", "vehicle"),
            ("KMs", "total_kms"),
            ("Odom Start", "odometer_start"),
            ("Odom End", "odometer_end"),
            ("Amount Due", "amount"),
            ("Paid", "paid_amount"),
            ("Balance", "balance"),
            ("Status", "status"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Driver": "driver",
            "Vehicle": "vehicle",
            "Pickup Date": "order_date",
            "Destination": "destination",
        },
    },
    "Invoiced Charges": {
        "key": "invoiced_charges",
        "has_date_filter": True,
        "has_cancelled_filter": False,
        "detail_columns": [
            ("Reserve #", "reserve_number"),
            ("Date", "charter_date"),
            ("Client", "client_name"),
            ("Description", "description"),
            ("Charge Type", "charge_type"),
            ("Category", "category"),
            ("Rate", "rate"),
            ("Amount", "amount"),
            ("GST", "gst_amount"),
            ("Account #", "account_number"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Charge Type": "charge_type",
            "Category": "category",
            "Account Number": "account_number",
            "Reserve #": "reserve_number",
        },
    },
    "Driver Pay": {
        "key": "driver_pay",
        "has_date_filter": True,
        "has_cancelled_filter": False,
        "detail_columns": [
            ("Reserve #", "order_number"),
            ("Date", "order_date"),
            ("Driver", "driver"),
            ("Hours", "driver_hours_worked"),
            ("Hourly Rate", "driver_hourly_rate"),
            ("Base Pay", "driver_base_pay"),
            ("Gratuity", "driver_gratuity"),
            ("Total Pay", "driver_total_expense"),
            ("Paid?", "driver_paid"),
            ("Vehicle", "vehicle"),
            ("Charter Type", "run_type"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Driver": "driver",
            "Pickup Date": "order_date",
            "Paid Status": "driver_paid",
            "Charter Type": "run_type",
            "Vehicle": "vehicle",
        },
    },
    "Fleet Status": {
        "key": "fleet",
        "has_date_filter": False,
        "has_cancelled_filter": False,
        "detail_columns": [
            ("Vehicle #", "vehicle_number"),
            ("Make", "make"),
            ("Model", "model"),
            ("Year", "year"),
            ("Plate", "license_plate"),
            ("Type", "vehicle_type"),
            ("Capacity", "passenger_capacity"),
            ("Op. Status", "operational_status"),
            ("Lifecycle", "lifecycle_status"),
            ("CVIP Expiry", "cvip_expiry_date"),
            ("Next Service", "next_service_due"),
            ("Odometer", "odometer"),
            ("Fuel", "fuel_type"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Operational Status": "operational_status",
            "Vehicle Type": "vehicle_type",
            "Vehicle Category": "vehicle_category",
            "Lifecycle Status": "lifecycle_status",
            "Fuel Type": "fuel_type",
        },
    },
    "Client Activity": {
        "key": "client_activity",
        "has_date_filter": True,
        "has_cancelled_filter": True,
        "detail_columns": [
            ("Reserve #", "order_number"),
            ("Date", "order_date"),
            ("Account #", "account_number"),
            ("Company", "company_name"),
            ("Client", "passenger_name"),
            ("Charter Type", "run_type"),
            ("Amount Due", "amount"),
            ("Paid", "paid_amount"),
            ("Balance", "balance"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Account Number": "account_number",
            "Company Name": "company_name",
            "Charter Type": "run_type",
        },
    },
    "Payment List": {
        "key": "payment_list",
        "has_date_filter": True,
        "has_cancelled_filter": False,
        "detail_columns": [
            ("Date", "payment_date"),
            ("Client", "client_name"),
            ("Charter", "charter_id"),
            ("Amount", "amount"),
            ("Method", "payment_method"),
            ("Source", "source"),
            ("Ref", "payment_key"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Payment Method": "payment_method",
            "Source": "source",
            "Client": "client_name",
        },
    },
    "Aged Receivables": {
        "key": "aged_receivables",
        "has_date_filter": False,
        "has_cancelled_filter": True,
        "detail_columns": [
            ("Reserve #", "order_number"),
            ("Date", "order_date"),
            ("Client", "passenger_name"),
            ("Account #", "account_number"),
            ("Driver", "driver"),
            ("Amount Due", "amount"),
            ("Paid", "paid_amount"),
            ("Balance", "balance"),
            ("Days Out", "days_outstanding"),
            ("Age Bracket", "age_bracket"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Age Bracket": "age_bracket",
            "Account Number": "account_number",
            "Driver": "driver",
        },
    },
    "Income Summary": {
        "key": "income_summary",
        "has_date_filter": True,
        "has_cancelled_filter": False,
        "detail_columns": [
            ("Date", "transaction_date"),
            ("Reserve #", "reserve_number"),
            ("Category", "revenue_category"),
            ("Sub-Category", "revenue_subcategory"),
            ("Gross", "gross_amount"),
            ("GST", "gst_collected"),
            ("Net", "net_amount"),
            ("Method", "payment_method"),
            ("Fiscal Year", "fiscal_year"),
            ("Source", "source_system"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Revenue Category": "revenue_category",
            "Fiscal Year": "fiscal_year",
            "Fiscal Quarter": "fiscal_quarter",
            "Payment Method": "payment_method",
            "Source System": "source_system",
        },
    },
    "Short Trip": {
        "key": "short_trip",
        "has_date_filter": True,
        "has_cancelled_filter": True,
        "detail_columns": [
            ("Reserve #", "order_number"),
            ("Date", "order_date"),
            ("Client", "passenger_name"),
            ("Account #", "account_number"),
            ("Driver", "driver"),
            ("Vehicle", "vehicle"),
            ("Destination", "destination"),
            ("Charter Type", "run_type"),
            ("Pmt Status", "payment_type"),
            ("Amount Due", "amount"),
            ("Paid", "paid_amount"),
            ("Balance", "balance"),
            ("Status", "status"),
        ],
        "group_by_options": {
            "(No Grouping)": "none",
            "Driver": "driver",
            "Vehicle": "vehicle",
            "Pickup Date": "order_date",
            "Charter Type": "run_type",
            "Account Number": "account_number",
        },
    },
}

OPS_GROUP_COLUMNS = [
    ("Group", "group_value"),
    ("Runs", "runs"),
    ("Total Amount", "total_amount"),
    ("Total Paid", "total_paid"),
    ("Balance", "total_balance"),
]
CHARGE_GROUP_COLUMNS = [
    ("Group", "group_value"),
    ("Lines", "runs"),
    ("Total Amount", "total_amount"),
    ("Total GST", "total_gst"),
]
PAY_GROUP_COLUMNS = [
    ("Group", "group_value"),
    ("Runs", "runs"),
    ("Total Base Pay", "total_base_pay"),
    ("Total Gratuity", "total_gratuity"),
    ("Total Pay", "total_pay"),
    ("Total Hours", "total_hours"),
]
FLEET_GROUP_COLUMNS = [("Group", "group_value"), ("Count", "runs")]
CLIENT_GROUP_COLUMNS = [
    ("Account #", "group_value"),
    ("Company", "company_name"),
    ("Runs", "runs"),
    ("Total Amount", "total_amount"),
    ("Total Paid", "total_paid"),
    ("Balance", "total_balance"),
]
PLIST_GROUP_COLUMNS = [
    ("Group", "group_value"),
    ("Payments", "runs"),
    ("Total Amount", "total_amount"),
]
AGED_GROUP_COLUMNS = [
    ("Age Bracket", "group_value"),
    ("Count", "runs"),
    ("Total Balance", "total_balance"),
]
INCOME_GROUP_COLUMNS = [
    ("Group", "group_value"),
    ("Lines", "runs"),
    ("Gross", "total_gross"),
    ("GST", "total_gst"),
    ("Net", "total_net"),
]


class _ReportQueryThread(QThread):
    finished = pyqtSignal(list, list, dict)
    error = pyqtSignal(str)

    def __init__(
        self, db, family_key, group_by, start_date, end_date, include_cancelled
    ) -> None:
        super().__init__()
        self.db = db
        self.family_key = family_key
        self.group_by = group_by
        self.start_date = start_date
        self.end_date = end_date
        self.include_cancelled = include_cancelled

    @staticmethod
    def _first_col(cur, table, candidates) -> str | None:
        for col in candidates:
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' "
                "AND table_name=%s AND column_name=%s "
                "LIMIT 1",
                (table, col),
            )
            if cur.fetchone():
                return col
        return None

    @staticmethod
    def _t(col, alias="") -> str:
        expr = f"COALESCE(c.{col}::text,'')" if col else "''"
        return f"{expr} AS {alias}" if alias else expr

    @staticmethod
    def _n(col, alias="", fb="0") -> str:
        expr = f"COALESCE(c.{col}::numeric,{fb})" if col else fb
        return f"{expr} AS {alias}" if alias else expr

    def run(self) -> None:
        try:
            dispatch = {
                "manifest": self._query_ops,
                "reserve_list": self._query_ops,
                "sales_summary": self._query_ops,
                "long_trip": self._query_long_trip,
                "invoiced_charges": self._query_invoiced_charges,
                "driver_pay": self._query_driver_pay,
                "fleet": self._query_fleet,
                "client_activity": self._query_client_activity,
                "payment_list": self._query_payment_list,
                "aged_receivables": self._query_aged_receivables,
                "income_summary": self._query_income_summary,
                "short_trip": self._query_short_trip,
            }
            items, groups, totals = dispatch.get(
                self.family_key, self._query_ops
            )()
            self.finished.emit(items, groups, totals)
        except Exception as exc:
            try:
                if hasattr(self.db, "rollback"):
                    self.db.rollback()
                elif getattr(self.db, "conn", None):
                    self.db.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.exception("Crystal report query failed")
            self.error.emit(str(exc))

    def _query_ops(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:

            def fc(candidates) -> str | None:
                return self._first_col(cur, "charters", candidates)

            date_col = fc(
                ["charter_date", "pickup_date", "order_date", "created_at"]
            )
            reserve_col = fc(["reserve_number", "reserve_no", "order_number"])
            amount_col = fc(
                ["total_amount_due", "amount", "total", "quoted_amount"]
            )
            paid_col = fc(["paid_amount", "total_paid"])
            payment_col = fc(["payment_status", "nrd_method"])
            ctype_col = fc(["charter_type", "run_type"])
            cancel_col = fc(["cancelled"])
            dest_col = fc(["dropoff_address", "destination"])
            client_col = fc(["client_display_name", "client_name"])
            acct_col = fc(["account_number"])
            driver_col = fc(["driver", "driver_name"])
            vehicle_col = fc(["vehicle"])
            status_col = fc(["status"])
            order_date_expr = (
                f"c.{date_col}::date" if date_col else "NULL::date"
            )
            sel = f"""
                SELECT
                    {self._t(reserve_col, 'order_number')},
                    {order_date_expr} AS order_date,
                    {self._t(client_col, 'passenger_name')},
                    {self._t(acct_col, 'account_number')},
                    {self._t(driver_col, 'driver')},
                    {self._t(vehicle_col, 'vehicle')},
                    {self._t(dest_col, 'destination')},
                    {self._t(ctype_col, 'run_type')},
                    {self._t(payment_col, 'payment_type')},
                    {self._n(amount_col, 'amount')},
                    {self._n(paid_col, 'paid_amount')},
                    ({self._n(amount_col)}-{self._n(paid_col)}) AS balance,
                    {self._t(status_col, 'status')}
                FROM charters c"""
            conds, params = [], []
            if date_col:
                conds.append(f"c.{date_col}::date BETWEEN %s AND %s")
                params.extend([self.start_date, self.end_date])
            if not self.include_cancelled and cancel_col:
                conds.append(f"COALESCE(c.{cancel_col},false)=false")
            where = (" WHERE " + " AND ".join(conds)) if conds else ""
            cur.execute(
                sel
                + where
                + " ORDER BY order_date NULLS LAST,order_number LIMIT 5000",
                params,
            )
            col_names = [d[0] for d in cur.description]
        items = []
        while True:
            rows = cur.fetchmany(500)
            if not rows:
                break
            for row in rows:
                rec = dict(zip(col_names, row))
                if hasattr(rec.get("order_date"), "isoformat"):
                    rec["order_date"] = rec["order_date"].isoformat()
                for f in ("amount", "paid_amount", "balance"):
                    rec[f] = float(rec.get(f) or 0)
                items.append(rec)
        return self._agg_ops(items)

    def _agg_ops(self, items) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        totals = {
            "runs": len(items),
            "total_amount": round(sum(i["amount"] for i in items), 2),
            "total_paid": round(sum(i["paid_amount"] for i in items), 2),
            "total_balance": round(sum(i["balance"] for i in items), 2),
        }
        groups = []
        if self.group_by != "none":
            agg = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_paid": 0.0,
                    "total_balance": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(self.group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_paid"] += item["paid_amount"]
                r["total_balance"] += item["balance"]
            groups = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )
        return items, groups, totals

    def _query_long_trip(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:

            def fc(candidates) -> str | None:
                return self._first_col(cur, "charters", candidates)

            date_col = fc(["charter_date", "pickup_date", "created_at"])
            reserve_col = fc(["reserve_number", "reserve_no"])
            amount_col = fc(["total_amount_due", "amount", "total"])
            paid_col = fc(["paid_amount", "total_paid"])
            cancel_col = fc(["cancelled"])
            oot_col = fc(["is_out_of_town"])
            kms_col = fc(["total_kms"])
            client_col = fc(["client_display_name", "client_name"])
            order_date_expr = (
                f"c.{date_col}::date" if date_col else "NULL::date"
            )
            dropoff_expr = self._t(
                fc(["dropoff_address", "destination"]), "destination"
            )
            sel = f"""
                SELECT {self._t(reserve_col, 'order_number')},
                    {order_date_expr} AS order_date,
                    {self._t(client_col, 'passenger_name')},
                    {self._t(fc(['pickup_address']), 'pickup_address')},
                    {dropoff_expr},
                    {self._t(fc(['driver', 'driver_name']), 'driver')},
                    {self._t(fc(['vehicle']), 'vehicle')},
                    {self._n(kms_col, 'total_kms')},
                    {self._n(fc(['odometer_start']), 'odometer_start')},
                    {self._n(fc(['odometer_end']), 'odometer_end')},
                    {self._n(amount_col, 'amount')},
                    {self._n(paid_col, 'paid_amount')},
                    ({self._n(amount_col)}-{self._n(paid_col)}) AS balance,
                    {self._t(fc(['status']), 'status')}
                FROM charters c"""
            conds, params = [], []
            if date_col:
                conds.append(f"c.{date_col}::date BETWEEN %s AND %s")
                params.extend([self.start_date, self.end_date])
            tc = []
            if oot_col:
                tc.append(f"COALESCE(c.{oot_col},false)=true")
            if kms_col:
                tc.append(f"COALESCE(c.{kms_col},0)>0")
            if tc:
                conds.append("(" + " OR ".join(tc) + ")")
            if not self.include_cancelled and cancel_col:
                conds.append(f"COALESCE(c.{cancel_col},false)=false")
            where = (" WHERE " + " AND ".join(conds)) if conds else ""
            cur.execute(
                sel
                + where
                + " ORDER BY order_date NULLS LAST,order_number LIMIT 5000",
                params,
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = []
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
        return self._agg_ops(items)

    def _query_invoiced_charges(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:

            def fc(candidates) -> str | None:
                return self._first_col(cur, "charters", candidates)

            date_col = fc(["charter_date", "pickup_date", "created_at"])
            client_col = fc(["client_display_name", "client_name"])
            date_expr = f"c.{date_col}::date" if date_col else "NULL::date"
            client_expr = (
                f"COALESCE(c.{client_col}::text,'')" if client_col else "''"
            )
            cur.execute(
                f"""
                SELECT cc.reserve_number,{date_expr} AS charter_date,
                    {client_expr} AS client_name,
                    COALESCE(cc.description,'') AS description,
                    COALESCE(cc.charge_type,'') AS charge_type,
                    COALESCE(cc.category,'') AS category,
                    COALESCE(cc.rate,0) AS rate,
                    COALESCE(cc.amount,0) AS amount,
                    COALESCE(cc.gst_amount,0) AS gst_amount,
                    COALESCE(cc.account_number,'') AS account_number
                FROM charter_charges cc
                LEFT JOIN charters c
                    ON CAST(c.charter_id AS TEXT)=CAST(cc.charter_id AS TEXT)
                WHERE {date_expr} BETWEEN %s AND %s
                ORDER BY charter_date NULLS LAST,
                    cc.reserve_number
                LIMIT 10000""",
                [self.start_date, self.end_date],
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("charter_date"), "isoformat"):
                rec["charter_date"] = rec["charter_date"].isoformat()
            for f in ("rate", "amount", "gst_amount"):
                rec[f] = float(rec.get(f) or 0)
            items.append(rec)
        totals = {
            "runs": len(items),
            "total_amount": round(sum(i["amount"] for i in items), 2),
            "total_gst": round(sum(i["gst_amount"] for i in items), 2),
        }
        groups = []
        if self.group_by != "none":
            agg = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_gst": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(self.group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_gst"] += item["gst_amount"]
            groups = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )
        return items, groups, totals

    def _query_driver_pay(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:

            def fc(candidates) -> str | None:
                return self._first_col(cur, "charters", candidates)

            date_col = fc(["charter_date", "pickup_date", "created_at"])
            reserve_col = fc(["reserve_number", "reserve_no"])
            ctype_col = fc(["charter_type", "run_type"])
            hours_col = fc(["driver_hours_worked"])
            rate_col = fc(["driver_hourly_rate"])
            base_col = fc(["driver_base_pay"])
            grat_col = fc(["driver_gratuity"])
            total_col = fc(["driver_total_expense"])
            paid_col = fc(["driver_paid"])
            vehicle_col = fc(["vehicle"])
            driver_col = fc(["driver", "driver_name"])
            date_expr = f"c.{date_col}::date" if date_col else "NULL::date"
            paid_expr = (
                f"COALESCE(c.{paid_col}::text,'')" if paid_col else "''"
            )
            cur.execute(
                f"""
                SELECT {self._t(reserve_col, 'order_number')},
                    {date_expr} AS order_date,
                    {self._t(driver_col, 'driver')},
                    {self._n(hours_col, 'driver_hours_worked')},
                    {self._n(rate_col, 'driver_hourly_rate')},
                    {self._n(base_col, 'driver_base_pay')},
                    {self._n(grat_col, 'driver_gratuity')},
                    {self._n(total_col, 'driver_total_expense')},
                    {paid_expr} AS driver_paid,
                    {self._t(vehicle_col, 'vehicle')},
                    {self._t(ctype_col, 'run_type')}
                FROM charters c
                WHERE {date_expr} BETWEEN %s AND %s
                  AND ({self._n(total_col)}>0 OR {self._n(base_col)}>0)
                ORDER BY order_date NULLS LAST,driver LIMIT 5000""",
                [self.start_date, self.end_date],
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = []
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
        totals = {
            "runs": len(items),
            "total_base_pay": round(
                sum(i["driver_base_pay"] for i in items), 2
            ),
            "total_gratuity": round(
                sum(i["driver_gratuity"] for i in items), 2
            ),
            "total_pay": round(
                sum(i["driver_total_expense"] for i in items), 2
            ),
            "total_hours": round(
                sum(i["driver_hours_worked"] for i in items), 2
            ),
        }
        groups = []
        if self.group_by != "none":
            agg = defaultdict(
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
                gv = str(item.get(self.group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_base_pay"] += item["driver_base_pay"]
                r["total_gratuity"] += item["driver_gratuity"]
                r["total_pay"] += item["driver_total_expense"]
                r["total_hours"] += item["driver_hours_worked"]
            groups = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )
        return items, groups, totals

    def _query_fleet(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    vehicle_number,
                    COALESCE(make,'') AS make,
                    COALESCE(model,'') AS model,
                    COALESCE(year::text,'') AS year,
                    COALESCE(license_plate,'') AS license_plate,
                    COALESCE(vehicle_type,'') AS vehicle_type,
                    COALESCE(vehicle_category,'') AS vehicle_category,
                    COALESCE(passenger_capacity::text,'')
                        AS passenger_capacity,
                    COALESCE(operational_status,'') AS operational_status,
                    COALESCE(lifecycle_status,'') AS lifecycle_status,
                    COALESCE(cvip_expiry_date::text,'') AS cvip_expiry_date,
                    COALESCE(next_service_due::text,'') AS next_service_due,
                    COALESCE(odometer::text,'') AS odometer,
                    COALESCE(fuel_type,'') AS fuel_type,
                    COALESCE(status,'') AS status
                FROM vehicles
                ORDER BY vehicle_number""")
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = [dict(zip(col_names, row)) for row in rows]
        totals = {"runs": len(items)}
        groups = []
        if self.group_by != "none":
            agg = defaultdict(lambda: {"group_value": "", "runs": 0})
            for item in items:
                gv = str(item.get(self.group_by) or "")
                agg[gv]["group_value"] = gv
                agg[gv]["runs"] += 1
            groups = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )
        return items, groups, totals

    def _query_client_activity(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:

            def fc(candidates) -> str | None:
                return self._first_col(cur, "charters", candidates)

            def fcc(candidates) -> str | None:
                return self._first_col(cur, "clients", candidates)

            date_col = fc(["charter_date", "pickup_date", "created_at"])
            reserve_col = fc(["reserve_number", "reserve_no", "order_number"])
            amount_col = fc(["total_amount_due", "amount", "total"])
            paid_col = fc(["paid_amount", "total_paid"])
            cancel_col = fc(["cancelled"])
            acct_col = fc(["account_number"])
            client_col = fc(["client_display_name", "client_name"])
            ctype_col = fc(["charter_type", "run_type"])
            acct_cl = fcc(["account_number"])
            company_col = fcc(["company_name", "client_name", "name"])
            date_expr = f"c.{date_col}::date" if date_col else "NULL::date"
            company_expr = (
                f"COALESCE(cl.{company_col}::text,'')" if company_col else "''"
            )
            acct_join = (
                f"c.{acct_col} =cl.{acct_cl} "
                if acct_col and acct_cl
                else "false"
            )
            conds, params = [], []
            if date_col:
                conds.append(f"c.{date_col}::date BETWEEN %s AND %s")
                params.extend([self.start_date, self.end_date])
            if not self.include_cancelled and cancel_col:
                conds.append(f"COALESCE(c.{cancel_col},false)=false")
            where = (" WHERE " + " AND ".join(conds)) if conds else ""
            cur.execute(
                f"""
                SELECT {self._t(reserve_col, 'order_number')},
                    {date_expr} AS order_date,
                    {self._t(acct_col, 'account_number')},
                    {company_expr} AS company_name,
                    {self._t(client_col, 'passenger_name')},
                    {self._t(ctype_col, 'run_type')},
                    {self._n(amount_col, 'amount')},
                    {self._n(paid_col, 'paid_amount')},
                    ({self._n(amount_col)}-{self._n(paid_col)}) AS balance
                FROM charters c LEFT JOIN clients cl ON {acct_join}
                {where} ORDER BY account_number,order_date LIMIT 5000""",
                params,
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = []
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
        groups = []
        if self.group_by != "none":
            agg = defaultdict(
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
                gv = str(item.get(self.group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["company_name"] = item.get("company_name", "")
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_paid"] += item["paid_amount"]
                r["total_balance"] += item["balance"]
            groups = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )
        return items, groups, totals

    def _query_payment_list(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payment_date,
                    COALESCE(client_name,'') AS client_name,
                    COALESCE(charter_id::text,'') AS charter_id,
                    COALESCE(amount,0) AS amount,
                    COALESCE(payment_method,'') AS payment_method,
                    COALESCE(source,'') AS source,
                    COALESCE(payment_key,'') AS payment_key
                FROM charter_payments
                WHERE payment_date BETWEEN %s AND %s
                ORDER BY payment_date,client_name LIMIT 10000""",
                [self.start_date, self.end_date],
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = []
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
        groups = []
        if self.group_by != "none":
            agg = defaultdict(
                lambda: {"group_value": "", "runs": 0, "total_amount": 0.0}
            )
            for item in items:
                gv = str(item.get(self.group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_amount"] += item["amount"]
            groups = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )
        return items, groups, totals

    def _query_aged_receivables(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:

            def fc(candidates) -> str | None:
                return self._first_col(cur, "charters", candidates)

            date_col = fc(["charter_date", "pickup_date", "created_at"])
            reserve_col = fc(["reserve_number", "reserve_no", "order_number"])
            amount_col = fc(["total_amount_due", "amount", "total"])
            paid_col = fc(["paid_amount", "total_paid"])
            cancel_col = fc(["cancelled"])
            acct_col = fc(["account_number"])
            client_col = fc(["client_display_name", "client_name"])
            driver_col = fc(["driver", "driver_name"])
            date_expr = f"c.{date_col}::date" if date_col else "NULL::date"
            conds = []
            params = []
            if not self.include_cancelled and cancel_col:
                conds.append(f"COALESCE(c.{cancel_col},false)=false")
            extra = (" AND " + " AND ".join(conds)) if conds else ""
            cur.execute(
                f"""
                SELECT {self._t(reserve_col, 'order_number')},
                    {date_expr} AS order_date,
                    {self._t(client_col, 'passenger_name')},
                    {self._t(acct_col, 'account_number')},
                    {self._t(driver_col, 'driver')},
                    {self._n(amount_col, 'amount')},
                    {self._n(paid_col, 'paid_amount')},
                    ({self._n(amount_col)}-{self._n(paid_col)}) AS balance,
                    (CURRENT_DATE - COALESCE({date_expr},
                    CURRENT_DATE))::int AS days_outstanding,
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
                WHERE ({self._n(amount_col)}-{self._n(paid_col)})>0{extra}
                ORDER BY order_date NULLS LAST LIMIT 5000""",
                params,
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = []
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
        groups = []
        if self.group_by != "none":
            agg = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_amount": 0.0,
                    "total_balance": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(self.group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_amount"] += item["amount"]
                r["total_balance"] += item["balance"]
            groups = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )
        return items, groups, totals

    def _query_income_summary(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:
            cur.execute(
                """
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
                ORDER BY transaction_date,revenue_category LIMIT 10000""",
                [self.start_date, self.end_date],
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("transaction_date"), "isoformat"):
                rec["transaction_date"] = rec["transaction_date"].isoformat()
            for f in ("gross_amount", "gst_collected", "net_amount"):
                rec[f] = float(rec.get(f) or 0)
            items.append(rec)
        totals = {
            "runs": len(items),
            "total_gross": round(sum(i["gross_amount"] for i in items), 2),
            "total_gst": round(sum(i["gst_collected"] for i in items), 2),
            "total_net": round(sum(i["net_amount"] for i in items), 2),
        }
        groups = []
        if self.group_by != "none":
            agg = defaultdict(
                lambda: {
                    "group_value": "",
                    "runs": 0,
                    "total_gross": 0.0,
                    "total_gst": 0.0,
                    "total_net": 0.0,
                }
            )
            for item in items:
                gv = str(item.get(self.group_by) or "")
                r = agg[gv]
                r["group_value"] = gv
                r["runs"] += 1
                r["total_gross"] += item["gross_amount"]
                r["total_gst"] += item["gst_collected"]
                r["total_net"] += item["net_amount"]
            groups = sorted(
                agg.values(), key=lambda x: (x["group_value"] or "").lower()
            )
        return items, groups, totals

    def _query_short_trip(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        conn = self.db.conn
        with conn.cursor() as cur:

            def fc(candidates) -> str | None:
                return self._first_col(cur, "charters", candidates)

            date_col = fc(
                ["charter_date", "pickup_date", "order_date", "created_at"]
            )
            reserve_col = fc(["reserve_number", "reserve_no", "order_number"])
            amount_col = fc(
                ["total_amount_due", "amount", "total", "quoted_amount"]
            )
            paid_col = fc(["paid_amount", "total_paid"])
            payment_col = fc(["payment_status", "nrd_method"])
            ctype_col = fc(["charter_type", "run_type"])
            cancel_col = fc(["cancelled"])
            dest_col = fc(["dropoff_address", "destination"])
            client_col = fc(["client_display_name", "client_name"])
            acct_col = fc(["account_number"])
            driver_col = fc(["driver", "driver_name"])
            vehicle_col = fc(["vehicle"])
            status_col = fc(["status"])
            oot_col = fc(["is_out_of_town"])
            kms_col = fc(["total_kms"])
            order_date_expr = (
                f"c.{date_col}::date" if date_col else "NULL::date"
            )
            sel = f"""
                SELECT {self._t(reserve_col, 'order_number')},
                    {order_date_expr} AS order_date,
                    {self._t(client_col, 'passenger_name')},
                    {self._t(acct_col, 'account_number')},
                    {self._t(driver_col, 'driver')},
                    {self._t(vehicle_col, 'vehicle')},
                    {self._t(dest_col, 'destination')},
                    {self._t(ctype_col, 'run_type')},
                    {self._t(payment_col, 'payment_type')},
                    {self._n(amount_col, 'amount')},
                    {self._n(paid_col, 'paid_amount')},
                    ({self._n(amount_col)}-{self._n(paid_col)}) AS balance,
                    {self._t(status_col, 'status')}
                FROM charters c"""
            conds, params = [], []
            if date_col:
                conds.append(f"c.{date_col}::date BETWEEN %s AND %s")
                params.extend([self.start_date, self.end_date])
            short_conds = []
            if oot_col:
                short_conds.append(f"COALESCE(c.{oot_col},false)=false")
            if kms_col:
                short_conds.append(f"COALESCE(c.{kms_col},0)=0")
            if short_conds:
                conds.append("(" + " AND ".join(short_conds) + ")")
            if not self.include_cancelled and cancel_col:
                conds.append(f"COALESCE(c.{cancel_col},false)=false")
            where = (" WHERE " + " AND ".join(conds)) if conds else ""
            cur.execute(
                sel
                + where
                + " ORDER BY order_date NULLS LAST,order_number LIMIT 5000",
                params,
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        items = []
        for row in rows:
            rec = dict(zip(col_names, row))
            if hasattr(rec.get("order_date"), "isoformat"):
                rec["order_date"] = rec["order_date"].isoformat()
            for f in ("amount", "paid_amount", "balance"):
                rec[f] = float(rec.get(f) or 0)
            items.append(rec)
        return self._agg_ops(items)


class CrystalReportsWidget(QWidget):
    """Crystal-style grouped reports for Arrow Limo — Phase 1 + Phase 2 +"
    "Phase 3."""

    _MONEY_KEYS = frozenset(
        {
            "amount",
            "paid_amount",
            "balance",
            "total_amount",
            "total_paid",
            "total_balance",
            "rate",
            "gst_amount",
            "total_gst",
            "driver_base_pay",
            "driver_gratuity",
            "driver_total_expense",
            "driver_hourly_rate",
            "total_base_pay",
            "total_gratuity",
            "total_pay",
            "gross_amount",
            "gst_collected",
            "net_amount",
            "total_gross",
            "total_net",
        }
    )
    _RIGHT_KEYS = frozenset(
        {
            "total_kms",
            "odometer_start",
            "odometer_end",
            "driver_hours_worked",
            "total_hours",
            "runs",
            "passenger_capacity",
            "days_outstanding",
        }
    )

    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self._items = []
        self._groups = []
        self._totals = {}
        self._thread = None
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        title = QLabel("Crystal-Style Operations Reports")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        root.addWidget(title)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Report Family:"))
        self.family_combo = QComboBox()
        self.family_combo.setMinimumWidth(180)
        for lbl in FAMILY_CONFIG:
            self.family_combo.addItem(lbl)
        self.family_combo.currentTextChanged.connect(self._on_family_changed)
        row1.addWidget(self.family_combo)
        row1.addSpacing(16)
        row1.addWidget(QLabel("Group By:"))
        self.group_combo = QComboBox()
        self.group_combo.setMinimumWidth(180)
        row1.addWidget(self.group_combo)
        row1.addStretch()
        root.addLayout(row1)

        row2 = QHBoxLayout()
        self.date_from_lbl = QLabel("From:")
        row2.addWidget(self.date_from_lbl)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate().addYears(-1).addDays(1))
        row2.addWidget(self.start_date)
        self.date_to_lbl = QLabel("To:")
        row2.addWidget(self.date_to_lbl)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        row2.addWidget(self.end_date)
        row2.addSpacing(16)
        self.cancelled_chk = QCheckBox("Include Cancelled")
        self.cancelled_chk.setChecked(True)
        row2.addWidget(self.cancelled_chk)
        row2.addStretch()
        root.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Client:"))
        self.client_filter = QComboBox()
        self.client_filter.setMinimumWidth(180)
        self.client_filter.addItem("All clients", "")
        row3.addWidget(self.client_filter)
        row3.addWidget(QLabel("Reserve #:"))
        self.reserve_filter = QLineEdit()
        self.reserve_filter.setPlaceholderText("All charters")
        self.reserve_filter.setClearButtonEnabled(True)
        self.reserve_filter.setMinimumWidth(120)
        row3.addWidget(self.reserve_filter)
        row3.addWidget(QLabel("Driver:"))
        self.driver_filter = QComboBox()
        self.driver_filter.setMinimumWidth(160)
        self.driver_filter.addItem("All drivers", "")
        row3.addWidget(self.driver_filter)
        row3.addWidget(QLabel("Vehicle:"))
        self.vehicle_filter = QComboBox()
        self.vehicle_filter.setMinimumWidth(140)
        self.vehicle_filter.addItem("All vehicles", "")
        row3.addWidget(self.vehicle_filter)
        row3.addStretch()
        root.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Year:"))
        self.year_filter = QComboBox()
        self.year_filter.addItem("All Years", None)
        current_year = date.today().year
        for year in range(current_year + 1, current_year - 15, -1):
            self.year_filter.addItem(str(year), year)
        row4.addWidget(self.year_filter)
        row4.addWidget(QLabel("Month:"))
        self.month_filter = QComboBox()
        self.month_filter.addItem("All Months", None)
        for month_number, month_name in enumerate(
            (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ),
            start=1,
        ):
            self.month_filter.addItem(month_name, month_number)
        row4.addWidget(self.month_filter)
        row4.addWidget(QLabel("Pay Period:"))
        self.pay_period_filter = QComboBox()
        self.pay_period_filter.addItem("All Periods", "all")
        self.pay_period_filter.addItem("Days 1-15", "first_half")
        self.pay_period_filter.addItem("Days 16-end", "second_half")
        row4.addWidget(self.pay_period_filter)
        row4.addWidget(QLabel("Balance:"))
        self.balance_filter = QComboBox()
        self.balance_filter.addItem("All Statuses", "all")
        self.balance_filter.addItem("Paid / Zero Balance", "paid")
        self.balance_filter.addItem("Outstanding Balance", "outstanding")
        row4.addWidget(self.balance_filter)
        self.clear_filters_btn = QPushButton("Clear Filters")
        self.clear_filters_btn.clicked.connect(self._clear_local_filters)
        row4.addWidget(self.clear_filters_btn)
        row4.addStretch()
        root.addLayout(row4)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("▶  Run Report")
        self.run_btn.setFixedHeight(32)
        self.run_btn.clicked.connect(self._run_report)
        btn_row.addWidget(self.run_btn)
        self.csv_btn = QPushButton("⬇  Export CSV")
        self.csv_btn.setEnabled(False)
        self.csv_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(self.csv_btn)
        self.print_btn = QPushButton("🖨  Print Preview")
        self.print_btn.setEnabled(False)
        self.print_btn.clicked.connect(self._print_preview)
        btn_row.addWidget(self.print_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.status_label = QLabel(
            "Select a report family and click Run Report."
        )
        self.status_label.setStyleSheet("color: #666;")
        root.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self.table)

        self._on_family_changed(self.family_combo.currentText())

    def _on_family_changed(self, family_label) -> None:
        cfg = FAMILY_CONFIG.get(family_label, {})
        options = cfg.get("group_by_options", {"(No Grouping)": "none"})
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        for lbl in options:
            self.group_combo.addItem(lbl)
        self.group_combo.blockSignals(False)
        has_date = cfg.get("has_date_filter", True)
        has_cancel = cfg.get("has_cancelled_filter", True)
        for w in (
            self.date_from_lbl,
            self.start_date,
            self.date_to_lbl,
            self.end_date,
        ):
            w.setVisible(has_date)
        self.cancelled_chk.setVisible(has_cancel)
        has_vehicle = any(
            key == "vehicle"
            for _, key in cfg.get("detail_columns", [])
        )
        has_driver = any(
            key == "driver"
            for _, key in cfg.get("detail_columns", [])
        )
        has_reserve = any(
            key in {"order_number", "reserve_number", "charter_id"}
            for _, key in cfg.get("detail_columns", [])
        )
        self.reserve_filter.setVisible(has_reserve)
        self.vehicle_filter.setVisible(has_vehicle)
        self.driver_filter.setVisible(has_driver)
        self.year_filter.setVisible(has_date)
        self.month_filter.setVisible(has_date)
        self.pay_period_filter.setVisible(has_date)
        self.balance_filter.setVisible(
            any(key == "balance" for _, key in cfg.get("detail_columns", []))
        )

    def _run_report(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        try:
            if hasattr(self.db, "rollback"):
                self.db.rollback()
            elif getattr(self.db, "conn", None):
                self.db.conn.rollback()
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
        family_label = self.family_combo.currentText()
        cfg = FAMILY_CONFIG.get(family_label, {})
        family_key = cfg.get("key", "manifest")
        group_label = self.group_combo.currentText()
        group_by = cfg.get("group_by_options", {}).get(group_label, "none")
        qstart = self.start_date.date()
        qend = self.end_date.date()
        start = date(qstart.year(), qstart.month(), qstart.day())
        end = date(qend.year(), qend.month(), qend.day())
        self.run_btn.setEnabled(False)
        self.csv_btn.setEnabled(False)
        self.print_btn.setEnabled(False)
        self.status_label.setText("Running query…")
        self.table.setRowCount(0)
        self._thread = _ReportQueryThread(
            self.db,
            family_key,
            group_by,
            start,
            end,
            self.cancelled_chk.isChecked(),
        )
        self._thread.finished.connect(self._on_results)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_results(self, items, groups, totals) -> None:
        family_label = self.family_combo.currentText()
        self._refresh_selector_options(items)
        filtered_items = self._apply_local_filters(items, family_label)
        filtered_groups, filtered_totals = self._rebuild_filtered_results(
            filtered_items, family_label
        )
        self._items = filtered_items
        self._groups = filtered_groups
        self._totals = filtered_totals
        self.run_btn.setEnabled(True)
        self.csv_btn.setEnabled(True)
        self.print_btn.setEnabled(True)
        grouped = self.group_combo.currentText() != "(No Grouping)"
        if grouped:
            self._populate_grouped(filtered_groups, family_label)
        else:
            self._populate_detail(filtered_items, family_label)
        self._update_status(filtered_totals, family_label)

    def _on_error(self, msg) -> None:
        try:
            if hasattr(self.db, "rollback"):
                self.db.rollback()
            elif getattr(self.db, "conn", None):
                self.db.conn.rollback()
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
        self.run_btn.setEnabled(True)
        self.status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Report Error", msg)

    def _update_status(self, totals, family_label) -> None:
        runs = totals.get("runs", 0)
        key = FAMILY_CONFIG.get(family_label, {}).get("key", "")
        if key == "fleet":
            self.status_label.setText(f"{runs} vehicles")
        elif key == "driver_pay":
            self.status_label.setText(
                f"{runs} runs  |  Base Pay: ${totals.get('total_base_pay', 0):,.2f}"
                f"  |  Gratuity: ${totals.get('total_gratuity', 0):,.2f}"
                f"  |  Total Pay: ${totals.get('total_pay', 0):,.2f}"
                f"  |  Hours: {totals.get('total_hours', 0):,.1f}"
            )
        elif key == "invoiced_charges":
            self.status_label.setText(
                f"{runs} lines  |  Amount: ${totals.get('total_amount', 0):,.2f}"
                f"  |  GST: ${totals.get('total_gst', 0):,.2f}"
            )
        elif key == "payment_list":
            self.status_label.setText(
                f"{runs} payments  |  Total: ${totals.get('total_amount', 0):,.2f}"
            )
        elif key == "aged_receivables":
            self.status_label.setText(
                f"{runs} outstanding  |  Total Owed: ${totals.get('total_amount', 0):,.2f}"
                f"  |  Balance: ${totals.get('total_balance', 0):,.2f}"
            )
        elif key == "income_summary":
            self.status_label.setText(
                f"{runs} entries  |  Gross: ${totals.get('total_gross', 0):,.2f}"
                f"  |  GST: ${totals.get('total_gst', 0):,.2f}"
                f"  |  Net: ${totals.get('total_net', 0):,.2f}"
            )
        else:
            self.status_label.setText(
                f"{runs} runs  |  Amount: ${totals.get('total_amount', 0):,.2f}"
                f"  |  Paid: ${totals.get('total_paid', 0):,.2f}"
                f"  |  Balance: ${totals.get('total_balance', 0):,.2f}"
            )

    def _get_detail_cols(self, family_label) -> list[tuple[str, str]]:
        return FAMILY_CONFIG.get(family_label, {}).get("detail_columns", [])

    def _get_group_cols(self, family_label) -> list[tuple[str, str]]:
        key = FAMILY_CONFIG.get(family_label, {}).get("key", "")
        if key == "invoiced_charges":
            return CHARGE_GROUP_COLUMNS
        if key == "driver_pay":
            return PAY_GROUP_COLUMNS
        if key == "fleet":
            return FLEET_GROUP_COLUMNS
        if key == "client_activity":
            return CLIENT_GROUP_COLUMNS
        if key == "payment_list":
            return PLIST_GROUP_COLUMNS
        if key == "aged_receivables":
            return AGED_GROUP_COLUMNS
        if key == "income_summary":
            return INCOME_GROUP_COLUMNS
        return OPS_GROUP_COLUMNS

    def _clear_local_filters(self) -> None:
        self.client_filter.setCurrentIndex(0)
        self.reserve_filter.clear()
        self.driver_filter.setCurrentIndex(0)
        self.vehicle_filter.setCurrentIndex(0)
        self.year_filter.setCurrentIndex(0)
        self.month_filter.setCurrentIndex(0)
        self.pay_period_filter.setCurrentIndex(0)
        self.balance_filter.setCurrentIndex(0)

    def _refresh_selector_options(self, items) -> None:
        self._set_combo_values(
            self.client_filter,
            "All clients",
            self._collect_filter_values(
                items,
                ["passenger_name", "client_name", "company_name"],
            ),
        )
        self._set_combo_values(
            self.driver_filter,
            "All drivers",
            self._collect_filter_values(items, ["driver"]),
        )
        self._set_combo_values(
            self.vehicle_filter,
            "All vehicles",
            self._collect_filter_values(items, ["vehicle", "vehicle_number"]),
        )

    @staticmethod
    def _collect_filter_values(items, keys) -> list[str]:
        values = set()
        for item in items:
            for key in keys:
                value = str(item.get(key) or "").strip()
                if value:
                    values.add(value)
        return sorted(values, key=str.lower)

    @staticmethod
    def _set_combo_values(combo, default_label, values) -> None:
        current_value = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(default_label, "")
        for value in values:
            combo.addItem(value, value)
        restore_index = combo.findData(current_value)
        combo.setCurrentIndex(restore_index if restore_index >= 0 else 0)
        combo.blockSignals(False)

    def _parse_item_date(self, item) -> date | None:
        for key in ("order_date", "charter_date", "payment_date", "transaction_date"):
            raw_value = item.get(key)
            if not raw_value:
                continue
            if isinstance(raw_value, datetime):
                return raw_value.date()
            if isinstance(raw_value, date):
                return raw_value
            try:
                return datetime.fromisoformat(str(raw_value)).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _matches_text_filter(value, needle) -> bool:
        return needle in str(value or "").strip().lower()

    def _apply_local_filters(self, items, family_label) -> list[dict[str, Any]]:
        client_text = str(self.client_filter.currentData() or "").strip().lower()
        reserve_text = self.reserve_filter.text().strip().lower()
        driver_text = str(self.driver_filter.currentData() or "").strip().lower()
        vehicle_text = str(self.vehicle_filter.currentData() or "").strip().lower()
        year_value = self.year_filter.currentData()
        month_value = self.month_filter.currentData()
        pay_period_value = self.pay_period_filter.currentData()
        balance_value = self.balance_filter.currentData()

        filtered = []
        for item in items:
            if client_text and not any(
                self._matches_text_filter(item.get(key), client_text)
                for key in ("passenger_name", "client_name", "company_name", "group_value")
            ):
                continue
            if reserve_text and not any(
                self._matches_text_filter(item.get(key), reserve_text)
                for key in ("order_number", "reserve_number", "charter_id")
            ):
                continue
            if driver_text and not self._matches_text_filter(
                item.get("driver"), driver_text
            ):
                continue
            if vehicle_text and not self._matches_text_filter(
                item.get("vehicle") or item.get("vehicle_number"),
                vehicle_text,
            ):
                continue

            item_date = self._parse_item_date(item)
            if year_value and item_date and item_date.year != year_value:
                continue
            if month_value and item_date and item_date.month != month_value:
                continue
            if pay_period_value == "first_half" and item_date and item_date.day > 15:
                continue
            if pay_period_value == "second_half" and item_date and item_date.day < 16:
                continue

            balance = item.get("balance")
            if balance_value == "paid" and balance is not None and float(balance) > 0.005:
                continue
            if balance_value == "outstanding" and (
                balance is None or float(balance) <= 0.005
            ):
                continue

            filtered.append(item)
        return filtered

    def _rebuild_filtered_results(self, items, family_label) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        key = FAMILY_CONFIG.get(family_label, {}).get("key", "")
        group_label = self.group_combo.currentText()
        group_by = FAMILY_CONFIG.get(family_label, {}).get(
            "group_by_options", {}
        ).get(group_label, "none")

        if key in {"manifest", "reserve_list", "sales_summary", "long_trip", "short_trip"}:
            totals = {
                "runs": len(items),
                "total_amount": round(sum(float(i.get("amount") or 0) for i in items), 2),
                "total_paid": round(sum(float(i.get("paid_amount") or 0) for i in items), 2),
                "total_balance": round(sum(float(i.get("balance") or 0) for i in items), 2),
            }
            groups = self._group_rows(
                items,
                group_by,
                {
                    "total_amount": "amount",
                    "total_paid": "paid_amount",
                    "total_balance": "balance",
                },
            )
            return groups, totals
        if key == "invoiced_charges":
            totals = {
                "runs": len(items),
                "total_amount": round(sum(float(i.get("amount") or 0) for i in items), 2),
                "total_gst": round(sum(float(i.get("gst_amount") or 0) for i in items), 2),
            }
            groups = self._group_rows(
                items,
                group_by,
                {"total_amount": "amount", "total_gst": "gst_amount"},
            )
            return groups, totals
        if key == "driver_pay":
            totals = {
                "runs": len(items),
                "total_base_pay": round(sum(float(i.get("driver_base_pay") or 0) for i in items), 2),
                "total_gratuity": round(sum(float(i.get("driver_gratuity") or 0) for i in items), 2),
                "total_pay": round(sum(float(i.get("driver_total_expense") or 0) for i in items), 2),
                "total_hours": round(sum(float(i.get("driver_hours_worked") or 0) for i in items), 2),
            }
            groups = self._group_rows(
                items,
                group_by,
                {
                    "total_base_pay": "driver_base_pay",
                    "total_gratuity": "driver_gratuity",
                    "total_pay": "driver_total_expense",
                    "total_hours": "driver_hours_worked",
                },
            )
            return groups, totals
        if key == "fleet":
            totals = {"runs": len(items)}
            groups = self._group_rows(items, group_by, {})
            return groups, totals
        if key == "client_activity":
            totals = {
                "runs": len(items),
                "total_amount": round(sum(float(i.get("amount") or 0) for i in items), 2),
                "total_paid": round(sum(float(i.get("paid_amount") or 0) for i in items), 2),
                "total_balance": round(sum(float(i.get("balance") or 0) for i in items), 2),
            }
            groups = self._group_rows(
                items,
                group_by,
                {
                    "company_name": "company_name",
                    "total_amount": "amount",
                    "total_paid": "paid_amount",
                    "total_balance": "balance",
                },
            )
            return groups, totals
        if key == "payment_list":
            totals = {
                "runs": len(items),
                "total_amount": round(sum(float(i.get("amount") or 0) for i in items), 2),
            }
            groups = self._group_rows(items, group_by, {"total_amount": "amount"})
            return groups, totals
        if key == "aged_receivables":
            totals = {
                "runs": len(items),
                "total_amount": round(sum(float(i.get("amount") or 0) for i in items), 2),
                "total_paid": round(sum(float(i.get("paid_amount") or 0) for i in items), 2),
                "total_balance": round(sum(float(i.get("balance") or 0) for i in items), 2),
            }
            groups = self._group_rows(
                items,
                group_by,
                {"total_amount": "amount", "total_balance": "balance"},
            )
            return groups, totals
        if key == "income_summary":
            totals = {
                "runs": len(items),
                "total_gross": round(sum(float(i.get("gross_amount") or 0) for i in items), 2),
                "total_gst": round(sum(float(i.get("gst_collected") or 0) for i in items), 2),
                "total_net": round(sum(float(i.get("net_amount") or 0) for i in items), 2),
            }
            groups = self._group_rows(
                items,
                group_by,
                {
                    "total_gross": "gross_amount",
                    "total_gst": "gst_collected",
                    "total_net": "net_amount",
                },
            )
            return groups, totals
        return [], {"runs": len(items)}

    def _group_rows(self, items, group_by, metric_map) -> list[dict[str, Any]]:
        if group_by == "none":
            return []
        groups = defaultdict(lambda: {"group_value": "", "runs": 0})
        for item in items:
            group_value = str(item.get(group_by) or "")
            row = groups[group_value]
            row["group_value"] = group_value
            row["runs"] += 1
            for total_key, item_key in metric_map.items():
                if total_key == "company_name":
                    row[total_key] = item.get(item_key, "")
                    continue
                row[total_key] = row.get(total_key, 0.0) + float(
                    item.get(item_key) or 0
                )
        return sorted(groups.values(), key=lambda value: value["group_value"].lower())

    def _fill_table(self, columns, row_data) -> None:
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([c[0] for c in columns])
        self.table.setRowCount(len(row_data))
        for ri, row in enumerate(row_data):
            for ci, (_, key) in enumerate(columns):
                val = row.get(key, "")
                if key in self._MONEY_KEYS and val not in ("", None):
                    cell = QTableWidgetItem(f"${float(val):,.2f}")
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                elif key in self._RIGHT_KEYS and val not in ("", None):
                    cell = QTableWidgetItem(
                        f"{float(val): ,.2f} "
                        if isinstance(val, float)
                        else str(val)
                    )
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    cell = QTableWidgetItem(
                        str(val) if val is not None else ""
                    )
                self.table.setItem(ri, ci, cell)
        self.table.resizeColumnsToContents()

    def _populate_detail(self, items, family_label) -> None:
        self._fill_table(self._get_detail_cols(family_label), items)

    def _populate_grouped(self, groups, family_label) -> None:
        self._fill_table(self._get_group_cols(family_label), groups)

    def _export_csv(self) -> None:
        family_label = self.family_combo.currentText()
        grouped = self.group_combo.currentText() != "(No Grouping)"
        rows_data = self._groups if grouped else self._items
        cols = (
            self._get_group_cols(family_label)
            if grouped
            else self._get_detail_cols(family_label)
        )
        if not rows_data:
            QMessageBox.information(self, "Export", "No data to export.")
            return
        default_name = (
            f"crystal_{family_label.replace(' ', '_')}_{date.today().isoformat()}.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", default_name, "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([c[0] for c in cols])
                for row in rows_data:
                    w.writerow([row.get(c[1], "") for c in cols])
            QMessageBox.information(self, "Export", f"Saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _print_preview(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(
            printer.pageLayout().orientation().Landscape
        )
        dialog = QPrintPreviewDialog(printer, self)
        dialog.paintRequested.connect(self._do_print)
        dialog.exec()

    def _do_print(self, printer) -> None:
        from PyQt6.QtGui import QPainter, QTextDocument

        family_label = self.family_combo.currentText()
        grouped = self.group_combo.currentText() != "(No Grouping)"
        rows_data = self._groups if grouped else self._items
        cols = (
            self._get_group_cols(family_label)
            if grouped
            else self._get_detail_cols(family_label)
        )
        start_lbl = self.start_date.date().toString("yyyy-MM-dd")
        end_lbl = self.end_date.date().toString("yyyy-MM-dd")
        runs = self._totals.get("runs", 0)
        group_label = self.group_combo.currentText()
        html = ["<html><body>", f"<h2>{family_label}</h2>"]
        html.append(
            f"<p>Group By: {group_label} | "
            f"Period: {start_lbl} - {end_lbl} | Rows: {runs}</p>"
        )
        html.append(
            "<table border='1' cellpadding='3' cellspacing='0' "
            "style='border-collapse:collapse;font-size:9pt;width:100%'>"
        )
        header_cells = "".join(
            f"<th style='background:#ddd'>{c[0]}</th>" for c in cols
        )
        html.append(f"<tr>{header_cells}</tr>")
        for row in rows_data:
            html.append("<tr>")
            for _, key in cols:
                val = row.get(key, "")
                if isinstance(val, float):
                    val = f"${val:,.2f}"
                html.append(f"<td>{val}</td>")
            html.append("</tr>")
        html.append("</table></body></html>")
        doc = QTextDocument()
        doc.setHtml("".join(html))
        painter = QPainter(printer)
        doc.drawContents(painter)
        painter.end()
