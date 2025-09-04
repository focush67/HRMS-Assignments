async function maybeCalculateProbationEnd(frm) {
  return new Promise((resolve, reject) => {
    frappe.call({
      method:
        "hrms_assignments.custom_script.employee.employee.calculate_probation_end_date",
      args: {
        employee: frm.doc.name,
      },
      callback: function (response) {
        resolve(response.message);
      },
      error: function (error) {
        reject(error);
      },
    });
  });
}

frappe.ui.form.on("Employee", {
  async custom_is_under_probation(frm) {
    if (frm.doc.custom_is_under_probation === 1) {
      const response = await maybeCalculateProbationEnd(frm);
      frm.set_value("custom_probation_end_date", response.end_date);
    }
  },

  validate(frm) {
    if (frm.doc.custom_is_under_probation) {
      if (frm.doc.custom_employment_status !== "Probation") {
        frappe.throw(
          "Not allowed to change the employment status from Probation to anything else while the employee is under probation"
        );
      }
    }
  },
});
