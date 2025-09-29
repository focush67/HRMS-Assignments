import frappe
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    _normalize_filters(filters)
    columns = _get_columns(filters)
    employees = _get_employees(filters)
    if not employees:
        frappe.msgprint("No employees found for the selected filters.")
        return columns, []

    rows = []
    for emp in employees:
        base = _compute_base_from_employee_ctc(emp, filters)
        exemptions_total = _get_exemptions(emp.name, filters)

        regimes = ["Old", "New"] if filters.regime == "Both" else [filters.regime]
        for regime in regimes:
            if regime == "Old":
                calc = _compute_tax_old_custom(
                    gross_annual=base["gross_annual"],
                    exemptions_vi_a_annual=exemptions_total,
                    annualize=bool(int(filters.annualize or 0)),
                )
            else:
                calc = _compute_tax_new_custom(
                    gross_annual=base["gross_annual"],
                    annualize=bool(int(filters.annualize or 0)),
                )

            row = [
                emp.name,
                emp.employee_name or "",
                regime,
                calc["gross_annual"],
                calc["std_deduction"],
                calc["exemptions_total"],
                calc["taxable_income"],
                calc["slab_tax"],
                calc["rebate_applied"],
                calc["cess_amount"],
                calc["net_tax"],
                calc["monthly_tds"],
                calc["effective_rate_pct"],
            ]

            rows.append(row)

    return columns, rows


def _normalize_filters(filters):
    if not filters.get("company"):
        frappe.throw("Please select a Company.")
    if not filters.get("as_on"):
        frappe.throw("Please select an As On date.")
    if not filters.get("regime"):
        filters.regime = "Both"

    filters.annualize = int(filters.get("annualize") or 1)
    filters.use_verified_exemptions_only = int(
        filters.get("use_verified_exemptions_only") or 1
    )
    filters.as_on = getdate(filters.as_on)


