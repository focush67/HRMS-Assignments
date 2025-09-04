import frappe
from frappe.utils import flt, getdate

# ============================== PUBLIC API ==============================


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
        base = _compute_base(emp, filters)
        # base has: gross_monthly, gross_annual, non_taxable_annual, prof_tax_annual, nps_employer_annual, debug_gross_source

        exemptions_total = _get_exemptions(
            emp.name, filters
        )  # VI-A proofs/decl (Old only by design)
        regimes = ["Old", "New"] if filters.regime == "Both" else [filters.regime]

        for regime in regimes:
            calc = _compute_tax_for_regime(
                company=filters.company,
                as_on=filters.as_on,
                regime=regime,
                gross_annual=base["gross_annual"],
                non_taxable_annual=base["non_taxable_annual"],
                nps_employer_annual=base[
                    "nps_employer_annual"
                ],  # allowed in BOTH regimes
                prof_tax_annual=base["prof_tax_annual"],  # allowed only in OLD regime
                exemptions_vi_a_annual=exemptions_total,  # VI-A only in OLD
                annualize=bool(int(filters.annualize or 0)),
                want_breakdown=bool(int(filters.get("debug") or 0)),
            )

            # If you want a per-regime popup for single employee, uncomment:
            # if filters.get("employee") and bool(int(filters.get("debug") or 0)):
            #     _show_breakdown_msg(emp, regime, calc)

            row = [
                emp.name,
                emp.employee_name or "",
                regime,
                calc["gross_annual"],
                calc["std_deduction"],
                calc["exemptions_total"],  # VI-A used (Old), else 0
                calc["taxable_income"],
                calc["slab_tax"],
                calc["rebate_applied"],
                calc["cess_amount"],
                calc["net_tax"],
                calc["monthly_tds"],
                calc["effective_rate_pct"],
            ]

            if bool(int(filters.get("debug") or 0)):
                row.extend(
                    [
                        calc.get("debug_slab_name") or "",
                        base.get("gross_monthly"),
                        base.get("non_taxable_annual"),
                        base.get("nps_employer_annual"),
                        base.get("prof_tax_annual"),
                        base.get("debug_gross_source"),
                        len(calc.get("bands", []) or []),
                    ]
                )

            rows.append(row)

    return columns, rows


# ============================== HELPERS ==============================


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
    filters.debug = int(filters.get("debug") or 0)
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
    if bool(int(filters.get("debug") or 0)):
        cols.extend(
            [
                {
                    "label": "DEBUG: Slab",
                    "fieldname": "debug_slab",
                    "fieldtype": "Data",
                    "width": 180,
                },
                {
                    "label": "DEBUG: Base (Monthly)",
                    "fieldname": "debug_base",
                    "fieldtype": "Currency",
                    "width": 130,
                },
                {
                    "label": "DEBUG: Non-Tax Earn (Ann)",
                    "fieldname": "debug_nontax",
                    "fieldtype": "Currency",
                    "width": 150,
                },
                {
                    "label": "DEBUG: NPS ER (Ann)",
                    "fieldname": "debug_nps",
                    "fieldtype": "Currency",
                    "width": 140,
                },
                {
                    "label": "DEBUG: PT (Ann)",
                    "fieldname": "debug_pt",
                    "fieldtype": "Currency",
                    "width": 120,
                },
                {
                    "label": "DEBUG: Gross Source",
                    "fieldname": "debug_gross_src",
                    "fieldtype": "Data",
                    "width": 180,
                },
                {
                    "label": "DEBUG: Bands",
                    "fieldname": "debug_band_count",
                    "fieldtype": "Int",
                    "width": 90,
                },
            ]
        )
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


# ---------- Employee CTC helpers ----------


def _field_exists(doctype, fieldname):
    try:
        return any(df.fieldname == fieldname for df in frappe.get_meta(doctype).fields)
    except Exception:
        return False


def _extract_ctc_from_employee(emp_name):
    """
    Reads common CTC field names from Employee and returns:
      { "annual": <float>, "source_field": "<fieldname>" }
    Checks (first that exists and >0):
      Annual fields: cost_to_company, ctc, annual_ctc, total_ctc, ctc_annual, ctc_yearly, ctc_year
      Monthly fields: ctc_monthly, monthly_ctc, ctc_per_month (×12)
    """
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

    monthly_fields = [
        "ctc_monthly",
        "monthly_ctc",
        "ctc_per_month",
    ]
    for f in monthly_fields:
        if _field_exists("Employee", f):
            val = flt(getattr(doc, f, 0) or 0)
            if val > 0:
                return {"annual": val * 12.0, "source_field": f}

    return {"annual": 0.0, "source_field": None}


