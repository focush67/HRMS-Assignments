from __future__ import annotations
import re
import frappe
from frappe.utils import (
    nowdate,
    add_days,
    add_months,
    today,
    getdate,
    formatdate,
    escape_html,
)

from hrms_assignments.custom_script.employee.employee import (
    generate_and_attach_experience_letter,
)

AUTO_MARKER = "[AUTO:PROBATION-REMINDER]"
REMINDER_DAYS_BEFORE = 15
COMMENT_MARKER = "Auto-marked Employee as Left from Separation completion"
RESIGNATION_MARKER = (
    "Auto-updated Resignation status to Completed (Separation completed)"
)


# -----Helpers----------#


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


def _find_linked_resignation(sep_name: str, employee: str) -> str | None:
    direct = frappe.db.get_value(
        "Employee Resignation", {"employee_separation": sep_name}, "name"
    )
    if direct:
        return direct

    rows = frappe.get_all(
        "Employee Resignation",
        filters={"employee": employee, "docstatus": 1},
        fields=["name"],
        order_by="modified desc",
        limit=1,
    )
    return rows[0]["name"] if rows else None


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


def _maybe_complete_resignation_for_separation(sep_name: str, employee: str) -> None:
    res_name = _find_linked_resignation(sep_name, employee)
    if not res_name:
        return

    if _resignation_already_marked(res_name):
        return

    try:
        res = frappe.get_doc("Employee Resignation", res_name)
        current = (res.status or "").strip().lower()
        if current != "completed":
            res.status = "Completed"
            res.save(ignore_permissions=True)

        _drop_resignation_marker_comment(res.name)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"_maybe_complete_resignation_for_separation failed: {res_name}",
        )


def _already_processed(separation_name: str) -> bool:
    return bool(
        frappe.get_all(
            "Comment",
            filters={
                "reference_doctype": "Employee Separation",
                "reference_name": separation_name,
                "content": ("like", f"%{COMMENT_MARKER}%"),
            },
            limit=1,
        )
    )


def _drop_resignation_marker_comment(resignation_name: str) -> None:
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Comment",
            "reference_doctype": "Resignation",
            "reference_name": resignation_name,
            "content": RESIGNATION_MARKER,
        }
    ).insert(ignore_permissions=True)


def _drop_marker_comment(separation_name: str) -> None:
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Comment",
            "reference_doctype": "Employee Separation",
            "reference_name": separation_name,
            "content": COMMENT_MARKER,
        }
    ).insert(ignore_permissions=True)


def _resignation_already_marked(resignation_name: str) -> bool:
    return bool(
        frappe.get_all(
            "Comment",
            filters={
                "reference_doctype": "Resignation",
                "reference_name": resignation_name,
                "content": ("like", f"%{RESIGNATION_MARKER}%"),
            },
            limit=1,
        )
    )


def _mark_employee_left_for_separation(sep_row: dict) -> None:
    emp = frappe.get_doc("Employee", sep_row["employee"])
    last_day = (
        sep_row.get("boarding_begins_on")
        or sep_row.get("resignation_letter_date")
        or getdate(today())
    )

    changed = False

    if getattr(emp, "status", None) != "Left":
        emp.status = "Left"
        changed = True

    if hasattr(emp, "relieving_date") and not emp.relieving_date:
        emp.relieving_date = last_day
        changed = True

    ed = emp.as_dict()
    if "custom_employment_status" in ed and emp.custom_employment_status != "Exited":
        emp.custom_employment_status = "Exited"
        changed = True

    if "custom_is_under_probation" in ed and emp.custom_is_under_probation:
        emp.custom_is_under_probation = 0
        changed = True

    if changed:
        emp.save(ignore_permissions=True)
    try:
        generate_and_attach_experience_letter(
            employee_name=sep_row["employee"], letter_date=today
        )
    except Exception as e:
        frappe.throw(f"Error while attaching experience letter")


# -------Main Logic-------#


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


def mark_as_left():
    try:
        rows = frappe.get_all(
            "Employee Separation",
            filters={"docstatus": 1, "boarding_status": "Completed"},
            fields=[
                "name",
                "employee",
                "boarding_begins_on",
                "resignation_letter_date",
            ],
            limit=500,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "mark_as_left: query failed")
        return

    for sep in rows:
        emp_name = sep.get("employee")
        if not emp_name:
            continue

        if _already_processed(sep["name"]):
            _maybe_complete_resignation_for_separation(
                sep_name=sep["name"], employee=emp_name
            )
            continue

        try:
            _mark_employee_left_for_separation(sep)
            _drop_marker_comment(sep["name"])
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"mark_as_left: failed processing separation {sep['name']}",
            )

        try:
            _maybe_complete_resignation_for_separation(
                sep_name=sep["name"], employee=emp_name
            )
        except Exception as e:
            frappe.log_error(
                frappe.get_traceback(),
                f"mark_as_left: failed updating resignation for separation {sep['name']}",
            )
