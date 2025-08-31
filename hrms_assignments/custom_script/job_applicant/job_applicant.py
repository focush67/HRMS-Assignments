from __future__ import annotations
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, now_datetime

WORKFLOW = {
    "STATE_NEW": "New",
    "STATE_INTERVIEWING": "Interviewing",
    "STATE_OFFERED": "Offered",
    "STATE_ON_HOLD": "On Hold",
}

ACTIVE_OFFER_STATUSES = {s.lower() for s in ("Awaiting Response", "Accepted")}


def _has_scheduled_interview_record(applicant_name: str) -> bool:
    try:
        interviews = frappe.get_all(
            "Interview",
            filters={
                "job_applicant": applicant_name,
                "docstatus": ["!=", 2],
            },
            fields=[
                "name",
                "status",
                "scheduled_on",
                "from_time",
                "to_time",
            ],
            limit=100,
        )
    except Exception:
        return False

    if not interviews:
        return False

    for it in interviews:
        has_date = bool(it.get("scheduled_on"))
        has_time = bool(it.get("from_time") or it.get("to_time"))
        if not (has_date and has_time):
            continue

        try:
            participants = frappe.get_all(
                "Interview Detail",
                filters={"parenttype": "Interview", "parent": it["name"]},
                fields=["name"],
                limit=1,
            )
            if participants:
                return True
        except Exception:
            return True

    return False


def _has_participant(interview_name: str) -> bool:
    try:
        participants = frappe.get_all(
            "Interview Detail",
            filters={"parenttype": "Interview", "parent": interview_name},
            fields=["name"],
            limit=1,
        )
        return bool(participants)
    except Exception:
        return False


def _has_upcoming_interview(applicant_name: str) -> bool:
    """
    Upcoming = scheduled_on is in the future OR (scheduled_on is today AND from_time/to_time is later than now).
    Requires ≥1 participant in 'Interview Detail'.
    """
    nowdt = now_datetime()
    today = getdate(nowdt)
    nowt = nowdt.time()

    try:
        interviews = frappe.get_all(
            "Interview",
            filters={
                "job_applicant": applicant_name,
                "docstatus": ["!=", 2],
                "scheduled_on": [">=", today],
            },
            fields=["name", "scheduled_on", "from_time", "to_time"],
            limit=100,
        )
    except Exception:
        return False

    if not interviews:
        return False

    for it in interviews:
        sch_date = it.get("scheduled_on")
        if not sch_date:
            continue

        from_time = it.get("from_time")
        to_time = it.get("to_time")

        if sch_date > today and (from_time is None and to_time is None):
            if _has_participant(it["name"]):
                return True

        # If times exist, treat as upcoming only if start/end is later than now when date == today,
        # or any time when date > today.
        if sch_date > today:
            if _has_participant(it["name"]):
                return True
        elif sch_date == today:
            # consider upcoming if either start or end is still ahead of now
            if (from_time and from_time > nowt) or (to_time and to_time > nowt):
                if _has_participant(it["name"]):
                    return True

    return False


# Validation: Only allow Interviewing if there nos(interviews) >= 1
def _require_interview_for_new_to_interviewing(doc: Document):
    before = doc.get_doc_before_save()
    if not before:
        return

    previous_state = (before.workflow_state or "").strip()
    current_state = (doc.workflow_state or "").strip()

    if not (
        previous_state == WORKFLOW["STATE_NEW"]
        and current_state == WORKFLOW["STATE_INTERVIEWING"]
    ):
        return

    if _has_scheduled_interview_record(doc.name):
        return

    frappe.throw(
        "Add at least one <b>Interview</b> (scheduled with participants) "
        f"before moving the applicant to <b>{WORKFLOW['STATE_INTERVIEWING']}</b>."
    )


