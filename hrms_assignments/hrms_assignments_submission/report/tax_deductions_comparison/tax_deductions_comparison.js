frappe.query_reports["Tax Deductions Comparison"] = {
  filters: [
    {
      fieldname: "company",
      label: "Company",
      fieldtype: "Link",
      options: "Company",
      reqd: 1,
      default: frappe.defaults.get_default("company"),
      change: () => {
        const emp = frappe.query_report.get_filter("employee");
        if (emp) emp.refresh();
      },
    },
    {
      fieldname: "as_on",
      label: "As On",
      fieldtype: "Date",
      reqd: 1,
      default: frappe.datetime.get_today(),
    },
    {
      fieldname: "payroll_period",
      label: "Payroll Period",
      fieldtype: "Link",
      options: "Payroll Period",
      reqd: 0, // optional: only used to read exemptions
      get_query: () => {
        const company = frappe.query_report.get_filter_value("company");
        return company ? { filters: { company } } : {};
      },
    },
    {
      fieldname: "employee",
      label: "Employee",
      fieldtype: "Link",
      options: "Employee",
      reqd: 0,
      get_query: () => {
        const company = frappe.query_report.get_filter_value("company");
        return company ? { filters: { company } } : {};
      },
    },
    {
      fieldname: "use_verified_exemptions_only",
      label: "Use Verified Exemptions Only",
      fieldtype: "Check",
      default: 1,
    },
    {
      fieldname: "annualize",
      label: "Annualize (12 months)",
      fieldtype: "Check",
      default: 1,
    },
    {
      fieldname: "debug",
      label: "Debug",
      fieldtype: "Check",
      default: 0,
    },
  ],

  onload(report) {
    report.datatable_options = report.datatable_options || {};
    report.datatable_options.freezeColumns = 3;

    report.page.add_inner_button("Legend", () => {
      frappe.msgprint({
        title: "Legend",
        message: `
          <div>
            <b>Gross (Annual)</b> → Annualized gross used for tax<br/>
            <b>Standard Deduction</b> → From Income Tax Slab (regime-wise)<br/>
            <b>Exemptions Total</b> → From Proofs (or Declaration if allowed)<br/>
            <b>Net Tax</b> → Slab Tax - Rebate + Cess<br/>
            <b>TDS / Month</b> → Net Tax / 12 (if annualize checked)
          </div>
        `,
        indicator: "blue",
      });
    });
  },

  formatter(value, row, column, data, default_formatter) {
    const label = column.label || "";
    let out = default_formatter(value, row, column, data);

    if (label === "Regime") {
      out = `<span style="font-weight:600">${out}</span>`;
    }

    const taxish = [
      "Slab Tax",
      "Rebate u/s 87A",
      "Cess",
      "Net Tax (Annual)",
      "TDS / Month",
    ];
    if (taxish.includes(label)) {
      out = `<span style="font-weight:600">${out}</span>`;
    }

    if (label === "Effective Rate %") {
      const n = parseFloat(data["effective_rate_pct"] || value || 0);
      const color =
        n >= 12
          ? "var(--red-500)"
          : n <= 5
          ? "var(--green-500)"
          : "var(--gray-700)";
      out = `<span style="font-weight:600;color:${color}">${frappe.format(n, {
        fieldtype: "Percent",
      })}</span>`;
    }
    return out;
  },
};
