import frappe
import re
from frappe.model.document import Document
from frappe.utils import getdate, add_months, formatdate, add_days
import frappe.utils

STATE_OPEN = "Open"
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
        self._enforce_workflow_field_rules()
        if self.workflow_state == "Completed":
            self._calculate_final_verdict()

    def before_submit(self):
        self._calculate_final_verdict()

    def on_submit(self):
        verdict = self.final_verdict
        if verdict == "Passed":
            print("Need to update employee")
            self._update_employee_as_cleared()

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
        employee_doc = frappe.get_doc("Employee", self.name)
        employee_doc.custom_is_under_probation = 0
        employee_doc.custom_employment_status = "Confirmed"
        employee_doc.final_confirmation_date = frappe.utils.today()
        employee_doc.save()

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
