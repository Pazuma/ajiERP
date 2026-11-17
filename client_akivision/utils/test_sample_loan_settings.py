import unittest
from unittest.mock import patch

import frappe
from client_akivision.utils.sample_loan_settings import prepare


class Record(frappe._dict):
	def set(self, key, value):
		self[key] = value


class TestSampleLoanSettings(unittest.TestCase):
	def test_supplier_loan_out(self):
		row = Record(party_type="Supplier", supplier="SUP-1", customer="OLD")
		doc = frappe._dict(doctype="Sample Loan Out")
		doc.items = [row]
		prepare(doc)
		self.assertIsNone(row.customer)
		self.assertEqual(row.supplier, "SUP-1")

	def test_customer_loan_in_default_warehouse(self):
		doc = Record(doctype="Sample Loan In", party_type="Customer", customer="C-1", supplier="OLD")
		doc.items = [frappe._dict(loan_warehouse=None), frappe._dict(loan_warehouse="Chosen")]
		with patch.object(frappe.db, "get_single_value", return_value="Default"):
			prepare(doc)
		self.assertEqual(doc["items"][0].loan_warehouse, "Default")
		self.assertEqual(doc["items"][1].loan_warehouse, "Chosen")
		self.assertIsNone(doc.supplier)
