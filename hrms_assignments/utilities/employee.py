import frappe
from datetime import date

CAT_80C = "Section 80C (Umbrella)"
CAT_80D_SF_NS = "Section 80D - Self/Family (Non-Senior)"

CAT_80D_PARENTS_SR = "Section 80D - Parents (Senior)"

SC_80C_PPF = "80C-PPF"
SC_80C_ELSS = "80C-ELSS"
SC_80C_LIC = "80C-LIC"

SC_80D_SF_NS_PREMIUM = "80D-SF-NS-Premium"
SC_80D_SF_NS_PREVENTIVE = "80D-SF-NS-Preventive"

SC_80D_P_SR_PREMIUM = "80D-Parents-SR-Premium"
SC_80D_P_SR_PREVENTIVE = "80D-Parents-SR-Preventive"

# ----------------- helpers -----------------


def _fy_to_dates(fy_str=None):
    s = (fy_str or "").replace(" ", "")
    if "-" in s:
        left, right = s.split("-", 1)

        def norm(y: str, ref=None):
            y = y.strip()
            if len(y) == 2:
                cent = str(ref)[:2] if ref else "20"
                return int(cent + y)
            return int(y)

        y1 = norm(left)
        y2 = norm(right, ref=y1)
    else:
        y1 = int(s)
        y2 = y1 + 1

    return date(y1, 4, 1), date(y2, 3, 31)


def _get_payroll_period_for_dates(start: date, end: date):
    rows = frappe.get_all(
        "Payroll Period",
        filters={"start_date": ["<=", start], "end_date": [">=", end]},
        fields=["name"],
        order_by="start_date desc",
        limit=1,
    )
    return rows[0]["name"] if rows else None


def _get_or_create_eted(employee: str, payroll_period: str):
    name = frappe.db.get_value(
        "Employee Tax Exemption Declaration",
        {"employee": employee, "payroll_period": payroll_period},
        "name",
    )
    if name:
        return frappe.get_doc("Employee Tax Exemption Declaration", name)

    emp = frappe.get_doc("Employee", employee)
    eted = frappe.get_doc(
        {
            "doctype": "Employee Tax Exemption Declaration",
            "employee": employee,
            "employee_name": emp.employee_name,
            "company": emp.company,
            "currency": frappe.db.get_value("Company", emp.company, "default_currency"),
            "payroll_period": payroll_period,
            "declarations": [],
        }
    )
    eted.insert(ignore_permissions=True)
    return eted


def _reset_declarations(eted):
    eted.set("declarations", [])


def _append_decl(eted, category_name: str, subcategory_name=None, amount=None):
    amt = float(amount or 0)
    if amt <= 0:
        return
    if not frappe.db.exists(
        "Employee Tax Exemption Category", {"name": category_name, "is_active": 1}
    ):
        frappe.throw(f"Tax Exemption Category '{category_name}' not found or inactive.")
    if subcategory_name:
        if not frappe.db.exists(
            "Employee Tax Exemption Sub Category",
            {"name": subcategory_name, "is_active": 1},
        ):
            frappe.throw(
                f"Tax Exemption Sub Category '{subcategory_name}' not found or inactive."
            )

    eted.append(
        "declarations",
        {
            "exemption_category": category_name,
            "exemption_sub_category": subcategory_name,
            "amount": amt,
        },
    )


def _get_80c_verified_from_custom(doc):
    rows = frappe.get_all(
        "Employee Investment Line",
        filters={"parent": doc.name, "parenttype": doc.doctype, "section_code": "80C"},
        fields=["subcategory", "amount_verified"],
    )
    out = {"PPF": 0.0, "ELSS": 0.0, "LIC": 0.0}
    for r in rows:
        sub = (r.get("subcategory") or "").strip().lower()
        val = float(r.get("amount_verified") or 0)
        if sub == "ppf":
            out["PPF"] += val
        elif sub == "elss":
            out["ELSS"] += val
        elif sub in ("lic", "life insurance", "life-insurance"):
            out["LIC"] += val

    total = min(sum(out.values()), 150000.0)
    if total < sum(out.values()) and total > 0:
        factor = total / max(sum(out.values()), 1.0)
        for k in out:
            out[k] = round(out[k] * factor, 2)
    return out


