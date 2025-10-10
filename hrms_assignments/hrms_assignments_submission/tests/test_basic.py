import frappe
import unittest


class TestBasic(unittest.TestCase):
    def test_math_works(self):
        self.assertEqual(2 + 2, 4)
        self.assertEqual(2 - 2, 0)
        self.assertEqual(2 * 3, 6)
        self.assertEqual(2 / 2, 1)

    def test_new_doc_creation(self):
        doc = frappe.get_doc(
            {
                "doctype": "ToDo",
                "description": "This is a test todo generated from test case",
                "status": "Open",
                "allocated_to": "Administrator",
            }
        )
        doc.insert()
        self.assertTrue(doc.name)
