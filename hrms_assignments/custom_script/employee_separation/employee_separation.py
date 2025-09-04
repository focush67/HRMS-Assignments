import frappe
from frappe.utils import today, getdate, today, add_days


def _get_plwd(doc):
    if doc.boarding_begins_on:
        return getdate(doc.boarding_begins_on)
    res = frappe.get_all(
        "Employee Resignation",
        filters={"employee": doc.employee, "docstatus": 1},
        fields=["proposed_last_working_date"],
        order_by="creation desc",
        limit=1,
    )
    if res and res[0].get("proposed_last_working_date"):
        return getdate(res[0]["proposed_last_working_date"])
    return None


def before_submit(doc, method=None):
    buffer_days = 10
    resignation = doc.custom_employee_resignation
    if not resignation:
        return None
    plwd = _get_plwd(doc)
    print("Last DAY", plwd)
    if not plwd:
        frappe.throw(
            "Proposed Last Working Date (boarding_begins_on) is required before submission."
        )

    window_open = add_days(getdate(plwd), -buffer_days)
    print("Window Open", window_open)
    if getdate(today()) < window_open:
        frappe.throw(
            f"Employee Separation can be submitted on or after "
            f"<b>{(window_open)}</b> "
            f"(buffer {buffer_days} days before Proposed Last Working Date)."
        )
