import frappe
import unittest
from frappe.utils import nowdate, add_days


class TestEmployee(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.db.rollback()

    def test_can_create_employee(self):
        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "Test",
                "last_name": "User",
                "gender": "Prefer not to say",
                "date_of_birth": "2024-01-01",
                "date_of_joining": "2024-06-01",
                "status": "Active",
                "cell_number": "1234567890",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
            }
        )
        emp.insert()
        self.assertTrue(emp.name)
        self.assertEqual(emp.status, "Active")

    def test_duplicate_employee_is_not_allowed(self):
        emp1 = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "Alice",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "date_of_joining": "2024-06-01",
                "status": "Active",
                "gender": "Prefer not to say",
                "cell_number": "1234567890",
                "date_of_birth": "1990-01-01",
            }
        ).insert()

        emp2 = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "Alice",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "date_of_joining": "2024-06-01",
                "status": "Active",
                "cell_number": "1234567890",
                "gender": "Prefer not to say",
                "date_of_birth": "1990-01-01",
            }
        )

        with self.assertRaises(frappe.DuplicateEntryError):
            emp2.insert()

    def test_employee_must_have_company(self):
        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "NoCompanyUser",
                "cell_number": "1234567890",
            }
        )
        with self.assertRaises(frappe.ValidationError):
            emp.insert()

    def test_employee_must_have_mobile(self):
        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "NoMobileUser",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "date_of_joining": "2024-06-01",
                "status": "Active",
                "gender": "Prefer not to say",
                "date_of_birth": "1990-01-01",
            }
        )

        with self.assertRaises(frappe.MandatoryError):
            emp.insert()

    def test_linked_user_can_be_created(self):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": "emp_test_user@example.com",
                "first_name": "EmpUser",
                "cell_number": "1234567890",
            }
        ).insert(ignore_if_duplicate=True)

        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "Linked",
                "user_id": user.name,
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "gender": "Prefer not to say",
                "date_of_birth": "1990-01-01",
                "date_of_joining": nowdate(),
                "status": "Active",
                "cell_number": "1234567890",
            }
        ).insert()

        self.assertEqual(emp.user_id, user.name)

    def test_onboarding_defaults(self):
        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "Onboarding",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "gender": "Prefer not to say",
                "date_of_birth": "1990-01-01",
                "date_of_joining": nowdate(),
                "status": "Active",
                "cell_number": "1234567890",
            }
        ).insert()

        self.assertIn(emp.status, ["Active", "Inactive"])
        self.assertIsNotNone(emp.date_of_joining)

    def test_probation_guard_blocks_early_confirmation_without_override(self):
        rm = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "ManagerUser",
                "user_id": "Administrator",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "cell_number": "9999999999",
                "date_of_joining": "2025-01-01",
                "date_of_birth": "1990-09-10",
                "status": "Active",
                "gender": "Prefer not to say",
            }
        ).insert()

        joining = add_days(nowdate(), -5)
        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "ProbationUser",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "status": "Active",
                "gender": "Prefer not to say",
                "date_of_birth": "1990-01-01",
                "date_of_joining": joining,
                "cell_number": "1234567890",
                "custom_is_under_probation": 1,
                "custom_probation_period": "30 days",
                "reports_to": rm.name,
            }
        ).insert()

        self.assertEqual(emp.custom_employment_status, "Probation")
        self.assertIsNotNone(emp.custom_probation_end_date)

        emp.custom_employment_status = "Confirmed"
        with self.assertRaises(frappe.ValidationError):
            emp.save()

    def test_probation_guard_blocks_early_confirmation_with_override(self):
        rm = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "ManagerUser2",
                "user_id": "Administrator",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "cell_number": "8888888888",
                "date_of_joining": "2025-01-01",
                "date_of_birth": "1989-09-10",
                "status": "Active",
                "gender": "Prefer not to say",
            }
        ).insert()

        joining = add_days(nowdate(), -5)
        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "ProbationUser2",
                "company": frappe.defaults.get_global_default("company")
                or "The Testing Company Private Limited",
                "status": "Active",
                "gender": "Prefer not to say",
                "date_of_birth": "1990-01-01",
                "date_of_joining": joining,
                "cell_number": "1234567890",
                "custom_is_under_probation": 1,
                "custom_probation_period": "30 days",
                "reports_to": rm.name,
            }
        ).insert()

        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "Employee",
                "reference_name": emp.name,
                "content": "Please End Probation Early for good performance",
                "owner": "Administrator",
            }
        ).insert()

        emp.custom_employment_status = "Confirmed"
        emp.save()

        self.assertEqual(emp.custom_has_early_probation_end, 1)

    def test_compute_probation_end_date_calculates_correctly(self):
        from hrms_assignments.custom_script.employee.employee import (
            compute_probation_end_date,
        )
        from frappe.utils import getdate, add_days, add_months, formatdate

        joining = getdate("2025-10-01")
        result = compute_probation_end_date(joining, "30 days")
        expected_end = str(add_days(joining, 30))
        self.assertEqual(result["end_date"], expected_end)
        self.assertEqual(result["end_date_formatted"], formatdate(expected_end))

        result = compute_probation_end_date(joining, "3 months")
        expected_end = str(add_months(joining, 3))
        self.assertEqual(result["end_date"], expected_end)

        result = compute_probation_end_date(joining, "not_a_valid_input")
        self.assertIsNone(result["end_date"])
        self.assertIsNone(result["end_date_formatted"])

        result = compute_probation_end_date(joining, "2025-12-31")
        self.assertEqual(result["end_date"], "2025-12-31")

    def test_extract_days_or_months_calculates_correctly(self):
        from hrms_assignments.custom_script.employee.employee import (
            _extract_days_or_months,
        )

        self.assertEqual(_extract_days_or_months(15), ("days", 15))
        self.assertEqual(_extract_days_or_months("30 days"), ("days", 30))
        self.assertEqual(_extract_days_or_months("3 months"), ("months", 3))
        self.assertEqual(_extract_days_or_months("45"), ("days", 45))
        self.assertEqual(_extract_days_or_months("-10"), (None, None))
        self.assertEqual(_extract_days_or_months("abc"), (None, None))
        self.assertEqual(_extract_days_or_months("12 weeks"), ("days", 84))
        self.assertEqual(_extract_days_or_months(None), (None, None))
        self.assertEqual(_extract_days_or_months(""), (None, None))
