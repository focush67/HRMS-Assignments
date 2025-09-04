frappe.query_reports["Recruitment Sources"] = {
  filters: [
    {
      fieldname: "source",
      label: __("Source"),
      fieldtype: "Link",
      options: "Job Applicant Source",
      reqd: 0,
    },
  ],
};
