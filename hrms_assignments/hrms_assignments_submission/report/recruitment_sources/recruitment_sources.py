from __future__ import annotations
import frappe
from frappe import _
from typing import Any, Dict, List, Tuple


def execute(
    filters: Dict[str, Any] | None = None,
):
    filters = filters or {}
    columns = get_columns()
    rows = get_data(filters)
    chart = make_chart(rows)
    summary = make_summary(rows)
    return columns, rows, None, chart, summary


# ---------------------------- Columns ----------------------------


def get_columns():
    return [
        {
            "label": _("ID"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Job Applicant",
            "width": 140,
        },
        {
            "label": _("Applicant Name"),
            "fieldname": "applicant_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Email"),
            "fieldname": "email_id",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Phone"),
            "fieldname": "phone_number",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": _("Country"),
            "fieldname": "country",
            "fieldtype": "Link",
            "options": "Country",
            "width": 120,
        },
        {
            "label": _("Job Title"),
            "fieldname": "job_title",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": _("Designation"),
            "fieldname": "designation",
            "fieldtype": "Link",
            "options": "Designation",
            "width": 160,
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Source"),
            "fieldname": "source",
            "fieldtype": "Link",
            "options": "Job Applicant Source",
            "width": 160,
        },
        {
            "label": _("Rating"),
            "fieldname": "applicant_rating",
            "fieldtype": "Float",
            "width": 100,
        },
        {
            "label": _("Application Date"),
            "fieldname": "creation",
            "fieldtype": "Datetime",
            "width": 180,
        },
    ]


# ----------------------------- Data -----------------------------


def get_data(filters: Dict[str, Any]):
    conds = ["ja.docstatus < 2"]
    params: Dict[str, Any] = {}

    if filters.get("source"):
        conds.append("ja.source = %(source)s")
        params["source"] = filters["source"]

    where_clause = " AND ".join(conds)

    sql = f"""
        SELECT
            ja.name,
            ja.applicant_name,
            ja.email_id,
            ja.phone_number,
            ja.country,
            ja.job_title,
            ja.designation,
            ja.status,
            ja.source,
            ja.applicant_rating,
            ja.creation
        FROM `tabJob Applicant` ja
        WHERE {where_clause}
        ORDER BY ja.creation DESC
    """

    return frappe.db.sql(sql, params, as_dict=True)


# ----------------------------- Chart -----------------------------


def make_chart(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_source: Dict[str, int] = {}
    for r in rows:
        key = (r.get("source") or "Unknown").strip() or "Unknown"
        by_source[key] = by_source.get(key, 0) + 1

    labels = list(by_source.keys())
    values = [by_source[k] for k in labels]

    return {
        "data": {"labels": labels, "datasets": [{"values": values}]},
        "type": "pie",
    }


# --------------------------- Summary ----------------------------


def make_summary(rows: List[Dict[str, Any]]):
    total = len(rows)
    unique_sources = len(
        {(r.get("source") or "Unknown").strip() or "Unknown" for r in rows}
    )

    return [
        {"label": _("Total Applicants"), "value": total, "indicator": "blue"},
        {"label": _("Unique Sources"), "value": unique_sources, "indicator": "orange"},
    ]