# ---------- BASE COMPUTATION (with Salary Slip -> Employee CTC -> Structure/SSA) ----------


def _compute_base(emp, filters):
    """
    Priority:
      (A) Latest Salary Slip (posting_date <= as_on): best, computed gross
      (B) Employee CTC (custom field on Employee): next best
      (C) Salary Structure / SSA: last resort

    Also computes:
      - non_taxable_annual via Salary Component flag 'exempted_from_income_tax' (if exists)
      - prof_tax_annual from deductions named 'Professional Tax' or 'PT'
      - nps_employer_annual from earnings whose component name contains 'nps' & 'employer'
    """
    as_on = filters.as_on
    gross_monthly = 0.0
    non_taxable_monthly = 0.0
    prof_tax_monthly = 0.0
    nps_employer_monthly = 0.0
    gross_source = "—"

    # (A) Latest Salary Slip
    slip = frappe.get_all(
        "Salary Slip",
        filters={
            "employee": emp.name,
            "company": filters.company,
            "posting_date": ["<=", as_on],
            "docstatus": ["in", [0, 1]],  # draft or submitted
        },
        fields=["name", "gross_pay"],
        order_by="posting_date desc, creation desc",
        limit=1,
    )
    if slip:
        slip = slip[0]
        slip_name = slip.name
        slip_earn = frappe.get_all(
            "Salary Detail",
            filters={
                "parenttype": "Salary Slip",
                "parent": slip_name,
                "parentfield": "earnings",
            },
            fields=["salary_component", "amount"],
        )
        slip_ded = frappe.get_all(
            "Salary Detail",
            filters={
                "parenttype": "Salary Slip",
                "parent": slip_name,
                "parentfield": "deductions",
            },
            fields=["salary_component", "amount"],
        )

        gross_monthly = flt(slip.gross_pay or 0)
        if gross_monthly <= 0:
            gross_monthly = sum(flt(x.amount) for x in slip_earn or [])

        if _has_field("Salary Component", "exempted_from_income_tax") and slip_earn:
            sc_map = _get_salary_component_flags(
                [e.salary_component for e in slip_earn], "exempted_from_income_tax"
            )
            for e in slip_earn:
                if sc_map.get(e.salary_component):
                    non_taxable_monthly += flt(e.amount)

        for d in slip_ded or []:
            comp = (d.salary_component or "").lower()
            if "professional tax" in comp or comp == "pt":
                prof_tax_monthly += flt(d.amount)

        for e in slip_earn or []:
            comp = (e.salary_component or "").lower()
            if "nps" in comp and "employer" in comp:
                nps_employer_monthly += flt(e.amount)

        gross_source = f"Salary Slip: {slip_name}"

    # (B) Employee CTC fallback (annual -> monthly)
    if gross_monthly <= 0:
        ctc = _extract_ctc_from_employee(emp.name)
        if ctc["annual"] > 0:
            gross_monthly = ctc["annual"] / 12.0  # normalize to monthly
            gross_source = f"Employee CTC ({ctc['source_field']})"

    # (C) Salary Structure / SSA last resort
    if gross_monthly <= 0:
        ssa = frappe.get_all(
            "Salary Structure Assignment",
            filters={"employee": emp.name, "docstatus": 1},
            fields=["name", "base", "salary_structure", "from_date"],
            order_by="from_date desc",
            limit=1,
        )
        if ssa:
            ssa = ssa[0]
            ss_name = ssa.get("salary_structure")

            earnings = []
            if ss_name:
                earnings = frappe.get_all(
                    "Salary Detail",
                    filters={
                        "parenttype": "Salary Structure",
                        "parent": ss_name,
                        "parentfield": "earnings",
                    },
                    fields=["salary_component", "amount"],
                )
            if earnings:
                gross_monthly = sum(flt(x.amount) for x in earnings)

                if _has_field("Salary Component", "exempted_from_income_tax"):
                    sc_map = _get_salary_component_flags(
                        [e.salary_component for e in earnings],
                        "exempted_from_income_tax",
                    )
                    for e in earnings:
                        if sc_map.get(e.salary_component):
                            non_taxable_monthly += flt(e.amount)

                for e in earnings:
                    comp = (e.salary_component or "").lower()
                    if "nps" in comp and "employer" in comp:
                        nps_employer_monthly += flt(e.amount)

                gross_source = f"Salary Structure: {ss_name}"

            elif flt(ssa.get("base")) > 0:
                gross_monthly = flt(ssa.get("base"))
                gross_source = f"SSA.base ({ssa.name})"

            if ss_name:
                deductions = frappe.get_all(
                    "Salary Detail",
                    filters={
                        "parenttype": "Salary Structure",
                        "parent": ss_name,
                        "parentfield": "deductions",
                    },
                    fields=["salary_component", "amount"],
                )
                for d in deductions or []:
                    comp = (d.salary_component or "").lower()
                    if "professional tax" in comp or comp == "pt":
                        prof_tax_monthly += flt(d.amount)

    months = 12 if bool(int(filters.annualize or 0)) else 1
    base = {
        "gross_monthly": flt(gross_monthly, 2),
        "gross_annual": flt(gross_monthly * months, 2),
        "non_taxable_annual": flt(non_taxable_monthly * months, 2),
        "prof_tax_annual": flt(prof_tax_monthly * months, 2),
        "nps_employer_annual": flt(nps_employer_monthly * months, 2),
        "debug_gross_source": gross_source,
    }

    if bool(int(filters.get("debug") or 0)):
        frappe.msgprint(
            f"{emp.employee_name or emp.name}: Gross from {gross_source} → {base['gross_annual']}"
        )

    return base


