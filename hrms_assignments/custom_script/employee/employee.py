import frappe
import re
from frappe.utils import getdate, add_months, formatdate, add_days, nowdate, cint

KEYWORDS = ("end", "probation", "early")
BYPASSERS = "Bypasser"


def compute_probation_end_date(joining_date, probation_period):
    if not joining_date or not probation_period:
        return {"end_date": None, "end_date_formatted": None}
    if isinstance(probation_period, str) and "-" in probation_period.strip():
        try:
            end_date = str(getdate(probation_period))
            return {"end_date": end_date, "end_date_formatted": formatdate(end_date)}
        except Exception:
            pass

    unit, qty = _extract_days_or_months(probation_period)
    if qty is None:
        return {"end_date": None, "end_date_formatted": None}
    base = getdate(joining_date)
    if unit == "months":
        end_date = str(add_months(base, qty))
    else:
        end_date = str(add_days(base, qty))
    return {"end_date": end_date, "end_date_formatted": formatdate(end_date)}


def _safe_date(d):
    try:
        return getdate(d) if d else None
    except Exception as e:
        return False


def _extract_days_or_months(value):
    if value is None or value == "":
        return (None, None)
    try:
        qty = int(value)
        return ("days", qty if qty >= 0 else None)
    except Exception as e:
        pass

    if isinstance(value, str):
        s = value.strip().lower()
        m = re.search(f"(\d+)", s)
        if not m:
            return (None, None)
        qty = int(m.group(1))
        if "month" in s or "months" in s or re.search(r"\bmo(nth)?s?\b", s):
            return ("months", qty)
        return ("days", qty)

    return (None, None)


def before_insert(doc, method=None):
    if doc.custom_is_under_probation == 0:
        return None
    else:
        response = compute_probation_end_date(
            joining_date=doc.date_of_joining,
            probation_period=doc.custom_probation_period,
        )
        doc.custom_probation_end_date = response.get("end_date")
        doc.custom_employment_status = "Probation"


def _current_user_is_bypasser(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user == "Administrator":
        return False
    try:
        return BYPASSERS in (frappe.get_roles(user) or [])
    except Exception:
        return False


def _contains_all_keywords(text: str) -> bool:
    s = (text or "").lower()
    return all(re.search(rf"\b{re.escape(k)}\b", s) for k in KEYWORDS)


def _has_rm_early_end_comment(emp_doc):
    rm_employee = emp_doc.get("reports_to")
    rm_id = frappe.db.get_value("Employee", rm_employee, "user_id")
    if not rm_id:
        return False
    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Employee",
            "reference_name": emp_doc.name,
            "comment_type": "Comment",
            "owner": ["in", [rm_id, "Administrator"]],
        },
        fields=["content"],
        order_by="creation desc",
        limit=10,
    )

    if not comments:
        return False
    for c in comments:
        if _contains_all_keywords(c.get("content" or "")):
            return True
    return False


@frappe.whitelist()
def calculate_probation_end_date(employee=None):
    if not employee:
        return None

    emp = frappe.db.get_value(
        "Employee",
        employee,
        ["date_of_joining", "custom_probation_period", "custom_is_under_probation"],
        as_dict=True,
    )
    if not emp:
        frappe.throw(f"Employee '{employee}' not found.")

    doj = emp.get("date_of_joining")
    pp = emp.get("custom_probation_period")

    end_date = None

    if isinstance(pp, str) and "-" in pp:
        try:
            end_date = str(getdate(pp))
        except Exception:
            end_date = None

    if end_date is None and doj is not None and pp is not None:
        unit, qty = _extract_days_or_months(pp)
        if qty is not None:
            base = getdate(doj)
            if unit == "months":
                end_date = str(add_months(base, qty))
            else:
                end_date = str(add_days(base, qty))

    return {
        "end_date": end_date,
        "end_date_formatted": formatdate(end_date) if end_date else None,
    }


def validate_probation_guards(doc, method=None):
    if _current_user_is_bypasser():
        return None
    end_date = _safe_date(doc.custom_probation_end_date)
    if not end_date:
        return None

    today = getdate(nowdate())
    probation_not_ended = today < end_date

    before_saving = doc.get_doc_before_save()
    previous_state = before_saving.custom_employment_status if before_saving else None
    new_state = doc.get("custom_employment_status")
    stage_changed_to_confirmed = (
        new_state == "Confirmed" and previous_state != "Confirmed"
    )

    prev_prob_flag = (
        cint(before_saving.custom_is_under_probation)
        if (before_saving and "custom_is_under_probation" in before_saving.as_dict())
        else None
    )
    new_prob_flag = cint(doc.get("custom_is_under_probation"))
    prob_flag_toggled_off = (prev_prob_flag is not None) and (
        prev_prob_flag == 1 and new_prob_flag == 0
    )

    if not probation_not_ended:
        return None

    has_manager_override = _has_rm_early_end_comment(doc)
    if stage_changed_to_confirmed and not has_manager_override:
        frappe.throw(
            f"Cannot mark employee <b>{doc.employee_name or doc.name}</b> as <b>Confirmed</b> "
            f"before <b>Probation Ends On</b> ({frappe.utils.formatdate(end_date)}).<br>"
            f"Ask the Reporting Manager to add a comment containing the keywords "
            f"<b>End</b>, <b>Probation</b>, <b>Early</b> to allow early confirmation.",
            title="Probation Guard",
        )

    if prob_flag_toggled_off and not has_manager_override:
        frappe.throw(
            f"Cannot remove <b>Under Probation</b> before <b>Probation Ends On</b> "
            f"({frappe.utils.formatdate(end_date)}) without a Reporting Manager comment "
            f"containing <b>End</b>, <b>Probation</b>, <b>Early</b>.",
            title="Probation Guard",
        )
    doc.custom_has_early_probation_end = 1