# Validation: Block Holding Job Applicant unless there is a future interview scheduled
def _require_upcoming_interview_for_hold_to_interviewing(doc: Document):
    before = doc.get_doc_before_save()
    if not before:
        return

    previous_state = (before.workflow_state or "").strip()
    current_state = (doc.workflow_state or "").strip()

    if not (
        previous_state == WORKFLOW["STATE_ON_HOLD"]
        and current_state == WORKFLOW["STATE_INTERVIEWING"]
    ):
        return

    if _has_upcoming_interview(doc.name):
        return

    frappe.throw(
        "Schedule a <b>future Interview</b> (date/time with participants) before resuming to "
        f"<b>{WORKFLOW['STATE_INTERVIEWING']}</b> from <b>{WORKFLOW['STATE_ON_HOLD']}</b>."
    )


# Validation: Cannot accept the Job Applicant unless all the interviews are cleared
def _require_all_interviews_cleared_for_accept(doc: Document):
    before = doc.get_doc_before_save()
    if not before:
        return

    prev_status = (before.status or "").strip().lower()
    curr_status = (doc.status or "").strip().lower()

    if not (prev_status != "accepted" and curr_status == "accepted"):
        return

    interviews = frappe.get_all(
        "Interview",
        filters={"job_applicant": doc.name, "docstatus": ["!=", 2]},
        fields=["name", "status"],
        limit=1000,
    )

    if not interviews:
        frappe.throw(
            _(
                "Add and complete Interviews first. All Interviews must be marked {0} before setting status to {1}."
            ).format(frappe.bold("Cleared"), frappe.bold("Accepted"))
        )

    offenders = []
    for it in interviews:
        raw = (it.get("status") or "").strip()
        if raw.lower() != "cleared":
            offenders.append((it["name"], raw or "—"))

    if offenders:
        details = "<br>".join(
            f"• {frappe.bold(n)} (status: {frappe.bold(s)})" for n, s in offenders[:12]
        )
        more = "" if len(offenders) <= 12 else f"<br>…and {len(offenders) - 12} more."
        frappe.throw(
            _(
                "All linked {0} must have status {1} before setting Job Applicant to {2}.<br><br>{3}{4}"
            ).format(
                frappe.bold("Interview"),
                frappe.bold("Cleared"),
                frappe.bold("Accepted"),
                details,
                more,
            )
        )


# Validation: Cannot offer unless there is exactly one active job offer
def _require_single_active_offer_for_offered(doc: Document):
    before = doc.get_doc_before_save()
    prev = (before.workflow_state or "").strip() if before else None
    curr = (doc.workflow_state or "").strip()

    interviewing = WORKFLOW.get("STATE_INTERVIEWING", "Interviewing")
    offered = WORKFLOW.get("STATE_OFFERED", "Offered")

    if not (
        (prev == interviewing and curr == offered)
        or (prev == offered and curr == offered)
        or (prev is None and curr == offered)
    ):
        return

    offers = frappe.get_all(
        "Job Offer",
        filters={
            "job_applicant": doc.name,
            "docstatus": ["!=", 2],
        },
        fields=["name", "status"],
        limit=200,
    )

    active = []
    for o in offers:
        st = (o.get("status") or "").strip().lower()
        if st in ACTIVE_OFFER_STATUSES:
            active.append(o)

    if len(active) == 1:
        return

    if len(active) == 0:
        allowed = ", ".join(sorted(s.title() for s in ACTIVE_OFFER_STATUSES))
        frappe.throw(
            f"Create/link exactly one active <b>Job Offer</b> (status: {allowed}) "
            f"before moving/saving the applicant in <b>{offered}</b>."
        )

    details = ", ".join(
        f"{o['name']} (status: {o.get('status') or '-'})" for o in active
    )
    frappe.throw(
        f"Only one active <b>Job Offer</b> is allowed while in <b>{offered}</b>. "
        f"Found: {details}."
    )


def validate_job_applicant(doc: Document, method=None):
    _require_interview_for_new_to_interviewing(doc)
    _require_upcoming_interview_for_hold_to_interviewing(doc)
    _require_all_interviews_cleared_for_accept(doc)
    _require_single_active_offer_for_offered(doc)