def _get_salary_component_flags(names, fieldname):
    """Return a dict {component_name: bool} for a given boolean field on Salary Component."""
    out = {}
    if not names:
        return out
    unique = list({n for n in names if n})
    if not _has_field("Salary Component", fieldname):
        return out
    comps = frappe.get_all(
        "Salary Component", filters={"name": ["in", unique]}, fields=["name", fieldname]
    )
    for c in comps:
        out[c.name] = int(getattr(c, fieldname, 0)) == 1
    return out


def _get_exemptions(employee, filters):
    """
    VI-A exemptions via Proofs (preferred) or Declaration (if allowed).
    Returned as an annual amount used ONLY in OLD regime.
    """
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


# ============================== TAX COMPUTATION ==============================


def _compute_tax_for_regime(
    company,
    as_on,
    regime,
    gross_annual,
    non_taxable_annual,
    nps_employer_annual,
    prof_tax_annual,
    exemptions_vi_a_annual,
    annualize=True,
    want_breakdown=False,
):
    slab_name = _find_regime_slab(company, as_on, regime)
    if not slab_name:
        empty = _empty_calc(gross_annual, 0.0)
        empty["debug_slab_name"] = None
        empty["bands"] = []
        return empty

    slab_doc = frappe.get_doc("Income Tax Slab", slab_name)

    # Standard deduction per slab schema (if present)
    std_deduction = 0.0
    if _has_field("Income Tax Slab", "allow_tax_exemption") and _has_field(
        "Income Tax Slab", "standard_tax_exemption_amount"
    ):
        if int(getattr(slab_doc, "allow_tax_exemption", 0)) == 1:
            std_deduction = flt(getattr(slab_doc, "standard_tax_exemption_amount", 0.0))

    # Optional fields
    cess_pct = flt(_safe_get(slab_doc, ["education_cess_percent", "education_cess"], 0))
    rebate_thr = flt(
        _safe_get(slab_doc, ["rebate_applicable_below", "rebate_threshold"], 0)
    )
    rebate_amt = flt(_safe_get(slab_doc, ["rebate_amount", "rebate_u_s_87a_amount"], 0))

    # Start with taxable base after removing non-taxable earnings
    taxable_base = max(0.0, flt(gross_annual) - flt(non_taxable_annual))

    # Always-allowed deductions
    deductions_common = std_deduction + flt(nps_employer_annual)

    # Old-regime-only deductions
    deductions_old_only = flt(prof_tax_annual) + flt(exemptions_vi_a_annual)

    total_deductions = deductions_common + (
        deductions_old_only if regime == "Old" else 0.0
    )
    taxable_income = max(0.0, taxable_base - total_deductions)

    # Slab tax calc
    child_table = _detect_slab_child_table(slab_doc)
    slab_tax = 0.0
    bands = []
    for r in sorted(child_table, key=lambda x: flt(getattr(x, "from_amount", 0) or 0)):
        lower = flt(getattr(r, "from_amount", 0) or 0)
        upper_val = getattr(r, "to_amount", None)
        upper = flt(upper_val) if (upper_val not in (None, "")) else 9e18
        if taxable_income <= lower:
            continue
        band = min(taxable_income, upper) - lower
        if band <= 0:
            continue
        rate = flt(getattr(r, "percent", None) or getattr(r, "rate", None) or 0.0)
        fixed = flt(
            getattr(r, "fixed_amount", None) or getattr(r, "tax_amount", None) or 0.0
        )
        band_tax = (band * rate / 100.0) + fixed
        slab_tax += band_tax
        if want_breakdown:
            bands.append(
                {
                    "from": lower,
                    "to": (None if upper >= 9e18 else upper),
                    "slice": flt(band, 2),
                    "rate_pct": rate,
                    "fixed": fixed,
                    "tax": flt(band_tax, 2),
                }
            )

    rebate_applied = 0.0
    if rebate_thr and taxable_income <= rebate_thr:
        rebate_applied = min(slab_tax, rebate_amt)
        slab_tax = max(0.0, slab_tax - rebate_applied)

    cess_amount = flt(slab_tax * (cess_pct / 100.0)) if cess_pct else 0.0
    net_tax = flt(slab_tax + cess_amount)

    months = 12 if annualize else 1
    monthly_tds = flt(net_tax / months, 2)
    effective_rate_pct = (
        flt((net_tax / gross_annual * 100.0), 2) if gross_annual > 0 else 0.0
    )

    return {
        "gross_annual": flt(gross_annual, 2),
        "std_deduction": flt(std_deduction, 2),
        "exemptions_total": flt(exemptions_vi_a_annual if regime == "Old" else 0.0, 2),
        "taxable_income": flt(taxable_income, 2),
        "slab_tax": flt(slab_tax, 2),
        "rebate_applied": flt(rebate_applied, 2),
        "cess_amount": flt(cess_amount, 2),
        "net_tax": flt(net_tax, 2),
        "monthly_tds": monthly_tds,
        "effective_rate_pct": effective_rate_pct,
        "debug_slab_name": slab_name,
        "bands": bands,
    }


