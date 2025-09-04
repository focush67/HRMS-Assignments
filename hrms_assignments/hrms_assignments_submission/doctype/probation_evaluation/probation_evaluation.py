import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days, nowdate

STATE_OPEN = "Open"
MAX_EXTENSION = 30
MIN_REASON_CHARS = 20
STATE_AWAITING_SET = {"Awaiting Manager Evaluation", "Waiting Manager Evaluation"}
STATE_COMPLETED = "Completed"

SE_FIELDS = [
    "theoretical_se",
    "practical_se",
    "quality_of_work_se",
    "team_work_abilities_se",
    "interpersonal_skills_se",
    "capacity_to_develop_se",
]

RM_FIELDS = [
    "quality_of_work_rm",
    "capacity_to_develop_rm",
    "team_work_abilities_rm",
    "interpersonal_skills_rm",
    "theoretical_rm",
    "practical_rm",
]


class ProbationEvaluation(Document):
    def validate(self):
        if getattr(self, "final_verdict", None) == "Extended":
            return None
        self._enforce_workflow_field_rules()
        if self.workflow_state == "Completed":
            self._calculate_final_verdict()

    def before_submit(self):
        if getattr(self, "final_verdict", None) == "Extended":
            return None
        if hasattr(self, "_calculate_final_verdict"):
            self._calculate_final_verdict()

    def on_submit(self):
        verdict = self.final_verdict
        if verdict == "Passed":
            self._update_employee_as_cleared()
        elif verdict == "Failed":
            sep_name = self._initiate_employee_separation()
            if sep_name:
                frappe.msgprint(
                    f"Employee Separation Initiated: {sep_name}. Please fill relevant information and complete offboarding"
                )

    def _label_for(self, fieldname):
        df = self.meta.get_field(fieldname)
        return (
            df.label
            if df and getattr(df, "label", None)
            else fieldname.replace("_", " ").title()
        )

    def _update_employee_as_cleared(self):
        if self.final_verdict == "Failed":
            return None
        employee_doc = frappe.get_doc("Employee", self.employee)
        employee_doc.custom_is_under_probation = 0
        employee_doc.custom_employment_status = "Confirmed"
        employee_doc.final_confirmation_date = frappe.utils.today()
        employee_doc.save()

    def _initiate_employee_separation(self):
        if not self.employee:
            frappe.throw("Employee is required for initiating separation")
        existing = None
        existing = frappe.get_all(
            "Employee Separation",
            filters={
                "employee": self.employee,
                "docstatus": ["!=", 2],
            },
            fields=["name"],
            limit=1,
        )

        if existing:
            return existing[0]["name"]

        emp = frappe.get_doc("Employee", self.employee)
        today = frappe.utils.today()
        payload = {
            "doctype": "Employee Separation",
            "employee": emp.name,
            "boarding_begins_on": today,
            "exit_interview": f"Auto-initiated on probation failure from Evaluation {self.name}.",
        }

        sep = frappe.get_doc(payload).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "Employee Separation",
                "reference_name": sep.name,
                "content": f"Created from Probation Evaluation <b>{self.name}</b> (verdict <b>Failed</b>).",
            }
        ).insert(ignore_permissions=True)

        return sep.name

    def _find_out_of_range(self, fields, lo: int = 1, hi: int = 10):
        bad = []
        for f in fields:
            v = self.get(f)
            try:
                v_int = int(v if v is not None else 0)
            except Exception:
                v_int = 0
            if not (lo <= v_int <= hi):
                bad.append(f)
        return bad

    def _enforce_workflow_field_rules(self):
        before = self.get_doc_before_save()
        prev_state = getattr(before, "workflow_state", None) if before else None
        curr_state = getattr(self, "workflow_state", None)

        if prev_state == curr_state:
            return

        if curr_state in STATE_AWAITING_SET:
            bad = self._find_out_of_range(SE_FIELDS, 1, 10)
            if bad:
                labels = ", ".join(
                    f"<b>{frappe.utils.escape_html(self._label_for(f))}</b>"
                    for f in bad
                )
                frappe.throw(
                    f"The following Self-Evaluation fields must be between 1 and 10 (no zeros): {labels}."
                )

        if curr_state == STATE_COMPLETED:
            bad = self._find_out_of_range(RM_FIELDS, 1, 10)
            if bad:
                labels = ", ".join(
                    f"<b>{frappe.utils.escape_html(self._label_for(f))}</b>"
                    for f in bad
                )
                frappe.throw(
                    f"The following Manager Evaluation fields must be between 1 and 10 (no zeros): {labels}."
                )

    def _calculate_final_verdict(self):
        fields = SE_FIELDS + RM_FIELDS
        values = [int(self.get(f) or 0) for f in fields]

        if not values:
            self.final_verdict = "Failed"
            return

        total_score = sum(values)
        max_score = len(values) * 10
        percent = (total_score / max_score) * 100

        self.final_verdict = "Passed" if percent >= 70 else "Failed"
        frappe.msgprint(f"Final Verdict: {self.final_verdict} ({percent:.2f}%)")


@frappe.whitelist()
def extend_probation_conditionally(evaluation, days, reason):
    if not evaluation:
        frappe.throw("Missing Evaluation ID")
    pe = frappe.get_doc("Probation Evaluation", evaluation)
    if pe.docstatus != 0:
        frappe.thow("Extension can only happen for Draft Probation Evaluations")
    if not pe.employee:
        frappe.throw("Evaluation is not linked to any Employee")

    emp = frappe.get_doc("Employee", pe.employee)
    rm_user = (
        frappe.db.get_value("Employee", emp.get("reports_to"), "user_id")
        if emp.get("reports_to")
        else None
    )

    if frappe.session.user not in set(filter(None, [rm_user, "Administrator"])):
        frappe.throw(
            f"Only the Reporting Manager or Administrator can extend probation. Got {frappe.session.user}"
        )

    try:
        days = int(days)
    except Exception as e:
        frappe.throw("Extension days must be a valid integer", str(e))

    if days < 7 or days > MAX_EXTENSION:
        frappe.throw(
            f"Extension cannot exceed {MAX_EXTENSION} days, and cannot be lesser than a week"
        )

    reason = (reason or "").strip()
    if len(reason) < MIN_REASON_CHARS:
        frappe.throw(f"Please provide a detailed reason for extension of Probation")

    base_end = emp.get("custom_probation_end_date")
    if not base_end:
        frappe.throw(
            "Employee does not have Probation End Date set in its Employee master. Please first set it and then try again later"
        )

    new_end = add_days(getdate(base_end), days)
    emp.db_set("custom_probation_end_date", new_end, update_modified=True)
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Comment",
            "reference_doctype": "Employee",
            "reference_name": emp.name,
            "content": f"Probation extended by <b>{days} days</b> (from {frappe.utils.formatdate(base_end)} to {frappe.utils.formatdate(new_end)}).<br>"
            f"Reason: {frappe.utils.escape_html(reason)}<br>"
            f"By: {frappe.session.user} on {frappe.utils.formatdate(nowdate())}",
        }
    ).insert(ignore_permissions=True)

    if "extension_days" in pe.as_dict():
        pe.extension_days = days
    if "extension_reason" in pe.as_dict():
        pe.extension_reason = reason

    pe.final_verdict = "Extended"
    if "workflow_state" in pe.as_dict():
        pe.workflow_state = "Completed"

    pe.flags.ignore_validate_update_after_submit = True
    pe.save()
    pe.submit()

    return {
        "employee": emp.name,
        "old_end": str(getdate(base_end)),
        "new_end": str(new_end),
        "evaluation": pe.name,
        "verdict": "Extended",
    }