def _get_columns(filters):
    cols = [
        {
            "label": "Employee",
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120,
        },
        {
            "label": "Employee Name",
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {"label": "Regime", "fieldname": "regime", "fieldtype": "Data", "width": 80},
        {
            "label": "Gross (Annual)",
            "fieldname": "gross_annual",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Standard Deduction",
            "fieldname": "std_deduction",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": "Exemptions Total",
            "fieldname": "exemptions_total",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": "Taxable Income",
            "fieldname": "taxable_income",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Slab Tax",
            "fieldname": "slab_tax",
            "fieldtype": "Currency",
            "width": 110,
        },
        {
            "label": "Rebate u/s 87A",
            "fieldname": "rebate_applied",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Cess",
            "fieldname": "cess_amount",
            "fieldtype": "Currency",
            "width": 90,
        },
        {
            "label": "Net Tax (Annual)",
            "fieldname": "net_tax",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": "TDS / Month",
            "fieldname": "monthly_tds",
            "fieldtype": "Currency",
            "width": 110,
        },
        {
            "label": "Effective Rate %",
            "fieldname": "effective_rate_pct",
            "fieldtype": "Percent",
            "width": 120,
        },
    ]
    return cols


def _get_employees(filters):
    cond = {"company": filters.company}
    if filters.get("employee"):
        cond["name"] = filters.employee
    return frappe.get_all(
        "Employee",
        filters=cond,
        fields=["name", "employee_name"],
        order_by="employee_name",
    )


def _field_exists(doctype, fieldname):
    try:
        meta = frappe.get_meta(doctype)
        return any(df.fieldname == fieldname for df in meta.fields)
    except Exception:
        return False


def _extract_ctc_from_employee(emp_name):
    doc = frappe.get_doc("Employee", emp_name)

    annual_fields = [
        "cost_to_company",
        "ctc",
        "annual_ctc",
        "total_ctc",
        "ctc_annual",
        "ctc_yearly",
        "ctc_year",
    ]
    for f in annual_fields:
        if _field_exists("Employee", f):
            val = flt(getattr(doc, f, 0) or 0)
            if val > 0:
                return {"annual": val, "source_field": f}

    monthly_fields = ["ctc_monthly", "monthly_ctc", "ctc_per_month"]
    for f in monthly_fields:
        if _field_exists("Employee", f):
            val = flt(getattr(doc, f, 0) or 0)
            if val > 0:
                return {"annual": val * 12.0, "source_field": f}

    return {"annual": 0.0, "source_field": None}


def _compute_base_from_employee_ctc(emp, filters):
    ctc = _extract_ctc_from_employee(emp.name)
    gross_annual = flt(ctc["annual"], 2)
    base = {
        "gross_annual": gross_annual,
        "debug_gross_source": (
            f"Employee CTC ({ctc['source_field']})"
            if ctc["source_field"]
            else "Employee CTC: not found"
        ),
    }
    return base


def _get_exemptions(employee, filters):
    payroll_period = filters.get("payroll_period")
    if not payroll_period:
        return 0.0

    proofs = frappe.get_all(
        "Employee Tax Exemption Proof Submission",
        filters={
            "employee": employee,
            "payroll_period": payroll_period,
            "docstatus": 1,
        },
        fields=["name"],
    )
    if proofs:
        rows = frappe.get_all(
            "Employee Tax Exemption Proofs",
            filters={"parent": ["in", [p.name for p in proofs]]},
            fields=["approved_amount"],
        )
        return flt(sum(flt(r.approved_amount) for r in rows), 2)

    if not bool(int(filters.use_verified_exemptions_only or 0)):
        decl = frappe.get_all(
            "Employee Tax Exemption Declaration",
            filters={
                "employee": employee,
                "payroll_period": payroll_period,
                "docstatus": 1,
            },
            fields=["name"],
        )
        if decl:
            rows = frappe.get_all(
                "Employee Tax Exemption",
                filters={"parent": ["in", [d.name for d in decl]]},
                fields=["amount"],
            )
            return flt(sum(flt(r.amount) for r in rows), 2)

    return 0.0


def _compute_tax_old_custom(
    gross_annual, exemptions_vi_a_annual, annualize=True, want_breakdown=False
):
    std_deduction = 50000.0
    taxable_income = max(
        0.0, flt(gross_annual) - std_deduction - flt(exemptions_vi_a_annual)
    )

    bands = []

    def _add(from_amt, to_amt, rate_pct):
        nonlocal bands
        upper = to_amt if to_amt is not None else 9e18
        if taxable_income <= from_amt:
            return 0.0
        slice_amt = min(taxable_income, upper) - from_amt
        if slice_amt <= 0:
            return 0.0
        tax = slice_amt * (rate_pct / 100.0)
        if want_breakdown:
            bands.append(
                {
                    "from": flt(from_amt, 2),
                    "to": (None if to_amt is None else flt(to_amt, 2)),
                    "slice": flt(slice_amt, 2),
                    "rate_pct": flt(rate_pct, 2),
                    "fixed": 0.0,
                    "tax": flt(tax, 2),
                }
            )
        return tax

    slab_tax = 0.0
    slab_tax += _add(0, 250000, 0)

    if taxable_income > 500000:
        slab_tax += _add(250000, 500000, 5)
    else:
        pass

    slab_tax += _add(500000, 1000000, 20)

    slab_tax += _add(1000000, None, 30)

    rebate_applied = 0.0
    if taxable_income <= 500000:
        rebate_applied = flt(slab_tax, 2)
        slab_tax = 0.0

    cess_amount = flt(slab_tax * 0.04, 2) if slab_tax > 0 else 0.0
    net_tax = flt(slab_tax + cess_amount, 2)

    months = 12 if annualize else 1
    monthly_tds = flt(net_tax / months, 2)
    effective_rate_pct = (
        flt((net_tax / gross_annual * 100.0), 2) if gross_annual > 0 else 0.0
    )

    return {
        "gross_annual": flt(gross_annual, 2),
        "std_deduction": flt(std_deduction, 2),
        "exemptions_total": flt(exemptions_vi_a_annual, 2),
        "taxable_income": flt(taxable_income, 2),
        "slab_tax": flt(slab_tax, 2),
        "rebate_applied": flt(rebate_applied, 2),
        "cess_amount": flt(cess_amount, 2),
        "net_tax": flt(net_tax, 2),
        "monthly_tds": monthly_tds,
        "effective_rate_pct": effective_rate_pct,
        "bands": bands if want_breakdown else [],
    }


def _compute_tax_new_custom(gross_annual, annualize=True, want_breakdown=False):
    std_deduction = 60000.0
    taxable_income = max(0.0, flt(gross_annual) - std_deduction)

    bands = []

    def _add(from_amt, to_amt, rate_pct):
        nonlocal bands
        upper = to_amt if to_amt is not None else 9_999_999_99.0
        if taxable_income <= from_amt:
            return 0.0
        slice_amt = min(taxable_income, upper) - from_amt
        if slice_amt <= 0:
            return 0.0
        tax = slice_amt * (rate_pct / 100.0)
        if want_breakdown:
            bands.append(
                {
                    "from": flt(from_amt, 2),
                    "to": (None if to_amt is None else flt(to_amt, 2)),
                    "slice": flt(slice_amt, 2),
                    "rate_pct": flt(rate_pct, 2),
                    "fixed": 0.0,
                    "tax": flt(tax, 2),
                }
            )
        return tax

    slab_tax = 0.0
    slab_tax += _add(0, 400000, 0)
    slab_tax += _add(400000, 800000, 5)
    slab_tax += _add(800000, 1200000, 10)
    slab_tax += _add(1200000, 1600000, 15)
    slab_tax += _add(1600000, 2000000, 20)
    slab_tax += _add(2000000, 2400000, 25)
    slab_tax += _add(2400000, None, 30)
    rebate_applied = 0.0

    cess_amount = flt(slab_tax * 0.04, 2) if slab_tax > 0 else 0.0
    net_tax = flt(slab_tax + cess_amount, 2)

    months = 12 if annualize else 1
    monthly_tds = flt(net_tax / months, 2)
    effective_rate_pct = (
        flt((net_tax / gross_annual * 100.0), 2) if gross_annual > 0 else 0.0
    )

    return {
        "gross_annual": flt(gross_annual, 2),
        "std_deduction": flt(std_deduction, 2),
        "exemptions_total": 0.0,
        "taxable_income": flt(taxable_income, 2),
        "slab_tax": flt(slab_tax, 2),
        "rebate_applied": flt(rebate_applied, 2),
        "cess_amount": flt(cess_amount, 2),
        "net_tax": flt(net_tax, 2),
        "monthly_tds": monthly_tds,
        "effective_rate_pct": effective_rate_pct,
        "bands": bands if want_breakdown else [],
    }