def _empty_calc(gross_annual, exemptions):
    taxable = max(0.0, flt(gross_annual) - flt(exemptions))
    return {
        "gross_annual": flt(gross_annual, 2),
        "std_deduction": 0.0,
        "exemptions_total": flt(exemptions, 2),
        "taxable_income": flt(taxable, 2),
        "slab_tax": 0.0,
        "rebate_applied": 0.0,
        "cess_amount": 0.0,
        "net_tax": 0.0,
        "monthly_tds": 0.0,
        "effective_rate_pct": 0.0,
        "debug_slab_name": None,
        "bands": [],
    }


# ============================== DETECTION / META ==============================


def _find_regime_slab(company, as_on, regime):
    regime_filters = []
    if _has_field("Income Tax Slab", "tax_regime"):
        regime_filters.append({"tax_regime": regime})
    elif _has_field("Income Tax Slab", "regime"):
        regime_filters.append({"regime": regime})
    elif _has_field("Income Tax Slab", "is_new_regime"):
        regime_filters.append({"is_new_regime": 1 if regime == "New" else 0})
    else:
        regime_filters.append({})

    for rf in regime_filters:
        name = frappe.db.get_value(
            "Income Tax Slab",
            {"company": company, "disabled": 0, "effective_from": ["<=", as_on], **rf},
            "name",
            order_by="effective_from desc",
        )
        if name:
            return name

    return frappe.db.get_value(
        "Income Tax Slab",
        {"company": company, "disabled": 0, "effective_from": ["<=", as_on]},
        "name",
        order_by="effective_from desc",
    )


def _detect_slab_child_table(slab_doc):
    if hasattr(slab_doc, "slabs") and slab_doc.slabs:
        return slab_doc.slabs
    if hasattr(slab_doc, "tax_slabs") and slab_doc.tax_slabs:
        return slab_doc.tax_slabs
    if hasattr(slab_doc, "income_tax_slabs") and slab_doc.income_tax_slabs:
        return slab_doc.income_tax_slabs
    return []