def _get_80d_verified_from_custom(doc):
    rows = frappe.get_all(
        "Medical Insurance Line",
        filters={"parent": doc.name, "parenttype": doc.doctype},
        fields=[
            "insured_for",
            "is_a_senior_citizen",
            "amount_verified",
            "preventive_health_checkup",
        ],
    )

    agg = {
        "SF_NS_Premium": 0.0,
        "SF_NS_Preventive": 0.0,
        "P_SR_Premium": 0.0,
        "P_SR_Preventive": 0.0,
    }

    for r in rows:
        who = (r.get("insured_for") or "").strip().lower()
        senior = 1 if int(r.get("is_a_senior_citizen") or 0) else 0
        amt = float(r.get("amount_verified") or 0)
        is_prev = 1 if int(r.get("preventive_health_checkup") or 0) else 0

        if who in {"self", "spouse", "children"} and senior == 0:
            if is_prev:
                agg["SF_NS_Preventive"] += amt
            else:
                agg["SF_NS_Premium"] += amt

        if who == "parents" and senior == 1:
            if is_prev:
                agg["P_SR_Preventive"] += amt
            else:
                agg["P_SR_Premium"] += amt

    def cap_bucket(prem_key: str, prev_key: str, cap_total: float, cap_prev: float):
        prev_allow = min(agg[prev_key], cap_prev)
        overflow_prev = max(agg[prev_key] - prev_allow, 0.0)
        normal = agg[prem_key] + overflow_prev
        total_allow = min(prev_allow + normal, cap_total)
        if total_allow < prev_allow:
            prev_allow = total_allow
            normal_allow = 0.0
        else:
            normal_allow = total_allow - prev_allow
        agg[prem_key] = round(normal_allow, 2)
        agg[prev_key] = round(prev_allow, 2)

    cap_bucket("SF_NS_Premium", "SF_NS_Preventive", 25000.0, 5000.0)
    cap_bucket("P_SR_Premium", "P_SR_Preventive", 50000.0, 5000.0)

    return agg


def sync_to_eted_from_custom(doc):
    fy_start, fy_end = _fy_to_dates(doc.fiscal_year)
    pp = _get_payroll_period_for_dates(fy_start, fy_end)
    print("Start", fy_start)
    print("End", fy_end)
    if not pp:
        frappe.throw(f"No Payroll Period found covering {fy_start} to {fy_end}.")

    eted = _get_or_create_eted(doc.employee, pp)

    _reset_declarations(eted)

    c80c = _get_80c_verified_from_custom(doc)
    _append_decl(eted, CAT_80C, SC_80C_PPF, c80c["PPF"])
    _append_decl(eted, CAT_80C, SC_80C_ELSS, c80c["ELSS"])
    _append_decl(eted, CAT_80C, SC_80C_LIC, c80c["LIC"])

    d80d = _get_80d_verified_from_custom(doc)
    _append_decl(eted, CAT_80D_SF_NS, SC_80D_SF_NS_PREMIUM, d80d["SF_NS_Premium"])
    _append_decl(eted, CAT_80D_SF_NS, SC_80D_SF_NS_PREVENTIVE, d80d["SF_NS_Preventive"])
    _append_decl(eted, CAT_80D_PARENTS_SR, SC_80D_P_SR_PREMIUM, d80d["P_SR_Premium"])
    _append_decl(
        eted, CAT_80D_PARENTS_SR, SC_80D_P_SR_PREVENTIVE, d80d["P_SR_Preventive"]
    )

    if eted.docstatus == 0:
        eted.save(ignore_permissions=True)
        try:
            eted.submit()
        except Exception:
            pass
    else:
        try:
            eted.save(ignore_permissions=True)
        except Exception:
            pass

    frappe.msgprint(f"Synced to ETED: {eted.name}", alert=True, indicator="green")
