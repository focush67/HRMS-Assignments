from __future__ import annotations
import re
import frappe
from frappe.utils import nowdate, add_days, add_months, getdate, formatdate, escape_html

AUTO_MARKER = "[AUTO:PROBATION-REMINDER]"
REMINDER_DAYS_BEFORE = 15


def run_daily_probation_reminders():
    today = getdate(nowdate())
    employees = frappe.get_all(
        "Employee",
        filters={
            "custom_is_under_probation": 1,
            "status": "Active",
        },
        fields=[
            "name",
            "employee_name",
            "user_id",
            "reports_to",
            "date_of_joining",
            "custom_probation_period",
        ],
    )

    for emp in employees:
        end_date_of_probation = _compute_probation_completion_date(
            doj=emp.get("date_of_joining"),
            probation_period=emp.get("custom_probation_period"),
        )

        if not end_date_of_probation:
            continue

        if getdate(add_days(end_date_of_probation, -REMINDER_DAYS_BEFORE)) != today:
            continue

        employee_user = (emp.get("user_id") or "").strip() or None
        manager = _get_manager_user(emp.get("reports_to"))

        _maybe_create_todo_for_user(
            employee_name=emp["name"],
            employee_display=emp.get("employee_name") or emp["name"],
            allocated_to=employee_user,
            role="employee",
            end_date=str(end_date_of_probation),
        )

        _maybe_create_todo_for_user(
            employee_name=emp["name"],
            employee_display=emp.get("employee_name") or emp["name"],
            allocated_to=manager,
            role="reporting manager",
            end_date=str(end_date_of_probation),
        )


def _compute_probation_completion_date(doj, probation_period):
    if not doj:
        return None
    try:
        if probation_period:
            pp_as_date = getdate(probation_period)
            if isinstance(probation_period, str) and "-" in probation_period:
                return str(pp_as_date)
    except Exception as e:
        pass

    months = _extract_months(probation_period)
    if months is not None:
        try:
            doj_date = getdate(doj)
            return str(add_months(doj_date, months))
        except Exception as e:
            return None

    return None


def _extract_months(value):
    if value is None:
        return None

    try:
        iv = int(value)
        if iv >= 0:
            return iv
    except Exception:
        pass

    if isinstance(value, str):
        m = re.search(r"(\d+)", value)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    return None


def _get_manager_user(reports_to_emp):
    if not reports_to_emp:
        return None
    return frappe.db.get_value("Employee", reports_to_emp, "user_id")


def _maybe_create_todo_for_user(
    employee_name: str,
    employee_display: str,
    allocated_to,
    role: str,
    end_date: str,
):
    if not allocated_to:
        return

    exists = frappe.db.exists(
        "ToDo",
        {
            "reference_type": "Employee",
            "reference_name": employee_name,
            "allocated_to": allocated_to,
            "status": "Open",
            "description": ["like", f"%{AUTO_MARKER}%"],
        },
    )
    if exists:
        return

    description = (
        f"{AUTO_MARKER} Probation reminder for <b>{escape_html(employee_display)}</b> "
        f"(Employee: {escape_html(employee_name)}) — probation ends on "
        f"<b>{formatdate(end_date)}</b>.<br>"
        f"Please complete the probation evaluation form."
    )

    todo = frappe.get_doc(
        {
            "doctype": "ToDo",
            "allocated_to": allocated_to,
            "status": "Open",
            "priority": "Medium",
            "date": nowdate(),
            "reference_type": "Employee",
            "reference_name": employee_name,
            "description": description,
        }
    )
    todo.insert(ignore_permissions=True)
