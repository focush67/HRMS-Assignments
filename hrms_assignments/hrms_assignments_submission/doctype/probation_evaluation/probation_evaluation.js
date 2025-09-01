function renderLegend(frm) {
  const html = `
    <div style="
      margin-top:8px;padding:10px;border:1px solid #e5e7eb;border-radius:8px;
      font-size:13px;line-height:1.6;background:#fafafa;
    ">
      <div style="font-weight:600;margin-bottom:6px;">Result Criteria</div>
      <div style="display:flex;gap:18px;flex-wrap:wrap;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="display:inline-block;width:10px;height:10px;border-radius:9999px;background:#16a34a;"></span>
          <span><b>Passed</b>: ≥ 70%</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="display:inline-block;width:10px;height:10px;border-radius:9999px;background:#ef4444;"></span>
          <span><b>Failed</b>: &lt; 70%</span>
        </div>
      </div>
    </div>
  `;

  if (frm.fields_dict["criteria_legend"]?.$wrapper) {
    frm.fields_dict["criteria_legend"].$wrapper.html(html);
    return;
  }

  if (frm.dashboard?.set_headline_safe) {
    frm.dashboard.set_headline_safe(html);
  }
}

function setEmployeeUnderProbationQuery(frm) {
  frm.set_query("employee", function () {
    return {
      filters: {
        custom_is_under_probation: 1,
        status: "Active",
      },
    };
  });
}

frappe.ui.form.on("Probation Evaluation", {
  onload(frm) {
    setEmployeeUnderProbationQuery(frm);
  },
  refresh(frm) {
    setEmployeeUnderProbationQuery(frm);
    renderLegend(frm);
  },
});