def _has_field(doctype, fieldname):
    try:
        meta = frappe.get_meta(doctype)
        return any(df.fieldname == fieldname for df in meta.fields)
    except Exception:
        return False


def _safe_get(doc, keys, default=None):
    for k in keys:
        if hasattr(doc, k):
            val = getattr(doc, k)
            if val not in (None, ""):
                return val
    return default


# ============================== OPTIONAL UI POPUP ==============================


def _show_breakdown_msg(emp, regime, calc):
    bands = calc.get("bands") or []
    if not bands:
        html_rows = "<tr><td colspan='6' style='padding:6px'>No band-level breakdown available (no slabs matched or zero taxable income).</td></tr>"
    else:
        html_rows = ""
        for b in bands:
            to_display = (
                "∞"
                if b.get("to") in (None, "", 0)
                else (
                    frappe.utils.fmt_money(b["to"], currency=None)
                    if isinstance(b["to"], (int, float))
                    else b["to"]
                )
            )
            html_rows += f"""
            <tr>
              <td style="padding:6px">{frappe.utils.fmt_money(b['from'], currency=None)}</td>
              <td style="padding:6px">{to_display}</td>
              <td style="padding:6px; text-align:right">{frappe.utils.fmt_money(b['slice'], currency=None)}</td>
              <td style="padding:6px; text-align:right">{flt(b['rate_pct'], 2)}%</td>
              <td style="padding:6px; text-align:right">{frappe.utils.fmt_money(b['fixed'], currency=None)}</td>
              <td style="padding:6px; text-align:right">{frappe.utils.fmt_money(b['tax'], currency=None)}</td>
            </tr>
            """

    total_row = f"""
    <tr style="font-weight:600;border-top:1px solid #ddd">
      <td colspan="5" style="padding:6px">Slab Tax</td>
      <td style="padding:6px; text-align:right">{frappe.utils.fmt_money(calc['slab_tax'], currency=None)}</td>
    </tr>
    <tr>
      <td colspan="5" style="padding:6px">Rebate u/s 87A</td>
      <td style="padding:6px; text-align:right">{frappe.utils.fmt_money(calc['rebate_applied'], currency=None)}</td>
    </tr>
    <tr>
      <td colspan="5" style="padding:6px">Cess</td>
      <td style="padding:6px; text-align:right">{frappe.utils.fmt_money(calc['cess_amount'], currency=None)}</td>
    </tr>
    <tr style="font-weight:700;border-top:1px solid #ddd">
      <td colspan="5" style="padding:6px">Net Tax</td>
      <td style="padding:6px; text-align:right">{frappe.utils.fmt_money(calc['net_tax'], currency=None)}</td>
    </tr>
    """

    head = f"""
      <div style="margin-bottom:8px">
        <b>Employee:</b> {frappe.utils.escape_html(emp.employee_name or emp.name)} &nbsp;|&nbsp;
        <b>Regime:</b> {regime} &nbsp;|&nbsp;
        <b>Slab:</b> {frappe.utils.escape_html(calc.get('debug_slab_name') or '—')}
      </div>
      <div style="margin-bottom:6px">
        <b>Gross (Annual):</b> {frappe.utils.fmt_money(calc['gross_annual'], currency=None)} &nbsp;|&nbsp;
        <b>Std. Deduction:</b> {frappe.utils.fmt_money(calc['std_deduction'], currency=None)} &nbsp;|&nbsp;
        <b>Exemptions Used:</b> {frappe.utils.fmt_money(calc['exemptions_total'], currency=None)}
      </div>
    """

    html = f"""
    {head}
    <table style="width:100%; border-collapse:collapse; font-size:12px">
      <thead>
        <tr style="border-bottom:1px solid #ddd">
          <th style="text-align:left; padding:6px">From</th>
          <th style="text-align:left; padding:6px">To</th>
          <th style="text-align:right; padding:6px">Taxed Slice</th>
          <th style="text-align:right; padding:6px">Rate %</th>
          <th style="text-align:right; padding:6px">Fixed</th>
          <th style="text-align:right; padding:6px">Tax</th>
        </tr>
      </thead>
      <tbody>
        {html_rows}
        {total_row}
      </tbody>
    </table>
    """
    frappe.msgprint(
        html,
        title=f"Tax Breakdown — {emp.employee_name or emp.name} ({regime})",
        indicator="blue",
    )
