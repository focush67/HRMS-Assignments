# Copyright (c) 2025, Sparsh Verma
# License: see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate, today, cint


class EmployeeResignation(Document):
    """Employee files resignation → Manager approves → Submit → create/refresh DRAFT Employee Separation.
    PLWD (proposed_last_working_date) is the source of truth and is required before submit.
    """

    def validate(self):
        self._ensure_employee_is_active()
        if self.notice_period is None:
            self.notice_period = 0
        if cint(self.notice_period) < 0:
            frappe.throw("Notice Period cannot be negative.")

        if not self.resignation_letter_date:
            self.resignation_letter_date = getdate(today())

        if not self.proposed_last_working_date:
            self.proposed_last_working_date = self._compute_plwd()

        reason = (self.reason or "").strip()
        if reason and len(reason) < 10:
            frappe.throw(
                "Please provide a bit more detail in the Reason (≥ 10 characters)."
            )

        if not (self.status or "").strip():
            self.status = "Pending Approval"

    def before_submit(self):
        self.status = "Pending"
        if not self.acceptance_date:
            self.acceptance_date = getdate(today())

        if not self.proposed_last_working_date:
            self.proposed_last_working_date = self._compute_plwd()

    def on_submit(self):
        sep_name = self._upsert_draft_separation()
        if sep_name and hasattr(self, "employee_separation"):
            self.db_set("employee_separation", sep_name, update_modified=False)

        frappe.db.set_value(
            "Employee",
            self.employee,
            "resignation_letter_date",
            getdate(self.resignation_letter_date or today()),
        )

        try:
            frappe.msgprint(
                f"Draft Employee Separation <b>{sep_name}</b> has been initiated."
            )
        except Exception:
            pass

    def on_update_after_submit(self):
        if not getattr(self, "employee_separation", None):
            return

        frappe.db.set_value(
            "Employee Separation",
            self.employee_separation,
            {
                "boarding_begins_on": getdate(self.proposed_last_working_date),
                "resignation_letter_date": getdate(
                    self.resignation_letter_date or today()
                ),
            },
            update_modified=True,
        )

    def on_cancel(self):
        sep_name = getattr(self, "employee_separation", None)
        if not sep_name:
            return

        try:
            sep = frappe.get_doc("Employee Separation", sep_name)
        except Exception:
            return

        if (sep.boarding_status or "").strip() == "Completed":
            return

        try:
            if sep.docstatus == 1:
                sep.cancel()
            elif sep.docstatus == 0:
                sep.delete()
        except Exception:
            try:
                sep.db_set("boarding_status", "Pending", update_modified=True)
                frappe.get_doc(
                    {
                        "doctype": "Comment",
                        "comment_type": "Comment",
                        "reference_doctype": "Employee Separation",
                        "reference_name": sep.name,
                        "content": f"Resignation {self.name} was cancelled; separation left pending.",
                    }
                ).insert(ignore_permissions=True)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(), "Resignation.on_cancel fallback failed"
                )

    def _ensure_employee_is_active(self):
        if not self.employee:
            frappe.throw("Employee is required.")
        emp = frappe.get_doc("Employee", self.employee)
        if getattr(emp, "status", None) == "Left":
            frappe.throw("Employee is already marked as Left. Resignation not allowed.")

    def _compute_plwd(self):
        letter_dt = getdate(self.resignation_letter_date or today())
        ndays = cint(self.notice_period or 0)
        return add_days(letter_dt, ndays)

    def _find_existing_open_separation(self):
        rows = frappe.get_all(
            "Employee Separation",
            filters={
                "employee": self.employee,
                "docstatus": ("!=", 2),
                "boarding_status": ("!=", "Completed"),
            },
            fields=["name"],
            limit=1,
        )
        return rows[0]["name"] if rows else None

    def _upsert_draft_separation(self) -> str:
        """Create/refresh a DRAFT separation. Heavy tasks must run on separation SUBMIT,
        which will be date-gated in EmployeeSeparation.before_submit."""
        name = self._find_existing_open_separation()

        payload = {
            "employee": self.employee,
            "employee_name": self.employee_name,
            "department": self.department,
            "designation": frappe.db.get_value(
                "Employee", self.employee, "designation"
            ),
            "employee_grade": self.employee_grade,
            "company": self.company,
            "boarding_status": "Pending",
            "resignation_letter_date": getdate(self.resignation_letter_date or today()),
            "boarding_begins_on": getdate(self.proposed_last_working_date),
            "notify_users_by_email": 0,
            "exit_interview": f"Created from Resignation {self.name}.",
            "custom_employee_resignation": self.name,
        }

        if name:
            frappe.db.set_value(
                "Employee Separation", name, payload, update_modified=True
            )
            return name

        sep = frappe.get_doc({"doctype": "Employee Separation", **payload})
        sep.insert(ignore_permissions=True)
        return sep.name
